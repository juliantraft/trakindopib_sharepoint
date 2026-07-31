from argparse import ArgumentParser, Namespace, RawTextHelpFormatter
from dotenv import load_dotenv
from pathlib import Path
from time import sleep

from pyodbc import Connection, Cursor, Error as DBError, connect

from src import task_manager as tm
from src.sharepoint_bot import sharepoint_bot
from src.logging_setup import Logger, enable_ntfy_logging, init_logging, add_log_context, del_log_context
from src.utils import get_env


SHAREPOINT_URL = 'https://tmtgroup.sharepoint.com/sites/portal_trakindo/pib/PIBDocument/Forms/AllItems.aspx?'


def get_args(argv: list[str] | None = None) -> Namespace:
    parser = ArgumentParser(
        formatter_class=RawTextHelpFormatter,
        description='Sharepoint web automation for CEISA documents',
        usage='%(prog)s [options]',
        epilog='(c) 2026 PT Pratama Natanusa Mandiri | github.com/juliantraft',
    )
    parser.add_argument('-d', '--debug', action='store_true', help='toggle debug mode')
    return parser.parse_args(argv)


def get_logger(debug: bool = False) -> Logger:
    logger: Logger = init_logging(debug)
    if not debug:
        topic_url: str = get_env('NTFY_TOPIC_URL')
        enable_ntfy_logging(topic_url)
    return logger


def get_db_cnxn(logger: Logger) -> Connection:
    cnxn_str: str = (
        f'DRIVER={get_env("DB_DRIVER")};'
        f'SERVER={get_env("DB_HOST")};'
        f'DATABASE={get_env("DB_DATABASE")};'
        f'PORT={get_env("DB_PORT")};'
        f'UID={get_env("DB_USERNAME")};'
        f'PWD={get_env("DB_PASSWORD")};'
        'TrustServerCertificate=yes;'
    )
    try:
        db_cnxn: Connection = connect(cnxn_str)
        logger.info(f'Connection to "{get_env("DB_DATABASE")}" established')
        return db_cnxn
    except DBError as e:
        logger.critical(
            f'Connection to "{get_env("DB_DATABASE")}" failed: {e}',
        )
        raise


def upload_doc(task: tm.PIBTask, bot: sharepoint_bot, logger: Logger) -> None:
    SUPPORTING_DOCS_DIR = Path(get_env('DOC_FOLDER'))
    TEMP_FOLDER = 'TEMP_RPA'

    # Find supporting docs
    supporting_docs: list[Path] = []
    for item in SUPPORTING_DOCS_DIR.iterdir():
        if item.is_file() and item.name.startswith(task.data.no_aju):
            supporting_docs.append(item)

    if not supporting_docs:
        logger.critical('No supporting doc found')
        return

    bot.open_folder('CEISA')

    if not bot.folder_exists(TEMP_FOLDER):
        bot.create_folder(TEMP_FOLDER)
    bot.open_folder(TEMP_FOLDER)

    if not bot.folder_is_empty():
        bot.select_all_files()
        bot.delete_selection()
        bot.page.reload() # type: ignore
        # Still have no idea why reload is needed.
        # Details in dev_notes.txt
        # TODO find out why.

    bot.upload_multiple_files(supporting_docs)

    # Step 2 - move main doc
    bot.load_page(SHAREPOINT_URL, '#listTabPanel')
    bot.open_folder(task.data.type)

    target_file = f'{task.data.no_aju}.pdf'

    result_exist = bot.search_file(target_file)
    if (result_exist):
        bot.sr_open_copy_menu_for_file(target_file)
        bot.fp_move_one_level_up()
        bot.fp_open_folder('CEISA')
        bot.fp_open_folder(TEMP_FOLDER)
        bot.fp_sr_finish()
    else:
        logger.warning(f'Main document "{target_file}" not found')

    # Step 3 - Edit properties and move files
    bot.load_page(SHAREPOINT_URL, '#listTabPanel')
    bot.open_folder('CEISA')
    bot.open_folder(TEMP_FOLDER)
    
    sleep(2)
    bot.select_all_files()
    bot.open_property_editor()

    bot.pe_fill_form('KodeBilling', task.data.bill_code)
    bot.pe_fill_form('AJUNo', task.data.no_aju)
    bot.pe_fill_form('Total', str(task.data.bill_total))
    bot.pe_save()

    folder_struct = (
        task.data.type,                  # Parts/PortalInput/etc
        task.data.trx_date.strftime('%Y'),    # 2025
        task.data.trx_date.strftime('%m')     # 05
    )

    bot.open_move_menu()
    bot.fp_move_one_level_up()

    for folder in folder_struct:
        if bot.fp_folder_exists(folder):
            bot.fp_open_folder(folder)
        else:
            bot.fp_create_folder(folder)

    bot.fp_finish()
    task.status = tm.PIBStatus.SP_UPLOADED


def rpa(logger: Logger, db_cnxn: Connection) -> None:
    cursor: Cursor = db_cnxn.cursor()
    tasks: list[tm.PIBTask] = tm.get_tasks(cursor, 100)

    if not tasks:
        return

    with sharepoint_bot(headless=False) as bot:
        bot.login(get_env('LOGIN_EMAIL'), get_env('LOGIN_PASSWORD'))

        for task in tasks:
            add_log_context({'no_aju': task.data.no_aju})
            bot.load_page(SHAREPOINT_URL, '[data-automationid="appMainContent"]')
            upload_doc(task, bot, logger)

        del_log_context('no_aju')


def main(argv: list[str] | None = None):
    load_dotenv()
    args: Namespace = get_args(argv)
    logger: Logger = get_logger(debug=args.debug)
    db_cnxn: Connection = get_db_cnxn(logger)

    try:
        rpa(logger, db_cnxn)
    except Exception as e:
        err_name: str = e.__class__.__name__
        if isinstance(e, (RuntimeError,)):
            logger.critical(f'{err_name}: {e}')
        else:
            logger.critical(f'Unhandled {err_name}: {e}', exc_info=(not args.debug))
        raise
    finally:
        db_cnxn.close()
        logger.info(f'Connection to "{get_env("DB_DATABASE")}" closed')


if __name__ == '__main__':
    main()