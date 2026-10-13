const $ = id => document.getElementById(id);
let ready = false;
let busy = false;
let sourceList = [];
let answerSources = [];
let selection = '';
const examples = {
  python: ['Who wrote the Zen of Python?', 'zen-of-python.txt'],
  pdf: ['Which page is a blank page?', 'preview-demo.pdf'],
  csv: ['What species is in data row 1?', 'iris.csv'],
};

function status(message = '', error = false) {
  $('status').textContent = message;
  $('status').setAttribute('role', error ? 'alert' : 'status');
}
function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function controls() {
  document.querySelectorAll('#upload, #file, #filter, #question, [data-example], .doc-select, .remove').forEach(node => {
    node.disabled = !ready || busy;
  });
  $('ask').disabled = !ready || busy || $('question').value.trim().length < 3;
  $('ask').textContent = busy ? 'Working…' : 'Ask';
  $('question-form').setAttribute('aria-busy', String(busy));
}
function sourceKey(doc) { return `${doc.scope}:${doc.doc_id}`; }
function selectedSource() { return sourceList.find(doc => sourceKey(doc) === $('filter').value); }
function selectSource(key) {
  if (key !== selection) {
    $('result').replaceChildren();
    answerSources = [];
    selection = key;
    status();
  }
  $('filter').value = key;
  document.querySelectorAll('.doc-select').forEach(button => {
    button.setAttribute('aria-pressed', String(button.dataset.key === key));
  });
  $('examples').hidden = Boolean(selectedSource()?.scope === 'uploads');
  document.body.classList.remove('show-sources');
  $('toggle-sources').setAttribute('aria-expanded', 'false');
}
async function api(path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 90000);
  try {
    const response = await fetch(path, { ...options, signal: controller.signal });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const message = typeof data?.detail === 'string' ? data.detail : 'The server is unavailable. Please try again.';
      const error = new Error(message); error.status = response.status; throw error;
    }
    if (data === null) throw new Error('The server returned an unexpected response. Please retry.');
    return data;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('The server took too long. Please retry.');
    if (error instanceof TypeError) throw new Error('Could not connect. Check your connection and retry.');
    throw error;
  } finally { clearTimeout(timeout); }
}
async function documents() {
  const selected = $('filter').value;
  sourceList = await api('/api/documents');
  $('docs').replaceChildren();
  $('filter').replaceChildren(new Option('All documents', ''));
  $('doc-count').textContent = sourceList.length;
  for (const scope of ['uploads', 'samples']) {
    const docs = sourceList.filter(doc => doc.scope === scope);
    if (!docs.length) continue;
    $('docs').append(element('p', scope === 'uploads' ? 'Your uploads' : 'Samples', 'group-label'));
    for (const doc of docs) {
      const key = sourceKey(doc);
      const row = element('div', null, 'doc');
      const button = element('button', null, 'doc-select');
      button.dataset.key = key; button.title = doc.filename;
      button.setAttribute('aria-label', `Search ${doc.filename}`);
      button.append(element('span', doc.filename.split('.').pop().toUpperCase(), 'file-kind'));
      button.append(element('span', doc.filename, 'file-name'));
      button.onclick = () => { selectSource(key); $('question').focus(); };
      row.append(button);
      if (scope === 'uploads') {
        const remove = element('button', '×', 'remove');
        remove.setAttribute('aria-label', `Remove ${doc.filename}`);
        remove.title = `Remove ${doc.filename}`;
        remove.onclick = () => removeDocument(doc);
        row.append(remove);
      }
      $('docs').append(row);
      $('filter').append(new Option(`${doc.filename}${scope === 'samples' ? ' · sample' : ''}`, key));
    }
  }
  selectSource(sourceList.some(doc => sourceKey(doc) === selected) ? selected : '');
  controls();
}
async function action(fn) {
  if (!ready || busy) return;
  busy = true; controls();
  try { await fn(); } catch (error) { status(error.message, true); }
  finally { busy = false; controls(); }
}
function renderAnswer(result, question) {
  $('result').replaceChildren(element('p', question, 'asked'));
  const answer = result.answer.replace(/ \[1\]$/, '');
  $('result').append(element('p', result.abstained ? 'No answer found in these documents.' : answer, 'answer'));
  answerSources = result.citations.map(c => c.doc_id);
  result.citations.forEach((citation, index) => {
    const details = element('details', null, 'source');
    details.open = citation.used_for_answer;
    details.append(element('summary', `${citation.used_for_answer ? 'Source' : `Related passage ${index + 1}`} · ${citation.filename} · ${citation.location}`));
    const passage = element('pre');
    const offset = citation.used_for_answer ? citation.passage.indexOf(answer) : -1;
    if (offset >= 0) {
      passage.append(document.createTextNode(citation.passage.slice(0, offset)));
      passage.append(element('mark', answer));
      passage.append(document.createTextNode(citation.passage.slice(offset + answer.length)));
    } else passage.textContent = citation.passage;
    details.append(passage);
    if (citation.source_url) {
      const link = element('a', 'Open original ↗');
      link.href = citation.source_url; link.target = '_blank'; link.rel = 'noopener noreferrer';
      details.append(link);
    }
    $('result').append(details);
  });
}
async function ask() {
  const question = $('question').value.trim();
  if (question.length < 3) return;
  const doc = selectedSource();
  await action(async () => {
    status('Reading documents…');
    const result = await api('/api/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question, doc_id: doc?.doc_id, scope: doc?.scope }) });
    renderAnswer(result, question);
    status(result.abstained ? 'Try a more specific question.' : '');
  });
}
async function upload(file) {
  if (!file) return;
  if (!ready || busy) { status('Please wait for the current operation.'); return; }
  if (!/\.(pdf|txt|csv)$/i.test(file.name)) { status('Choose a PDF, text or CSV file.', true); $('file').value = ''; return; }
  if (file.size > 5 * 1024 * 1024) { status('Files must be 5 MB or smaller.', true); $('file').value = ''; return; }
  await action(async () => {
    status(`Adding ${file.name}…`);
    const body = new FormData(); body.append('file', file);
    const result = await api('/api/ingest', { method: 'POST', body });
    await documents(); selectSource(`uploads:${result.doc_id}`);
    status(result.duplicate ? `${result.filename} is already uploaded.` : `Added ${result.filename}.`);
    $('question').focus();
  });
  $('file').value = '';
}
async function removeDocument(doc) {
  await action(async () => {
    status(`Removing ${doc.filename}…`);
    await api(`/api/uploads/${doc.doc_id}`, { method: 'DELETE' });
    if (answerSources.includes(doc.doc_id)) { $('result').replaceChildren(); answerSources = []; }
    await documents(); status(`Removed ${doc.filename}.`);
  });
}
async function connect() {
  ready = false; controls(); $('retry').hidden = true;
  $('connection').textContent = 'Starting…'; $('connection').dataset.ready = 'false';
  status('Connecting…');
  const hint = setTimeout(() => status('Starting the server. This can take a minute.'), 8000);
  try {
    for (let attempt = 0; attempt < 30; attempt++) {
      try { await api('/ready'); await documents(); ready = true; controls(); $('connection').textContent = 'Ready'; $('connection').dataset.ready = 'true'; status(); return; }
      catch (error) {
        if (error.status !== 503 && error.status !== 429) throw error;
        await new Promise(resolve => setTimeout(resolve, 2500));
      }
    }
    throw new Error('The server is still starting. Please retry shortly.');
  } catch (error) { status(error.message, true); $('connection').textContent = 'Offline'; $('retry').hidden = false; }
  finally { clearTimeout(hint); }
}
$('question-form').onsubmit = event => { event.preventDefault(); ask(); };
$('question').oninput = controls;
$('question').onkeydown = event => { if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) { event.preventDefault(); ask(); } };
$('filter').onchange = () => selectSource($('filter').value);
$('upload').onclick = () => $('file').click();
$('file').onchange = event => upload(event.target.files[0]);
$('retry').onclick = connect;
$('toggle-sources').onclick = () => { const expanded = document.body.classList.toggle('show-sources'); $('toggle-sources').setAttribute('aria-expanded', String(expanded)); };
document.querySelectorAll('[data-example]').forEach(button => button.onclick = () => {
  const [question, filename] = examples[button.dataset.example];
  const doc = sourceList.find(doc => doc.scope === 'samples' && doc.filename === filename);
  $('question').value = question; selectSource(doc ? sourceKey(doc) : ''); controls(); $('question').focus();
});
window.addEventListener('dragover', event => { if ([...event.dataTransfer.types].includes('Files')) event.preventDefault(); });
window.addEventListener('drop', event => {
  if (![...event.dataTransfer.types].includes('Files') || event.defaultPrevented) return;
  event.preventDefault();
  if (event.dataTransfer.files.length > 1) { status('Upload one document at a time.', true); return; }
  upload(event.dataTransfer.files[0]);
});
for (const name of ['dragenter', 'dragover']) $('drop').addEventListener(name, event => { event.preventDefault(); $('drop').classList.add('drag'); });
$('drop').ondragleave = () => $('drop').classList.remove('drag');
$('drop').ondrop = event => { event.preventDefault(); $('drop').classList.remove('drag'); if (event.dataTransfer.files.length > 1) { status('Upload one document at a time.', true); return; } upload(event.dataTransfer.files[0]); };
connect();
