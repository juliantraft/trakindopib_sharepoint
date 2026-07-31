# type: ignore
from datetime import datetime
from logging import Logger, getLogger
from pathlib import Path
from time import sleep

from playwright.sync_api import Locator, Page, TimeoutError as PwTimeoutError, sync_playwright

from src.utils import get_main_path


LOGIN_URL = 'https://login.microsoftonline.com/'


PROJECT_DIR: Path = get_main_path().parent
SCREENSHOT_DIR: Path = PROJECT_DIR / 'screenshots'
SCREENSHOT_DIR.mkdir(exist_ok=True)


def take_screenshot(page: Page, save_dir: Path) -> Path:
    """
    Takes screenshot and saves it into a directory.

    Args:
        page (Page): `Page` object.
        save_dir (Path): `Path` of save directory.

    Returns:
        Path: `Path` object of the saved screenshot.
    """
    save_dir.mkdir(exist_ok=True)
    filename: str = datetime.now().strftime('%Y-%m-%d_%H-%M-%S_%f') + '.png'
    filepath: Path = save_dir / filename

    page.screenshot(path=filepath)
    return filepath


class sharepoint_bot:
    '''
    Playwright bot implementation for common Sharepoint tasks.
    '''
    logger: Logger = getLogger(__qualname__)

    def __init__(self, headless=True):
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.iframe = None

    def __enter__(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=self.headless)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type:
            take_screenshot(self.page, SCREENSHOT_DIR)

        self.context.close()
        self.browser.close()
        self.playwright.stop()

    def load_page(
        self,
        url: str,
        wait_selector: str,
        timeout: int = 30000,
        max_retries: int = 3
    ) -> None:
        '''
        Loads a page and wait for specific element to be visible before continuing.
        '''
        self.logger.info(f'Loading page: {url}...')

        page = self.page
        for attempt in range(max_retries):
            try:
                page.goto(url)
                page.wait_for_selector(wait_selector, timeout=timeout)
                self.logger.info('    OK')
                break
            except PwTimeoutError:
                page.reload()
        else:
            self.logger.error(f'Error: Failed to load {url} after {max_retries} retries')
            raise PwTimeoutError
    
    def login(self, email: str, password: str) -> None:
        '''
        Performs login through [Microsoft](online.microsoft.com).
        '''
        self.logger.info('Logging in...')
        page = self.page

        selector = {
            'email'             : 'input[type="email"]',
            'password'          : 'input[type="password"]',
            'sign_in_btn'       : 'input[type="submit"]',
            'do_not_remember'   : 'input[type="button"][value="No"]'
        }

        self.load_page(LOGIN_URL, selector['email'])
        page.fill(selector['email'], email)
        page.press(selector['email'], 'Enter')
        page.wait_for_selector(selector['password'])
        page.fill(selector['password'], password)
        page.click(selector['sign_in_btn'])

        # Choose no if prompted to stay signed in.
        try:
            page.wait_for_selector(selector['do_not_remember'], timeout=2000)
            page.click(selector['do_not_remember'])
        except PwTimeoutError:
            pass
        self.logger.info('    OK')
  
    def open_folder(self, folder_name: str, timeout: int = 30000) -> None:
        '''
        Open a folder by name.
        '''
        self.logger.info(f'Opening folder "{folder_name}"')
        folder_row_selector = f'[data-automationid="field-LinkFilename"] span[role="button"]:text("{folder_name}")'
        self.page.dblclick(folder_row_selector)

        # Wait for folder to appear in last breadcrumb
        breadcrumbs = self.page.locator('ol[data-automationid="breadcrumb-root-id"] > li')
        last_crumb = breadcrumbs.nth(-1)
        crumb = last_crumb.locator(f'span[title="{folder_name}"]')
        crumb.wait_for(state="visible", timeout=timeout)

    def folder_exists(self, folder_name: str, timeout=5000) -> bool:
        '''
        Checks if a folder exist within current directory.
        '''
        self.logger.info(f'Checking folder "{folder_name}" presence...')
        folder_row_selector = f'[data-automationid="field-LinkFilename"] span[role="button"]:text("{folder_name}")'
        try:
            self.page.wait_for_selector(folder_row_selector, timeout=timeout)
            self.logger.info('    OK: True')
            return True
        except PwTimeoutError:
            self.logger.info('    OK: False')
            return False
    
    def folder_is_empty(self, timeout=5000) -> bool:
        '''
        Checks if the current folder is empty.
        '''
        self.logger.info('Checking file presence...')
        empty_selector = '[data-automationid="list-empty-placeholder-title"]'
        try:
            self.page.wait_for_selector(empty_selector, timeout=timeout)
            self.logger.info('    OK: True')
            return True
        except PwTimeoutError:
            self.logger.info('    OK: False')
            return False
    
    def create_folder(self, folder_name: str) -> None:
        '''
        Create new folder.
        '''
        self.logger.info(f'Creating folder "{folder_name}"...')
        page = self.page
        new_btn_selector = 'button[data-automationid="newCommand"]'
        new_folder_selector = 'button[data-automationid="newFolderCommand"]'
        input_selector = '[class*=nameDialogTextContent] input[type="text"]'
        create_btn_selector = '.fui-DialogActions button[data-automation-id="Create"]'
        folder_row_selector = f'[data-automationid="field-LinkFilename"] span[role="button"]:text("{folder_name}")'

        page.wait_for_selector(new_btn_selector)
        page.click(new_btn_selector)
        page.wait_for_selector(new_folder_selector)
        page.click(new_folder_selector)
        page.wait_for_selector(input_selector)
        page.fill(input_selector, folder_name)
        page.click(create_btn_selector)
        page.wait_for_selector(folder_row_selector, timeout=10000)
        self.logger.info('    OK')

    def upload_multiple_files(self, file_paths: list[Path]) -> None:
        '''
        Upload multiple files from local path.
        '''
        self.logger.info(f'Uploading files: {file_paths}...')
        p: Page = self.page
        l_upl_btn: Locator = p.locator('button[data-automationid="newCommand"]')
        l_upl_files_btn: Locator = p.locator('button[data-automationid="uploadFile"]')
        l_toast: Locator = p.locator('[class*="toastInnerContainer"] i[data-icon-name="CompletedSolid"]')

        l_upl_btn.click()    
        with p.expect_file_chooser() as fc_info:
            l_upl_files_btn.click()
            fc = fc_info.value
            fc.set_files(file_paths)

        l_toast.wait_for(state='visible', timeout=20000)
        self.logger.info('    OK')

    def folder_has_one_file(self) -> bool:
        '''
        Checks if folder has only one file.
        '''
        folder_row_selector = '[data-automationid="field-LinkFilename"] span[role="button"]:'
        files = self.page.query_selector_all(folder_row_selector)
        return True if len(files) == 1 else False

    def select_all_files(self) -> None:
        '''
        Select all visible files.
        '''
        self.logger.info('Selecting all visible files')
        header_row_selector = '[data-automationid="row-selection-header"]'
        self.page.locator(header_row_selector).click()

    def delete_selection(self) -> None:
        '''
        Delete selected files.
        '''
        self.logger.info('Deleting selected files...')
        delete_btn_selector = '[role="menuitem"][data-automationid="deleteCommand"]'
        confirm_btn_selector = '.ms-Dialog-actions [data-automationid="confirmbutton"]'
        success_toast_selector = '[data-automationid="msFluentToast"] i[data-icon-name="CompletedSolid"]'

        self.page.click(delete_btn_selector)
        self.page.click(confirm_btn_selector)
        self.page.wait_for_selector(success_toast_selector)
        self.logger.info('    OK')
        

    def open_property_editor(self) -> None:
        '''
        Opens property editor.
        '''
        self.logger.info('Opening property editor')
        more_btn_selector = '[data-automationid="more"][role="menuitem"]'
        properties_btn_selector = '[data-automationid="properties"]'
        editor_panel_selector = '.ReactClientFormContent'

        # One file operation
        edit_all_selector = '[data-automationid="sp-itemDialog-editAll"]'
        
        self.page.click(more_btn_selector)
        self.page.click(properties_btn_selector)
        self.page.wait_for_selector(editor_panel_selector)

        try:
            self.page.click(edit_all_selector,timeout=1000)
        except PwTimeoutError:
            pass

    def open_move_menu(self) -> None:
        '''
        Opens the file picker for move operation.
        '''
        self.logger.info('Opening move menu')
        more_btn_selector = '[role="menuitem"][data-automationid="more"]'
        move_btn_selector = '[data-automationid="moveCommand"]'
        fp_iframe_selector = 'iframe[data-automationid="filePickerFrame"]'

        self.page.click(more_btn_selector)
        self.page.click(move_btn_selector)

        iframe_element = self.page.wait_for_selector(fp_iframe_selector)
        self.iframe = iframe_element.content_frame()

    def search_file(self, file_name: str, timeout=10000) -> bool:
        '''
        Search for a file by name.
        '''
        self.logger.info(f'Searching file "{file_name}"...')
        page = self.page
        search_selector = 'input[type="search"][role="combobox"]'
        loading_selector = '[data-automationid*="row-selection-undefined"]'
        result_selector = f'[role="row"]:has(span[title="{file_name}" i])'
        empty_result_selector = '[data-automationid="list-empty-placeholder"]'
        
        page.fill(search_selector, file_name)
        page.press(search_selector, 'Enter')
        sleep(2)
        page.locator(loading_selector).wait_for(state='detached', timeout=timeout)

        try:
            page.wait_for_selector(result_selector, timeout=100)
            self.logger.info('    OK: found')
            return True
        except PwTimeoutError:
            try:
                page.wait_for_selector(empty_result_selector, timeout=1000)
                self.logger.warning('    OK: not found')
                return False
            except PwTimeoutError:
                self.logger.critical('Unknown search error')
                raise

    def search_by_property(self, key: str, value: str,  timeout=10000) -> None:
        '''
        Search file based on properties.
        '''
        page = self.page
        search_selector = 'input[type="search"][role="combobox"]'
        result_selector = f'.ms-DetailsRow:has([data-automation-key="{key}"] > [class*=fieldText_]:has-text("{value}"))'
        empty_result_selector = '[data-automationid="emptyFolderContainer"]'

        page.fill(search_selector, value)
        page.press(search_selector, 'Enter')
        try:
            page.wait_for_selector(result_selector, timeout=timeout)

            name_field_selector = '[class*="nameField_"][data-automationid="FieldRenderer-name"]'
            name_field = page.locator(name_field_selector)
            return name_field.inner_text()
        except PwTimeoutError:
            try:
                page.wait_for_selector(empty_result_selector, timeout=1000)
                self.logger.error(f'Error: no items match "{value}" for "{key}')
                return False
            except PwTimeoutError:
                self.logger.error('Unknown search error')

    ### SEARCH RESULT METHODS

    def sr_open_copy_menu_for_file(self, file_name: str) -> None:
        '''
        Selects a file in search result and opens the `Copy to` menu.
        '''
        self.logger.info(f'Opening copy menu for file "{file_name}"...')
        page = self.page
        result_checkbox_selector = (
            f'[class*="row_"]:has(span[title="{file_name}" i]) [data-automationid*="row-selection"]'
        )
        more_action_selector = 'button[role="menuitem"][aria-label="more" i]'
        copy_btn_selector = 'button[data-automationid="copyCommand"]'

        try:
            page.wait_for_selector(result_checkbox_selector, timeout=5000)
        except PwTimeoutError:
            self.logger.error(f'Error opening copy menu: file "{file_name}" not found in result')
            raise

        page.click(result_checkbox_selector)
        page.wait_for_selector(more_action_selector)
        page.click(more_action_selector)
        page.wait_for_selector(copy_btn_selector)
        page.click(copy_btn_selector)

        # Set the current file picker as current iframe
        iframe_selector = 'iframe[data-automationid="filePickerFrame"]'
        iframe_element = page.wait_for_selector(iframe_selector)
        self.iframe = iframe_element.content_frame()
        self.logger.info('    OK')

    def sr_open_move_menu_for_file(self, file_name: str) -> None:
            '''
            Selects a file in search result and opens the `Copy to` menu.
            '''
            page = self.page
            result_row_selector = f'[role="row"][aria-label*="{file_name}" i]'
            more_action_selector = 'button[data-automationid="FieldRender-DotDotDot"]'
            move_btn_selector = '[data-automationid="launchMovePickerCommand"]'
            try:
                page.wait_for_selector(result_row_selector, timeout=5000)
            except PwTimeoutError:
                self.logger.error(f'Error opening move menu: file "{file_name}" not found in result')
                raise PwTimeoutError

            page.click(result_row_selector)
            page.wait_for_selector(more_action_selector)
            page.click(more_action_selector)
            page.wait_for_selector(move_btn_selector)
            page.click(move_btn_selector)

            # Set the current file picker as current iframe
            iframe_selector = 'iframe[data-automationid="filePickerFrame"]'
            iframe_element = page.wait_for_selector(iframe_selector)
            self.iframe = iframe_element.content_frame()

    def sr_select_all_files(self) -> None:
        '''
        Select all files in search result page.
        '''
        check_all_selector = '[data-automationid="DetailsHeader"] [data-automationid="DetailsRowCheck"]'
        check_all_selector_checked = '[data-automationid="DetailsHeader"] [data-automationid="DetailsRowCheck"][aria-checked="true"]'

        self.page.click(check_all_selector)
        self.page.wait_for_selector(check_all_selector_checked)

    def sr_open_property_editor(self) -> None:
        '''
        Open properties editor in search result page.
        '''
        more_btn_selector = '[aria-label="More"][role="menuitem"]'
        properties_button_selector = 'button[name="Properties"]'
        editor_panel_selector = '.ReactClientFormContent'

        # One file operation
        edit_all_selector = 'button[role="menuitem"][name="Edit all"]'

        self.page.click(more_btn_selector)
        self.page.wait_for_selector(properties_button_selector)
        self.page.click(properties_button_selector)
        self.page.wait_for_selector(editor_panel_selector)

        try:
            self.page.click(edit_all_selector,timeout=1000)
        except PwTimeoutError:
            pass

    # PROPERTIES EDITOR METHODS

    def pe_fill_form(self, form_name: str, value: str) -> None:
        '''
        Fill a form in properties editor.
        '''
        self.logger.info(f'Filling "{form_name}"...')
        form_selector = f'.ReactFieldEditor:has(label.ReactFieldEditor-fieldTitle:has-text("{form_name}"))'
        input_selector = 'input[type="text"]'

        self.page.locator(form_selector).locator(input_selector).fill(value)

    def pe_save(self) -> None:
        '''
        Save changes in properties editor.
        '''
        self.logger.info('Saving changes...')
        save_btn_selector = 'button[data-automationid="ReactClientFormSaveButton"]'
        outer_panel_selector = '.ReactClientFormContent'
        outer_panel_close_btn = 'button[class*=od-Panel-button--close]'
        inner_panel_selector = '[class*=ReactClientForm]:has(.ReactClientForm-editButtons)'

        self.page.click(save_btn_selector)
        self.page.locator(inner_panel_selector).wait_for(state='detached')

        try:
            self.page.wait_for_selector(outer_panel_selector,timeout=1000)
            self.page.click(outer_panel_close_btn)
            self.page.locator(outer_panel_selector).wait_for(state='detached')
        except PwTimeoutError as e:
            self.logger.debug(e)
            pass
        self.logger.info('    OK')

    def pe_cancel(self) -> None:
        '''
        Cancel changes in properties editor.
        '''
        close_btn_selector = '[data-automationid="splitbuttonprimary"][title="Close"]'
        editor_panel_selector = '.ReactClientFormContent'
        
        self.page.click(close_btn_selector)
        self.page.locator(editor_panel_selector).wait_for(state='detached')

    ### FILE PICKER METHODS (iframe)

    def fp_open_folder(self, folder_name: str, timeout: int = 10000) -> None:
        '''
        Open folder in file picker window.
        '''
        self.logger.info(f'Opening folder "{folder_name}"')
        folder_row_selector = f'[data-automationid="DetailsRow"] button[title="{folder_name}" i]'
        self.iframe.dblclick(folder_row_selector)

        # Wait for folder to appear in breadcrumb
        breadcrumbs = self.iframe.locator('.ms-Breadcrumb[role="navigation"] li')
        crumb = breadcrumbs.nth(-1).locator(f'.ms-TooltipHost:has-text("{folder_name}")')
        crumb.wait_for(state="visible", timeout=timeout)

    def fp_search(self, search_input: str, timeout: int = 10000) -> None:
        '''
        Search folder in file picker window.
        '''
        
        search_selector = 'input[role="searchbox"]'
        
        self.iframe.fill(search_selector, search_input)
        self.iframe.press(search_selector, 'Enter')

        result_selector = '.ms-List-surface[role="presentation"] > .ms-List-page[role="presentation"]'
        empty_result_selector = '[data-automationid="emptyFolderContainer"]'

        try:
            self.iframe.wait_for_selector(result_selector, timeout=timeout)
            return True
        except PwTimeoutError:
            try:
                self.iframe.wait_for_selector(empty_result_selector, timeout=1000)
                self.logger.error(f'Error: no items match "{search_input}"')
                return False
            except PwTimeoutError:
                self.logger.error('Unknown search error')

    def fp_move_one_level_up(self) -> None:
        '''
        Navigate one level up in file picker by clicking second last breadcrumb.
        '''
        self.logger.info('Moving one folder level up...')
        breadcrumbs = self.iframe.locator('.ms-Breadcrumb[role="navigation"] li')
        second_last_crumb = breadcrumbs.nth(-2)
        second_last_crumb.click()

    def fp_folder_exists(self, folder_name: str, timeout=3000) -> bool:
        '''
        Checks if a folder exist in file picker window.
        '''
        self.logger.info(f'Checking folder "{folder_name}" presence...')
        folder_row_selector = f'[data-automationid="DetailsRow"][aria-label*="{folder_name}, Folder" i]'
        try:
            self.iframe.wait_for_selector(folder_row_selector, timeout=timeout)
            self.logger.info('    OK: True')
            return True
        except PwTimeoutError:
            self.logger.info('    OK: False')
            return False
        
    def fp_create_folder(self, folder_name: str) -> None:
        '''
        Create new folder in file picker window.
        '''
        self.logger.info(f'Creating folder "{folder_name}"...')
        iframe = self.iframe
        new_folder_btn_selector = 'button[data-automationid="createFolderCommand"]'
        input_selector = '[class*=nameDialogTextContent] input[type="text"]'
        create_btn_selector = '.ms-Dialog-actions button[data-automation-id="Create"]'
        
        iframe.click(new_folder_btn_selector)
        iframe.wait_for_selector(input_selector)
        iframe.fill(input_selector, folder_name)
        iframe.click(create_btn_selector)

        # Wait for folder to appear in last breadcrumb
        breadcrumbs = self.iframe.locator('.ms-Breadcrumb[role="navigation"] li')
        last_crumb = breadcrumbs.nth(-1)
        crumb = last_crumb.locator(f'.ms-TooltipHost:has-text("{folder_name}")')
        crumb.wait_for(state="visible")
        self.logger.info('    OK')

    def fp_finish(self) -> None:
        '''
        Finish file picker operation (move/copy).
        '''
        self.logger.info('Finishing copy/move operation...')
        finish_btn_selector = 'button[data-automationid="picker-complete"]'
        completed_toast_selector = '[data-automationid="msFluentToast"] i[data-icon-name="CompletedSolid"]'

        self.iframe.click(finish_btn_selector)
        self.page.locator(completed_toast_selector).wait_for(state='visible') # Completed notif
        self.iframe = None
        self.logger.info('    OK')

    def fp_sr_finish(self) -> None:
        '''
        Finish file picker operation (move/copy) in search result page.
        '''
        self.logger.info('Finishing copy/move operation...')
        finish_btn_selector = 'button[data-automationid="picker-complete"]'
        toast_selector = '[data-automationid="msFluentToast"] i[data-icon-name="CompletedSolid"]'
        error_selector = '[data-automationid="msFluentToast"] i[data-icon-name="StatusErrorFull"]'
        error_msg = '[class*="errorDescription"]'
        close_btn = 'button[title*="Dismiss notification"]'


        self.iframe.click(finish_btn_selector)
        try:
            self.page.locator(toast_selector).wait_for(state='visible') # Completed notif
        except PwTimeoutError:
            self.page.locator(error_selector).wait_for(state='visible', timeout=5000)
            msg = self.page.locator(error_msg).inner_text()

            if 'A file with this name already exist' in msg:            
                self.logger.warning('    WARNING: some files already exist')
                self.page.locator(close_btn).click()
            else:
                raise RuntimeError(f'Unknown error msg after move/copy operation: {msg}')

        self.iframe = None
        self.logger.info('    OK')
