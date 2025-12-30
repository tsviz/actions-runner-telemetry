#!/usr/bin/env bash
set -euo pipefail

# Local test for Node action (index.js + post.js) in Docker
# Simulates a run on a self-hosted larger runner label (tsvi-linux8cores)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/output"
IMAGE_NAME="telemetry-node-test"

echo "📦 Building Ubuntu image with Python and Node..."
docker build -t "$IMAGE_NAME" - <<'DOCKERFILE'
FROM ubuntu:22.04
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      python3 ca-certificates curl jq procps && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /work
DOCKERFILE

mkdir -p "$OUTPUT_DIR"

echo "🚀 Running Node action start → workload → post ..."
docker run --rm \
  -v "${OUTPUT_DIR}:/github/workspace" \
  -v "${SCRIPT_DIR}:/repo" \
  -e GITHUB_WORKSPACE="/github/workspace" \
  -e GITHUB_STEP_SUMMARY="/github/workspace/step-summary.md" \
  -e RUNNER_OS="Linux" \
  -e RUNNER_NAME="tsvi-linux8cores" \
  -e REPO_VISIBILITY="public" \
  -w /repo \
  "$IMAGE_NAME" \
  bash -lc '
set -e
echo "→ node dist/index.js (start)"
node dist/index.js
echo "→ simulate workload (cpu/mem)"
python3 - <<"PY"
import time, math
start=time.time()
while time.time()-start<6:
    x=0.0
    for i in range(200000):
        x+=math.sin(i)*math.cos(i)
PY
echo "→ node dist/post.js (stop + report)"
node dist/post.js
echo "→ list outputs"
ls -lah /github/workspace | sed -n "1,200p"
'

echo "\n✅ Done. Check ${OUTPUT_DIR} for telemetry-report.md and dashboard."
