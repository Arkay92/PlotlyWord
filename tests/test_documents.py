import io
import zipfile

import pytest
from docx import Document
from flask import Flask

from plotlyword.formats import (docx_to_html, export_document, html_to_docx,
                               import_document, plain_text, sanitize)
from plotlyword.storage import ConflictError, Store
from plotlyword.web import configure


def test_docx_preserves_formatting_table_link_and_page_settings():
    source = '<h1>Quarterly plan</h1><p><strong>Bold</strong> and <em>italic</em> <a href="https://example.com">reference</a></p><ol><li>First</li><li>Second</li></ol><table><tr><th>Owner</th><th>Due</th></tr><tr><td>Jane</td><td>Friday</td></tr></table>'
    data = html_to_docx(source,'Plan',{'size':'Letter','orientation':'landscape','margin':'narrow'})
    doc = Document(io.BytesIO(data))
    assert doc.core_properties.title == 'Plan'
    assert doc.paragraphs[0].style.name == 'Heading 1'
    assert doc.paragraphs[1].runs[0].bold
    assert doc.tables[0].cell(1,0).text == 'Jane'
    assert doc.tables[0].cell(0,0).paragraphs[0].runs[0].bold
    assert doc.sections[0].page_width.inches == 11
    markup, settings, warnings = docx_to_html(data)
    assert '<strong>Bold</strong>' in markup
    assert '<em>italic</em>' in markup
    assert 'href="https://example.com"' in markup
    assert '<ol><li>First</li><li>Second</li></ol>' in markup
    assert settings == {'size':'Letter','orientation':'landscape','margin':'narrow'}
    assert warnings


def test_docx_image_roundtrip():
    import base64
    from PIL import Image
    image = io.BytesIO(); Image.new('RGB',(60,30),'green').save(image,'PNG')
    source = '<p>An image <img src="data:image/png;base64,' + base64.b64encode(image.getvalue()).decode() + '" alt="green"></p>'
    docx = html_to_docx(source)
    assert len(Document(io.BytesIO(docx)).inline_shapes) == 1
    assert 'data:image/png;base64,' in docx_to_html(docx)[0]


def test_sanitizer_blocks_scripts_handlers_and_remote_images():
    result = sanitize('<script>alert(1)</script><p onclick="evil()" style="color:red;background-image:url(https://evil)">Safe</p><img src="https://evil/pixel"><img src="data:image/svg+xml;base64,AAAA"><a href="javascript:evil()">bad</a><a href="data:text/html;base64,AAAA">bad2</a>')
    assert 'script' not in result and 'onclick' not in result
    assert '<img' not in result and 'javascript:' not in result
    assert 'background-image' not in result and 'data:text' not in result
    assert 'Safe' in result and 'color:red' in result


@pytest.mark.parametrize('encoding',['utf-8-sig','utf-16','cp1252'])
def test_text_import_unicode(encoding):
    result = import_document('notes.txt','Café\nA second line'.encode(encoding))
    assert 'Café' in result['html']
    data, _ = export_document(result['html'],'notes',{},'txt')
    assert data.decode() == 'Café\nA second line'


def test_reject_invalid_documents_and_formats():
    with pytest.raises(ValueError): import_document('file.exe',b'abcd')
    with pytest.raises(ValueError): import_document('file.docx',b'abcd')
    with pytest.raises(ValueError): import_document('file.txt',b'')
    with pytest.raises(ValueError): export_document('<p>a</p>','file',{},'exe')


def test_plain_text_does_not_split_inline_runs():
    assert plain_text('<p>Hello <strong>beautiful</strong> world.</p><p>Next line.</p>') == 'Hello beautiful world.\nNext line.'


def test_legacy_formats_explain_missing_converter(monkeypatch):
    monkeypatch.setattr('plotlyword.formats.office_path',lambda:None)
    with pytest.raises(ValueError,match='LibreOffice'):
        import_document('old.doc',b'legacy')
    with pytest.raises(ValueError,match='LibreOffice'):
        export_document('<p>Test</p>','Test',{},'pdf')


def test_store_conflicts_history_retention_and_delete(tmp_path):
    store = Store(tmp_path / 'documents.db')
    first = store.save('First','<p>One</p>',{})
    second = store.save('Second','<p>Two</p>',{},first['id'],1)
    with pytest.raises(ConflictError): store.save('Stale','<p>Stale</p>',{},first['id'],1)
    assert store.get(first['id'])['title'] == 'Second'
    assert store.revision(first['id'],1)['html'] == '<p>One</p>'
    for _ in range(52):
        second = store.save('Next','<p>Next</p>',{},first['id'],second['version'])
    assert len(store.history(first['id'])) == 50
    store.delete(first['id'])
    assert store.list() == []
    with pytest.raises(KeyError): store.get(first['id'])


@pytest.fixture
def client(tmp_path):
    app = Flask(__name__)
    configure(app,tmp_path / 'test.db')
    return app.test_client()


def test_api_lifecycle_exports_and_errors(client):
    created = client.post('/api/documents',json={'title':'Hello','html':'<h1>Hello</h1><p>World</p>'})
    assert created.status_code == 201
    doc = created.json
    assert client.get('/api/documents').json[0]['id'] == doc['id']
    assert client.put('/api/documents/'+doc['id'],json={**doc,'html':'<p>New</p>'}).status_code == 200
    assert client.put('/api/documents/'+doc['id'],json=doc).status_code == 409
    assert len(client.get('/api/documents/'+doc['id']+'/history').json) == 2
    assert client.get('/api/documents/missing').status_code == 404
    for ext in ('txt','docx','html'):
        response = client.post('/api/export/'+ext,json=doc)
        assert response.status_code == 200
        assert 'attachment' in response.headers['Content-Disposition']
        if ext == 'docx': assert zipfile.is_zipfile(io.BytesIO(response.data))
    assert client.delete('/api/documents/'+doc['id']).status_code == 204


def test_api_sanitizes_imports_and_rejects_cross_origin_writes(client):
    result = client.post('/api/import',data={'file':(io.BytesIO(b'<h1>Safe</h1><script>evil()</script>'),'file.html')})
    assert result.status_code == 200
    assert 'script' not in result.json['html']
    assert client.post('/api/documents',json={'title':'Test'},headers={'Origin':'https://evil.example'}).status_code == 403
    assert client.post('/api/documents',json=[]).status_code == 400
