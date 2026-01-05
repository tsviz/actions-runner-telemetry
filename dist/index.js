/******/ (() => { // webpackBootstrap
/******/ 	var __webpack_modules__ = ({

/***/ 317:
/***/ ((module) => {

"use strict";
module.exports = require("child_process");

/***/ }),

/***/ 896:
/***/ ((module) => {

"use strict";
module.exports = require("fs");

/***/ }),

/***/ 857:
/***/ ((module) => {

"use strict";
module.exports = require("os");

/***/ }),

/***/ 928:
/***/ ((module) => {

"use strict";
module.exports = require("path");

/***/ })

/******/ 	});
/************************************************************************/
/******/ 	// The module cache
/******/ 	var __webpack_module_cache__ = {};
/******/ 	
/******/ 	// The require function
/******/ 	function __nccwpck_require__(moduleId) {
/******/ 		// Check if module is in cache
/******/ 		var cachedModule = __webpack_module_cache__[moduleId];
/******/ 		if (cachedModule !== undefined) {
/******/ 			return cachedModule.exports;
/******/ 		}
/******/ 		// Create a new module (and put it into the cache)
/******/ 		var module = __webpack_module_cache__[moduleId] = {
/******/ 			// no module.id needed
/******/ 			// no module.loaded needed
/******/ 			exports: {}
/******/ 		};
/******/ 	
/******/ 		// Execute the module function
/******/ 		var threw = true;
/******/ 		try {
/******/ 			__webpack_modules__[moduleId](module, module.exports, __nccwpck_require__);
/******/ 			threw = false;
/******/ 		} finally {
/******/ 			if(threw) delete __webpack_module_cache__[moduleId];
/******/ 		}
/******/ 	
/******/ 		// Return the exports of the module
/******/ 		return module.exports;
/******/ 	}
/******/ 	
/************************************************************************/
/******/ 	/* webpack/runtime/compat */
/******/ 	
/******/ 	if (typeof __nccwpck_require__ !== 'undefined') __nccwpck_require__.ab = __dirname + "/";
/******/ 	
/************************************************************************/
var __webpack_exports__ = {};
// Node action entry: starts telemetry, marks steps, supports manual stop/snapshot
// No external deps; uses GITHUB_OUTPUT and environment files directly.

const fs = __nccwpck_require__(896);
const path = __nccwpck_require__(928);
const os = __nccwpck_require__(857);
const { spawn, spawnSync } = __nccwpck_require__(317);

// Cross-platform temp directory
const TEMP_DIR = os.tmpdir();

function appendOutput(name, value) {
  const out = process.env.GITHUB_OUTPUT;
  if (!out) return;
  fs.appendFileSync(out, `${name}=${value}\n`);
}

function saveState(name, value) {
  const stateFile = process.env.GITHUB_STATE;
  if (!stateFile) return;
  fs.appendFileSync(stateFile, `${name}=${value}\n`);
}

function log(msg) {
  process.stdout.write(`${msg}\n`);
}

function setEnv(k, v) {
  process.env[k] = v;
}

function getInputEnv(name, def) {
  const v = process.env[`INPUT_${name.toUpperCase().replace(/-/g, '_')}`];
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
  const logPath = path.join(TEMP_DIR, 'telemetry_collector.log');
  const pidPath = path.join(TEMP_DIR, 'telemetry_collector.pid');
  
  // Clear any old log file
  try { fs.writeFileSync(logPath, ''); } catch (_) {}
  
  const isWindows = process.platform === 'win32';
  
  let child;
  if (isWindows) {
    // On Windows, spawn Python directly without shell
    // Use environment variables to pass the data file path
    child = spawn(pyCmd, [py, 'start'], {
      detached: true,
      stdio: ['ignore', fs.openSync(logPath, 'a'), fs.openSync(logPath, 'a')],
      windowsHide: true,
    });
  } else {
    child = spawn(pyCmd, [py, 'start'], {
      detached: true,
      stdio: ['ignore', fs.openSync(logPath, 'a'), fs.openSync(logPath, 'a')],
    });
  }
  
  fs.writeFileSync(pidPath, String(child.pid));
  child.unref();
  log(`✅ Telemetry collector started (PID: ${child.pid})`);
  log(`   Log file: ${logPath}`);
}

function showCollectorLog() {
  const logPath = path.join(TEMP_DIR, 'telemetry_collector.log');
  if (fs.existsSync(logPath)) {
    const content = fs.readFileSync(logPath, 'utf8');
    if (content.trim()) {
      log('📋 Collector log:');
      log(content);
    } else {
      log('📋 Collector log is empty (collector may have crashed immediately)');
    }
  } else {
    log('📋 No collector log file found');
  }
}

function stopCollectorIfRunning() {
  const pidFile = path.join(TEMP_DIR, 'telemetry_collector.pid');
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
  const uploadArtifacts = getInputEnv('upload-artifacts', 'false');
  const artifactName = getInputEnv('artifact-name', 'runner-telemetry');

  // Save inputs to state for post action
  log(`📋 Saving state: upload-artifacts=${uploadArtifacts}, artifact-name=${artifactName}`);
  saveState('upload-artifacts', uploadArtifacts);
  saveState('artifact-name', artifactName);

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
      // Check if data file exists before running stop
      const dataFile = path.join(workspace, '.telemetry_data.json');
      if (!fs.existsSync(dataFile)) {
        log('⚠️  No telemetry data file found - showing collector log for debugging:');
        showCollectorLog();
      } else {
        // Check if there are 0 samples - also show log for debugging
        try {
          const data = JSON.parse(fs.readFileSync(dataFile, 'utf-8'));
          if (!data.samples || data.samples.length === 0) {
            log('⚠️  Data file exists but has 0 samples - showing collector log for debugging:');
            showCollectorLog();
          }
        } catch (_) {}
      }
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
      // Scope lock to this run/workspace to avoid stale locks on self-hosted runners
      try { fs.writeFileSync(path.join(workspace, '.telemetry_report_done'), String(Date.now())); } catch (_) {}
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

module.exports = __webpack_exports__;
/******/ })()
;