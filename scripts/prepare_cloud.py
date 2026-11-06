"""Build a clean Plotly Cloud upload folder and ZIP, like the sibling projects.

Run from anywhere: python scripts/prepare_cloud.py
Only application code and assets are included, never local documents or environments.
"""
from pathlib import Path
import shutil
import zipfile


ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'deploy' / 'plotly-cloud'
ARCHIVE = ROOT / 'deploy' / 'plotlyword-plotly-cloud.zip'


def main():
    # Check resolved paths before replacing this generated directory, including
    # Windows junctions in the parent path. Never remove a runtime database.
    if DEST.resolve() != ROOT / 'deploy' / 'plotly-cloud' or DEST.is_symlink():
        raise RuntimeError('Refusing to replace an unexpected deployment path.')
    if ARCHIVE.resolve() != ROOT / 'deploy' / 'plotlyword-plotly-cloud.zip':
        raise RuntimeError('Refusing to overwrite an unexpected archive path.')
    if DEST.exists():
        if (DEST / 'data').exists() or any(DEST.rglob('*.sqlite3')) or any(DEST.rglob('*.db')):
            raise RuntimeError('Deployment folder contains runtime data. Back it up and move it out before rebuilding.')
        if any(path.is_symlink() or path.resolve() != DEST / path.relative_to(DEST)
               for path in DEST.rglob('*')):
            raise RuntimeError('Deployment folder contains a linked path; refusing to replace it.')
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True)

    for name in ('app.py', 'requirements.txt', 'LICENSE'):
        shutil.copy2(ROOT / name, DEST / name)
    for folder in ('plotlyword', 'assets'):
        for source in sorted((ROOT / folder).rglob('*')):
            relative = source.relative_to(ROOT)
            if not source.is_file() or any(part.startswith('.') or part == '__pycache__' for part in relative.parts):
                continue
            if source.suffix in ('.pyc', '.pyo') or source.is_symlink():
                continue
            destination = DEST / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    shutil.copy2(ROOT / 'deploy' / 'README.md', DEST / 'README.md')
    # The source entry point stays identical; main.py is an optional cloud-host
    # launcher for hosts that execute a file rather than discover the Dash app.
    (DEST / 'main.py').write_text(
        '"""Optional cloud launcher; Plotly Cloud entry point is app.py."""\n'
        'import os\n'
        'from app import app, server\n\n'
        'if __name__ == "__main__":\n'
        '    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8050")), debug=False)\n',
        encoding='utf-8')
    with zipfile.ZipFile(ARCHIVE, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(DEST.rglob('*')):
            if path.is_file():
                bundle.write(path, path.relative_to(DEST))
    print(f'Upload folder: {DEST}')
    print(f'ZIP archive: {ARCHIVE} ({ARCHIVE.stat().st_size:,} bytes)')
    print('Upload the folder contents, preserving subfolders. Entry point: app.py. Python: 3.11.')
    print('No local documents, databases, environments or tests are included.')


if __name__ == '__main__':
    main()
