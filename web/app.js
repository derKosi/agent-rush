// Wires the shell to the API. No framework: the whole product is three endpoints,
// and a build step would cost more than it explains.
const $ = (id) => document.getElementById(id);
let timer = null;

function setStatus(text, kind) {
  const el = $('status');
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
  trace(`loading shared run ${linked}`);
  setStatus('loading', 'busy');
  poll(linked).then((run) => {
    if (run && (run.state === 'running' || run.state === 'queued')) {
      timer = setInterval(() => poll(linked).catch(fail), 2000);
    }
  }).catch(fail);
}

fetch('health').then((r) => r.json()).then((h) => {
  if (!h.model_configured) {
    $('note').textContent = 'no model configured: the verdict will be rule-based only';
  }
}).catch(() => {});
