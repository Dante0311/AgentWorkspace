#!/usr/bin/env node
'use strict';

const { spawn } = require('node:child_process');
const { join } = require('node:path');

const child = spawn(join(__dirname, 'runtime', 'python.exe'),
  ['-B', '-u', '-X', 'utf8', '-m', 'agent_workspace', ...process.argv.slice(2)],
  { stdio: 'inherit', windowsHide: true });

// Windows sends console Ctrl+C to both processes. Let Python finish its cleanup.
process.on('SIGINT', () => {});
process.on('SIGTERM', () => child.kill('SIGTERM'));
child.on('error', error => {
  console.error(`Could not start the bundled Agent Workspace runtime: ${error.message}`);
  process.exitCode = 1;
});
child.on('exit', code => { process.exitCode = code ?? 1; });
