#!/usr/bin/env python3
"""
Generate visual telemetry report for GitHub Step Summary.
Uses GitHub-compatible visualizations (tables, progress bars, Unicode charts).
"""

import os
import sys
import json
import math
from datetime import datetime
from pathlib import Path

DATA_FILE = os.environ.get('TELEMETRY_DATA_FILE', '/tmp/telemetry_data.json')

# Health thresholds
THRESHOLDS = {
    'cpu_warning': 60,
    'cpu_critical': 85,
    'mem_warning': 70,
    'mem_critical': 90,
    'load_warning': 2.0,
    'load_critical': 4.0,
    'swap_warning': 20,
    'swap_critical': 50,
    'iowait_warning': 15,
    'iowait_critical': 30,
    'steal_warning': 5,
    'steal_critical': 15,
}

def get_health_status(value, warning_threshold, critical_threshold):
    """Get health status and icon based on value."""
    if value >= critical_threshold:
        return 'critical', '🔴'
    elif value >= warning_threshold:
        return 'warning', '🟡'
    else:
        return 'good', '🟢'

def format_bytes(bytes_val, precision=1):
    """Format bytes to human readable."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024:
            return f"{bytes_val:.{precision}f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.{precision}f} PB"

def format_duration(seconds):
    """Format seconds to human readable duration."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h"

def create_sparkline(values, width=20):
    """Create a Unicode sparkline chart."""
    if not values:
        return "▁" * width
    
    # Normalize values to 0-8 range for Unicode block characters
    min_val = min(values)
    max_val = max(values)
    if max_val == min_val:
        return "▄" * min(len(values), width)  # Flat line at middle
    
    # Sample values if more than width
    if len(values) > width:
        step = len(values) / width
        sampled = [values[int(i * step)] for i in range(width)]
    else:
        sampled = values
    
    # Unicode block characters for sparkline (▁▂▃▄▅▆▇█)
    blocks = "▁▂▃▄▅▆▇█"
    
    result = ""
    for v in sampled:
        normalized = (v - min_val) / (max_val - min_val)
        idx = min(int(normalized * 7), 7)
        result += blocks[idx]
    
    return result

def create_progress_bar(value, max_val=100, width=20, show_percent=True):
    """Create a text-based progress bar."""
    percent = min(value / max_val, 1.0) if max_val > 0 else 0
    filled = int(percent * width)
    empty = width - filled
    
    # Color indicator
    if percent >= 0.85:
        indicator = "🔴"
    elif percent >= 0.60:
        indicator = "🟡"
    else:
        indicator = "🟢"
    
    bar = "█" * filled + "░" * empty
    
    if show_percent:
        return f"{indicator} `{bar}` {value:.1f}%"
    return f"{indicator} `{bar}`"

def create_horizontal_bar(value, max_val, color_emoji="🔵"):
    """Create a simple horizontal bar using markdown."""
    percent = min(value / max_val, 1.0) if max_val > 0 else 0
    filled = int(percent * 15)
    return f"`{'█' * filled}{'░' * (15 - filled)}` {value:.1f}"

def analyze_steps(data):
    """Analyze step-level metrics."""
    steps = data.get('steps', [])
    samples = data.get('samples', [])
    start_time = data.get('start_time', 0)
    
    if not steps or not samples:
        return []
    
    analyzed_steps = []
    
    for step in steps:
        step_start = step.get('start_time', start_time)
        step_end = step.get('end_time', data.get('end_time', step_start))
        
        step_samples = [
            s for s in samples 
            if step_start <= s['timestamp'] <= step_end
        ]
        
        if step_samples:
            cpu_values = [s['cpu_percent'] for s in step_samples]
            mem_values = [s['memory']['percent'] for s in step_samples]
            
            analyzed_step = {
                'name': step['name'],
                'duration': step_end - step_start,
                'sample_count': len(step_samples),
                'avg_cpu': sum(cpu_values) / len(cpu_values),
                'max_cpu': max(cpu_values),
                'avg_mem': sum(mem_values) / len(mem_values),
                'max_mem': max(mem_values),
                'cpu_values': cpu_values,
                'mem_values': mem_values,
            }
        else:
            analyzed_step = {
                'name': step['name'],
                'duration': step_end - step_start,
                'sample_count': 0,
                'avg_cpu': 0, 'max_cpu': 0,
                'avg_mem': 0, 'max_mem': 0,
                'cpu_values': [],
                'mem_values': [],
            }
        
        analyzed_steps.append(analyzed_step)
    
    return analyzed_steps

def generate_steps_section(data):
    """Generate the per-step analysis section."""
    analyzed_steps = analyze_steps(data)
    
    if not analyzed_steps:
        return ""
    
    duration = data.get('duration', 0)
    
    heaviest_cpu = max(analyzed_steps, key=lambda s: s['avg_cpu'])
    heaviest_mem = max(analyzed_steps, key=lambda s: s['avg_mem'])
    longest_step = max(analyzed_steps, key=lambda s: s['duration'])
    
    section = f'''
---

## 📋 Per-Step Analysis

| Step | Duration | Avg CPU | Max CPU | Avg Mem | Trend |
|:-----|:--------:|:-------:|:-------:|:-------:|:-----:|
'''
    
    for step in analyzed_steps:
        cpu_trend = create_sparkline(step['cpu_values'], 10)
        is_heavy = step == heaviest_cpu
        badge = "🔥" if is_heavy else ""
        section += f"| {badge} {step['name'][:25]} | {format_duration(step['duration'])} | {step['avg_cpu']:.1f}% | {step['max_cpu']:.1f}% | {step['avg_mem']:.1f}% | `{cpu_trend}` |\n"
    
    # Insights
    section += f'''

### 💡 Insights

- **Longest Step:** {longest_step['name'][:30]} ({format_duration(longest_step['duration'])})
- **Heaviest CPU:** {heaviest_cpu['name'][:30]} ({heaviest_cpu['avg_cpu']:.1f}% avg)
- **Heaviest Memory:** {heaviest_mem['name'][:30]} ({heaviest_mem['avg_mem']:.1f}% avg)

'''
    
    return section

def generate_report(data):
    """Generate the full visual report."""
    samples = data.get('samples', [])
    
    if not samples:
        return "## ⚠️ No telemetry data collected\n\nNo samples were recorded during the monitoring period."
    
    # Extract time series data
    cpu_values = [s['cpu_percent'] for s in samples]
    mem_values = [s['memory']['percent'] for s in samples]
    load_1m = [s['load']['load_1m'] for s in samples]
    disk_read = [s['disk_io']['read_rate'] / (1024*1024) for s in samples]
    disk_write = [s['disk_io']['write_rate'] / (1024*1024) for s in samples]
    net_rx = [s['network_io']['rx_rate'] / (1024*1024) for s in samples]
    net_tx = [s['network_io']['tx_rate'] / (1024*1024) for s in samples]
    
    # Extended metrics
    iowait_values = [s.get('cpu_iowait_percent', 0) for s in samples]
    steal_values = [s.get('cpu_steal_percent', 0) for s in samples]
    swap_values = [s.get('swap', {}).get('percent', 0) for s in samples]
    
    # Calculate statistics
    avg_cpu = sum(cpu_values) / len(cpu_values)
    max_cpu = max(cpu_values)
    avg_mem = sum(mem_values) / len(mem_values)
    max_mem = max(mem_values)
    avg_load = sum(load_1m) / len(load_1m)
    max_load = max(load_1m)
    total_disk_read = sum(disk_read) * data.get('interval', 2)
    total_disk_write = sum(disk_write) * data.get('interval', 2)
    total_net_rx = sum(net_rx) * data.get('interval', 2)
    total_net_tx = sum(net_tx) * data.get('interval', 2)
    
    avg_iowait = sum(iowait_values) / len(iowait_values) if iowait_values else 0
    max_iowait = max(iowait_values) if iowait_values else 0
    avg_steal = sum(steal_values) / len(steal_values) if steal_values else 0
    max_steal = max(steal_values) if steal_values else 0
    avg_swap = sum(swap_values) / len(swap_values) if swap_values else 0
    max_swap = max(swap_values) if swap_values else 0
    
    duration = data.get('duration', 0)
    
    # Get health statuses
    _, cpu_icon = get_health_status(max_cpu, THRESHOLDS['cpu_warning'], THRESHOLDS['cpu_critical'])
    _, mem_icon = get_health_status(max_mem, THRESHOLDS['mem_warning'], THRESHOLDS['mem_critical'])
    _, load_icon = get_health_status(max_load, THRESHOLDS['load_warning'], THRESHOLDS['load_critical'])
    _, iowait_icon = get_health_status(max_iowait, THRESHOLDS['iowait_warning'], THRESHOLDS['iowait_critical'])
    _, steal_icon = get_health_status(max_steal, THRESHOLDS['steal_warning'], THRESHOLDS['steal_critical'])
    _, swap_icon = get_health_status(max_swap, THRESHOLDS['swap_warning'], THRESHOLDS['swap_critical'])
    
    # Overall health
    all_statuses = [
        get_health_status(max_cpu, THRESHOLDS['cpu_warning'], THRESHOLDS['cpu_critical'])[0],
        get_health_status(max_mem, THRESHOLDS['mem_warning'], THRESHOLDS['mem_critical'])[0],
        get_health_status(max_load, THRESHOLDS['load_warning'], THRESHOLDS['load_critical'])[0],
    ]
    status_priority = {'good': 0, 'warning': 1, 'critical': 2}
    overall = max(all_statuses, key=lambda s: status_priority[s])
    overall_icon = {'critical': '🔴', 'warning': '🟡', 'good': '🟢'}[overall]
    overall_text = {'critical': 'Critical', 'warning': 'Warning', 'good': 'Healthy'}[overall]
    
    # Create sparklines for trends
    cpu_sparkline = create_sparkline(cpu_values)
    mem_sparkline = create_sparkline(mem_values)
    load_sparkline = create_sparkline(load_1m)
    
    # Create progress bars for current state
    final_cpu = cpu_values[-1] if cpu_values else 0
    final_mem = mem_values[-1] if mem_values else 0
    cpu_bar = create_progress_bar(final_cpu)
    mem_bar = create_progress_bar(final_mem)
    
    # Get context info
    ctx = data.get('github_context', {})
    initial = data.get('initial_snapshot', {})
    final_snapshot = data.get('final_snapshot', {})
    
    # Build report
    report = f'''# 🖥️ Runner Telemetry Dashboard

## 📊 Executive Summary

| Metric | Status | Peak | Avg | Trend |
|:-------|:------:|:----:|:---:|:-----:|
| **Overall Health** | {overall_icon} {overall_text} | - | - | - |
| **CPU Usage** | {cpu_icon} | {max_cpu:.1f}% | {avg_cpu:.1f}% | `{cpu_sparkline}` |
| **Memory Usage** | {mem_icon} | {max_mem:.1f}% | {avg_mem:.1f}% | `{mem_sparkline}` |
| **System Load** | {load_icon} | {max_load:.2f} | {avg_load:.2f} | `{load_sparkline}` |
| **I/O Wait** | {iowait_icon} | {max_iowait:.1f}% | {avg_iowait:.1f}% | - |
| **CPU Steal** | {steal_icon} | {max_steal:.1f}% | {avg_steal:.1f}% | - |
| **Swap Usage** | {swap_icon} | {max_swap:.1f}% | {avg_swap:.1f}% | - |

**Duration:** {format_duration(duration)} • **Samples:** {len(samples)} • **Interval:** {data.get('interval', 2)}s

---

## 📈 Current Resource Usage

| Resource | Status Bar | Value |
|:---------|:-----------|------:|
| **CPU** | {cpu_bar} | |
| **Memory** | {mem_bar} | |

---

## 💾 I/O Summary

| Metric | Total | Avg Rate |
|:-------|------:|---------:|
| **Disk Read** | {format_bytes(total_disk_read * 1024 * 1024)} | {format_bytes(sum(disk_read) / len(disk_read) * 1024 * 1024)}/s |
| **Disk Write** | {format_bytes(total_disk_write * 1024 * 1024)} | {format_bytes(sum(disk_write) / len(disk_write) * 1024 * 1024)}/s |
| **Network RX** | {format_bytes(total_net_rx * 1024 * 1024)} | {format_bytes(sum(net_rx) / len(net_rx) * 1024 * 1024)}/s |
| **Network TX** | {format_bytes(total_net_tx * 1024 * 1024)} | {format_bytes(sum(net_tx) / len(net_tx) * 1024 * 1024)}/s |

'''

    # Add per-step analysis if we have steps
    steps_section = generate_steps_section(data)
    if steps_section:
        report += steps_section
    
    # System information section
    report += f'''
---

## 🖥️ System Information

| Component | Details |
|:----------|:--------|
| **Runner** | {ctx.get('runner_name', 'Unknown')} |
| **OS** | {ctx.get('runner_os', 'Unknown')} |
| **Architecture** | {ctx.get('runner_arch', 'Unknown')} |
| **Total Memory** | {initial.get('memory', {}).get('total_mb', 0)} MB |
| **CPU Cores** | {initial.get('cpu_count', 'N/A')} |

'''
    
    # Top processes
    top_procs = final_snapshot.get('processes', initial.get('processes', {}))
    if top_procs.get('by_cpu'):
        report += '''
<details>
<summary>🔝 Top Processes by CPU</summary>

| Process | CPU % | Memory % |
|:--------|------:|---------:|
'''
        for p in top_procs.get('by_cpu', [])[:5]:
            cmd = p['command'].split('/')[-1].split()[0][:30]
            report += f"| {cmd} | {p['cpu']:.1f}% | {p['mem']:.1f}% |\n"
        report += '\n</details>\n'
    
    if top_procs.get('by_mem'):
        report += '''
<details>
<summary>🔝 Top Processes by Memory</summary>

| Process | Memory % | CPU % |
|:--------|------:|---------:|
'''
        for p in top_procs.get('by_mem', [])[:5]:
            cmd = p['command'].split('/')[-1].split()[0][:30]
            report += f"| {cmd} | {p['mem']:.1f}% | {p['cpu']:.1f}% |\n"
        report += '\n</details>\n'
    
    # Recommendations
    recommendations = []
    if max_cpu > THRESHOLDS['cpu_critical']:
        recommendations.append(f"⚠️ **High CPU Usage:** Peak reached {max_cpu:.1f}%. Consider optimizing intensive operations or using a larger runner.")
    if max_mem > THRESHOLDS['mem_critical']:
        recommendations.append(f"⚠️ **High Memory Usage:** Peak reached {max_mem:.1f}%. Watch for OOM issues or consider runners with more RAM.")
    if max_iowait > THRESHOLDS['iowait_warning']:
        recommendations.append(f"⚠️ **High I/O Wait:** Peak reached {max_iowait:.1f}%. Disk operations may be bottlenecking your workflow.")
    if max_steal > THRESHOLDS['steal_warning']:
        recommendations.append(f"⚠️ **CPU Steal Detected:** Peak reached {max_steal:.1f}%. The runner may be oversubscribed. Consider different runner types.")
    
    if recommendations:
        report += '\n---\n\n## 💡 Recommendations\n\n'
        for rec in recommendations:
            report += f"- {rec}\n"
    
    # Raw data link
    report += f'''
---

<details>
<summary>📊 Raw Data Summary</summary>

```json
{{
  "duration_seconds": {duration:.1f},
  "sample_count": {len(samples)},
  "cpu": {{"avg": {avg_cpu:.1f}, "max": {max_cpu:.1f}}},
  "memory": {{"avg": {avg_mem:.1f}, "max": {max_mem:.1f}}},
  "load_1m": {{"avg": {avg_load:.2f}, "max": {max_load:.2f}}}
}}
```

</details>

---

*Generated by [Runner Telemetry Action](https://github.com/tsviz/actions-runner-telemetry)*
'''
    
    return report


def export_csv_files(data, output_dir):
    """Export CSV and JSON summary files."""
    samples = data.get('samples', [])
    start_time = data.get('start_time', 0)
    
    if not samples:
        return
    
    # CSV export
    csv_path = os.path.join(output_dir, 'telemetry-samples.csv')
    try:
        with open(csv_path, 'w') as f:
            headers = ['timestamp', 'elapsed_sec', 'cpu_percent', 'memory_percent', 
                      'memory_used_mb', 'load_1m', 'disk_read_rate', 'disk_write_rate',
                      'net_rx_rate', 'net_tx_rate', 'iowait_percent', 'steal_percent']
            f.write(','.join(headers) + '\n')
            
            for s in samples:
                row = [
                    f"{s['timestamp']:.2f}",
                    f"{s['timestamp'] - start_time:.2f}",
                    f"{s['cpu_percent']:.2f}",
                    f"{s['memory']['percent']:.2f}",
                    f"{s['memory']['used_mb']}",
                    f"{s['load']['load_1m']:.2f}",
                    f"{s['disk_io']['read_rate']:.0f}",
                    f"{s['disk_io']['write_rate']:.0f}",
                    f"{s['network_io']['rx_rate']:.0f}",
                    f"{s['network_io']['tx_rate']:.0f}",
                    f"{s.get('cpu_iowait_percent', 0):.2f}",
                    f"{s.get('cpu_steal_percent', 0):.2f}",
                ]
                f.write(','.join(row) + '\n')
        print(f"✅ CSV exported to {csv_path}")
    except Exception as e:
        print(f"⚠️ Failed to export CSV: {e}")
    
    # JSON summary
    json_path = os.path.join(output_dir, 'telemetry-summary.json')
    try:
        cpu_values = [s['cpu_percent'] for s in samples]
        mem_values = [s['memory']['percent'] for s in samples]
        load_values = [s['load']['load_1m'] for s in samples]
        
        summary = {
            'duration_seconds': data.get('duration', 0),
            'sample_count': len(samples),
            'interval': data.get('interval', 2),
            'cpu': {
                'avg': sum(cpu_values) / len(cpu_values),
                'max': max(cpu_values),
                'min': min(cpu_values),
            },
            'memory': {
                'avg': sum(mem_values) / len(mem_values),
                'max': max(mem_values),
                'min': min(mem_values),
            },
            'load_1m': {
                'avg': sum(load_values) / len(load_values),
                'max': max(load_values),
            },
            'github_context': data.get('github_context', {}),
        }
        
        with open(json_path, 'w') as f:
            json.dump(summary, f, indent=2)
        print(f"✅ Summary JSON exported to {json_path}")
    except Exception as e:
        print(f"⚠️ Failed to export summary JSON: {e}")


def main():
    # Load collected data
    if not os.path.exists(DATA_FILE):
        print(f"Error: No data file found at {DATA_FILE}")
        sys.exit(1)
    
    with open(DATA_FILE, 'r') as f:
        data = json.load(f)
    
    report = generate_report(data)
    
    # Write to GITHUB_STEP_SUMMARY if available
    summary_file = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary_file:
        with open(summary_file, 'a') as f:
            f.write(report)
        print("✅ Report written to GitHub Step Summary")
    
    # Also write to local file
    output_dir = os.environ.get('GITHUB_WORKSPACE', '/github/workspace')
    report_path = os.path.join(output_dir, 'telemetry-report.md')
    
    try:
        with open(report_path, 'w') as f:
            f.write(report)
        print(f"✅ Report saved to {report_path}")
    except:
        with open('telemetry-report.md', 'w') as f:
            f.write(report)
        print("✅ Report saved to telemetry-report.md")
    
    # Save raw data as JSON
    try:
        json_path = os.path.join(output_dir, 'telemetry-raw.json')
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"✅ Raw data saved to {json_path}")
    except:
        pass
    
    # Export CSV and summary files
    export_csv_files(data, output_dir)
    
    # Print summary to console
    print("\n" + "="*60)
    print(f"📊 Telemetry Summary:")
    print(f"   Duration: {format_duration(data.get('duration', 0))}")
    print(f"   Samples: {len(data.get('samples', []))}")
    if data.get('samples'):
        cpu_vals = [s['cpu_percent'] for s in data['samples']]
        mem_vals = [s['memory']['percent'] for s in data['samples']]
        print(f"   CPU: avg={sum(cpu_vals)/len(cpu_vals):.1f}%, max={max(cpu_vals):.1f}%")
        print(f"   Memory: avg={sum(mem_vals)/len(mem_vals):.1f}%, max={max(mem_vals):.1f}%")
    print("="*60)

if __name__ == '__main__':
    main()
