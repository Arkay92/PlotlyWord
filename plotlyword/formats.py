"""Safe editable HTML, direct DOCX conversion, and optional LibreOffice bridge.

HTML is the editing model, not a lossless representation of arbitrary OOXML.
"""
import base64
import io
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from html import escape
from pathlib import Path

import bleach
from bleach.css_sanitizer import CSSSanitizer
from bs4 import BeautifulSoup, NavigableString
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from PIL import Image

MAX_BYTES = 20 * 1024 * 1024
TAGS = {'p','div','br','h1','h2','h3','h4','h5','h6','strong','b','em','i','u','s',
        'strike','sup','sub','span','font','a','ul','ol','li','blockquote','pre','code',
        'table','thead','tbody','tr','td','th','img','hr'}
CSS = CSSSanitizer(allowed_css_properties=[
    'color','background-color','font-family','font-size','font-weight','font-style',
    'text-decoration','text-align','line-height','margin-left','page-break-before','break-before'])


def sanitize(value):
    if not isinstance(value, str) or len(value.encode('utf-8')) > MAX_BYTES:
        raise ValueError('Document content must be text and smaller than 20 MB.')
    soup = BeautifulSoup(value, 'html.parser')
    for tag in soup(['script','style','iframe','object','embed','svg','math']):
        tag.decompose()
    clean = bleach.clean(str(soup), tags=TAGS,
        attributes={'*':['style'], 'a':['href','title'], 'img':['src','alt','width','height'],
                    'font':['face','color','size'], 'td':['colspan','rowspan'],
                    'th':['colspan','rowspan'], 'ol':['start']},
        protocols=['http','https','mailto','data'], css_sanitizer=CSS, strip=True)
    soup = BeautifulSoup(clean, 'html.parser')
    for image in soup.find_all('img'):
        if not re.fullmatch(r'data:image/(?:png|jpeg|gif|webp);base64,[A-Za-z0-9+/=\s]+', image.get('src','')):
            image.decompose()
    for link in soup.find_all('a'):
        if not re.match(r'^(https?://|mailto:|#)', link.get('href',''), re.I):
            link.attrs.pop('href', None)
        link['rel'] = 'noopener noreferrer'
    return str(soup)


def plain_text(value):
    soup = BeautifulSoup(value, 'html.parser')
    for br in soup.find_all('br'):
        br.replace_with('\n')
    for node in soup.find_all(['p','div','h1','h2','h3','h4','li','tr','blockquote']):
        node.append('\n')
    for cell in soup.find_all(['td','th']):
        cell.append('\t')
    return soup.get_text().strip()


def settings_checked(value):
    value = value if isinstance(value, dict) else {}
    return {'size': value.get('size') if value.get('size') in ('A4','Letter') else 'A4',
            'orientation': 'landscape' if value.get('orientation') == 'landscape' else 'portrait',
            'margin': 'narrow' if value.get('margin') == 'narrow' else 'normal'}


def office_path():
    explicit = os.environ.get('PLOTLYWORD_SOFFICE')
    candidates = [explicit, shutil.which('soffice'), shutil.which('libreoffice'),
        r'C:\Program Files\LibreOffice\program\soffice.exe',
        '/Applications/LibreOffice.app/Contents/MacOS/soffice']
    return next((str(p) for p in candidates if p and Path(p).is_file()), None)


def office_convert(data, source_ext, target):
    executable = office_path()
    if not executable:
        raise ValueError('This format needs LibreOffice. Install it and restart PlotlyWord, or set PLOTLYWORD_SOFFICE to its executable. DOCX, TXT and HTML work without it.')
    filters = {'doc':'doc:MS Word 97', 'docx':'docx:Office Open XML Text',
               'odt':'odt', 'rtf':'rtf', 'pdf':'pdf:writer_pdf_Export'}
    if target not in filters or source_ext not in {'doc','docx','rtf','odt'}:
        raise ValueError('Unsupported conversion.')
    with tempfile.TemporaryDirectory(prefix='plotlyword-') as folder:
        root = Path(folder)
        source = root / ('source.' + source_ext)
        source.write_bytes(data)
        out = root / 'output'
        out.mkdir()
        try:
            result = subprocess.run([executable, '-env:UserInstallation=' + (root / 'profile').as_uri(),
                '--headless','--convert-to',filters[target],'--outdir',str(out),str(source)],
                capture_output=True, timeout=60, creationflags=0x08000000 if os.name == 'nt' else 0)
        except subprocess.TimeoutExpired as exc:
            raise ValueError('Conversion timed out after 60 seconds.') from exc
        converted = out / ('source.' + target)
        if result.returncode or not converted.exists():
            raise ValueError('LibreOffice could not convert this document. Check whether it is damaged or password protected.')
        return converted.read_bytes()


def _check_zip(data):
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if sum(i.file_size for i in archive.infolist()) > 100 * 1024 * 1024:
                raise ValueError('Expanded document exceeds the 100 MB limit.')
            if len(archive.infolist()) > 10000:
                raise ValueError('Document contains too many parts.')
    except zipfile.BadZipFile as exc:
        raise ValueError('This is not a valid DOCX/ODT file.') from exc


def docx_to_html(data):
    _check_zip(data)
    doc = Document(io.BytesIO(data))

    def run_html(run):
        text = escape(run.text).replace('\n','<br>')
        for drawing in run._r.xpath('.//a:blip'):
            rid = drawing.get(qn('r:embed'))
            if rid and rid in doc.part.related_parts:
                part = doc.part.related_parts[rid]
                if part.content_type in ('image/png','image/jpeg','image/gif','image/webp'):
                    text += f'<img src="data:{part.content_type};base64,{base64.b64encode(part.blob).decode()}" alt="Imported image">'
        styles = []
        if run.font.name: styles.append('font-family:' + run.font.name)
        if run.font.size: styles.append(f'font-size:{run.font.size.pt}pt')
        if run.font.color.rgb: styles.append('color:#' + str(run.font.color.rgb))
        if styles: text = '<span style="' + escape(';'.join(styles), quote=True) + '">' + text + '</span>'
        for enabled, tag in ((run.bold,'strong'),(run.italic,'em'),(run.underline,'u'),
                             (run.font.strike,'s'),(run.font.superscript,'sup'),(run.font.subscript,'sub')):
            if enabled: text = f'<{tag}>{text}</{tag}>'
        if run._r.xpath('.//w:br[@w:type="page"]'):
            text += '<div style="page-break-before:always"><br></div>'
        return text

    def paragraph(p):
        style = p.style.name if p.style else ''
        tag = 'h' + style[-1] if re.fullmatch(r'Heading [1-6]', style) else 'p'
        if style == 'Title': tag = 'h1'
        body = ''
        for item in p.iter_inner_content():
            if hasattr(item, 'url'):
                body += f'<a href="{escape(item.url, quote=True)}">' + ''.join(run_html(r) for r in item.runs) + '</a>'
            else:
                body += run_html(item)
        css = []
        align = {WD_ALIGN_PARAGRAPH.CENTER:'center', WD_ALIGN_PARAGRAPH.RIGHT:'right',
                 WD_ALIGN_PARAGRAPH.JUSTIFY:'justify'}.get(p.alignment)
        if align: css.append('text-align:' + align)
        if p.paragraph_format.page_break_before: css.append('page-break-before:always')
        attr = f' style="{";".join(css)}"' if css else ''
        is_list = 'List' in style or p._p.xpath('./w:pPr/w:numPr')
        if is_list:
            kind = 'ol' if 'Number' in style else 'ul'
            num = p._p.xpath('./w:pPr/w:numPr/w:numId/@w:val')
            if num:
                definitions = doc.part.numbering_part.element
                abstract = definitions.xpath(f'./w:num[@w:numId="{num[0]}"]/w:abstractNumId/@w:val')
                if abstract:
                    fmt = definitions.xpath(f'./w:abstractNum[@w:abstractNumId="{abstract[0]}"]/w:lvl/w:numFmt/@w:val')
                    if fmt: kind = 'ul' if fmt[0] == 'bullet' else 'ol'
            return kind, f'<li{attr}>{body or "<br>"}</li>'
        return None, f'<{tag}{attr}>{body or "<br>"}</{tag}>'

    def blocks(container):
        result, list_kind = [], None
        for item in container.iter_inner_content():
            if hasattr(item, 'rows'):
                kind = None
                markup = '<table><tbody>' + ''.join('<tr>' + ''.join('<td>' + blocks(c) + '</td>' for c in row.cells) + '</tr>' for row in item.rows) + '</tbody></table>'
            else:
                kind, markup = paragraph(item)
            if kind != list_kind:
                if list_kind: result.append(f'</{list_kind}>')
                if kind: result.append(f'<{kind}>')
                list_kind = kind
            result.append(markup)
        if list_kind: result.append(f'</{list_kind}>')
        return ''.join(result)

    section = doc.sections[0]
    landscape = section.page_width > section.page_height
    width = min(section.page_width.inches, section.page_height.inches)
    settings = {'size':'Letter' if abs(width - 8.5) < .1 else 'A4',
                'orientation':'landscape' if landscape else 'portrait',
                'margin':'narrow' if section.left_margin.inches < .75 else 'normal'}
    warnings = ['Imported editable text and common formatting. Complex layouts, fields, comments and tracked changes may be simplified. Keep your original file.']
    return sanitize(blocks(doc)), settings, warnings


def html_to_docx(value, title='Untitled document', settings=None):
    doc = Document()
    settings = settings_checked(settings)
    section = doc.sections[0]
    width, height = (8.2677, 11.6929) if settings['size'] == 'A4' else (8.5, 11)
    if settings['orientation'] == 'landscape': width, height = height, width
    section.page_width, section.page_height = Inches(width), Inches(height)
    margin = .5 if settings['margin'] == 'narrow' else 1
    section.top_margin = section.bottom_margin = section.left_margin = section.right_margin = Inches(margin)
    doc.core_properties.title = title
    doc.styles['Normal'].font.name = 'Calibri'
    doc.styles['Normal'].font.size = Pt(11)
    soup = BeautifulSoup(sanitize(value), 'html.parser')

    def css_of(node):
        return dict(part.split(':',1) for part in node.get('style','').split(';') if ':' in part)

    def inline(node, p, inherited=None):
        attrs = dict(inherited or {})
        if isinstance(node, NavigableString):
            run = p.add_run(str(node))
            for key in ('bold','italic','underline'):
                if attrs.get(key): setattr(run, key, True)
            run.font.strike = attrs.get('strike',False)
            run.font.superscript = attrs.get('sup',False)
            run.font.subscript = attrs.get('sub',False)
            if attrs.get('font'): run.font.name = attrs['font']
            if attrs.get('size'): run.font.size = Pt(attrs['size'])
            if attrs.get('color'): run.font.color.rgb = RGBColor.from_string(attrs['color'])
            if attrs.get('background'):
                shd = OxmlElement('w:shd'); shd.set(qn('w:fill'),attrs['background'])
                run._r.get_or_add_rPr().append(shd)
            if attrs.get('link'):
                link = OxmlElement('w:hyperlink')
                link.set(qn('r:id'), p.part.relate_to(attrs['link'],
                    'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink', is_external=True))
                p._p.append(link); link.append(run._r)
            return
        if node.name == 'br': p.add_run().add_break(); return
        if node.name == 'img':
            try:
                raw = base64.b64decode(node['src'].split(',',1)[1], validate=True)
                with Image.open(io.BytesIO(raw)) as im:
                    im.load()
                    image_width = min(im.width / 96, width - 2 * margin)
                    normalized = io.BytesIO(); im.convert('RGB').save(normalized, 'PNG')
                normalized.seek(0)
                p.add_run().add_picture(normalized, width=Inches(image_width))
            except (ValueError, KeyError, OSError) as exc:
                raise ValueError('An embedded image could not be exported.') from exc
            return
        for tag, key in [('b','bold'),('strong','bold'),('i','italic'),('em','italic'),('u','underline'),('s','strike'),('strike','strike'),('sup','sup'),('sub','sub')]:
            if node.name == tag: attrs[key] = True
        css = {k.strip():v.strip() for k,v in css_of(node).items()}
        if css.get('font-weight') in ('bold','700','800','900'): attrs['bold'] = True
        if css.get('font-style') == 'italic': attrs['italic'] = True
        if 'underline' in css.get('text-decoration',''): attrs['underline'] = True
        if css.get('font-family') or node.get('face'): attrs['font'] = (css.get('font-family') or node['face']).split(',')[0].strip(' "\'')
        size = css.get('font-size','')
        if re.fullmatch(r'[\d.]+(?:pt|px)', size): attrs['size'] = min(96,max(6,float(size[:-2]) * (.75 if size.endswith('px') else 1)))
        if node.name == 'font' and node.get('size') in list('1234567'):
            attrs['size'] = [8,10,12,14,18,24,36][int(node['size'])-1]
        for prop, key in [('color','color'),('background-color','background')]:
            color = css.get(prop, node.get('color','') if prop == 'color' else '')
            try:
                from PIL import ImageColor
                if color: attrs[key] = '%02x%02x%02x' % ImageColor.getrgb(color)[:3]
            except ValueError: pass
        if node.name == 'a' and node.get('href'): attrs['link'] = node['href']
        for child in node.children: inline(child,p,attrs)

    def blocks(nodes, container):
        for node in nodes:
            if isinstance(node,NavigableString):
                if str(node).strip(): inline(node,container.add_paragraph())
                continue
            if node.name == 'table':
                rows = node.find_all('tr')
                if not rows: continue
                count = max(len(row.find_all(['td','th'],recursive=False)) for row in rows)
                if not count: continue
                table = container.add_table(rows=len(rows), cols=count)
                table.style = 'Table Grid'
                for i, row in enumerate(rows):
                    for j, cell in enumerate(row.find_all(['td','th'],recursive=False)):
                        target = table.cell(i,j)
                        blocks(cell.contents,target)
                        if len(target.paragraphs)>1 and not target.paragraphs[0].text:
                            target._tc.remove(target.paragraphs[0]._p)
                        if cell.name == 'th':
                            for paragraph in target.paragraphs:
                                for run in paragraph.runs:
                                    run.bold = True
            elif node.name in ('ul','ol'):
                for li in node.find_all('li',recursive=False):
                    p = container.add_paragraph(style='List Number' if node.name == 'ol' else 'List Bullet')
                    for child in li.contents:
                        if getattr(child,'name',None) in ('ul','ol'): blocks([child],container)
                        else: inline(child,p)
            elif node.name == 'div' and node.find(['p','h1','h2','h3','table','ul','ol'],recursive=False):
                blocks(node.contents,container)
            else:
                p = container.add_paragraph()
                if re.fullmatch('h[1-6]',node.name or ''): p.style = 'Heading ' + node.name[1]
                if node.name == 'blockquote': p.style = 'Quote'
                css = {k.strip():v.strip() for k,v in css_of(node).items()}
                p.alignment = {'center':WD_ALIGN_PARAGRAPH.CENTER,'right':WD_ALIGN_PARAGRAPH.RIGHT,
                               'justify':WD_ALIGN_PARAGRAPH.JUSTIFY}.get(css.get('text-align'), WD_ALIGN_PARAGRAPH.LEFT)
                if css.get('page-break-before') == 'always' or css.get('break-before') == 'page':
                    p.paragraph_format.page_break_before = True
                if node.name == 'hr': p.add_run('—' * 20)
                else: inline(node,p)
    blocks(soup.contents,doc)
    stream = io.BytesIO(); doc.save(stream)
    return stream.getvalue()


def import_document(filename, data):
    if not data or len(data) > MAX_BYTES:
        raise ValueError('Choose a nonempty file smaller than 20 MB.')
    ext = Path(filename).suffix.lower().lstrip('.')
    settings, warnings = settings_checked({}), []
    if ext in ('doc','rtf','odt'):
        if ext == 'odt': _check_zip(data)
        data = office_convert(data,ext,'docx'); ext = 'docx'
    if ext == 'docx':
        markup, settings, warnings = docx_to_html(data)
    elif ext in ('txt','md','html','htm'):
        try:
            encoding = 'utf-16' if data.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig'
            text = data.decode(encoding)
        except UnicodeDecodeError:
            text = data.decode('cp1252'); warnings.append('Decoded this file as Windows-1252.')
        markup = sanitize(text) if ext in ('html','htm') else ''.join('<p>' + escape(line or '\u00a0') + '</p>' for line in text.splitlines())
        if ext == 'md': warnings.append('Markdown opened as plain text; Markdown syntax is not rendered.')
    else:
        raise ValueError('Supported imports: DOCX, DOC, TXT, HTML, RTF, ODT and plain-text Markdown.')
    return {'title':Path(filename).stem[:180] or 'Imported document', 'html':markup,
            'settings':settings, 'warnings':warnings}


def export_document(markup, title, settings, extension):
    markup = sanitize(markup)
    if extension == 'txt': return plain_text(markup).encode('utf-8'), 'text/plain; charset=utf-8'
    if extension == 'html':
        value = '<!doctype html><html><head><meta charset="utf-8"><title>' + escape(title) + '</title></head><body>' + markup + '</body></html>'
        return value.encode(), 'text/html; charset=utf-8'
    if extension not in ('docx','doc','odt','rtf','pdf'): raise ValueError('Unsupported export format.')
    data = html_to_docx(markup,title,settings)
    if extension == 'docx': return data, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    return office_convert(data,'docx',extension), {'pdf':'application/pdf','doc':'application/msword',
        'rtf':'application/rtf','odt':'application/vnd.oasis.opendocument.text'}[extension]
