"""Run `python app.py`, then visit http://127.0.0.1:8053."""
import os
import sys
import gzip
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if (ROOT / '.deps').is_dir():
    sys.path.insert(0, str(ROOT / '.deps'))

import plotly.graph_objects as go
from plotly.offline import get_plotlyjs
from dash import Dash, Input, Output
from flask import Response

from plotlyword.ui import layout
from plotlyword.web import configure

app = Dash(__name__, title='PlotlyWord · A space for your words',
           assets_folder=str(ROOT / 'assets'), update_title=None,
           external_scripts=['/plotlyword-plotly.js'])
app.layout = layout
server = app.server
store = configure(server, os.environ.get('PLOTLYWORD_DATABASE', str(ROOT / 'data' / 'documents.sqlite3')))

# Serve the installed Plotly runtime locally and compressed. Loading it up front
# also avoids a large deferred script transfer when opening the insights panel.
_plotly_js = gzip.compress(get_plotlyjs().encode('utf-8'))


@server.route('/plotlyword-plotly.js')
def plotly_runtime():
    return Response(_plotly_js, mimetype='application/javascript',
                    headers={'Content-Encoding':'gzip','Cache-Control':'public, max-age=3600'})


@app.callback(Output('insights-graph','figure'), Input('editor-metrics','data'))
def insights(data):
    sections = (data or {}).get('sections', [])[:30]
    fig = go.Figure(go.Bar(x=[s['words'] for s in sections], y=[s['title'][:28] for s in sections],
                           orientation='h', marker_color='#779481', hovertemplate='%{x} words<extra></extra>'))
    fig.update_layout(template='plotly_white', margin=dict(l=10,r=15,t=15,b=30),
                      paper_bgcolor='#fafbf8', plot_bgcolor='#fafbf8', font=dict(family='Segoe UI',size=11,color='#52675a'),
                      yaxis=dict(autorange='reversed'), xaxis=dict(title='Words',gridcolor='#e8ece5'))
    return fig


if __name__ == '__main__':
    app.run(host=os.environ.get('HOST','127.0.0.1'), port=int(os.environ.get('PORT','8053')), debug=False)
