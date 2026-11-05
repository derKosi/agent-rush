// Node counterpart of import_pass.py: require each newly installed top-level package
// and report what happened. The payload fires here if it waits for first use.
const fs = require('fs');
const path = require('path');

const root = '/work/app/node_modules';
const base = new Set(
  fs.existsSync('/usr/local/share/base_node_modules.txt')
    ? fs.readFileSync('/usr/local/share/base_node_modules.txt', 'utf8').split('\n').filter(Boolean)
    : []
);

let modules = [];
try {
  modules = fs.readdirSync(root).filter((name) => !name.startsWith('.') && name !== 'npm' && !base.has(name));
} catch (err) {
  modules = [];
}

const report = { imports: [] };
for (const name of modules) {
  const entry = { module: name, ok: false };
  try {
    require(path.join(root, name));
    entry.ok = true;
  } catch (err) {
    entry.error = `${err.code || err.name}: ${err.message}`.slice(0, 200);
  }
  report.imports.push(entry);
}
console.log('AR_IMPORT_RESULT ' + JSON.stringify(report));
