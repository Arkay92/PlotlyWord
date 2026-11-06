import json
from dash import dcc, html


def native_input(**props):
    """Mount browser inputs omitted by dash.html without React controlling the caret."""
    return html.Span(**{'data-native-input':json.dumps(props)})


def button(label, action=None, cls='', title=None, **props):
    attrs = {'data-action':action} if action else {}
    return html.Button(label, className=cls, title=title or str(label), **attrs, **props)


def select(id, options, title):
    return html.Select([html.Option(label, value=value) for value,label in options], id=id, title=title, **{'aria-label':title})


def layout():
    return html.Div([
        dcc.Store(id='editor-metrics'),
        html.Aside([
            html.Div([html.Span('W',className='brand-mark'), html.Span(['Plotly',html.B('Word'),html.Span('.',className='brand-dot')])],className='brand'),
            html.Div('A LITTLE SPACE FOR BIG IDEAS',className='brand-caption'),
            button(['＋', ' New document'],'new','primary new-document'),
            html.Label(['↥', ' Import document',
                        native_input(type='file',id='file-input',accept='.docx,.doc,.txt,.html,.htm,.rtf,.odt,.md')],className='import-button',htmlFor='file-input'),
            html.Div([html.Span('YOUR WORKSPACE'),html.Span('LOCAL',className='tiny-pill')],className='section-label'),
            native_input(id='document-search',placeholder='Search documents…',type='search',**{'aria-label':'Search documents'}),
            html.Div(id='document-list',className='document-list'),
            html.Div([html.Div('MAKE ROOM FOR YOUR NEXT IDEA',className='eyebrow'),html.H3('Start with a little structure.'),
                      html.P('A brief, a meeting, a blank page. Make it yours.'),button('Explore templates  ↗','templates','text-button')],className='template-card'),
            html.Div([html.Span('●',className='online-dot'),html.Div(['Your words stay here',html.Small('Saved locally on this computer')])],className='local-note'),
        ],className='sidebar'),
        html.Main([
            html.Header([
                html.Div([html.Span('Workspace',className='muted'),html.Span('/',className='slash'),html.Span('Document studio')],className='breadcrumb'),
                html.Div([button('⌕  Find','find','quiet'),button('◴  History','history','quiet'),button('↗  Export','export','primary')],className='top-actions')
            ],className='topbar'),
            html.Div([
                html.Div([html.Div('YOUR NEXT GREAT DRAFT',className='eyebrow'),
                          native_input(id='document-title',value='Untitled document',maxLength=180,**{'aria-label':'Document title'}),
                          html.Div([html.Span('●',className='online-dot'),html.Span('Opening workspace…',id='save-status'),html.Span('·',className='dot'),html.Span('Only you')],className='save-meta')]),
                html.Div([html.Span('EDITING',className='editing-pill'),button('•••','more','more-button',title='Document actions')],className='heading-actions')
            ],className='document-heading'),
            html.Div([
                html.Div([button('Home','tab-home','tab active',id='tab-home'),button('Insert','tab-insert','tab',id='tab-insert'),
                          button('Layout','tab-layout','tab',id='tab-layout'),button('View','tab-view','tab',id='tab-view')],className='ribbon-tabs'),
                html.Div([
                    html.Div([button('↶','undo','tool',title='Undo (Ctrl+Z)'),button('↷','redo','tool',title='Redo (Ctrl+Y)')],className='tool-group'),
                    select('block-style',[('p','Normal text'),('h1','Heading 1'),('h2','Heading 2'),('h3','Heading 3'),('blockquote','Quote'),('pre','Code')],'Paragraph style'),
                    select('font-family',[('Calibri','Calibri'),('Arial','Arial'),('Georgia','Georgia'),('Times New Roman','Times New Roman'),('Courier New','Courier New')],'Font family'),
                    select('font-size',[('3','12'),('1','8'),('2','10'),('4','14'),('5','18'),('6','24'),('7','36')],'Font size'),
                    html.Div([button(html.B('B'),'bold','tool',title='Bold (Ctrl+B)'),button(html.I('I'),'italic','tool',title='Italic (Ctrl+I)'),
                              button(html.U('U'),'underline','tool',title='Underline (Ctrl+U)'),button('S̶','strikeThrough','tool',title='Strikethrough'),
                              html.Label(['A',native_input(id='text-color',type='color',value='#263c32',title='Text color')],className='color-tool'),
                              html.Label(['▰',native_input(id='highlight-color',type='color',value='#e8edbe',title='Highlight color')],className='color-tool')],className='tool-group'),
                    html.Div([button('≡','justifyLeft','tool',title='Align left'),button('☰','justifyCenter','tool',title='Align center'),
                              button('☷','justifyRight','tool',title='Align right'),button('☷','justifyFull','tool',title='Justify'),
                              button('• ≡','insertUnorderedList','tool',title='Bullet list'),button('1 ≡','insertOrderedList','tool',title='Numbered list'),
                              button('⇥','indent','tool',title='Increase indent'),button('⇤','outdent','tool',title='Decrease indent'),
                              button('Tx','removeFormat','tool',title='Clear formatting')],className='tool-group')
                ],id='ribbon-home',className='ribbon-panel'),
                html.Div([button('↗  Link','link','ribbon-button'),button('▦  Table','table','ribbon-button'),
                          button('▧  Image','image','ribbon-button'),button('↵  Page break','page-break','ribbon-button'),
                          button('—  Divider','insertHorizontalRule','ribbon-button'),button('＋  Table row','table-row','ribbon-button'),
                          button('−  Remove table','table-remove','ribbon-button')],id='ribbon-insert',className='ribbon-panel hidden'),
                html.Div([html.Span('Page size'),select('page-size',[('A4','A4'),('Letter','US Letter')],'Page size'),
                          html.Span('Orientation'),select('orientation',[('portrait','Portrait'),('landscape','Landscape')],'Orientation'),
                          html.Span('Margins'),select('page-margin',[('normal','Normal · 1 inch'),('narrow','Narrow · ½ inch')],'Margins')],id='ribbon-layout',className='ribbon-panel hidden'),
                html.Div([button('☷  Document outline','outline','ribbon-button'),button('◫  Focus mode','focus','ribbon-button'),
                          button('▥  Writing insights','insights','ribbon-button'),button('▤  Print / Save as PDF','print','ribbon-button')],id='ribbon-view',className='ribbon-panel hidden')
            ],className='ribbon'),
            html.Div([
                html.Aside([html.Div('IN THIS DOCUMENT',className='section-label'),html.Div(id='outline'),
                            html.Div([html.Span('✧'),html.P('Good ideas begin with a first draft.'),html.Small('Take your time. Find your words.')],className='outline-note')],id='outline-panel',className='outline-panel'),
                html.Div([html.Div([html.Span(str(i)) for i in range(1,9)],className='ruler'),
                          html.Div([html.Div(id='editor',contentEditable=True,spellCheck=True,role='textbox',
                                            **{'aria-label':'Document editor','aria-multiline':'true'})],id='paper',className='paper'),
                          html.Div('A little thought. A few words. Something worth saying.',className='canvas-caption')],id='canvas',className='canvas'),
                html.Aside([html.Div([html.H3('Writing insights'),button('×','insights','quiet',title='Close insights')],className='panel-heading'),
                            dcc.Graph(id='insights-graph',config={'displayModeBar':False},style={'height':'260px'}),
                            html.P('Word counts by section. Keep your document balanced.',className='muted')],id='insights-panel',className='insights-panel hidden')
            ],className='workspace'),
            html.Footer([html.Div([html.Span('0 words',id='word-count'),html.Span('0 characters',id='character-count'),html.Span('English · Browser spellcheck')]),
                         html.Div([html.Span('A4 · Portrait',id='page-status'),button('−','zoom-out','zoom-button',title='Zoom out'),
                                   html.Span('100%',id='zoom-label'),button('＋','zoom-in','zoom-button',title='Zoom in')])],className='statusbar')
        ],className='main-shell'),
        html.Div(id='toast',role='status',**{'aria-live':'polite'}),
        html.Dialog([html.Div([html.H2(id='dialog-title'),button('×','close-dialog','quiet',title='Close dialog')],className='dialog-heading'),html.Div(id='dialog-body')],id='dialog'),
        native_input(id='image-input',type='file',accept='image/png,image/jpeg,image/gif,image/webp',style={'display':'none'}),
    ],id='app-root')
