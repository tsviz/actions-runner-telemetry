# Runner Telemetry Action

Collects detailed system and environment telemetry from the GitHub Actions runner with **time-series graphs**, **visual dashboards**, and comprehensive metrics displayed directly in the workflow summary.

## ✨ Features

- 📈 **Time-Series Graphs** - CPU, Memory, Load, and I/O metrics over time
- 📊 **Real-time Gauges** - Circular gauges for CPU, Memory, and Disk usage
- 🔥 **Load Heatmaps** - Visual load average indicators
- 📉 **Process Charts** - Top processes by CPU and Memory usage
- 📡 **I/O Metrics** - Disk read/write and Network RX/TX rates
- 📋 **Statistics Cards** - Average, peak, and current values
- 🎨 **SVG Visualizations** - Pure SVG charts (no external dependencies)

## 📊 Visual Dashboard

The action generates a comprehensive visual dashboard in your workflow's **Summary** tab:

![Dashboard Preview](https://img.shields.io/badge/View-Job_Summary-blue?style=for-the-badge)

### Charts Included:
- **CPU & Memory Over Time** - Line chart with area fill
- **System Load Graph** - Load average trends
- **I/O Activity Chart** - Disk and Network throughput
- **Resource Gauges** - Current utilization percentages
- **Process Rankings** - Top consumers by CPU and Memory

## 🚀 Usage

### Simple (Recommended) ✨

Just add the action once - telemetry starts automatically and the report generates at job completion:

```yaml
steps:
  - uses: actions/checkout@v4
  
  - name: Enable Telemetry
    uses: tsviz/actions-runner-telemetry@main
  
  # Your build steps - telemetry runs in background
  - name: Build
    run: npm run build
  
  - name: Test
    run: npm test
  
  # Report auto-generates at job end - no "stop" needed!
```

### With Per-Step Tracking 📊

Add optional step markers to track resource usage for each phase:

```yaml
steps:
  - uses: actions/checkout@v4
  
  # Start telemetry (auto mode is default)
  - name: Enable Telemetry
    uses: tsviz/actions-runner-telemetry@main
  
  # Mark each step for tracking
  - name: Mark - Install
    uses: tsviz/actions-runner-telemetry@main
    with:
      mode: step
      step-name: "Install Dependencies"
  
  - name: Install Dependencies
    run: npm ci
  
  - name: Mark - Build
    uses: tsviz/actions-runner-telemetry@main
    with:
      mode: step
      step-name: "Build Application"
  
  - name: Build
    run: npm run build
  
  - name: Mark - Test
    uses: tsviz/actions-runner-telemetry@main
    with:
      mode: step
      step-name: "Run Tests"
  
  - name: Test
    run: npm test
  
  # Report auto-generates with per-step analysis!
```

The report will include:
- **Step Timeline (Gantt Chart)** - Visual timeline of each step
- **Resource Usage by Step** - Bar chart comparing CPU/Memory per step
- **Step Comparison Table** - Detailed metrics for each step
- **Insights** - Automatically identifies the most resource-intensive steps

### Upload Artifacts

```yaml
  - name: Upload telemetry
    uses: actions/upload-artifact@v4
    with:
      name: runner-telemetry
      path: |
        telemetry-report.md
        telemetry-data.json
        runner-telemetry.txt
```

## ⚙️ Inputs

| Input | Description | Default |
|-------|-------------|---------|
| `enabled` | Enable or disable telemetry collection | `true` |
| `mode` | Operation mode: `auto`, `step`, or `snapshot` | `auto` |
| `interval` | Sampling interval in seconds | `2` |
| `step-name` | Name of the current step (used with `mode: step`) | `""` |

### Mode Details

| Mode | Description |
|------|-------------|
| `auto` | **(Default)** Start collection automatically, report generates at job end |
| `step` | Mark a step boundary for per-step resource tracking |
| `snapshot` | Quick 10-second sample with instant report (legacy) |

### Disabling Telemetry

You can disable telemetry without removing the action from your workflow:

```yaml
env:
  TELEMETRY_ENABLED: 'false'  # Set to 'true' to re-enable

steps:
  - name: Enable Telemetry
    uses: tsviz/actions-runner-telemetry@main
    with:
      enabled: ${{ env.TELEMETRY_ENABLED }}
```

Or disable it directly:

```yaml
  - name: Enable Telemetry
    uses: tsviz/actions-runner-telemetry@main
    with:
      enabled: false  # Temporarily disabled
```

## 📤 Outputs

| Output | Description |
|--------|-------------|
| `report-path` | Path to the generated HTML report |
| `data-path` | Path to the raw telemetry JSON data |
| `csv-path` | Path to the time-series CSV file |
| `summary-path` | Path to the dashboard-ready summary JSON |
| `enabled` | Whether telemetry was enabled for this run |

## 🧪 Local Testing

```bash
# Build the image
docker build -t runner-telemetry-action .

# Run with output directory mounted
mkdir -p output
docker run --rm \
  -v "$(pwd)/output:/github/workspace" \
  -e GITHUB_WORKSPACE="/github/workspace" \
  -e GITHUB_STEP_SUMMARY="/github/workspace/summary.md" \
  -e RUNNER_OS="Linux" \
  -e GITHUB_JOB="test-job" \
  -e GITHUB_WORKFLOW="test-workflow" \
  -e GITHUB_RUN_ID="12345" \
  -e GITHUB_RUN_NUMBER="1" \
  -e GITHUB_REPOSITORY="your/repo" \
  -e GITHUB_ACTOR="your-username" \
  runner-telemetry-action

# View the report
cat output/telemetry-report.html
```

## 📁 Generated Files

| File | Description |
|------|-------------|
| `telemetry-report.html` | Visual dashboard with SVG charts |
| `telemetry-raw.json` | Raw metrics data for analysis |
| `telemetry-samples.csv` | Time-series data for BI tools |
| `telemetry-steps.csv` | Per-step metrics for analysis |
| `telemetry-summary.json` | Flattened summary for dashboards |
| `runner-telemetry.txt` | Plain text summary |

## License

MIT
