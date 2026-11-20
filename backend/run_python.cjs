// Prefer this project's interpreter, avoiding Windows Store Python aliases.
const { spawn } = require('node:child_process');
const { existsSync } = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const interpreter = path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
if (!existsSync(interpreter)) {
  console.error('Create .venv and install requirements.txt first. See README.md.');
  process.exit(1);
}
const child = spawn(interpreter, process.argv.slice(2), { cwd: root, stdio: 'inherit' });
child.on('error', error => { console.error(error.message); process.exit(1); });
child.on('exit', code => process.exit(code ?? 1));
