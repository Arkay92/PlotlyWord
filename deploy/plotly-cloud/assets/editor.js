/* Browser editing and selection bridge. Persistence and conversion live in Python. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let editor, current, savedRange, saveTimer, metricsTimer, dirty = false, saving = null;
  let generation = 0, zoom = 1, docs = [], capabilities = {}, toastTimer;
  const defaults = {size:'A4', orientation:'portrait', margin:'normal'};
  const welcome = `<p style="font-size:10pt;color:#7a8d7a">A SPACE FOR YOUR WORDS</p>
    <h1>Something worth saying.</h1>
    <p>Every good idea starts somewhere. A scribbled note. A conversation. A sentence you can’t quite get out of your head.</p>
    <p>This is your space to give it a little room.</p>
    <h2>Begin with the big idea</h2>
    <p>What do you want to say? Start with the part that matters most. You can find the perfect words later.</p>
    <blockquote>“You don’t have to see the whole staircase, just take the first step.”</blockquote>
    <h2>Make it your own</h2>
    <p>A few things to try as you settle in:</p>
    <ul><li><strong>Find your voice.</strong> Add a heading, a little emphasis, or a fresh perspective.</li>
    <li><strong>Bring ideas together.</strong> Insert a table, an image, or a useful link.</li>
    <li><strong>Take your work with you.</strong> Export your draft as a Word document or plain text.</li></ul>
    <h2>A note to your future self</h2><p>It doesn’t have to be perfect. It just has to begin.</p>`;
  const templates = {
    blank: {title:'Untitled document', html:'<p><br></p>'},
    brief: {title:'Project brief', html:'<p style="color:#7a8d7a">PROJECT BRIEF</p><h1>A clear direction.</h1><p>Project name · Prepared by your team</p><h2>The opportunity</h2><p>Describe the problem and why it matters.</p><h2>What success looks like</h2><ul><li>Define the primary outcome.</li><li>Choose how you will measure it.</li></ul><h2>The plan</h2><table><tbody><tr><th>Milestone</th><th>Owner</th><th>Target date</th></tr><tr><td>Discovery</td><td>Your name</td><td>To be confirmed</td></tr><tr><td>Delivery</td><td>Your name</td><td>To be confirmed</td></tr></tbody></table><h2>Next steps</h2><p>What happens next, and who will take the lead?</p>'},
    meeting: {title:'Meeting notes',html:'<p style="color:#7a8d7a">MEETING NOTES</p><h1>A conversation, captured.</h1><p>Date · Attendees</p><h2>On the agenda</h2><ol><li>What we need to discuss</li><li>Decisions we need to make</li></ol><h2>Discussion</h2><p>Capture the ideas that matter.</p><h2>Decisions</h2><ul><li>Record what was agreed.</li></ul><h2>Action items</h2><table><tbody><tr><th>Action</th><th>Owner</th><th>Due</th></tr><tr><td>Next step</td><td>Name</td><td>Date</td></tr></tbody></table>'},
    letter: {title:'A thoughtful letter',html:'<h1>A thoughtful letter.</h1><p>Your name<br>Your address</p><p>Dear recipient,</p><p>Start with what you want them to know.</p><p>Add a little context, and give your ideas room to breathe.</p><p>Warm regards,</p><p>Your name</p>'}
  };

  async function api(path, options={}) {
    const response = await fetch(path, options);
    if (!response.ok) {
      let data; try { data = await response.json(); } catch (_) { data = {}; }
      throw new Error(data.error || `Request failed (${response.status}).`);
    }
    return response.status === 204 ? null : response.json();
  }
  const json = (method, body) => ({method, headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  function toast(message, error=false) {
    $('toast').textContent = message; $('toast').className = 'visible' + (error ? ' error' : '');
    clearTimeout(toastTimer); toastTimer = setTimeout(() => $('toast').className = '', error ? 12000 : 5000);
  }
  function status(text, error=false) { $('save-status').textContent=text; $('save-status').className=error?'error-text':''; }
  function settings() { return {size:$('page-size').value,orientation:$('orientation').value,margin:$('page-margin').value}; }
  function snapshot() { return {title:$('document-title').value || 'Untitled document',html:editor.innerHTML,settings:settings(),version:current?.version}; }
  function backup() {
    try { localStorage.setItem('plotlyword-recovery',JSON.stringify({id:current?.id, ...snapshot(), dirty, updated:Date.now()})); }
    catch (_) { status('Browser backup unavailable. Save to disk.',true); }
  }
  function changed() {
    generation++; dirty=true; status('Unsaved changes…'); backup();
    clearTimeout(saveTimer); saveTimer=setTimeout(() => save().catch(e=>toast(e.message,true)),1200);
    clearTimeout(metricsTimer); metricsTimer=setTimeout(updateMetrics,250);
  }
  async function save() {
    clearTimeout(saveTimer);
    if (saving) { await saving; if (dirty) return save(); return; }
    if (!dirty || !current) return;
    const stamp = generation, id=current.id, data=snapshot();
    status('Saving…');
    saving = api('/api/documents/' + id,json('PUT',data));
    try {
      const result=await saving;
      current=result;
      if (generation === stamp) { dirty=false; status('All changes saved'); }
      else status('Unsaved changes…');
      backup(); await refreshLibrary();
    } catch (e) { status('Not saved · ' + e.message,true); throw e; }
    finally { saving=null; }
    if (dirty) return save();
  }
  async function refreshLibrary() { docs=await api('/api/documents'); renderLibrary(); }
  function renderLibrary() {
    const search=$('document-search').value.toLowerCase();
    const filtered=docs.filter(d=>d.title.toLowerCase().includes(search));
    $('document-list').innerHTML=filtered.map(d=>`<button class="document-item ${d.id===current?.id?'selected':''}" data-open="${d.id}" title="${esc(d.title)}"><span class="document-icon">▤</span><span><strong>${esc(d.title)}</strong><small>${new Date(d.updated).toLocaleDateString(undefined,{month:'short',day:'numeric'})} · Document</small></span></button>`).join('') || '<p class="empty-note">No documents found.</p>';
  }
  function load(doc) {
    current=doc; dirty=false; savedRange=null; generation++;
    editor.innerHTML=doc.html || '<p><br></p>';
    $('document-title').value=doc.title;
    const s={...defaults,...doc.settings};
    $('page-size').value=s.size; $('orientation').value=s.orientation; $('page-margin').value=s.margin;
    applyLayout(); updateMetrics(); renderLibrary(); status('All changes saved');
    try {localStorage.setItem('plotlyword-current',doc.id);} catch (_) {}
    backup(); $('canvas').scrollTop=0;
  }
  async function create(template=templates.blank) {
    await save();
    const doc=await api('/api/documents',json('POST',{...template,settings:template.settings||defaults}));
    await refreshLibrary(); load(doc); closeDialog(); editor.focus();
  }
  function applyLayout() {
    const s=settings();
    let [w,h]=s.size==='Letter'?[816,1056]:[794,1123];
    if (s.orientation==='landscape') [w,h]=[h,w];
    $('paper').style.width=w+'px'; $('paper').style.minHeight=h+'px';
    const padding=s.margin==='narrow'?48:96;
    $('paper').style.padding=padding+'px';
    editor.style.minHeight=Math.max(200,h-2*padding-2)+'px';
    $('paper').style.zoom=zoom;
    $('page-status').textContent=s.size+' · '+(s.orientation==='landscape'?'Landscape':'Portrait');
    let printStyle=$('print-page-style');
    if (!printStyle) {printStyle=document.createElement('style');printStyle.id='print-page-style';document.head.append(printStyle);}
    printStyle.textContent=`@page { size: ${s.size==='Letter'?'letter':'A4'} ${s.orientation}; margin: ${s.margin==='narrow'?'0.5in':'1in'}; }`;
  }
  function rememberSelection() {
    const sel=window.getSelection();
    if (sel.rangeCount && editor.contains(sel.anchorNode) && editor.contains(sel.focusNode)) savedRange=sel.getRangeAt(0).cloneRange();
  }
  function restoreSelection() {
    editor.focus(); const sel=window.getSelection();
    if (savedRange && editor.contains(savedRange.commonAncestorContainer)) { sel.removeAllRanges();sel.addRange(savedRange); }
    else {const range=document.createRange();range.selectNodeContents(editor);range.collapse(false);sel.removeAllRanges();sel.addRange(range);}
  }
  function command(name,value=null) { restoreSelection();document.execCommand(name,false,value);rememberSelection();changed(); }
  function updateMetrics() {
    const text=editor.innerText.trim(), words=text?text.split(/\s+/u).length:0;
    $('word-count').textContent=words.toLocaleString()+' words';
    $('character-count').textContent=text.length.toLocaleString()+' characters';
    const headings=[...editor.querySelectorAll('h1,h2,h3')];
    $('outline').innerHTML=headings.length?headings.map((h,i)=>`<button data-heading="${i}" class="outline-item level-${h.tagName.toLowerCase()}">${esc(h.textContent||'Untitled section')}</button>`).join(''):'<p class="empty-note">Add headings to find your way around.</p>';
    const sections=[]; let active={title:'Introduction',words:0};
    [...editor.children].forEach(node=>{
      if (/^H[1-3]$/.test(node.tagName)) {if(active.words)sections.push(active);active={title:node.textContent,words:0};}
      const t=node.innerText.trim();active.words+=t?t.split(/\s+/u).length:0;
    });
    if(active.words)sections.push(active);
    if(window.dash_clientside?.set_props) window.dash_clientside.set_props('editor-metrics',{data:{words,sections}});
  }
  function dialog(title,body) {
    rememberSelection(); $('dialog-title').textContent=title;$('dialog-body').innerHTML=body;
    if(!$('dialog').open)$('dialog').showModal();
    setTimeout(()=>$('dialog-body').querySelector('input,button,select')?.focus(),30);
  }
  function closeDialog() { $('dialog').close(); }
  function exportDialog() {
    dialog('Take your words with you',`<p class="dialog-intro">Download a copy of your current draft.</p><div class="format-grid">${[
      ['docx','Word document','.docx · Common formatting'],['txt','Plain text','.txt · Just your words'],['html','Web document','.html · Styled text'],
      ['doc','Word 97–2003','.doc · LibreOffice required'],['odt','OpenDocument','.odt · LibreOffice required'],['rtf','Rich text','.rtf · LibreOffice required'],
      ['pdf','PDF document','.pdf · LibreOffice required']].map(([ext,name,info])=>`<button data-export="${ext}" ${!capabilities.libreoffice&&['doc','odt','rtf','pdf'].includes(ext)?'disabled':''}><b>${name}</b><small>${info}</small></button>`).join('')}</div>
      ${!capabilities.libreoffice?'<p class="notice">LibreOffice is not installed. Install it to enable legacy Word, ODT, RTF and PDF conversion. You can also print to PDF from your browser.</p>':''}
      <p class="muted">Advanced Word features may be simplified. Keep original files when importing.</p><button class="secondary" data-action="print">Print / Save as PDF</button>`);
  }
  async function exportFile(ext) {
    const button=$('dialog-body').querySelector(`[data-export="${ext}"]`); if(button)button.disabled=true;
    try {
      const response=await fetch('/api/export/'+ext,json('POST',snapshot()));
      if(!response.ok) {const data=await response.json();throw new Error(data.error);}
      const url=URL.createObjectURL(await response.blob()),a=document.createElement('a');
      a.href=url;a.download=($('document-title').value||'document').replace(/[<>:"/\\|?*]/g,'_')+'.'+ext;
      a.click();setTimeout(()=>URL.revokeObjectURL(url),10000);toast('Your '+ext.toUpperCase()+' file is ready.');
    } finally {if(button)button.disabled=false;}
  }
  async function historyDialog() {
    await save();const history=await api(`/api/documents/${current.id}/history`);
    dialog('A little history',`<p class="dialog-intro">The last 50 saved versions. Restoring creates a new version.</p><div class="history-list">${history.map(h=>`<div><span><b>${esc(h.title)}</b><small>Version ${h.version} · ${new Date(h.updated).toLocaleString()}</small></span><button class="secondary" data-restore="${h.version}" ${h.version===current.version?'disabled':''}>${h.version===current.version?'Current':'Restore'}</button></div>`).join('')}</div>`);
  }
  function templateDialog() {
    dialog('A good place to begin',`<p class="dialog-intro">A little structure for whatever comes next.</p><div class="template-grid">${[['blank','01','A blank page','All the space you need.'],['brief','02','Project brief','Give your next idea direction.'],['meeting','03','Meeting notes','Keep the conversation moving.'],['letter','04','A thoughtful letter','Make a personal connection.']].map(([key,n,title,desc])=>`<button data-template="${key}"><span class="template-preview"><i>${n}</i><span>━━━━<br>━━━━━━━━<br>━━━━━━━━<br>━━━━━</span></span><b>${title}</b><small>${desc}</small></button>`).join('')}</div>`);
  }
  function findDialog() {
    dialog('Find & replace','<label class="field">Find<input id="find-text" placeholder="What are you looking for?"></label><label class="field">Replace with<input id="replace-text" placeholder="Replacement text"></label><p id="find-feedback" class="muted">Matches are case-sensitive. Replace preserves surrounding formatting.</p><div class="dialog-actions"><button class="secondary" data-action="find-next">Find next</button><button class="primary" data-action="replace-all">Replace all</button></div>');
  }
  function textNodes() {
    const walk=document.createTreeWalker(editor,NodeFilter.SHOW_TEXT),nodes=[];let node;
    while((node=walk.nextNode()))nodes.push(node);
    return nodes;
  }
  function findNext() {
    const query=$('find-text').value;if(!query)return;
    const nodes=textNodes();let text='',spans=[];
    nodes.forEach(node=>{spans.push({node,start:text.length,end:text.length+node.length});text+=node.textContent;});
    let from=0;
    if(savedRange){const span=spans.find(s=>s.node===savedRange.endContainer);if(span)from=span.start+savedRange.endOffset;}
    let at=text.indexOf(query,from);if(at<0)at=text.indexOf(query);
    if(at<0){$('find-feedback').textContent='No matches found.';return;}
    const start=spans.find(s=>at>=s.start&&at<s.end),end=spans.find(s=>at+query.length>s.start&&at+query.length<=s.end);
    const range=document.createRange();range.setStart(start.node,at-start.start);range.setEnd(end.node,at+query.length-end.start);
    savedRange=range;closeDialog();restoreSelection();start.node.parentElement.scrollIntoView({block:'center'});
  }
  function replaceAll() {
    const query=$('find-text').value,replacement=$('replace-text').value;if(!query)return;
    const nodes=textNodes();let text='',spans=[];
    nodes.forEach(node=>{spans.push({node,start:text.length,end:text.length+node.length});text+=node.textContent;});
    const matches=[];let at=0;
    while((at=text.indexOf(query,at))>=0){matches.push(at);at+=query.length;}
    // Replace from the end so earlier offsets remain valid, including across inline formatting.
    matches.reverse().forEach(index=>{
      const first=spans.find(s=>index>=s.start&&index<s.end),last=spans.find(s=>index+query.length>s.start&&index+query.length<=s.end);
      const range=document.createRange();range.setStart(first.node,index-first.start);range.setEnd(last.node,index+query.length-last.start);
      range.deleteContents();range.insertNode(document.createTextNode(replacement));
    });
    savedRange=null;changed();$('find-feedback').textContent=`Replaced ${matches.length} occurrence${matches.length===1?'':'s'}. Use version history to restore earlier text.`;
  }
  function selectedTable() { const node=savedRange?.startContainer; return (node?.nodeType===1?node:node?.parentElement)?.closest('table'); }
  const commands=new Set(['undo','redo','bold','italic','underline','strikeThrough','justifyLeft','justifyCenter','justifyRight','justifyFull','insertUnorderedList','insertOrderedList','indent','outdent','removeFormat','insertHorizontalRule']);
  async function action(name) {
    if(commands.has(name)){command(name);return;}
    if(name.startsWith('tab-')){
      const tab=name.slice(4);document.querySelectorAll('.ribbon-panel').forEach(p=>p.classList.toggle('hidden',p.id!=='ribbon-'+tab));
      document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active',t.id===name));return;
    }
    switch(name){
      case 'new': await create();break;
      case 'templates':templateDialog();break;
      case 'export':exportDialog();break;
      case 'history':await historyDialog();break;
      case 'find':findDialog();break;
      case 'find-next':findNext();break;
      case 'replace-all':replaceAll();break;
      case 'close-dialog':closeDialog();break;
      case 'print':closeDialog();window.print();break;
      case 'outline':$('outline-panel').classList.toggle('hidden');break;
      case 'focus':$('app-root').classList.toggle('focus-mode');break;
      case 'insights':$('insights-panel').classList.toggle('hidden');window.dispatchEvent(new Event('resize'));break;
      case 'zoom-in':case 'zoom-out':zoom=Math.min(1.5,Math.max(.5,zoom+(name==='zoom-in'?.1:-.1)));$('zoom-label').textContent=Math.round(zoom*100)+'%';applyLayout();break;
      case 'link':dialog('Add a link','<label class="field">Link text<input id="link-label" placeholder="Selected text" value="'+esc(savedRange?.toString()||'')+'"></label><label class="field">Web address<input id="link-url" type="url" placeholder="https://example.com"></label><button class="primary" data-action="insert-link">Insert link</button>');break;
      case 'insert-link':{
        const url=$('link-url').value.trim(),label=$('link-label').value||url;
        if(!/^(https?:\/\/|mailto:)/i.test(url))throw new Error('Enter a link beginning with https://, http:// or mailto:.');
        closeDialog();command('insertHTML',`<a href="${esc(url)}" rel="noopener noreferrer">${esc(label)}</a>`);break;
      }
      case 'table':dialog('Bring a little order','<div class="field-row"><label class="field">Rows<input id="table-rows" type="number" min="1" max="30" value="3"></label><label class="field">Columns<input id="table-cols" type="number" min="1" max="12" value="3"></label></div><button class="primary" data-action="insert-table">Insert table</button>');break;
      case 'insert-table':{
        const r=Number($('table-rows').value),c=Number($('table-cols').value);
        if(!Number.isInteger(r)||!Number.isInteger(c)||r<1||r>30||c<1||c>12)throw new Error('Choose 1–30 rows and 1–12 columns.');
        const table='<table><tbody>'+Array.from({length:r},(_,row)=>'<tr>'+Array.from({length:c},(_,col)=>`<${row?'td':'th'}>${row?'&nbsp;':'Column '+(col+1)}</${row?'td':'th'}>`).join('')+'</tr>').join('')+'</tbody></table><p><br></p>';
        closeDialog();command('insertHTML',table);break;
      }
      case 'table-row':{const table=selectedTable();if(!table)throw new Error('Place the cursor inside a table first.');const row=table.insertRow();for(let i=0;i<table.rows[0].cells.length;i++)row.insertCell().innerHTML='<br>';changed();break;}
      case 'table-remove':{const table=selectedTable();if(!table)throw new Error('Place the cursor inside a table first.');table.remove();savedRange=null;changed();break;}
      case 'image':$('image-input').click();break;
      case 'page-break':command('insertHTML','<div style="page-break-before:always"><br></div><p><br></p>');break;
      case 'more':dialog('Document actions','<div class="menu-actions"><button class="secondary" data-action="save">Save now <small>Ctrl / ⌘ + S</small></button><button class="secondary" data-action="duplicate">Make a copy</button><button class="secondary danger" data-action="delete">Delete this document</button></div>');break;
      case 'save':await save();toast('All changes saved.');break;
      case 'duplicate':await create({...snapshot(),title:$('document-title').value+' (copy)'});toast('A fresh copy is ready.');break;
      case 'delete':dialog('Delete this document?',`<p>This removes <strong>${esc(current.title)}</strong> and its saved versions from this computer.</p><div class="dialog-actions"><button class="secondary" data-action="close-dialog">Keep document</button><button class="primary danger" data-action="confirm-delete">Delete document</button></div>`);break;
      case 'confirm-delete':{
        clearTimeout(saveTimer);if(saving)await saving;await api('/api/documents/'+current.id,{method:'DELETE'});dirty=false;current=null;
        await refreshLibrary();if(docs.length)load(await api('/api/documents/'+docs[0].id));else await create();closeDialog();toast('Document deleted.');break;
      }
    }
  }
  async function importFile(file) {
    if(!file)return;if(file.size>20*1024*1024)throw new Error('Choose a file smaller than 20 MB.');
    await save();status('Importing…');
    const form=new FormData();form.append('file',file);
    const imported=await api('/api/import',{method:'POST',body:form});
    const doc=await api('/api/documents',json('POST',imported));await refreshLibrary();load(doc);
    if(imported.warnings.length)dialog('Your document is ready',`<p>${imported.warnings.map(esc).join('</p><p>')}</p><button class="primary" data-action="close-dialog">Start editing</button>`);
    else toast('Document imported.');
  }
  async function addImage(file) {
    if(!file)return;if(file.size>5*1024*1024)throw new Error('Choose an image smaller than 5 MB.');
    if(!/^image\/(png|jpeg|gif|webp)$/.test(file.type))throw new Error('Choose a PNG, JPEG, GIF or WebP image.');
    const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(file);});
    command('insertHTML',`<img src="${data}" alt="${esc(file.name)}"><p><br></p>`);
  }
  async function init() {
    document.querySelectorAll('[data-native-input]').forEach(holder=>{
      const props=JSON.parse(holder.dataset.nativeInput),input=document.createElement('input');
      Object.entries(props).forEach(([k,v])=>{if(k==='style')Object.assign(input.style,v);else input.setAttribute(k,String(v));});holder.append(input);
    });
    editor=$('editor');
    editor.addEventListener('input',changed);
    document.addEventListener('selectionchange',rememberSelection);
    document.addEventListener('mousedown',event=>{if(event.target.closest('.tool,.ribbon-button'))event.preventDefault();});
    document.addEventListener('click',event=>{
      const el=event.target.closest('[data-action],[data-open],[data-template],[data-export],[data-restore],[data-heading]');
      if(!el)return;
      (async()=>{
        if(el.dataset.action)await action(el.dataset.action);
        else if(el.dataset.open){await save();load(await api('/api/documents/'+el.dataset.open));}
        else if(el.dataset.template)await create(templates[el.dataset.template]);
        else if(el.dataset.export)await exportFile(el.dataset.export);
        else if(el.dataset.restore){const old=await api(`/api/documents/${current.id}/history/${el.dataset.restore}`);editor.innerHTML=old.html;$('document-title').value=old.title;const s=old.settings;$('page-size').value=s.size;$('orientation').value=s.orientation;$('page-margin').value=s.margin;applyLayout();savedRange=null;changed();await save();closeDialog();toast('Earlier version restored.');}
        else if(el.dataset.heading!==undefined)editor.querySelectorAll('h1,h2,h3')[Number(el.dataset.heading)]?.scrollIntoView({behavior:'smooth',block:'center'});
      })().catch(e=>toast(e.message,true));
    });
    $('document-title').addEventListener('input',changed);
    $('document-search').addEventListener('input',renderLibrary);
    [['block-style','formatBlock'],['font-family','fontName'],['font-size','fontSize'],['text-color','foreColor'],['highlight-color','hiliteColor']].forEach(([id,cmd])=>$(id).addEventListener('change',()=>command(cmd,$(id).value)));
    ['page-size','orientation','page-margin'].forEach(id=>$(id).addEventListener('change',()=>{applyLayout();changed();}));
    $('file-input').addEventListener('change',e=>{importFile(e.target.files[0]).catch(err=>{status('Import failed',true);toast(err.message,true);});e.target.value='';});
    $('image-input').addEventListener('change',e=>{addImage(e.target.files[0]).catch(err=>toast(err.message,true));e.target.value='';});
    // Sanitize rich clipboard content on the server before it can enter the DOM.
    editor.addEventListener('paste',async event=>{
      event.preventDefault();rememberSelection();const pasted=event.clipboardData.getData('text/html'),plain=event.clipboardData.getData('text/plain');
      try {if(pasted){const result=await api('/api/sanitize',json('POST',{html:pasted}));command('insertHTML',result.html);}else command('insertText',plain);}
      catch(e){toast(e.message,true);}
    });
    editor.addEventListener('dragover',event=>event.preventDefault());
    editor.addEventListener('drop',event=>{event.preventDefault();toast('Use Import document or Insert → Image to add files.');});
    editor.addEventListener('keydown',event=>{if(event.key==='Tab'){event.preventDefault();command(event.shiftKey?'outdent':'indent');}});
    document.addEventListener('keydown',event=>{
      if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='s'){event.preventDefault();save().then(()=>toast('All changes saved.')).catch(e=>toast(e.message,true));}
      if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='f'){event.preventDefault();findDialog();}
      if(event.key==='Escape')$('app-root').classList.remove('focus-mode');
    });
    window.addEventListener('beforeunload',event=>{if(dirty){backup();event.preventDefault();event.returnValue='';}});
    capabilities=await api('/api/capabilities');await refreshLibrary();
    let last,recovery;try{last=localStorage.getItem('plotlyword-current');recovery=JSON.parse(localStorage.getItem('plotlyword-recovery'));}catch(_){}
    if(docs.length)load(await api('/api/documents/'+(docs.some(d=>d.id===last)?last:docs[0].id)));
    else await create({title:'Something worth saying',html:welcome});
    if(recovery?.dirty){
      // Recover as a separate document; never overwrite a newer server revision.
      const doc=await api('/api/documents',json('POST',{...recovery,title:(recovery.title||'Document')+' (recovered)'}));
      await refreshLibrary();load(doc);toast('Recovered an unsaved draft as a separate document.');
    }
  }
  const observer=new MutationObserver(()=>{if($('editor')&&!editor){observer.disconnect();editor=$('editor');init().catch(e=>{status('Could not open workspace',true);toast(e.message,true);});}});
  observer.observe(document.documentElement,{childList:true,subtree:true});
})();
