// Wires the shell to the API. No framework: the whole product is three endpoints,
// and a build step would cost more than it explains.
const $ = (id) => document.getElementById(id);
let timer = null;

function setStatus(text, kind) {
  const el = $('status');
  // Defensive on purpose: a missing element must never take the rest of the page down
  // with it. That is exactly what happened when the top bar was redesigned.
  if (!el) return;
  el.textContent = text;
  el.className = 'status' + (kind ? ' ' + kind : '');
}

function trace(message, kind) {
  const list = $('trace-list');
  const empty = list.querySelector('.empty');
  if (empty) empty.remove();
  const li = document.createElement('li');
  const t = new Date().toISOString().slice(11, 19);
  li.className = kind || '';
  li.textContent = `${t}  ${message}`;
  list.appendChild(li);
  list.scrollTop = list.scrollHeight;   // scroll the list, never the page
}

function renderPlan(plan) {
  $('plan-source').textContent = plan.source === 'model' ? 'model' : 'default';
  const chips = $('probes');
  chips.innerHTML = '';
  (plan.probes || []).forEach((p) => {
    const s = document.createElement('span');
    s.className = 'chip';
    s.textContent = p;
    chips.appendChild(s);
  });
  if ((plan.rejected || []).length) {
    const s = document.createElement('span');
    s.className = 'chip rejected';
    s.textContent = 'rejected: ' + plan.rejected.join(', ');
    chips.appendChild(s);
  }
  $('plan-reason').textContent = plan.reason || '';
}

function modelLabel(run) {
  const v = run.verdict || {};
  const name = run.model || v.model;
  if (name) return name;
  return v.model_used ? 'model' : 'rules only';
}

function renderHero(run) {
  const hero = $('hero');
  const v = run.verdict || {};
  if (!hero || !v.risk) return;
  const level = v.risk;
  hero.hidden = false;
  hero.className = 'hero ' + (level === 'high' ? 'high' : level === 'medium' ? 'medium' : 'low');

  const risk = $('hero-risk');
  risk.textContent = level;
  risk.className = 'badge ' + (level === 'high' ? 'high' : level === 'low' ? 'low' : 'muted');

  $('hero-pkg').textContent = ((run.task || {}).package || '—').split('/').pop();
  $('hero-sub').textContent = (run.task || {}).question || '';
  $('hero-model').textContent = modelLabel(run);
  const dur = ((run.evidence || {}).sandbox || {}).duration_s;
  $('hero-duration').textContent = dur ? `${dur}s` : '';
  $('hero-open').href = `?run=${run.id}`;

  const list = $('hero-findings');
  list.innerHTML = '';
  const findings = (v.findings || []).filter((f) => f.severity === 'high' || f.severity === 'medium').slice(0, 3);
  if (!findings.length) {
    const li = document.createElement('li');
    li.className = 'none';
    li.textContent = 'No high or medium findings. Nothing was blocked, and nothing was observed.';
    list.appendChild(li);
    return;
  }
  for (const f of findings) {
    const li = document.createElement('li');
    li.className = f.severity || 'info';
    const sev = document.createElement('span');
    sev.className = 'sev';
    sev.textContent = f.severity;
    li.appendChild(sev);
    li.appendChild(document.createTextNode(f.claim || ''));
    list.appendChild(li);
  }
}

let DEP_THRESHOLD = 7;

function parseArtifact(file) {
  const match = /^(.+?)-(\d[^-]*)/.exec(file || '');
  return match ? { name: match[1], version: match[2] } : { name: file || '—', version: '' };
}

function renderDependencies(run) {
  const panel = $('deps-panel');
  if (!panel) return;
  const dep = (run.evidence || {}).dependencies || {};
  const resolved = dep.resolved || [];
  const declared = dep.declared || [];
  if (!resolved.length && !declared.length) { panel.hidden = true; return; }

  panel.hidden = false;
  const vulns = dep.vulnerabilities || [];
  const outdated = dep.outdated || [];
  const scores = vulns.map((v) => v.max_score).filter((n) => typeof n === 'number');
  const worst = scores.length ? Math.max(...scores) : 0;

  $('deps-count').textContent = resolved.length ? `${resolved.length} resolved` : 'none resolved';

  const mark = $('deps-mark');
  mark.style.left = `${Math.min(100, worst * 10)}%`;
  const level = worst >= DEP_THRESHOLD ? 'bad' : worst >= 4 ? 'warn' : 'good';
  $('deps-caption').innerHTML =
    `<span class="dot ${level}"></span>worst advisory <strong>${worst ? worst.toFixed(1) : '—'}</strong> / 10` +
    ` &nbsp;·&nbsp; block from ${DEP_THRESHOLD}`;

  const body = $('deps-table').querySelector('tbody');
  body.innerHTML = '';
  for (const item of resolved) {
    const { name, version } = parseArtifact(item.file);
    const vuln = vulns.find((v) => v.package === name) || null;
    const behind = outdated.find((o) => o.package === name) || null;

    const tr = document.createElement('tr');

    const tdName = document.createElement('td');
    tdName.className = 'pkgname';
    tdName.textContent = name;

    const tdVersion = document.createElement('td');
    tdVersion.className = 'mono';
    tdVersion.textContent = version + (behind ? ` → ${behind.latest}` : '');

    const tdHash = document.createElement('td');
    tdHash.className = 'mono';
    tdHash.textContent = (item.sha256 || '').slice(0, 12) + '…';
    tdHash.title = item.sha256 || '';

    const tdAdv = document.createElement('td');
    if (vuln && vuln.count) {
      const pill = document.createElement('span');
      pill.className = 'pill ' + (vuln.max_score >= DEP_THRESHOLD ? 'bad' : 'warn');
      pill.textContent = `${vuln.count} · ${vuln.max_score ?? '?'}`;
      pill.title = (vuln.vulns || []).map((v) => `${v.id} ${v.severity}`).join('\n');
      tdAdv.appendChild(pill);
    } else {
      const pill = document.createElement('span');
      pill.className = 'pill good';
      pill.textContent = 'none';
      tdAdv.appendChild(pill);
    }

    const tdState = document.createElement('td');
    const state = document.createElement('span');
    if (vuln && vuln.count && vuln.max_score >= DEP_THRESHOLD) {
      state.className = 'pill bad'; state.textContent = 'blocked';
    } else if (behind) {
      state.className = 'pill warn'; state.textContent = 'behind';
    } else {
      state.className = 'pill good'; state.textContent = 'ok';
    }
    tdState.appendChild(state);

    tr.append(tdName, tdVersion, tdHash, tdAdv, tdState);
    body.appendChild(tr);
  }

  const note = $('deps-note');
  if (!resolved.length) {
    note.textContent = `Declared: ${declared.join(', ')} — nothing could be fetched, so nothing is known about it.`;
  } else if (!vulns.length) {
    note.textContent = 'Hashes are recorded for every artifact; no known advisories for this tree.';
  } else {
    note.textContent = 'Wheels are fetched and hashed, never installed. Advisories come from OSV; the score is the advisory label, or a coarse reading of its impact metrics.';
  }
}

function renderVerdict(v) {
  const risk = $('risk');
  risk.innerHTML = '';
  const badge = document.createElement('span');
  const level = v.risk || 'unknown';
  badge.className = 'badge ' + (level === 'high' ? 'high' : level === 'low' ? 'low' : 'muted');
  badge.textContent = level;
  risk.appendChild(badge);
  if (v.model_used) {
    const m = document.createElement('span');
    m.className = 'tag';
    m.textContent = 'model';
    risk.appendChild(m);
  }
  $('summary').textContent = v.summary || '';

  const rejected = v.rejected_claims || [];
  const box = $('rejected');
  box.innerHTML = '';
  if (rejected.length) {
    const head = document.createElement('div');
    head.className = 'veto-head';
    head.textContent = `veto: ${rejected.length} model claim(s) dropped`;
    box.appendChild(head);
    for (const r of rejected) {
      const row = document.createElement('div');
      row.className = 'veto-row';
      row.textContent = `“${r.claim}” — cited ${r.source}, which is not in this run`;
      box.appendChild(row);
    }
  } else {
    box.textContent = (v.notes || []).join(' · ');
  }

  // A hostile package that talks to the reader is worth a badge, not a footnote.
  const injected = (v.findings || []).some(
    (f) => (f.source === 'package_source_excerpt' || f.source === 'build_log_tail')
           && /instructions|directive/i.test(f.claim || ''));
  if (injected) {
    const badge = document.createElement('span');
    badge.className = 'tag warn';
    badge.textContent = 'injection detected';
    risk.appendChild(badge);
  }
}

function renderFindings(v) {
  const list = $('findings');
  const items = v.findings || [];
  list.innerHTML = '';
  $('finding-count').textContent = items.length ? `${items.length}` : '';
  if (!items.length) {
    const li = document.createElement('li');
    li.className = 'empty';
    li.textContent = 'no findings';
    list.appendChild(li);
    return;
  }
  for (const f of items) {
    const li = document.createElement('li');
    li.className = 'finding ' + (f.severity || 'info');
    li.innerHTML = `<span class="sev">${f.severity || 'info'}</span>
      <span class="src">${f.source || ''}</span>
      <span class="claim"></span>`;
    li.querySelector('.claim').textContent = f.claim || '';
    list.appendChild(li);
  }
}

function renderEvidence(run) {
  const ev = run.evidence || {};
  const list = $('artifacts');
  list.innerHTML = '';
  const names = Object.keys(ev.artifacts || {}).sort();
  if (!names.length) {
    const li = document.createElement('li');
    li.className = 'empty';
    li.textContent = 'no artifacts';
    list.appendChild(li);
  }
  for (const name of names) {
    const meta = ev.artifacts[name];
    const li = document.createElement('li');
    const a = document.createElement('a');
    a.href = `runs/${run.id}/artifacts/${encodeURIComponent(name)}`;
    a.textContent = name;
    li.appendChild(a);
    const size = document.createElement('span');
    size.className = 'muted';
    size.textContent = `  ${meta.bytes} B`;
    li.appendChild(size);
    list.appendChild(li);
  }
  const eg = ev.egress || {};
  $('egress').textContent = eg.collected
    ? `egress: ${eg.denied} denied, ${eg.allowed} allowed` +
      ((eg.denied_hosts || []).length ? ` — blocked: ${eg.denied_hosts.join(', ')}` : '')
    : 'egress: no proxy log for this run';
}

async function poll(id) {
  const r = await fetch(`runs/${id}`);
  if (!r.ok) throw new Error(`run ${id}: HTTP ${r.status}`);
  const run = await r.json();
  if (run.plan) renderPlan(run.plan);
  if (run.state === 'running' || run.state === 'done' || run.state === 'failed') {
    $('runid').textContent = id;
  }
  if ((run.attempts || []).length > 1) {
    const last = run.attempts[run.attempts.length - 1];
    trace(`retried after ${run.attempts[0].diagnosis.kind}; budget now ${last.timeout_s}s`, 'warn');
  }
  if (run.outcome) trace(`outcome: ${run.outcome}`, 'warn');
  if (run.verdict) {
    renderVerdict(run.verdict);
    renderFindings(run.verdict);
    renderHero(run);
    renderDependencies(run);
  }
  renderEvidence(run);
  setStatus(run.state, run.state === 'done' ? 'ok' : run.state === 'failed' ? 'bad' : 'busy');
  if (run.state === 'done' || run.state === 'failed') {
    clearInterval(timer);
    timer = null;
    $('run').disabled = false;
    if (run.state === 'failed') trace('run failed: ' + (run.error || 'unknown'), 'deny');
    else trace('verdict ready', 'ok');
  }
  return run;
}

async function start() {
  document.body.classList.remove('run-view');
  const pkg = $('pkg').value.trim();
  $('run').disabled = true;
  $('trace-list').innerHTML = '';
  $('findings').innerHTML = '<li class="empty">waiting</li>';
  $('note').textContent = '';
  setStatus('queued', 'busy');
  trace(`POST /tasks ${pkg}`);
  try {
    const res = await fetch('tasks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        package: pkg,
        question: $('q').value,
        egress_mode: $('proxy').checked ? 'proxy' : 'none',
      }),
    });
    if (!res.ok) {
      const body = await res.text();
      throw new Error(`HTTP ${res.status}: ${body.slice(0, 180)}`);
    }
    const { id } = await res.json();
    trace(`run ${id} accepted`, 'ok');
    timer = setInterval(() => poll(id).catch(fail), 700);
    await poll(id);
  } catch (err) {
    fail(err);
  }
}

function fail(err) {
  clearInterval(timer);
  timer = null;
  $('run').disabled = false;
  setStatus('error', 'bad');
  $('note').textContent = String(err.message || err);
  trace('error: ' + (err.message || err), 'deny');
}

$('run').addEventListener('click', start);
// Shareable link to a finished run: /?run=<id>
const linked = new URLSearchParams(location.search).get('run');
if (linked) {
  document.body.classList.add('run-view');
  trace(`loading shared run ${linked}`);
  setStatus('loading', 'busy');
  poll(linked).then((run) => {
    if (run && (run.state === 'running' || run.state === 'queued')) {
      timer = setInterval(() => poll(linked).catch(fail), 2000);
    }
  }).catch(fail);
}

fetch('health').then((r) => r.json()).then((h) => {
  const chip = $('model-chip');
  if (!chip) return;
  if (typeof h.dep_threshold === 'number') DEP_THRESHOLD = h.dep_threshold;
  if (h.model_configured) {
    chip.textContent = `${h.model || 'model'} · reasoning ${h.reasoning || 'off'}`;
    chip.classList.remove('off');
  } else {
    chip.textContent = 'rules only';
    chip.classList.add('off');
    $('note').textContent = 'no model configured: the verdict will be rule-based only';
  }
}).catch(() => {});


// --- history -------------------------------------------------------------------------
// Real runs from the store, not a mock: this is the product's own record of what it did.
function median(values) {
  const clean = values.filter((v) => typeof v === 'number' && v >= 0).sort((a, b) => a - b);
  if (!clean.length) return null;
  const mid = Math.floor(clean.length / 2);
  return clean.length % 2 ? clean[mid] : (clean[mid - 1] + clean[mid]) / 2;
}

function renderStats(runs) {
  const today = new Date().toISOString().slice(0, 10);
  const runsToday = runs.filter((r) => (r.created || '').slice(0, 10) === today).length;
  const blocked = runs.filter((r) => (r.verdict || {}).risk === 'high').length;
  const durations = runs.map((r) => ((r.evidence || {}).sandbox || {}).duration_s);
  const med = median(durations);

  $('stat-runs').textContent = String(runsToday);
  $('stat-blocked').textContent = String(blocked);
  $('stat-duration').textContent = med === null ? '—' : `${Math.round(med)}s`;
}

async function loadHistory() {
  const list = $('history-list');
  try {
    const res = await fetch('runs?limit=50');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const payload = await res.json();
    const all = payload.runs || [];
    const runs = all.slice(0, 8);
    renderStats(all);
    $('history-count').textContent = runs.length ? `${runs.length}` : '';
    list.innerHTML = '';
    if (!runs.length) {
      list.innerHTML = '<li class="empty">no runs yet</li>';
      return;
    }
    for (const run of runs) {
      const li = document.createElement('li');
      li.className = 'run-row';

      const when = document.createElement('span');
      when.className = 'when';
      when.textContent = (run.created || '').replace('T', ' ').replace('Z', '');

      const pkg = document.createElement('span');
      pkg.className = 'pkg';
      pkg.textContent = ((run.task || {}).package || '—').split('/').pop();

      const model = document.createElement('span');
      model.className = 'model';
      model.textContent = modelLabel(run);

      const risk = document.createElement('span');
      const level = (run.verdict || {}).risk || '—';
      risk.className = 'badge ' + (level === 'high' ? 'high' : level === 'low' ? 'low' : 'muted');
      risk.textContent = level;

      const state = document.createElement('span');
      state.className = 'state muted';
      state.textContent = run.state;

      li.append(when, pkg, model, risk, state);
      li.addEventListener('click', () => {
        history.replaceState(null, '', `?run=${run.id}`);
        trace(`loading shared run ${run.id}`);
        poll(run.id).catch(fail);
      });
      list.appendChild(li);
    }
  } catch (err) {
    list.innerHTML = `<li class="empty">history unavailable: ${err.message}</li>`;
  }
}

loadHistory();


// --- theme ---------------------------------------------------------------------------
function setTheme(next) {
  document.documentElement.dataset.theme = next;
  const toggle = $('theme-toggle');
  if (toggle) {
    toggle.textContent = next === 'light' ? '\u2600' : '\u263e';
    toggle.title = next === 'light' ? 'Switch to dark' : 'Switch to light';
  }
  try { localStorage.setItem('ar-theme', next); } catch (e) {}
}

setTheme(document.documentElement.dataset.theme || 'dark');

$('theme-toggle').addEventListener('click', () => {
  const now = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light';
  setTheme(now);
});

$('new-run').addEventListener('click', () => {
  document.body.classList.remove('run-view');
  $('pkg').focus();
  document.getElementById('task').scrollIntoView({ behavior: 'smooth', block: 'center' });
});
