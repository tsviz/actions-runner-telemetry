// Node action post: runs at job end, stops collector if active and generates report

const fs = require('fs');
const path = require('path');
const os = require('os');
const { spawn, spawnSync } = require('child_process');

// Cross-platform temp directory
const TEMP_DIR = os.tmpdir();

function log(msg) { process.stdout.write(`${msg}\n`); }
function setEnv(k, v) { process.env[k] = v; }
function appendOutput(name, value) {
  const out = process.env.GITHUB_OUTPUT;
  if (!out) return;
  fs.appendFileSync(out, `${name}=${value}\n`);
}
function actionPath(...parts) { return path.join(__dirname, '..', ...parts); }

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

function stopCollectorIfRunning() {
  const pidFile = path.join(TEMP_DIR, 'telemetry_collector.pid');
  if (fs.existsSync(pidFile)) {
    const pid = Number(fs.readFileSync(pidFile, 'utf8'));
    try {
      process.kill(pid, 0);
      log(`Stopping telemetry collector (PID: ${pid})...`);
      try { process.kill(pid); } catch (_) {}
    } catch (_) {}
    try { fs.unlinkSync(pidFile); } catch (_) {}
  }
}

(async function post() {
  const enabled = process.env.INPUT_ENABLED ?? 'true';
  if (enabled === 'false' || enabled === '0' || enabled === 'no') {
    log('🔍 Runner Telemetry - Skipping (disabled)');
    return;
  }

  const workspace = process.env.GITHUB_WORKSPACE || process.cwd();
  const dataFile = path.join(workspace, '.telemetry_data.json');
  setEnv('TELEMETRY_DATA_FILE', dataFile);
  setEnv('GITHUB_WORKSPACE', workspace);
  const fallbackDataFile = path.join(TEMP_DIR, 'telemetry_data.json');
  const pidFile = path.join(TEMP_DIR, 'telemetry_collector.pid');

  // If nothing was started, no-op
  if (!fs.existsSync(pidFile) && !fs.existsSync(dataFile)) {
    if (fs.existsSync(fallbackDataFile)) {
      setEnv('TELEMETRY_DATA_FILE', fallbackDataFile);
      log(`🔎 Using fallback data file at ${fallbackDataFile}`);
    } else {
      // As a last resort, take a quick snapshot so the report still renders
      log('🔍 No active collection found; taking a quick snapshot for reporting');
      await runPy('telemetry_collector.py', ['snapshot']);
    }
  }

  // Prevent duplicate generation when action is invoked multiple times
  // Scope lock to this run/workspace to avoid stale locks on self-hosted runners
  const lockFile = path.join(workspace, '.telemetry_report_done');
  if (fs.existsSync(lockFile)) {
    log('🔍 Runner Telemetry - Report already generated (skipping duplicate post)');
    return;
  }

  log('::group::📊 Generating Telemetry Report');
  stopCollectorIfRunning();
  await runPy('telemetry_collector.py', ['stop']);
  await runPy('generate_report.py');
  log('::endgroup::');
  log('✅ Telemetry report generated');

  try { fs.writeFileSync(lockFile, String(Date.now())); } catch (_) {}

  // Expose outputs for downstream steps
  appendOutput('report-path', path.join(workspace, 'telemetry-report.md'));
  appendOutput('dashboard-path', path.join(workspace, 'telemetry-dashboard.html'));
  appendOutput('data-path', path.join(workspace, 'telemetry-raw.json'));
  appendOutput('csv-path', path.join(workspace, 'telemetry-samples.csv'));
  appendOutput('summary-path', path.join(workspace, 'telemetry-summary.json'));
})();

function findPython() {
  const candidates = ['python3', 'python'];
  for (const cmd of candidates) {
    const res = spawnSync(cmd, ['-V']);
    if (res && res.status === 0) return cmd;
  }
  if (fs.existsSync('/usr/bin/python3')) return '/usr/bin/python3';
  return null;
}
