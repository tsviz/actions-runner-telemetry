#!/bin/bash
set -euo pipefail

# Local verification for repo visibility detection and billing output
# Builds the Docker image and runs the entrypoint with mocked GITHUB_EVENT_PATH
# Produces reports under ./output and prints key lines to verify Free vs Paid

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/output"
IMAGE_NAME="telemetry-test"

echo "🔧 Preparing output directory: ${OUTPUT_DIR}"
mkdir -p "${OUTPUT_DIR}"

echo "📦 Building Docker image: ${IMAGE_NAME}"
docker build -t "${IMAGE_NAME}" "${SCRIPT_DIR}" > /dev/null
echo "✅ Image built"

function run_case() {
  local case_name="$1"
  local is_private="$2"  # "true" or "false"
  local event_file="${OUTPUT_DIR}/event-${case_name}.json"

  cat >"${event_file}" <<EOF
{
  "repository": {
    "private": ${is_private}
  }
}
EOF

  echo "\n🚀 Running snapshot for case: ${case_name} (repository.private=${is_private})"
  docker run --rm \
    -v "${OUTPUT_DIR}:/github/workspace" \
    -e GITHUB_STEP_SUMMARY=/github/workspace/step-summary.md \
    -e GITHUB_WORKSPACE=/github/workspace \
    -e GITHUB_EVENT_PATH=/github/workspace/event-${case_name}.json \
    -e INPUT_MODE=snapshot \
    -e INPUT_INTERVAL=1 \
    -e INPUT_ENABLED=true \
    -e INPUT_REPO_VISIBILITY=auto \
    -e RUNNER_OS=Linux \
    -e RUNNER_NAME=local-test \
    "${IMAGE_NAME}" > "${OUTPUT_DIR}/logs-${case_name}.txt" 2>&1 || true

  echo "🧪 Checking report for ${case_name}"
  if [[ -f "${OUTPUT_DIR}/telemetry-report.md" ]]; then
    local runner_line cost_line
    runner_line=$(grep -m1 -E "^Runner Type|\*\*Runner Type\*\*" "${OUTPUT_DIR}/telemetry-report.md" || true)
    cost_line=$(grep -m1 -E "\$0\.0000|\$0\.0060|Cost" "${OUTPUT_DIR}/telemetry-report.md" || true)
    echo "   Runner: ${runner_line}"
    echo "   Cost:   ${cost_line}"
  else
    echo "   ❌ telemetry-report.md not found"
  fi

  echo "🔎 Visibility debug (first 10 lines):"
  head -n 10 "${OUTPUT_DIR}/logs-${case_name}.txt" || true
}

# Case A: Public repository (free standard runners)
run_case "public" "false"

# Move previous outputs aside
mv -f "${OUTPUT_DIR}/telemetry-report.md" "${OUTPUT_DIR}/telemetry-report-public.md" 2>/dev/null || true
mv -f "${OUTPUT_DIR}/telemetry-summary.json" "${OUTPUT_DIR}/telemetry-summary-public.json" 2>/dev/null || true
mv -f "${OUTPUT_DIR}/telemetry-dashboard.html" "${OUTPUT_DIR}/telemetry-dashboard-public.html" 2>/dev/null || true

# Case B: Private repository (paid standard runners)
run_case "private" "true"

mv -f "${OUTPUT_DIR}/telemetry-report.md" "${OUTPUT_DIR}/telemetry-report-private.md" 2>/dev/null || true
mv -f "${OUTPUT_DIR}/telemetry-summary.json" "${OUTPUT_DIR}/telemetry-summary-private.json" 2>/dev/null || true
mv -f "${OUTPUT_DIR}/telemetry-dashboard.html" "${OUTPUT_DIR}/telemetry-dashboard-private.html" 2>/dev/null || true

echo "\n✅ Local verification complete. See ${OUTPUT_DIR} for logs and reports."
