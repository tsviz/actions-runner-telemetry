#!/bin/bash
# Post-entrypoint: Runs automatically at end of job to stop collection and generate report

# Configuration
ENABLED="${INPUT_ENABLED:-true}"
TELEMETRY_DATA_FILE="${GITHUB_WORKSPACE:-/github/workspace}/.telemetry_data.json"
export TELEMETRY_DATA_FILE

# Check if action is disabled
if [ "$ENABLED" = "false" ] || [ "$ENABLED" = "0" ] || [ "$ENABLED" = "no" ]; then
  echo "🔍 Runner Telemetry - Skipping (disabled)"
  exit 0
fi

# Check if telemetry was started
if [ ! -f /tmp/telemetry_collector.pid ] && [ ! -f "$TELEMETRY_DATA_FILE" ]; then
  echo "🔍 Runner Telemetry - No active collection found"
  exit 0
fi

echo "::group::📊 Generating Telemetry Report"

# Give collector a moment to finalize
sleep 2

# Stop the collector if running
if [ -f /tmp/telemetry_collector.pid ]; then
  COLLECTOR_PID=$(cat /tmp/telemetry_collector.pid)
  if kill -0 "$COLLECTOR_PID" 2>/dev/null; then
    echo "Stopping telemetry collector (PID: $COLLECTOR_PID)..."
    kill "$COLLECTOR_PID" 2>/dev/null || true
    sleep 2  # Give it time to write final data
  fi
  rm -f /tmp/telemetry_collector.pid
fi

# Finalize data collection
python3 /telemetry_collector.py stop

# Check if data file exists before generating report
if [ ! -f "$TELEMETRY_DATA_FILE" ]; then
  echo "⚠️  No telemetry data collected"
  echo "::endgroup::"
  exit 0
fi
echo "Generating visual report..."
python3 /generate_report.py

echo "::endgroup::"

echo ""
echo "✅ Telemetry report generated"
echo "   View the report in the Job Summary or download the artifacts"
