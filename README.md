# PlotlyWord

A local document studio built with **Python, Plotly and Dash**. Its paper canvas, sage sidebar and compact controls take inspiration from the neighbouring Plotly Data Genie and PlotlyChess projects.

PlotlyWord is a working word-processing foundation, **not a feature-complete or lossless Microsoft Word replacement**. It supports common document editing and exchange; the compatibility table below describes the boundaries.

## Run locally

Requires Python 3.10 or newer.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python app.py
```

Open **http://127.0.0.1:8053**. The app binds to localhost by default. `app` and `server` are exposed in `app.py` for Dash/WSGI tooling.

On this development machine, `python app.py` also works with the existing Python packages and project-local `.deps` dependencies. A new installation should use the virtual environment commands above. To test against `.deps` without a virtual environment, set `$env:PYTHONPATH = "$PWD\.deps"` before running pytest, so test plugins load the same Flask runtime.

## What works

- Rich text: headings, font family and size, bold, italic, underline, strikethrough, text colour, highlight, alignment, indentation and lists.
- Insert links, embedded images, simple tables, additional table rows, dividers and explicit page breaks.
- A4 / Letter, portrait / landscape, normal / narrow margins, zoom, focus mode and browser printing.
- Document library, title editing, search, duplication and deletion with confirmation.
- Autosave after typing pauses, SQLite persistence, last 50 revisions, restoration and browser recovery drafts.
- Optimistic version checks prevent one tab silently overwriting another. Export your edits if a conflict occurs, then reload.
- Heading outline, word/character counts, and a Dash callback with a Plotly section-length chart.
- Case-sensitive find and replace, including matches spanning inline formatting.
- Blank, project brief, meeting notes and letter templates.
- Browser-provided spellcheck; Ctrl/Command+S to save, Ctrl/Command+F to find, normal browser editing shortcuts.

## File compatibility

| Format | Import | Export | Notes |
| --- | --- | --- | --- |
| DOCX | Yes | Yes | Python conversion for editable text, common inline styles, headings, simple lists/tables, links and embedded images. |
| TXT | Yes | Yes | UTF-8 and UTF-16 import; Windows-1252 fallback. UTF-8 export. |
| HTML / HTM | Yes | HTML | Sanitized editable HTML. Embedded raster images only; remote images are removed. |
| DOC | With LibreOffice | With LibreOffice | Real binary Word conversion, not a renamed DOCX. |
| RTF | With LibreOffice | With LibreOffice | Converted through DOCX. |
| ODT | With LibreOffice | With LibreOffice | Converted through DOCX. |
| PDF | No | With LibreOffice or browser print | PDF is an output format, not an editable document import. |
| Markdown | As plain text | Via TXT | Markdown syntax is not rendered. |

Uploads are limited to 20 MB. Embedded image insertion is limited to 5 MB. Expanded DOCX/ODT archives are limited to 100 MB.

### Enable legacy Word and additional formats

Install LibreOffice, then restart PlotlyWord. It detects the usual Windows/macOS installation or `soffice` / `libreoffice` on PATH. For another installation:

```powershell
$env:PLOTLYWORD_SOFFICE = 'C:\Program Files\LibreOffice\program\soffice.exe'
python app.py
```

Each conversion uses its own temporary directory and LibreOffice profile, a 60-second timeout, and no visible application window. The UI checks capabilities and disables unavailable exports. LibreOffice is optional and is not bundled.

### Fidelity boundaries

Keep original files. The editing model is sanitized HTML, not the entire original Word package. Imports can simplify or omit headers/footers, tracked changes, comments, footnotes/endnotes, fields, citations, equations, text boxes, floating objects, section breaks, nested numbering, merged cells, and advanced layout. Lists and tables are deliberately basic. Images are embedded; their original positioning/cropping is not retained. DOCX default styling can differ from the editor's paper styling.

The canvas is a continuous editing surface, not Word's live pagination engine. Explicit page breaks and print settings are applied during export/printing. No real-time collaboration, accounts, cloud synchronisation, review mode, or Word macro execution is implemented. Direct table edits and replace-all use version history for restoration rather than promising browser undo for every operation.

The browser bridge uses native `contenteditable` and `execCommand` to preserve the browser's ordinary typing/formatting undo stack. A structured editing engine would be the next step for advanced collaborative editing, precise selection state and complex document schemas.

## Data and deployment

- Documents and revision snapshots live in `data/documents.sqlite3`; back up this file while the app is stopped.
- `PLOTLYWORD_DATABASE` can select another SQLite path.
- `PORT` defaults to `8053`; `HOST` defaults to `127.0.0.1`.
- Recovery drafts are stored in this browser's local storage. Server documents remain after browser storage is cleared.
- Document content is processed locally. No AI service, external font CDN or remote editor library is needed.
- This is a **single-user local application**. All clients of the same server share the same library. Add authentication, user-scoped storage, TLS and production hosting before exposing it publicly. It is not ready for a public multi-user deployment.

## Cloud upload package

The same upload-folder convention as the sibling projects is available:

```powershell
python scripts/prepare_cloud.py
```

This generates `deploy/plotly-cloud/` and `deploy/plotlyword-plotly-cloud.zip`.
The folder includes the app, Python dependencies and assets, without local
documents, databases or environments. Use `app.py` as the entry point.
See [cloud deployment instructions](deploy/README.md) for persistent storage,
shared-library behaviour and optional LibreOffice support.

## Tests

```powershell
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m pytest -q
# With the app running and Google Chrome installed:
.\.venv\Scripts\python tests/browser_check.py
```

Backend tests cover formatting, hyperlinks, tables, images, Unicode encodings, sanitization, document history, concurrent-save conflicts, API workflows and missing converters. The browser check covers editing, formatting, persistence, tables, links, find/replace, layout, export/reimport and the Plotly insights panel. Browser screenshots and generated fixtures go in ignored `test-results/`.

## Source layout

- `app.py` — Dash entry point and Plotly writing-insights callback.
- `plotlyword/ui.py` — Python UI layout.
- `plotlyword/web.py` — local Flask document API.
- `plotlyword/storage.py` — transactional SQLite documents and history.
- `plotlyword/formats.py` — sanitization, DOCX conversion and LibreOffice adapter.
- `assets/editor.js` — selection, typing, toolbar and persistence bridge.
- `assets/styles.css` — responsive editor and print styling.

Implementation references: [Dash clientside integration](https://dash.plotly.com/clientside-callbacks), [python-docx text API](https://python-docx.readthedocs.io/en/latest/api/text.html), [LibreOffice command-line conversion](https://help.libreoffice.org/latest/en-GB/text/shared/guide/start_parameters.html).
