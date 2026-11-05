// One page, one run. The sidebar is the list; the main area is the document.
const $ = (id) => document.getElementById(id);
const el = (tag, cls, text) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
};

let DEP_THRESHOLD = 7;
let currentId = null;
let pollTimer = null;

const RISK_CLASS = (risk) => (risk === 'high' ? 'high' : risk === 'medium' ? 'medium' : risk === 'low' ? 'low' : '');
const modelLabel = (run) => run.model || (run.verdict || {}).model || ((run.verdict || {}).model_used ? 'model' : 'rules only');
const shortPkg = (path) => String(path || '—').split('/').pop();

async function getJSON(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

/* ---------------- sidebar ---------------- */
async function loadRuns() {
  const list = $('run-list');
  try {
    const { runs } = await getJSON('runs?limit=24');
    list.innerHTML = '';
    if (!runs.length) {
      list.appendChild(el('li', 'empty', 'no runs yet'));
      return;
    }
    for (const run of runs) {
      const li = el('li');
      if (run.id === currentId) li.classList.add('active');
      const dot = el('span', 'dot ' + RISK_CLASS((run.verdict || {}).risk));
      const name = el('span', 'name', shortPkg((run.task || {}).package));
      const time = el('span', 'time', (run.created || '').slice(11, 19) + ' · ' + ((run.verdict || {}).risk || run.state));
      li.append(dot, name, time);
      li.addEventListener('click', () => selectRun(run.id));
      list.appendChild(li);
    }
  } catch (err) {
    list.innerHTML = '';
    list.appendChild(el('li', 'empty', 'history unavailable'));
  }
}

/* ---------------- run view ---------------- */
function renderHead(run) {
  const risk = (run.verdict || {}).risk;
  const badge = $('risk-badge');
  badge.textContent = risk || run.state || '—';
  badge.className = 'badge ' + RISK_CLASS(risk);

  $('pkg-name').textContent = shortPkg((run.task || {}).package);
  const dur = ((run.evidence || {}).sandbox || {}).duration_s;
  $('run-meta').textContent = [modelLabel(run), dur ? `${dur}s` : null, run.created ? run.created.replace('T', ' ').replace('Z', '') : null]
    .filter(Boolean).join('  ·  ');
  $('run-question').textContent = (run.task || {}).question || '';
}

function renderSummary(run) {
  const pane = $('pane-summary');
  const v = run.verdict || {};
  pane.innerHTML = '';

  if (v.summary) pane.appendChild(el('p', 'summary-text', v.summary));

  const findings = v.findings || [];
  const serious = findings.filter((f) => f.severity === 'high' || f.severity === 'medium');
  const minor = findings.filter((f) => f.severity !== 'high' && f.severity !== 'medium');

  const list = (items) => {
    const ul = el('ul', 'findings');
    for (const f of items) {
      const li = el('li', f.severity || 'info');
      li.appendChild(el('span', 'sev', f.severity || 'info'));
      li.appendChild(el('span', 'claim', f.claim || ''));
      li.appendChild(el('span', 'src', ` — ${f.source || ''}`));
      ul.appendChild(li);
    }
    return ul;
  };

  if (serious.length) {
    pane.appendChild(el('div', 'section-label', `Findings · ${serious.length}`));
    pane.appendChild(list(serious));
  } else {
    pane.appendChild(el('div', 'section-label', 'Findings'));
    pane.appendChild(el('p', 'note', 'Nothing at medium or above. The run produced evidence, not concerns.'));
  }

  // Info-level notes are context, not findings. Folded away by default.
  if (minor.length) {
    const details = el('details', 'fold');
    details.appendChild(el('summary', '', `${minor.length} informational note(s)`));
    details.appendChild(list(minor));
    pane.appendChild(details);
  }

  const rejected = v.rejected_claims || [];
  if (rejected.length) {
    pane.appendChild(el('div', 'section-label', `Veto · ${rejected.length} claim(s) dropped`));
    const ul = el('ul', 'findings');
    for (const r of rejected) {
      const li = el('li', 'high');
      li.appendChild(el('span', 'sev', 'rejected'));
      li.appendChild(el('span', 'claim', `“${r.claim}” — cited ${r.source}, which is not in this run`));
      ul.appendChild(li);
    }
    pane.appendChild(ul);
  }

  const notes = v.notes || [];
  if (notes.length) pane.appendChild(el('p', 'note', notes.join(' · ')));
}

function parseArtifact(file) {
  const m = /^(.+?)-(\d[^-]*)/.exec(file || '');
  return m ? { name: m[1], version: m[2] } : { name: file || '—', version: '' };
}

function renderDeps(run) {
  const pane = $('pane-deps');
  const dep = (run.evidence || {}).dependencies || {};
  const resolved = dep.resolved || [];
  const declared = dep.declared || [];
  pane.innerHTML = '';

  if (!resolved.length && !declared.length) {
    pane.appendChild(el('p', 'note', 'This package declares no dependencies.'));
    return;
  }

  const vulns = dep.vulnerabilities || [];
  const outdated = dep.outdated || [];
  const scores = vulns.map((v) => v.max_score).filter((n) => typeof n === 'number');
  const worst = scores.length ? Math.max(...scores) : 0;

  if (resolved.length) {
    const row = el('div', 'gauge-row');
    const gauge = el('div', 'gauge');
    gauge.append(el('div', 'zone green'), el('div', 'zone amber'), el('div', 'zone red'), el('div', 'threshold'));
    const mark = el('div', 'mark');
    mark.style.left = `${Math.min(100, worst * 10)}%`;
    gauge.appendChild(mark);

    const caption = el('div', 'gauge-caption');
    caption.innerHTML = `worst advisory <strong>${worst ? worst.toFixed(1) : '—'}</strong> / 10 · block from ${DEP_THRESHOLD}`;
    row.append(gauge, caption);
    pane.appendChild(row);

    const table = el('table', 'deps');
    const thead = el('thead');
    const hr = el('tr');
    ['Package', 'Version', 'sha256', 'Advisories', 'State'].forEach((h) => hr.appendChild(el('th', '', h)));
    thead.appendChild(hr);
    table.appendChild(thead);

    const tbody = el('tbody');
    for (const item of resolved) {
      const { name, version } = parseArtifact(item.file);
      const vuln = vulns.find((v) => v.package === name);
      const behind = outdated.find((o) => o.package === name);
      const tr = el('tr');

      tr.appendChild(el('td', 'mono', name));
      tr.appendChild(el('td', 'mono', version + (behind ? ` → ${behind.latest}` : '')));

      const hash = el('td', 'mono muted', (item.sha256 || '').slice(0, 12) + '…');
      hash.title = item.sha256 || '';
      tr.appendChild(hash);

      const adv = el('td');
      if (vuln && vuln.count) {
        const pill = el('span', 'pill ' + (vuln.max_score >= DEP_THRESHOLD ? 'bad' : 'warn'), `${vuln.count} · ${vuln.max_score ?? '?'}`);
        pill.title = (vuln.vulns || []).map((v) => `${v.id} ${v.severity}`).join('\n');
        adv.appendChild(pill);
      } else {
        adv.appendChild(el('span', 'pill good', 'none'));
      }
      tr.appendChild(adv);

      const state = el('td');
      if (vuln && vuln.count && vuln.max_score >= DEP_THRESHOLD) state.appendChild(el('span', 'pill bad', 'blocked'));
      else if (behind) state.appendChild(el('span', 'pill warn', 'behind'));
      else state.appendChild(el('span', 'pill good', 'ok'));
      tr.appendChild(state);

      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    pane.appendChild(table);
  } else {
    pane.appendChild(el('p', 'note', `Declared: ${declared.join(', ')} — nothing could be fetched.`));
  }

  const note = vulns.length
    ? 'Wheels are fetched and hashed, never installed. Scores come from the advisory label, or a coarse reading of its impact metrics.'
    : 'Hashes are recorded for every artifact; no known advisories for this tree.';
  pane.appendChild(el('p', 'note', note));
}

function renderEvidence(run) {
  const pane = $('pane-evidence');
  const ev = run.evidence || {};
  const plan = run.plan || {};
  pane.innerHTML = '';

  const grid = el('div', 'ev-grid');

  const left = el('div');
  left.appendChild(el('div', 'section-label', 'Plan'));
  const chips = el('div', 'chips');
  (plan.probes || []).forEach((p) => chips.appendChild(el('span', 'chip', p)));
  if (!(plan.probes || []).length) chips.appendChild(el('span', 'chip', 'none'));
  left.appendChild(chips);
  if (plan.reason) left.appendChild(el('p', 'note', plan.reason));

  left.appendChild(el('div', 'section-label', 'Artifacts'));
  const ul = el('ul', 'ev-list');
  const names = Object.keys(ev.artifacts || {}).sort();
  if (!names.length) ul.appendChild(el('li', 'empty', 'none'));
  for (const name of names) {
    const li = el('li');
    const a = el('a', '', name);
    a.href = `runs/${run.id}/artifacts/${encodeURIComponent(name)}`;
    li.appendChild(a);
    li.appendChild(el('span', 'muted', `  ${(ev.artifacts[name] || {}).bytes} B`));
    ul.appendChild(li);
  }
  left.appendChild(ul);

  const eg = ev.egress || {};
  left.appendChild(el('div', 'section-label', 'Egress'));
  left.appendChild(el('p', 'note', eg.collected
    ? `${eg.denied} denied, ${eg.allowed} allowed${(eg.denied_hosts || []).length ? ` — blocked: ${eg.denied_hosts.join(', ')}` : ''}`
    : 'no proxy log for this run'));

  const right = el('div');
  right.appendChild(el('div', 'section-label', 'Timeline'));
  const ol = el('ol', 'trace');
  const events = [];
  if (run.created) events.push([run.created, 'accepted', '']);
  if ((run.plan || {}).source) events.push([null, `planned by ${plan.source}`, 'ok']);
  (run.attempts || []).forEach((a) => events.push([null, `attempt ${a.attempt} · ${a.timeout_s}s budget`, a.diagnosis ? 'warn' : '']));
  if (run.finished) events.push([run.finished, `finished · ${run.state}`, run.state === 'done' ? 'ok' : 'deny']);
  for (const [ts, text, kind] of events) {
    const li = el('li', kind, `${ts ? ts.slice(11, 19) + '  ' : ''}${text}`);
    ol.appendChild(li);
  }
  right.appendChild(ol);

  grid.append(left, right);
  pane.appendChild(grid);
}

async function selectRun(id) {
  currentId = id;
  // Keep the URL in sync so a run stays linkable and reload-safe.
  const url = new URL(location.href);
  url.searchParams.set('run', id);
  history.replaceState(null, '', url);
  clearInterval(pollTimer);
  try {
    const run = await getJSON(`runs/${id}`);
    $('placeholder').hidden = true;
    $('runview').hidden = false;
    renderHead(run);
    renderSummary(run);
    renderDeps(run);
    renderEvidence(run);
    loadRuns();
    if (run.state === 'running' || run.state === 'queued') {
      pollTimer = setInterval(() => selectRun(id), 2000);
    }
  } catch (err) {
    $('placeholder').hidden = false;
    $('placeholder').querySelector('h1').textContent = 'Run not found';
  }
}

/* ---------------- tabs ---------------- */
function showTab(name) {
  const target = document.querySelector(`.tab[data-tab="${name}"]`);
  if (!target) return;
  for (const tab of document.querySelectorAll('.tab')) tab.classList.toggle('active', tab === target);
  for (const pane of ['summary', 'deps', 'evidence']) {
    $(`pane-${pane}`).hidden = pane !== name;
  }
}

$('tabs').addEventListener('click', (event) => {
  const button = event.target.closest('.tab');
  if (button) showTab(button.dataset.tab);
});

// ?tab=deps makes a specific view linkable -- useful in a review or a recording.
const wantTab = new URLSearchParams(location.search).get('tab');
if (wantTab) showTab(wantTab);

/* ---------------- new run ---------------- */
const dialog = $('newrun');
$('new-run').addEventListener('click', () => { $('form-note').textContent = ''; dialog.showModal(); });
$('cancel').addEventListener('click', () => dialog.close());

$('run-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = $('submit-run');
  button.disabled = true;
  $('form-note').textContent = 'submitting…';
  try {
    const res = await fetch('tasks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        package: $('pkg').value.trim(),
        question: $('q').value,
        egress_mode: $('proxy').checked ? 'proxy' : 'none',
      }),
    });
    if (!res.ok) throw new Error((await res.text()).slice(0, 160));
    const { id } = await res.json();
    dialog.close();
    await selectRun(id);
  } catch (err) {
    $('form-note').textContent = String(err.message || err);
  } finally {
    button.disabled = false;
  }
});

/* ---------------- theme + boot ---------------- */
function setTheme(next) {
  document.documentElement.dataset.theme = next;
  const toggle = $('theme-toggle');
  if (toggle) toggle.textContent = next === 'light' ? '☀' : '☾';
  try { localStorage.setItem('ar-theme', next); } catch (e) {}
}
$('theme-toggle').addEventListener('click', () => {
  setTheme(document.documentElement.dataset.theme === 'light' ? 'dark' : 'light');
});
setTheme(document.documentElement.dataset.theme || 'dark');

getJSON('health').then((h) => {
  if (typeof h.dep_threshold === 'number') DEP_THRESHOLD = h.dep_threshold;
  $('model-chip').textContent = h.model_configured
    ? `${h.model} · reasoning ${h.reasoning}`
    : 'rules only';
}).catch(() => { $('model-chip').textContent = 'offline'; });

loadRuns().then(() => {
  const wanted = new URLSearchParams(location.search).get('run');
  if (wanted) { selectRun(wanted); return; }
  const first = document.querySelector('#run-list li:not(.empty)');
  if (first) first.click();
});
