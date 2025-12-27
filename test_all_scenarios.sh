#!/bin/bash
# Test all scenarios in Docker

set -e

echo "🐳 Building Docker image..."
docker build -t telemetry-test:latest . > /dev/null 2>&1

WORK_DIR=$(mktemp -d)
trap "rm -rf $WORK_DIR" EXIT

echo "🧪 Running comprehensive telemetry test scenarios..."
echo "============================================================"

docker run --rm \
  -v "$WORK_DIR":/github/workspace \
  -v "$(pwd)/telemetry_collector.py":/telemetry_scripts/telemetry_collector.py:ro \
  -v "$(pwd)/generate_report.py":/telemetry_scripts/generate_report.py:ro \
  -v "$(pwd)/test_scenarios.py":/test_scenarios.py:ro \
  --entrypoint python3 \
  telemetry-test:latest \
  /test_scenarios.py

echo ""
echo "============================================================"
echo "✅ All scenarios completed!"
