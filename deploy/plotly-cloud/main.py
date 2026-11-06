"""Optional cloud launcher; Plotly Cloud entry point is app.py."""
import os
from app import app, server

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8050")), debug=False)
