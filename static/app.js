// Lead Radar dashboard. All scraped content is untrusted: it is only ever inserted via textContent.
const $ = (s) => document.querySelector(s);
const SRC = { linkedin: 'LinkedIn', reddit: 'Reddit', hackernews: 'Hacker News', web: 'Web' };
const state = { searches: [], current: null, leads: [], cfg: { sources: {} }, maxId: 0 };

function h(tag, props = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === 'class') el.className = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) el.setAttribute(k, v === true ? '' : v);
  }
  for (const k of kids.flat()) if (k != null && k !== false) el.append(k.nodeType ? k : document.createTextNode(k));
  return el;
}
const safeUrl = (u) => (/^https?:\/\//i.test(u || '') ? u : null);

async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...opts });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.status === 204 ? null : r.json();
}

function ago(iso) {
  if (!iso) return '—';
  const s = Math.max(0, (Date.now() - new Date(iso)) / 1000);
  if (s < 90) return 'just now';
  if (s < 3600) return Math.round(s / 60) + ' min ago';
  if (s < 86400) return Math.round(s / 3600) + ' h ago';
  return Math.round(s / 86400) + ' d ago';
}
function toast(msg) {
  const t = $('#toast'); t.textContent = msg; t.hidden = false;
  clearTimeout(toast.t); toast.t = setTimeout(() => (t.hidden = true), 2400);
}

/* ---------- sidebar ---------- */
function renderSearches() {
  const nav = $('#searches'); nav.replaceChildren();
  const item = (id, name, meta, n) => h('button', {
    class: 's-item', 'aria-current': String(state.current === id),
    onclick: () => { state.current = id; refresh(true); },
  }, h('div', { class: 's-row' }, h('span', {}, name), n ? h('span', { class: 'badge' }, String(n)) : null),
     h('div', { class: 's-meta' }, meta));
  const total = state.searches.reduce((a, s) => a + s.new_count, 0);
  nav.append(item(null, 'All searches', `${state.searches.length} active`, total));
  for (const s of state.searches) {
    nav.append(item(s.id, s.name, s.is_demo ? 'Sample data' : `Scanned ${ago(s.last_run_at)}`, s.new_count));
  }
  const on = Object.entries(state.cfg.sources).filter(([, v]) => v).map(([k]) => SRC[k]);
  $('#sourceStatus').textContent = `Sources on: ${on.join(', ') || 'none'} · AI scoring ${state.cfg.ai ? 'on' : 'off'}`;
}

/* ---------- header, stats, banner ---------- */
function renderHeader() {
  const s = state.searches.find((x) => x.id === state.current);
  $('#title').textContent = s ? s.name : 'All leads';
  $('#subtitle').textContent = s
    ? `“${s.query}” · ${(s.sources || []).map((x) => SRC[x]).join(', ')}${s.last_error ? ' · ⚠ ' + s.last_error : ''}`
    : 'Every buying signal across your searches, newest first.';
  $('#runBtn').hidden = !s || s.is_demo;
  $('#csvBtn').href = '/api/leads.csv' + (s ? `?search_id=${s.id}` : '');

  const banner = $('#banner'); banner.replaceChildren();
  const hasDemo = state.searches.some((x) => x.is_demo);
  banner.hidden = !hasDemo;
  if (hasDemo) {
    banner.append(
      h('span', {}, 'You’re looking at sample leads. Create a search to start finding real ones.'),
      h('span', { style: 'display:flex;gap:8px' },
        h('button', { class: 'btn btn-accent btn-sm', onclick: openDlg }, 'Create search'),
        h('button', { class: 'btn btn-ghost btn-sm', onclick: async () => { await api('/api/demo', { method: 'DELETE' }); state.current = null; refresh(true); } }, 'Clear samples')));
  }
}
function renderStats() {
  const L = state.leads, day = Date.now() - 864e5;
  const stat = (n, l) => h('div', { class: 'stat' }, h('b', {}, String(n)), h('span', { class: 'label' }, l));
  $('#stats').replaceChildren(
    stat(L.length, 'Leads shown'),
    stat(L.filter((l) => l.status === 'new').length, 'New'),
    stat(L.filter((l) => l.score >= 80).length, 'Hot (80+)'),
    stat(L.filter((l) => new Date(l.found_at) > day).length, 'Found in 24 h'));
}

/* ---------- feed ---------- */
async function setStatus(l, status) {
  await api(`/api/leads/${l.id}`, { method: 'PATCH', body: JSON.stringify({ status }) });
  refresh(false);
}
function card(l) {
  const url = safeUrl(l.url), aurl = safeUrl(l.author_url);
  const text = h('p', { class: 'c-text' }, l.text);
  const hot = l.score >= 80;
  const el = h('article', { class: `card ${l.status === 'new' ? 'is-new' : ''} ${l.status === 'dismissed' ? 'is-dismissed' : ''}` },
    h('div', {},
      h('div', { class: 'c-meta small' },
        h('span', { class: 'label src' }, SRC[l.source] || l.source),
        l.is_demo ? h('span', { class: 'label sample' }, 'Sample') : null,
        h('span', {}, `Posted ${ago(l.posted_at)}`), h('span', {}, '·'),
        h('span', {}, `Found ${ago(l.found_at)}`),
        state.current ? null : h('span', {}, '· ' + l.search_name)),
      h('h3', { class: 'c-title' }, l.title || '(no title)'),
      l.text ? text : null,
      l.text && l.text.length > 220 ? h('button', { class: 'btn btn-sm', style: 'padding-left:0;color:#3355FF', onclick: (e) => { text.classList.toggle('open'); e.target.textContent = text.classList.contains('open') ? 'Show less' : 'Read more'; } }, 'Read more') : null,
      l.reason ? h('p', { class: 'c-why small' }, 'Why it’s a lead: ' + l.reason) : null,
      h('p', { class: 'c-by small' }, 'Posted by ',
        aurl ? h('a', { href: aurl, target: '_blank', rel: 'noopener noreferrer' }, l.author || 'profile') : h('b', {}, l.author || 'Unknown'))),
    h('div', { class: 'score' }, h('b', {}, String(l.score)), h('div', { class: `bar ${hot ? 'hot' : ''}` }, h('i', { style: `width:${l.score}%` }))),
    l.suggested_reply ? h('div', { class: 'reply' }, h('span', { class: 'label muted' }, 'Suggested reply'), h('p', {}, l.suggested_reply),
      h('button', { class: 'btn btn-ghost btn-sm', onclick: () => navigator.clipboard.writeText(l.suggested_reply).then(() => toast('Reply copied')) }, 'Copy reply')) : null,
    h('div', { class: 'c-actions' },
      url ? h('a', { class: 'btn btn-accent btn-sm', href: url, target: '_blank', rel: 'noopener noreferrer' }, 'Open post') : null,
      l.status !== 'saved' ? h('button', { class: 'btn btn-ghost btn-sm', onclick: () => setStatus(l, 'saved') }, 'Save') : null,
      l.status !== 'contacted' ? h('button', { class: 'btn btn-ghost btn-sm', onclick: () => setStatus(l, 'contacted') }, 'Mark contacted') : null,
      l.status !== 'dismissed' ? h('button', { class: 'btn btn-ghost btn-sm', onclick: () => setStatus(l, 'dismissed') }, 'Dismiss')
                               : h('button', { class: 'btn btn-ghost btn-sm', onclick: () => setStatus(l, 'new') }, 'Restore')));
  return el;
}
function renderFeed() {
  const feed = $('#feed'); feed.replaceChildren();
  if (!state.leads.length) {
    feed.append(h('div', { class: 'empty' }, h('h3', {}, 'No leads match yet'),
      h('p', { class: 'muted' }, 'New searches scan within a minute, then every ' + (state.cfg.poll_minutes || 15) + ' minutes. Try lowering the score filter.')));
    return;
  }
  feed.append(...state.leads.map(card));
}

/* ---------- data ---------- */
async function refresh(full) {
  try {
    const [cfg, searches] = await Promise.all([api('/api/config'), api('/api/searches')]);
    state.cfg = cfg; state.searches = searches;
    const p = new URLSearchParams();
    if (state.current) p.set('search_id', state.current);
    if ($('#source').value) p.set('source', $('#source').value);
    if ($('#minScore').value !== '0') p.set('min_score', $('#minScore').value);
    if ($('#status').value) p.set('status', $('#status').value);
    if ($('#q').value.trim()) p.set('q', $('#q').value.trim());
    const leads = await api('/api/leads?' + p);
    const fresh = leads.filter((l) => l.id > state.maxId && l.status === 'new').length;
    if (!full && state.maxId && fresh) toast(`${fresh} new lead${fresh > 1 ? 's' : ''}`);
    state.maxId = Math.max(state.maxId, ...leads.map((l) => l.id), 0);
    state.leads = leads;
    renderSearches(); renderHeader(); renderStats(); renderFeed();
    $('#liveText').textContent = 'Live · updated ' + new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch (e) { $('#liveText').textContent = 'Offline — retrying'; }
}

/* ---------- new search dialog ---------- */
const NEEDS = { reddit: 'Needs Reddit API keys', linkedin: 'Needs SERPER_API_KEY', web: 'Needs SERPER_API_KEY' };
function openDlg() {
  const box = $('#srcBoxes'); box.replaceChildren();
  for (const [k, label] of Object.entries(SRC)) {
    const on = state.cfg.sources[k];
    box.append(h('label', { class: on ? '' : 'off' },
      h('input', { type: 'checkbox', name: 'src', value: k, checked: on && (k === 'hackernews' || k === 'linkedin' || k === 'reddit'), disabled: !on }),
      h('span', {}, label, on ? null : h('small', {}, NEEDS[k]))));
  }
  $('#dlg').showModal();
}
$('#form').addEventListener('submit', async (e) => {
  if (e.submitter && e.submitter.value === 'cancel') return;
  const f = new FormData(e.target);
  const sources = f.getAll('src');
  if (!sources.length) { e.preventDefault(); toast('Pick at least one source'); return; }
  try {
    const s = await api('/api/searches', { method: 'POST', body: JSON.stringify({
      name: f.get('name'), query: f.get('query'), offering: f.get('offering'), sources }) });
    state.current = s.id; toast('Search created — scanning now'); e.target.reset();
    setTimeout(() => refresh(true), 1500); refresh(true);
  } catch (err) { toast(err.message); }
});

$('#newBtn').onclick = openDlg;
$('#runBtn').onclick = async () => {
  if (!state.current) return;
  await api(`/api/searches/${state.current}/run`, { method: 'POST' });
  toast('Scan started'); setTimeout(() => refresh(false), 4000);
};
for (const id of ['source', 'minScore', 'status']) $('#' + id).addEventListener('change', () => refresh(true));
let qt; $('#q').addEventListener('input', () => { clearTimeout(qt); qt = setTimeout(() => refresh(true), 300); });

refresh(true);
setInterval(() => refresh(false), 20000);
