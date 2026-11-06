"""Local-only document API. No document content is sent to external services."""
import io
import inspect
import re
from urllib.parse import urlsplit

from flask import jsonify, request, send_file
from werkzeug.exceptions import HTTPException

from .formats import (MAX_BYTES, export_document, import_document, office_path,
                      sanitize, settings_checked)
from .storage import ConflictError, Store


def configure(server, database):
    store = Store(database)
    server.config['MAX_CONTENT_LENGTH'] = MAX_BYTES + 1024 * 1024

    @server.before_request
    def same_origin():
        if request.path.startswith('/api/') and request.method not in ('GET','HEAD','OPTIONS'):
            origin = request.headers.get('Origin')
            if (origin and urlsplit(origin).netloc != request.host) or request.headers.get('Sec-Fetch-Site') == 'cross-site':
                return jsonify(error='Cross-origin changes are not allowed.'), 403

    @server.errorhandler(Exception)
    def error(exc):
        if not request.path.startswith('/api/'):
            if isinstance(exc, HTTPException): return exc
            server.logger.exception('Application error')
            return 'Application error', 500
        if isinstance(exc, ConflictError): return jsonify(error=str(exc)), 409
        if isinstance(exc, KeyError): return jsonify(error='Document not found.'), 404
        if isinstance(exc, ValueError): return jsonify(error=str(exc)), 400
        if isinstance(exc, HTTPException): return jsonify(error=exc.description), exc.code
        server.logger.exception('Document operation failed')
        return jsonify(error='The document could not be processed. It may be damaged or unsupported.'), 422

    def payload():
        value = request.get_json()
        if not isinstance(value, dict): raise ValueError('Expected a JSON object.')
        return value

    def fields(data):
        title = data.get('title','Untitled document')
        if not isinstance(title,str): raise ValueError('Title must be text.')
        return (title.strip()[:180] or 'Untitled document', sanitize(data.get('html','')),
                settings_checked(data.get('settings')))

    @server.route('/api/capabilities', methods=['GET'])
    def capabilities():
        return jsonify(libreoffice=bool(office_path()), max_upload_mb=20)

    @server.route('/api/documents', methods=['GET'])
    def documents(): return jsonify(store.list())

    @server.route('/api/documents', methods=['POST'])
    def create(): return jsonify(store.save(*fields(payload()))), 201

    @server.route('/api/documents/<doc_id>', methods=['GET'])
    def get(doc_id): return jsonify(store.get(doc_id))

    @server.route('/api/documents/<doc_id>', methods=['PUT'])
    def save(doc_id):
        data = payload()
        return jsonify(store.save(*fields(data), doc_id=doc_id, version=data.get('version')))

    @server.route('/api/documents/<doc_id>', methods=['DELETE'])
    def delete(doc_id):
        store.delete(doc_id)
        return '', 204

    @server.route('/api/documents/<doc_id>/history', methods=['GET'])
    def history(doc_id): return jsonify(store.history(doc_id))

    @server.route('/api/documents/<doc_id>/history/<int:version>', methods=['GET'])
    def revision(doc_id, version): return jsonify(store.revision(doc_id,version))

    @server.route('/api/import', methods=['POST'])
    def upload():
        file = request.files.get('file')
        if not file: raise ValueError('Choose a document to import.')
        return jsonify(import_document(file.filename,file.read(MAX_BYTES + 1)))

    @server.route('/api/sanitize', methods=['POST'])
    def clean(): return jsonify(html=sanitize(payload().get('html','')))

    @server.route('/api/export/<extension>', methods=['POST'])
    def export(extension):
        title, markup, settings = fields(payload())
        data, mime = export_document(markup,title,settings,extension)
        name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', title).strip('. ') or 'document'
        filename_key = 'download_name' if 'download_name' in inspect.signature(send_file).parameters else 'attachment_filename'
        return send_file(io.BytesIO(data), mimetype=mime, as_attachment=True,
                         **{filename_key: name + '.' + extension})

    return store
