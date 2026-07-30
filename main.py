from argparse import ArgumentParser, Namespace, RawTextHelpFormatter
from datetime import datetime
from dotenv import load_dotenv
from os import scandir
from os.path import abspath
from time import sleep

from src.sharepoint_bot import sharepoint_bot
from src.logging_setup import (
    Logger,
    enable_ntfy_logging,
    init_logging,
)
from src.utils import get_env

load_dotenv()


def get_args(argv: list[str] | None = None) -> Namespace:
    parser = ArgumentParser(
        formatter_class=RawTextHelpFormatter,
        description='Sharepoint web automation for CEISA documents',
        usage='%(prog)s [options]',
        epilog='(c) 2026 PT Pratama Natanusa Mandiri | github.com/juliantraft',
    )
    parser.add_argument('nomor_aju', help='ex: 00000000000000001234567890')
    parser.add_argument('-t', '--type' , type=str, metavar='', help='ex: Parts / SNP / PortalInput')
    parser.add_argument('-d', '--date' , type=str, metavar='', help='yyyy-mm-dd')
    parser.add_argument('-b', '--billcode' , type=str, metavar='', help='ex: 321250501703123')
    parser.add_argument('-s', '--total' , type=str, metavar='', help='ex: 123456789')
    return parser.parse_args()


def get_logger(debug: bool = False) -> Logger:
    logger: Logger = init_logging(debug)
    if not debug:
        topic_url: str = get_env('NTFY_TOPIC_URL')
        enable_ntfy_logging(topic_url)
    return logger


args = get_args()
SHAREPOINT_URL = 'https://tmtgroup.sharepoint.com/sites/portal_trakindo/pib/PIBDocument/Forms/AllItems.aspx?'
SUPPORTING_DOCS_FOLDER = get_env('DOC_FOLDER')
TEMP_FOLDER = 'TEMP_RPA'
DOC_DATE = datetime.strptime(args.date, "%Y-%m-%d")


with sharepoint_bot(headless=args.headless) as bot:
    bot.login(get_env('LOGIN_EMAIL'), get_env('LOGIN_PASSWORD'))
    bot.load_page(SHAREPOINT_URL, '[data-automationid="appMainContent"]')

    # Step 1 - upload supporting docs
    files_to_upload = []
    with scandir(SUPPORTING_DOCS_FOLDER) as entries:
        for entry in entries:
            if entry.is_file() and entry.name.startswith(args.nomor_aju):
                files_to_upload.append(abspath(entry.path))

    if not files_to_upload:
        msg = f'No supporting doc found for {args.nomor_aju} in {SUPPORTING_DOCS_FOLDER}'
        print (msg)
        raise NameError(msg)
        # TODO add error handling in RPA

    bot.open_folder('CEISA')

    if not bot.folder_exists(TEMP_FOLDER):
        bot.create_folder(TEMP_FOLDER)
    bot.open_folder(TEMP_FOLDER)

    if not bot.folder_is_empty():
        bot.select_all_files()
        bot.delete_selection()
        bot.page.reload()
        # Still have no idea why reload is needed.
        # Details in dev_notes.txt
        # TODO find out why.

    bot.upload_multiple_files(files_to_upload)

    # Step 2 - move main doc
    bot.load_page(SHAREPOINT_URL, '#listTabPanel')
    bot.open_folder('Parts')

    target_file = f'{args.nomor_aju}.pdf'

    result_exist = bot.search_file(target_file)
    if (result_exist):
        bot.sr_open_copy_menu_for_file(target_file)
        bot.fp_move_one_level_up()
        bot.fp_open_folder('CEISA')
        bot.fp_open_folder(TEMP_FOLDER)
        bot.fp_sr_finish()

    # Step 3 - Edit properties and move files
    bot.load_page(SHAREPOINT_URL, '#listTabPanel')
    bot.open_folder('CEISA')
    bot.open_folder(TEMP_FOLDER)
    
    sleep(5)
    bot.select_all_files()
    bot.open_property_editor()

    bot.pe_fill_form('KodeBilling', args.billcode)
    bot.pe_fill_form('AJUNo', args.nomor_aju)
    bot.pe_fill_form('Total', args.total)
    bot.pe_save()

    folder_struct = (
        args.type,                  # Parts/PortalInput/etc
        DOC_DATE.strftime('%Y'),    # 2025
        DOC_DATE.strftime('%m')     # 05
    )

    bot.open_move_menu()
    bot.fp_move_one_level_up()

    for folder in folder_struct:
        if bot.fp_folder_exists(folder):
            bot.fp_open_folder(folder)
        else:
            bot.fp_create_folder(folder)

    bot.fp_finish()