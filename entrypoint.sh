#!/bin/bash
set -e

# Configuration
ENABLED="${INPUT_ENABLED:-true}"
MODE="${INPUT_MODE:-auto}"
INTERVAL="${INPUT_INTERVAL:-2}"
STEP_NAME="${INPUT_STEP_NAME:-}"
REPO_VISIBILITY="${INPUT_REPO_VISIBILITY:-auto}"
TELEMETRY_DATA_FILE="${GITHUB_WORKSPACE:-/github/workspace}/.telemetry_data.json"
export TELEMETRY_DATA_FILE
export TELEMETRY_INTERVAL="$INTERVAL"
export REPO_VISIBILITY="$REPO_VISIBILITY"

## Repo visibility detection (public vs private)
# Order: explicit input → event payload → gh CLI → private fallback
if [ "$REPO_VISIBILITY" = "public" ] || [ "$REPO_VISIBILITY" = "private" ]; then
  export GITHUB_REPOSITORY_VISIBILITY="$REPO_VISIBILITY"
  echo "[VISIBILITY DEBUG] Using explicit visibility: $REPO_VISIBILITY"
else
  # Try GitHub event payload (repository.private) first
  if [ -n "$GITHUB_EVENT_PATH" ] && [ -f "$GITHUB_EVENT_PATH" ]; then
    if command -v jq >/dev/null 2>&1; then
      # Explicitly map to strings; treat missing as empty
      IS_PRIVATE=$(jq -r 'if .repository and (.repository.private==true) then "true" elif .repository and (.repository.private==false) then "false" else "" end' "$GITHUB_EVENT_PATH" | tr -d ' \n')
    else
      IS_PRIVATE=$(python3 - <<'PY'
import json, os
path = os.environ.get('GITHUB_EVENT_PATH','')
val = ''
try:
  with open(path,'r') as f:
    data = json.load(f)
    v = data.get('repository',{}).get('private', None)
    if v is True:
      val = 'true'
    elif v is False:
      val = 'false'
except Exception:
  pass
print(val)
PY
      )
      IS_PRIVATE=$(echo "$IS_PRIVATE" | tr -d ' \n')
    fi
    echo "[VISIBILITY DEBUG] Event payload repository.private: '$IS_PRIVATE'"
    if [ "$IS_PRIVATE" = "true" ]; then
      export GITHUB_REPOSITORY_VISIBILITY="private"
    elif [ "$IS_PRIVATE" = "false" ]; then
      export GITHUB_REPOSITORY_VISIBILITY="public"
    fi
  fi

  # If still not set, try gh CLI
  if [ -z "$GITHUB_REPOSITORY_VISIBILITY" ]; then
    if command -v gh >/dev/null 2>&1; then
      DETECTED_VISIBILITY=$(gh repo view --json isPrivate --jq '.isPrivate' 2>/dev/null | tr -d ' \n')
      echo "[VISIBILITY DEBUG] gh isPrivate: '$DETECTED_VISIBILITY'"
      if [ "$DETECTED_VISIBILITY" = "true" ]; then
        export GITHUB_REPOSITORY_VISIBILITY="private"
      elif [ "$DETECTED_VISIBILITY" = "false" ]; then
        export GITHUB_REPOSITORY_VISIBILITY="public"
      fi
    fi
  fi

  # Final fallback
  if [ -z "$GITHUB_REPOSITORY_VISIBILITY" ]; then
    export GITHUB_REPOSITORY_VISIBILITY="private"
    echo "[VISIBILITY DEBUG] Defaulting to private (unable to auto-detect)"
  fi
fi

echo "[VISIBILITY DEBUG] Final GITHUB_REPOSITORY_VISIBILITY=$GITHUB_REPOSITORY_VISIBILITY"

# Check if action is disabled
if [ "$ENABLED" = "false" ] || [ "$ENABLED" = "0" ] || [ "$ENABLED" = "no" ]; then
  echo "🔍 Runner Telemetry - DISABLED"
  echo "   Skipping telemetry collection (enabled=false)"
  echo "::set-output name=enabled::false"
  exit 0
fi

echo "::set-output name=enabled::true"

case "$MODE" in
  auto|start)
    # Auto mode: Start collection, report generates automatically via post-entrypoint
    echo "::group::📊 Starting Telemetry Collection"
    
    # Print initial system info
    echo "🔍 Runner Telemetry Action"
    echo ""
    echo "System Information:"
    echo "  OS: $(uname -s) $(uname -r)"
    echo "  Arch: $(uname -m)"
    echo "  CPUs: $(nproc)"
    echo "  Memory: $(free -h | awk '/^Mem:/ {print $2}')"
    echo "  Interval: ${INTERVAL}s"
    echo ""
    
    # Start collector in background
    echo "Starting background telemetry collector..."
    nohup python3 /telemetry_collector.py start > /tmp/telemetry_collector.log 2>&1 &
    COLLECTOR_PID=$!
    echo "$COLLECTOR_PID" > /tmp/telemetry_collector.pid
    
    echo "✅ Telemetry collector started (PID: $COLLECTOR_PID)"
    echo ""
    if [ "$MODE" = "auto" ]; then
      echo "ℹ️  Report will be generated automatically at job completion"
    fi
    echo "ℹ️  Use mode: 'step' with 'step-name' to track per-step resources (optional)"
    
    echo "::endgroup::"
    ;;
  
  step)
    if [ -z "$STEP_NAME" ]; then
      echo "⚠️  Warning: No step-name provided. Using timestamp."
      STEP_NAME="Step at $(date +%H:%M:%S)"
    fi
    
    echo "📍 Marking Step: $STEP_NAME"
    python3 /telemetry_collector.py step "$STEP_NAME"
    ;;
    
  stop)
    # Legacy mode: Manual stop (for backward compatibility)
    echo "::group::📊 Stopping Telemetry & Generating Report"
    
    # Stop the collector if running
    if [ -f /tmp/telemetry_collector.pid ]; then
      COLLECTOR_PID=$(cat /tmp/telemetry_collector.pid)
      if kill -0 "$COLLECTOR_PID" 2>/dev/null; then
        echo "Stopping collector (PID: $COLLECTOR_PID)..."
        kill "$COLLECTOR_PID" 2>/dev/null || true
        sleep 1
      fi
      rm -f /tmp/telemetry_collector.pid
    fi
    
    # Finalize data
    python3 /telemetry_collector.py stop
    
    # Generate report
    echo ""
    echo "Generating visual report..."
    python3 /generate_report.py
    
    echo "::endgroup::"
    ;;
    
  snapshot|*)
    echo "::group::📊 Runner Telemetry Snapshot"
    
    # OS and kernel info
    echo "OS Information:"
    uname -a
    
    # CPU and memory usage
    echo -e "\nCPU and Memory Usage (top 10 processes):"
    ps aux --sort=-%mem | head -n 11
    
    # Disk usage
    echo -e "\nDisk Usage:"
    df -h
    
    # CPU stats
    echo -e "\nCPU Stats:"
    mpstat 2>/dev/null || echo "mpstat not available"
    
    # GitHub Actions Runner Context
    echo -e "\nGitHub Actions Context:"
    echo "Runner OS: $RUNNER_OS"
    echo "Job: $GITHUB_JOB"
    echo "Workflow: $GITHUB_WORKFLOW"
    echo "Run ID: $GITHUB_RUN_ID"
    echo "Run Number: $GITHUB_RUN_NUMBER"
    echo "Repository: $GITHUB_REPOSITORY"
    echo "Actor: $GITHUB_ACTOR"
    
    echo "::endgroup::"
    
    # For snapshot mode, collect a few samples then generate report
    echo "::group::📈 Collecting Time-Series Data"
    
    # Collect samples for ~10 seconds
    echo "Collecting metrics over 10 seconds..."
    
    # Initialize and collect
    python3 -c "
import sys
sys.path.insert(0, '/')
from telemetry_collector import collect_sample, get_top_processes, get_memory_info
import json
import time
import os

data_file = os.environ.get('TELEMETRY_DATA_FILE', '/tmp/telemetry_data.json')
interval = 2

# Initial data
data = {
    'start_time': time.time(),
    'start_datetime': __import__('datetime').datetime.now().isoformat(),
    'interval': interval,
    'samples': [],
    'initial_snapshot': {
        'cpu_count': os.cpu_count(),
        'memory': get_memory_info(),
        'processes': get_top_processes(10)
    },
    'github_context': {
        'repository': os.environ.get('GITHUB_REPOSITORY', 'N/A'),
        'workflow': os.environ.get('GITHUB_WORKFLOW', 'N/A'),
        'job': os.environ.get('GITHUB_JOB', 'N/A'),
        'run_id': os.environ.get('GITHUB_RUN_ID', 'N/A'),
        'run_number': os.environ.get('GITHUB_RUN_NUMBER', 'N/A'),
        'actor': os.environ.get('GITHUB_ACTOR', 'N/A'),
        'runner_os': os.environ.get('RUNNER_OS', 'N/A'),
        'runner_name': os.environ.get('RUNNER_NAME', 'N/A'),
    }
}

prev_cpu = None
prev_cpu_detailed = None
prev_disk = None
prev_net = None
prev_ctxt = None

for i in range(6):  # 6 samples at 2s = 12 seconds
    sample, prev_cpu, prev_cpu_detailed, prev_disk, prev_net, prev_ctxt = collect_sample(prev_cpu, prev_cpu_detailed, prev_disk, prev_net, prev_ctxt)
    data['samples'].append(sample)
    print(f'  Sample {i+1}/6: CPU={sample[\"cpu_percent\"]:.1f}% MEM={sample[\"memory\"][\"percent\"]:.1f}%')
    if i < 5:
        time.sleep(interval)

data['end_time'] = time.time()
data['end_datetime'] = __import__('datetime').datetime.now().isoformat()
data['duration'] = data['end_time'] - data['start_time']
data['final_snapshot'] = {
    'processes': get_top_processes(10),
    'memory': get_memory_info()
}

with open(data_file, 'w') as f:
    json.dump(data, f, indent=2)

print(f'\\n✅ Collected {len(data[\"samples\"])} samples over {data[\"duration\"]:.1f}s')
"
    
    echo "::endgroup::"
    
    # Generate visual report
    echo "::group::🎨 Generating Visual Report"
    python3 /generate_report.py
    echo "::endgroup::"
    
    # Write text summary
    OUT_FILE="${GITHUB_WORKSPACE:-$(pwd)}/runner-telemetry.txt"
    {
      echo "Runner Telemetry Summary"
      echo "========================"
      echo ""
      echo "OS Information:"
      uname -a
      echo ""
      echo "CPU and Memory Usage (top 10 processes):"
      ps aux --sort=-%mem | head -n 11
      echo ""
      echo "Disk Usage:"
      df -h
      echo ""
      echo "GitHub Actions Context:"
      echo "Runner OS: $RUNNER_OS"
      echo "Job: $GITHUB_JOB"
      echo "Workflow: $GITHUB_WORKFLOW"
      echo "Run ID: $GITHUB_RUN_ID"
      echo "Repository: $GITHUB_REPOSITORY"
      echo "Actor: $GITHUB_ACTOR"
    } > "$OUT_FILE"
    
    echo "📝 Text summary written to $OUT_FILE"
    ;;
esac

echo ""
echo "✅ Telemetry action complete"
