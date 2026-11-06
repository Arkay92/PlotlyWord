# PlotlyWord — Plotly Cloud upload

This folder is a standalone application package. It includes `app.py`, an optional
`main.py` launcher, `requirements.txt`, the `plotlyword/` package and `assets/`.
No local documents, database, test output, Python environment or `.deps` directory
is included.

## Upload

1. Upload the **contents** of `deploy/plotly-cloud/`, preserving the subfolders.
   Alternatively, extract `plotlyword-plotly-cloud.zip` and upload its contents.
2. Select **app.py** as the entry point and **Python 3.11**.
3. Include `requirements.txt` so the host installs the application dependencies.
4. Keep the deployment private: the current application has one shared document
   library, not separate user accounts.

Plotly Cloud discovers the Dash application directly; no Procfile is needed.
See [Plotly's deployment guidance](https://roadmap.plotly.com/en/help/articles/3483180-what-changes-should-i-make-to-my-dash-app-to).

## Storage and formats

- Set `PLOTLYWORD_DATABASE` to a writable path on your configured persistent
  storage, for example `/your-mounted-storage/documents.sqlite3`. The example
  is a placeholder, not an automatically provisioned mount.
- Without this setting, the app writes `data/documents.sqlite3` beside `app.py`.
  Do not rely on that filesystem surviving restarts or redeployments. Export
  important documents unless persistent storage has been configured and verified.
- All users of this deployment share the same server library. The editor's
  local-workspace labels refer to the app server when hosted, not the visitor's
  computer. Browser recovery drafts remain in each visitor's browser.
- DOCX, TXT and HTML work with the Python dependencies alone. DOC, RTF, ODT and
  server PDF export require a LibreOffice executable on the host; it is not
  included in this package or installed by pip. Set `PLOTLYWORD_SOFFICE` if one
  is available. Otherwise those exports remain disabled; browser printing works.
- This package does not add real-time collaboration or multi-user isolation.

For a generic host, `app:server` is the WSGI target. If the host launches Python
directly, use `python main.py`, which binds to `0.0.0.0` and reads `PORT` (default
8050). Install a production WSGI server separately if your platform requires one.

## Rebuild from the source repository

```powershell
python scripts/prepare_cloud.py
```

The script regenerates the upload folder and ZIP. Edit the original application
files, then rebuild; changes made inside the generated folder will be replaced.
The builder refuses to replace a folder containing runtime databases.
