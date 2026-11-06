"""Transactional document storage with optimistic concurrency and version history."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


class ConflictError(Exception):
    pass


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, html TEXT NOT NULL,
                    settings TEXT NOT NULL, version INTEGER NOT NULL, updated TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS revisions (
                    document_id TEXT NOT NULL, version INTEGER NOT NULL, title TEXT NOT NULL,
                    html TEXT NOT NULL, settings TEXT NOT NULL, updated TEXT NOT NULL,
                    PRIMARY KEY(document_id, version));
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def decode(row):
        if row is None:
            raise KeyError('Document not found.')
        result = dict(row)
        if 'settings' in result:
            result['settings'] = json.loads(result['settings'])
        return result

    def list(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute(
                'SELECT id,title,version,updated FROM documents ORDER BY updated DESC')]

    def get(self, doc_id):
        with self.connect() as db:
            return self.decode(db.execute('SELECT * FROM documents WHERE id=?', (doc_id,)).fetchone())

    def save(self, title, html, settings, doc_id=None, version=None):
        now = datetime.now(timezone.utc).isoformat()
        encoded = json.dumps(settings)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if doc_id:
                old = db.execute('SELECT version FROM documents WHERE id=?', (doc_id,)).fetchone()
                if old is None:
                    raise KeyError('Document not found.')
                if version != old['version']:
                    raise ConflictError('This document changed in another tab. Export your edits, then reload to continue.')
                next_version = version + 1
                db.execute('UPDATE documents SET title=?,html=?,settings=?,version=?,updated=? WHERE id=?',
                           (title, html, encoded, next_version, now, doc_id))
            else:
                doc_id, next_version = uuid4().hex, 1
                db.execute('INSERT INTO documents VALUES (?,?,?,?,?,?)',
                           (doc_id, title, html, encoded, next_version, now))
            db.execute('INSERT INTO revisions VALUES (?,?,?,?,?,?)',
                       (doc_id, next_version, title, html, encoded, now))
            # Keep the last 50 revisions for each document.
            db.execute('DELETE FROM revisions WHERE document_id=? AND version<=?',
                       (doc_id, next_version - 50))
        return self.get(doc_id)

    def history(self, doc_id):
        self.get(doc_id)
        with self.connect() as db:
            return [dict(r) for r in db.execute(
                'SELECT version,title,updated FROM revisions WHERE document_id=? ORDER BY version DESC', (doc_id,))]

    def revision(self, doc_id, version):
        with self.connect() as db:
            return self.decode(db.execute('SELECT * FROM revisions WHERE document_id=? AND version=?',
                                         (doc_id, version)).fetchone())

    def delete(self, doc_id):
        with self.connect() as db:
            db.execute('DELETE FROM revisions WHERE document_id=?', (doc_id,))
            db.execute('DELETE FROM documents WHERE id=?', (doc_id,))
