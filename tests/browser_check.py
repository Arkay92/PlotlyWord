"""Run against a test instance: python tests/browser_check.py.

Creates and deletes its own test documents. Uses installed Chrome, no browser download.
"""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'test-results'
OUT.mkdir(exist_ok=True)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='chrome',headless=True)
        page = browser.new_page(viewport={'width':1440,'height':1080},device_scale_factor=1)
        errors=[]
        base = os.environ.get('PLOTLYWORD_TEST_URL','http://127.0.0.1:8053')
        initial_ids = {doc['id'] for doc in page.request.get(base+'/api/documents').json()}
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(os.environ.get('PLOTLYWORD_TEST_URL','http://127.0.0.1:8053'))
        page.wait_for_function("document.querySelector('#save-status')?.textContent === 'All changes saved'")
        page.screenshot(path=str(OUT / 'workspace.png'),full_page=True)
        page.get_by_role('button',name='New document',exact=False).click()
        page.wait_for_function("document.querySelector('#document-title')?.value === 'Untitled document'")
        page.locator('#document-title').fill('Browser test document')
        editor=page.locator('#editor')
        editor.fill('A test document with meaningful content.')
        editor.press('Control+a')
        page.get_by_title('Bold (Ctrl+B)').click()
        assert '<b>' in editor.inner_html() or '<strong>' in editor.inner_html()
        editor.press('End')
        editor.press('Enter')
        editor.press('Control+b')
        editor.press('Control+s')
        page.wait_for_function("document.querySelector('#save-status').textContent === 'All changes saved'")
        page.reload()
        page.wait_for_function("document.querySelector('#document-title')?.value === 'Browser test document'")
        assert 'meaningful content' in editor.inner_text()
        page.get_by_role('button',name='Insert',exact=True).click()
        page.get_by_role('button',name='▦ Table').click()
        page.get_by_role('button',name='Insert table',exact=True).click()
        assert editor.locator('table').count() == 1
        page.get_by_role('button',name='↗ Link').click()
        page.locator('#link-label').fill('OpenAI')
        page.locator('#link-url').fill('https://openai.com')
        page.get_by_role('button',name='Insert link',exact=True).click()
        assert editor.locator('a[href="https://openai.com"]').count() == 1
        page.get_by_role('button',name='⌕ Find').click()
        page.locator('#find-text').fill('meaningful')
        page.locator('#replace-text').fill('useful')
        page.get_by_role('button',name='Replace all').click()
        assert 'useful content' in editor.inner_text()
        page.get_by_title('Close dialog',exact=True).click()
        page.get_by_role('button',name='Layout',exact=True).click()
        page.locator('#orientation').select_option('landscape')
        page.locator('#page-margin').select_option('narrow')
        page.get_by_role('button',name='↗ Export').click()
        with page.expect_download() as download:
            page.get_by_role('button',name='Word document',exact=False).click()
        download.value.save_as(str(OUT/'roundtrip.docx'))
        page.get_by_title('Close dialog',exact=True).click()
        page.locator('#file-input').set_input_files(str(OUT/'roundtrip.docx'))
        page.get_by_role('button',name='Start editing',exact=True).wait_for()
        page.get_by_role('button',name='Start editing',exact=True).click()
        assert 'useful content' in editor.inner_text()
        assert editor.locator('table').count() == 1
        assert page.locator('#orientation').input_value() == 'landscape'
        page.get_by_role('button',name='View',exact=True).click()
        page.get_by_role('button',name='Writing insights',exact=False).click()
        page.locator('#insights-panel .js-plotly-plot').wait_for(state='visible')
        page.get_by_role('button',name='◴ History').click()
        assert page.locator('.history-list').inner_text()
        page.get_by_title('Close dialog',exact=True).click()
        page.screenshot(path=str(OUT/'editing.png'),full_page=True)
        assert not errors, errors
        # Remove only documents created by this test run.
        for doc in page.request.get(base+'/api/documents').json():
            if doc['id'] not in initial_ids and doc['title'] in ('Browser test document','roundtrip'):
                page.request.delete(base+'/api/documents/'+doc['id'])
        browser.close()
        print('Browser checks passed: edit, format, save, reload, table, link, replace, layout, DOCX export/import, insights, history.')


if __name__=='__main__':main()
