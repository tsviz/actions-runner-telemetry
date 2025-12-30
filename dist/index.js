// Node action entry: starts telemetry, marks steps, supports manual stop/snapshot
// No external deps; uses GITHUB_OUTPUT and environment files directly.

const fs = require('fs');
const path = require('path');
const { spawn, spawnSync } = require('child_process');

function appendOutput(name, value) {
  const out = process.env.GITHUB_OUTPUT;
  if (!out) return;
  fs.appendFileSync(out, `${name}=${value}\n`);
}

function log(msg) {
  process.stdout.write(`${msg}\n`);
}

function setEnv(k, v) {
  process.env[k] = v;
}

function getInputEnv(name, def) {
  const v = process.env[`INPUT_${name.toUpperCase()}`];
  return (v === undefined || v === '') ? def : v;
}

function actionPath(...parts) {
  // dist is under the action root; scripts live one level up
  return path.join(__dirname, '..', ...parts);
}

function detectRepoVisibility(explicit) {
  if (explicit === 'public' || explicit === 'private') {
    setEnv('GITHUB_REPOSITORY_VISIBILITY', explicit);
    return explicit;
  }
  const evtPath = process.env.GITHUB_EVENT_PATH;
  if (evtPath && fs.existsSync(evtPath)) {
    try {
      const payload = JSON.parse(fs.readFileSync(evtPath, 'utf8'));
      if (payload?.repository?.private === true) {
        setEnv('GITHUB_REPOSITORY_VISIBILITY', 'private');
        return 'private';
      }
      if (payload?.repository?.private === false) {
        setEnv('GITHUB_REPOSITORY_VISIBILITY', 'public');
        return 'public';
      }
    } catch (_) {}
  }
  // default safe fallback
  setEnv('GITHUB_REPOSITORY_VISIBILITY', 'private');
  return 'private';
}

function startCollector(interval) {
  const pyCmd = findPython();
  if (!pyCmd) {
    log('❌ Python is not available on this runner. Install python3 or python.');
    return;
  }
  const py = actionPath('telemetry_collector.py');
  const logPath = '/tmp/telemetry_collector.log';
  const child = spawn(pyCmd, [py, 'start'], {
    detached: true,
    stdio: ['ignore', fs.openSync(logPath, 'a'), fs.openSync(logPath, 'a')],
  });
  fs.writeFileSync('/tmp/telemetry_collector.pid', String(child.pid));
  child.unref();
  log(`✅ Telemetry collector started (PID: ${child.pid})`);
}

function stopCollectorIfRunning() {
  const pidFile = '/tmp/telemetry_collector.pid';
  if (fs.existsSync(pidFile)) {
    const pid = Number(fs.readFileSync(pidFile, 'utf8'));
    try {
      process.kill(pid, 0);
      log(`Stopping collector (PID: ${pid})...`);
      try { process.kill(pid); } catch (_) {}
    } catch (_) {}
    try { fs.unlinkSync(pidFile); } catch (_) {}
  }
}

function runPy(script, args = []) {
  const py = findPython();
  if (!py) {
    log('❌ Python is not available on this runner. Install python3 or python.');
    return Promise.resolve(1);
  }
  return new Promise((resolve) => {
    const child = spawn(py, [actionPath(script), ...args], { stdio: 'inherit' });
    child.on('exit', (code) => resolve(code));
  });
}

async function main() {
  const enabled = getInputEnv('enabled', 'true');
  const mode = getInputEnv('mode', 'start');
  const interval = getInputEnv('interval', '2');
  const stepName = getInputEnv('step-name', '');
  const repoVis = getInputEnv('repo-visibility', 'auto');

  if (enabled === 'false' || enabled === '0' || enabled === 'no') {
    log('🔍 Runner Telemetry - DISABLED');
    appendOutput('enabled', 'false');
    return;
  }
  appendOutput('enabled', 'true');

  // Set common env for Python scripts
  const workspace = process.env.GITHUB_WORKSPACE || process.cwd();
  try { fs.mkdirSync(workspace, { recursive: true }); } catch (_) {}
  setEnv('TELEMETRY_DATA_FILE', path.join(workspace, '.telemetry_data.json'));
  setEnv('TELEMETRY_INTERVAL', String(interval));
  setEnv('REPO_VISIBILITY', repoVis);
  detectRepoVisibility(repoVis);

  switch (mode) {
    case 'start':
    case 'auto': {
      log('::group::📊 Starting Telemetry Collection');
      log('🔍 Runner Telemetry Action');
      log(`Interval: ${interval}s`);
      startCollector(interval);
      log("ℹ️  Report will be generated automatically at job completion");
      log("ℹ️  Use mode: 'step' with 'step-name' to track per-step resources (optional)");
      log('::endgroup::');
      break;
    }
    case 'step': {
      const name = stepName || `Step at ${new Date().toLocaleTimeString()}`;
      log(`📍 Marking Step: ${name}`);
      await runPy('telemetry_collector.py', ['step', name]);
      break;
    }
    case 'stop': {
      log('::group::📊 Stopping Telemetry & Generating Report');
      stopCollectorIfRunning();
      await runPy('telemetry_collector.py', ['stop']);
      await runPy('generate_report.py');
      const outDir = workspace;
      appendOutput('report-path', path.join(outDir, 'telemetry-report.md'));
      appendOutput('dashboard-path', path.join(outDir, 'telemetry-dashboard.html'));
      appendOutput('data-path', path.join(outDir, 'telemetry-raw.json'));
      appendOutput('csv-path', path.join(outDir, 'telemetry-samples.csv'));
      appendOutput('summary-path', path.join(outDir, 'telemetry-summary.json'));
      log('::endgroup::');
      log('✅ Telemetry report generated');
      try { fs.writeFileSync('/tmp/telemetry_report_done', String(Date.now())); } catch (_) {}
      break;
    }
    case 'snapshot': {
      log('::group::📊 Runner Telemetry Snapshot');
      await runPy('telemetry_collector.py', ['snapshot']);
      await runPy('generate_report.py');
      appendOutput('report-path', path.join(workspace, 'telemetry-report.md'));
      log('::endgroup::');
      break;
    }
    default: {
      log(`❌ Unknown mode: ${mode}`);
      process.exit(1);
    }
  }
}

main().catch((e) => {
  console.error('Telemetry action failed:', e);
  process.exit(1);
});

function findPython() {
  const candidates = ['python3', 'python'];
  for (const cmd of candidates) {
    const res = spawnSync(cmd, ['-V']);
    if (res && res.status === 0) return cmd;
  }
  if (fs.existsSync('/usr/bin/python3')) return '/usr/bin/python3';
  return null;
}
