#!/usr/bin/env python3
"""
Generate visual telemetry report for GitHub Step Summary.
Uses Mermaid diagrams (natively supported by GitHub) and modern markdown styling.
Also generates an interactive HTML dashboard artifact.

Key Feature: Helps users understand if they're fully utilizing GitHub hosted runners
to maximize value and optimize costs.
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

# GitHub Hosted Runner Specifications with accurate pricing
# https://docs.github.com/en/enterprise-cloud@latest/billing/reference/actions-runner-pricing
GITHUB_RUNNERS = {
    # Standard runners
    'ubuntu-latest': {'vcpus': 2, 'ram_gb': 7, 'cost_per_min': 0.006, 'storage_gb': 14, 'name': 'Linux 2-core'},
    'ubuntu-24.04': {'vcpus': 2, 'ram_gb': 7, 'cost_per_min': 0.006, 'storage_gb': 14, 'name': 'Linux 2-core'},
    'ubuntu-22.04': {'vcpus': 2, 'ram_gb': 7, 'cost_per_min': 0.006, 'storage_gb': 14, 'name': 'Linux 2-core'},
    'ubuntu-20.04': {'vcpus': 2, 'ram_gb': 7, 'cost_per_min': 0.006, 'storage_gb': 14, 'name': 'Linux 2-core'},
    'ubuntu-slim': {'vcpus': 1, 'ram_gb': 3, 'cost_per_min': 0.002, 'storage_gb': 14, 'name': 'Linux 1-core'},
    'windows-latest': {'vcpus': 2, 'ram_gb': 7, 'cost_per_min': 0.010, 'storage_gb': 14, 'name': 'Windows 2-core'},
    'windows-2022': {'vcpus': 2, 'ram_gb': 7, 'cost_per_min': 0.010, 'storage_gb': 14, 'name': 'Windows 2-core'},
    'windows-2019': {'vcpus': 2, 'ram_gb': 7, 'cost_per_min': 0.010, 'storage_gb': 14, 'name': 'Windows 2-core'},
    'macos-latest': {'vcpus': 3, 'ram_gb': 14, 'cost_per_min': 0.062, 'storage_gb': 14, 'name': 'macOS 3-core'},
    'macos-14': {'vcpus': 3, 'ram_gb': 14, 'cost_per_min': 0.062, 'storage_gb': 14, 'name': 'macOS 3-core'},
    'macos-13': {'vcpus': 4, 'ram_gb': 14, 'cost_per_min': 0.062, 'storage_gb': 14, 'name': 'macOS 3-core'},
    'macos-12': {'vcpus': 3, 'ram_gb': 14, 'cost_per_min': 0.062, 'storage_gb': 14, 'name': 'macOS 3-core'},
    
    # x64 Larger runners (Linux)
    'linux_2_core_advanced': {'vcpus': 2, 'ram_gb': 7, 'cost_per_min': 0.006, 'storage_gb': 14, 'name': 'Linux Advanced 2-core'},
    'linux_4_core': {'vcpus': 4, 'ram_gb': 16, 'cost_per_min': 0.012, 'storage_gb': 150, 'name': 'Linux 4-core'},
    'linux_8_core': {'vcpus': 8, 'ram_gb': 32, 'cost_per_min': 0.022, 'storage_gb': 300, 'name': 'Linux 8-core'},
    'linux_16_core': {'vcpus': 16, 'ram_gb': 64, 'cost_per_min': 0.042, 'storage_gb': 600, 'name': 'Linux 16-core'},
    'linux_32_core': {'vcpus': 32, 'ram_gb': 128, 'cost_per_min': 0.082, 'storage_gb': 1200, 'name': 'Linux 32-core'},
    'linux_64_core': {'vcpus': 64, 'ram_gb': 256, 'cost_per_min': 0.162, 'storage_gb': 2040, 'name': 'Linux 64-core'},
    'linux_96_core': {'vcpus': 96, 'ram_gb': 384, 'cost_per_min': 0.252, 'storage_gb': 3060, 'name': 'Linux 96-core'},
    
    # x64 Larger runners (Windows)
    'windows_4_core': {'vcpus': 4, 'ram_gb': 16, 'cost_per_min': 0.022, 'storage_gb': 150, 'name': 'Windows 4-core'},
    'windows_8_core': {'vcpus': 8, 'ram_gb': 32, 'cost_per_min': 0.042, 'storage_gb': 300, 'name': 'Windows 8-core'},
    'windows_16_core': {'vcpus': 16, 'ram_gb': 64, 'cost_per_min': 0.082, 'storage_gb': 600, 'name': 'Windows 16-core'},
    'windows_32_core': {'vcpus': 32, 'ram_gb': 128, 'cost_per_min': 0.162, 'storage_gb': 1200, 'name': 'Windows 32-core'},
    'windows_64_core': {'vcpus': 64, 'ram_gb': 256, 'cost_per_min': 0.322, 'storage_gb': 2040, 'name': 'Windows 64-core'},
    'windows_96_core': {'vcpus': 96, 'ram_gb': 384, 'cost_per_min': 0.552, 'storage_gb': 3060, 'name': 'Windows 96-core'},
    
    # macOS Larger runners
    'macos_l': {'vcpus': 12, 'ram_gb': 28, 'cost_per_min': 0.077, 'storage_gb': 14, 'name': 'macOS 12-core'},
    'macos_xl': {'vcpus': 5, 'ram_gb': 32, 'cost_per_min': 0.102, 'storage_gb': 14, 'name': 'macOS M2 Pro (5-core)'},
    
    # ARM64 Larger runners (Linux)
    'linux_2_core_arm': {'vcpus': 2, 'ram_gb': 7, 'cost_per_min': 0.005, 'storage_gb': 14, 'name': 'Linux ARM 2-core'},
    'linux_4_core_arm': {'vcpus': 4, 'ram_gb': 16, 'cost_per_min': 0.008, 'storage_gb': 150, 'name': 'Linux ARM 4-core'},
    'linux_8_core_arm': {'vcpus': 8, 'ram_gb': 32, 'cost_per_min': 0.014, 'storage_gb': 300, 'name': 'Linux ARM 8-core'},
    'linux_16_core_arm': {'vcpus': 16, 'ram_gb': 64, 'cost_per_min': 0.026, 'storage_gb': 600, 'name': 'Linux ARM 16-core'},
    'linux_32_core_arm': {'vcpus': 32, 'ram_gb': 128, 'cost_per_min': 0.050, 'storage_gb': 1200, 'name': 'Linux ARM 32-core'},
    'linux_64_core_arm': {'vcpus': 64, 'ram_gb': 256, 'cost_per_min': 0.098, 'storage_gb': 2040, 'name': 'Linux ARM 64-core'},
    
    # ARM64 Larger runners (Windows)
    'windows_2_core_arm': {'vcpus': 2, 'ram_gb': 7, 'cost_per_min': 0.008, 'storage_gb': 14, 'name': 'Windows ARM 2-core'},
    'windows_4_core_arm': {'vcpus': 4, 'ram_gb': 16, 'cost_per_min': 0.014, 'storage_gb': 150, 'name': 'Windows ARM 4-core'},
    'windows_8_core_arm': {'vcpus': 8, 'ram_gb': 32, 'cost_per_min': 0.026, 'storage_gb': 300, 'name': 'Windows ARM 8-core'},
    'windows_16_core_arm': {'vcpus': 16, 'ram_gb': 64, 'cost_per_min': 0.050, 'storage_gb': 600, 'name': 'Windows ARM 16-core'},
    'windows_32_core_arm': {'vcpus': 32, 'ram_gb': 128, 'cost_per_min': 0.098, 'storage_gb': 1200, 'name': 'Windows ARM 32-core'},
    'windows_64_core_arm': {'vcpus': 64, 'ram_gb': 256, 'cost_per_min': 0.194, 'storage_gb': 2040, 'name': 'Windows ARM 64-core'},
    
    # GPU-powered larger runners
    'linux_4_core_gpu': {'vcpus': 4, 'ram_gb': 16, 'cost_per_min': 0.052, 'storage_gb': 150, 'name': 'Linux GPU 4-core'},
    'windows_4_core_gpu': {'vcpus': 4, 'ram_gb': 16, 'cost_per_min': 0.102, 'storage_gb': 150, 'name': 'Windows GPU 4-core'},
}

# Utilization thresholds for scoring
UTILIZATION_THRESHOLDS = {
    'excellent': 70,  # 70%+ utilization = excellent
    'good': 50,       # 50-70% = good
    'fair': 30,       # 30-50% = fair
    'poor': 0,        # <30% = poor (wasting resources)
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

def get_utilization_grade(utilization_pct, max_cpu_pct=None, max_mem_pct=None):
    """Get utilization grade and recommendation.
    
    Scoring logic:
    - A (90%+): Optimal utilization - job fits runner well
    - B (70-89%): Good utilization - acceptable
    - C (50-69%): Fair utilization - could optimize
    - D (<50%): Poor utilization - significant wasted capacity
    
    Overutilization flags (when either CPU or memory peaks at 90%+):
    - Job is too big for current runner → recommend upgrade
    """
    # Check for overutilization (job is too big for runner)
    is_overutilized = False
    if max_cpu_pct is not None and max_cpu_pct >= 90:
        is_overutilized = True
    if max_mem_pct is not None and max_mem_pct >= 90:
        is_overutilized = True
    
    # If overutilized, recommend upgrade instead of praising utilization
    if is_overutilized:
        if utilization_pct >= 85:
            return 'D', '🔴 Poor', 'Job exceeds runner capacity - consider upgrading to a larger runner'
        else:
            return 'C', '🟡 Fair', 'Job is straining resources - consider upgrading to a larger runner'
    
    # Normal utilization scoring (for jobs that fit the runner)
    if utilization_pct >= UTILIZATION_THRESHOLDS['excellent']:
        return 'A', '🟢 Excellent', 'Runner is well-utilized for this workload'
    elif utilization_pct >= UTILIZATION_THRESHOLDS['good']:
        return 'B', '🟢 Good', 'Runner utilization is healthy'
    elif utilization_pct >= UTILIZATION_THRESHOLDS['fair']:
        return 'C', '🟡 Fair', 'Consider optimizing or using a smaller runner'
    else:
        return 'D', '🔴 Poor', 'Runner is significantly underutilized'

def detect_runner_type(data):
    """Detect the runner type from the data."""
    ctx = data.get('github_context', {})
    runner_os = ctx.get('runner_os', 'Linux').lower()
    initial = data.get('initial_snapshot', {})
    cpu_count = initial.get('cpu_count', 2)
    
    if 'windows' in runner_os:
        return 'windows-latest'
    elif 'macos' in runner_os:
        return 'macos-latest'
    else:
        return 'ubuntu-latest'

def calculate_utilization_score(data):
    """Calculate the overall runner utilization score."""
    samples = data.get('samples', [])
    if not samples:
        return None
    
    initial = data.get('initial_snapshot', {})
    cpu_count = initial.get('cpu_count', 2)
    total_ram_mb = initial.get('memory', {}).get('total_mb', 7000)
    
    cpu_values = [s['cpu_percent'] for s in samples]
    mem_values = [s['memory']['percent'] for s in samples]
    
    avg_cpu = sum(cpu_values) / len(cpu_values)
    max_cpu = max(cpu_values)
    avg_mem = sum(mem_values) / len(mem_values)
    max_mem = max(mem_values)
    
    # Combined utilization score (weighted: CPU 60%, Memory 40%)
    utilization_score = (max_cpu * 0.6) + (max_mem * 0.4)
    
    return {
        'score': utilization_score,
        'avg_cpu_pct': avg_cpu,
        'max_cpu_pct': max_cpu,
        'avg_mem_pct': avg_mem,
        'max_mem_pct': max_mem,
        'total_cpu_cores': cpu_count,
        'total_ram_gb': total_ram_mb / 1024,
    }

def calculate_cost_analysis(data, utilization, analyzed_steps=None):
    """Calculate cost analysis and potential savings."""
    if not utilization:
        return None
    
    duration_seconds = data.get('duration', 0)
    duration_minutes = max(1, math.ceil(duration_seconds / 60))  # GitHub rounds up to nearest minute
    
    runner_type = detect_runner_type(data)
    runner_specs = GITHUB_RUNNERS.get(runner_type, GITHUB_RUNNERS['ubuntu-latest'])
    
    current_cost = duration_minutes * runner_specs['cost_per_min']
    
    right_sized_runner = runner_type
    potential_savings = 0
    
    avg_cpu = utilization['avg_cpu_pct']
    avg_mem = utilization['avg_mem_pct']
    
    # Check for right-sizing opportunity (under 40% utilization)
    if avg_cpu < 40 and avg_mem < 40:
        # Find smaller runner that could work
        for name, specs in sorted(GITHUB_RUNNERS.items(), key=lambda x: x[1]['cost_per_min']):
            if specs['cost_per_min'] < runner_specs['cost_per_min']:
                new_cost = duration_minutes * specs['cost_per_min']
                if new_cost < current_cost:
                    right_sized_runner = name
                    potential_savings = current_cost - new_cost
                    break
    
    # Check for parallelization opportunities
    parallelization_opportunity = None
    if analyzed_steps:
        for step in analyzed_steps:
            if step['avg_cpu'] < 25 and step['duration'] > 30:
                parallelization_opportunity = {
                    'step': step['name'],
                    'duration': step['duration'],
                    'avg_cpu': step['avg_cpu'],
                }
                break
    
    runs_per_day = 10
    monthly_runs = runs_per_day * 30
    
    return {
        'runner_type': runner_type,
        'runner_specs': runner_specs,
        'duration_minutes': duration_minutes,
        'current_cost': current_cost,
        'right_sized_runner': right_sized_runner,
        'potential_savings': potential_savings,
        'monthly_cost': current_cost * monthly_runs,
        'monthly_savings': potential_savings * monthly_runs,
        'parallelization_opportunity': parallelization_opportunity,
    }

def detect_idle_time(data):
    """Detect periods of low activity."""
    samples = data.get('samples', [])
    if len(samples) < 3:
        return None
    
    idle_threshold = 5
    interval = data.get('interval', 2)
    total_idle = 0
    
    for sample in samples:
        if sample['cpu_percent'] < idle_threshold:
            total_idle += interval
    
    total_duration = data.get('duration', 0)
    
    return {
        'total_idle_seconds': total_idle,
        'idle_percentage': (total_idle / total_duration * 100) if total_duration > 0 else 0,
    }

def generate_utilization_section(data, analyzed_steps=None):
    """Generate the runner utilization and cost efficiency section."""
    utilization = calculate_utilization_score(data)
    if not utilization:
        return ""
    
    cost_analysis = calculate_cost_analysis(data, utilization, analyzed_steps)
    idle_analysis = detect_idle_time(data)
    
    grade, grade_text, grade_desc = get_utilization_grade(
        utilization['score'],
        max_cpu_pct=utilization['max_cpu_pct'],
        max_mem_pct=utilization['max_mem_pct']
    )
    
    score = utilization['score']
    filled = int(score / 5)
    gauge = "█" * filled + "░" * (20 - filled)
    
    section = f'''
---

## 💰 Runner Utilization & Cost Efficiency

> **Key Question:** Are you getting maximum value from your GitHub hosted runner?

### Utilization Score: {grade} ({score:.0f}%)

{grade_text} - {grade_desc}

`{gauge}` **{score:.1f}%**

### 📊 What You're Paying For vs What You're Using

| Resource | Available | Peak Used | Avg Used |
|:---------|----------:|----------:|---------:|
| **CPU Cores** | {utilization['total_cpu_cores']} | {(utilization['max_cpu_pct']/100*utilization['total_cpu_cores']):.1f} | {(utilization['avg_cpu_pct']/100*utilization['total_cpu_cores']):.1f} |
| **RAM** | {utilization['total_ram_gb']:.1f} GB | {(utilization['max_mem_pct']/100*utilization['total_ram_gb']):.1f} GB | {(utilization['avg_mem_pct']/100*utilization['total_ram_gb']):.1f} GB |

'''
    
    if cost_analysis:
        section += f'''### 💵 Cost Analysis (Jan 2026+ Pricing)

> 📖 Pricing reference: [GitHub Actions Runner Pricing](https://docs.github.com/en/enterprise-cloud@latest/billing/reference/actions-runner-pricing)

| Metric | Value |
|:-------|------:|
| **Runner Type** | `{cost_analysis['runner_specs']['name']}` |
| **This Run** | ${cost_analysis['current_cost']:.4f} ({int(cost_analysis['duration_minutes'])} min) |
| **Est. Monthly** (10 runs/day) | ${cost_analysis['monthly_cost']:.2f} |

'''
        
        if cost_analysis['right_sized_runner'] != cost_analysis['runner_type']:
            right_specs = GITHUB_RUNNERS[cost_analysis['right_sized_runner']]
            savings_pct = (cost_analysis['potential_savings'] / cost_analysis['current_cost'] * 100) if cost_analysis['current_cost'] > 0 else 0
            section += f'''
> 💡 **Optimization Opportunity: Right-Size Your Runner**
>
> Based on your usage, `{right_specs['name']}` would be more cost-effective:
>
> | | Current | Right-Sized | Savings |
> |:--|--------:|----------:|--------:|
> | **Per Run** | ${cost_analysis['current_cost']:.4f} | ${cost_analysis['current_cost'] - cost_analysis['potential_savings']:.4f} | **${cost_analysis['potential_savings']:.4f}** ({savings_pct:.0f}%) |
> | **Monthly** | ${cost_analysis['monthly_cost']:.2f} | ${cost_analysis['monthly_cost'] - cost_analysis['monthly_savings']:.2f} | **${cost_analysis['monthly_savings']:.2f}** |
>
> **Action:** Change `runs-on:` to `{cost_analysis['right_sized_runner']}` in your workflow
>
> **Learn more:** [GitHub Actions Runner Pricing](https://docs.github.com/en/enterprise-cloud@latest/billing/reference/actions-runner-pricing)

'''
        
        if cost_analysis['parallelization_opportunity']:
            opp = cost_analysis['parallelization_opportunity']
            section += f'''
> ⚡ **Performance Optimization: Parallelize Slow Steps**
>
> Step **"{opp['step']}"** uses only {opp['avg_cpu']:.0f}% CPU for {opp['duration']:.0f}s.
> Consider using matrix strategy to run parallel jobs - same cost, faster completion.

'''
    
    if idle_analysis and idle_analysis['idle_percentage'] > 10:
        section += f'''
### ⏳ Idle Time Detected

**{idle_analysis['total_idle_seconds']:.0f}s ({idle_analysis['idle_percentage']:.0f}%)** of job time had minimal CPU activity.

Common causes:
- Waiting for package downloads (use caching)
- Sequential steps that could be parallelized
- Inefficient workflow design

'''
    
    # Decision helper - no self-hosted recommendation
    section += '''
### 🎯 Optimization Strategy

GitHub hosted runners are cost-effective when properly utilized:

'''
    
    # Check for overutilization (CPU or Memory at 90%+)
    is_overutilized = (utilization['max_cpu_pct'] >= 90 or utilization['max_mem_pct'] >= 90)
    
    if is_overutilized:
        section += f'''
**Priority: Upgrade to Larger Runner ⚠️**

Your job is **straining resources** on the current runner:
- CPU peaked at **{utilization['max_cpu_pct']:.1f}%** (avg: {utilization['avg_cpu_pct']:.1f}%)
- Memory peaked at **{utilization['max_mem_pct']:.1f}%** (avg: {utilization['avg_mem_pct']:.1f}%)

**Recommended Actions:**
1. **Upgrade runner** - Larger instance will reduce execution time and improve reliability
2. **Optimize code** - Profile and reduce computational complexity if possible
3. **Monitor cost/time trade-off** - Faster runs may offset higher per-minute cost

**Compare runner options:** [GitHub Actions Runner Pricing](https://docs.github.com/en/enterprise-cloud@latest/billing/reference/actions-runner-pricing)

See right-sizing suggestions below for cost comparison.

'''
    elif utilization['score'] < 30:
        section += f'''
**Priority: High Utilization Improvement**

1. **Right-size runner** - Use smaller instance (check suggestion above)
2. **Parallelize jobs** - Use matrix builds for independent steps  
3. **Optimize caching** - Cache dependencies to reduce download time
4. **Check for bottlenecks** - Identify and optimize slow sequential steps

With these optimizations, you can typically achieve 50-70% utilization and reduce costs by 30-50%.

'''
    elif utilization['score'] >= 70:
        section += f'''
**Status: Well-Optimized ✅**

Your runner utilization is excellent at {utilization['score']:.0f}%. Continue:
- Monitoring trends over time
- Considering larger runners only if hitting resource limits
- Regular performance reviews

'''
    else:
        section += f'''
**Status: Good with Room for Improvement**

Current utilization ({utilization['score']:.0f}%) is healthy. Next steps:
- Implement parallelization for slow steps
- Review caching strategies
- Monitor if you need a larger runner as usage grows

'''
    
    return section

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

| Step | Duration | Avg CPU | Max CPU | Avg Mem | Max Mem |
|:-----|:--------:|:-------:|:-------:|:-------:|:-------:|
'''
    
    for step in analyzed_steps:
        is_heavy = step == heaviest_cpu
        badge = "🔥 " if is_heavy else ""
        section += f"| {badge}{step['name'][:25]} | {format_duration(step['duration'])} | {step['avg_cpu']:.1f}% | {step['max_cpu']:.1f}% | {step['avg_mem']:.1f}% | {step['max_mem']:.1f}% |\n"
    
    section += f'''

> 💡 **Insights:** Longest step: **{longest_step['name'][:25]}** ({format_duration(longest_step['duration'])}) • 
> Heaviest CPU: **{heaviest_cpu['name'][:25]}** ({heaviest_cpu['avg_cpu']:.1f}%)

'''
    
    return section

def generate_report(data):
    """Generate the full visual report with Mermaid diagrams."""
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
    overall_text = {'critical': 'Needs Attention', 'warning': 'Warning', 'good': 'Healthy'}[overall]
    
    # Create resource bars
    def create_resource_bar(value):
        percent = min(value, 100) if value >= 0 else 0
        filled = int(percent / 5)
        if percent >= 85:
            indicator = "🔴"
        elif percent >= 60:
            indicator = "🟡"
        else:
            indicator = "🟢"
        bar = "█" * filled + "░" * (20 - filled)
        return f"{indicator} `{bar}` {value:.1f}%"
    
    cpu_bar = create_resource_bar(cpu_values[-1] if cpu_values else 0)
    mem_bar = create_resource_bar(mem_values[-1] if mem_values else 0)
    
    # Create Mermaid pie charts
    def create_mermaid_pie_chart(title, data):
        chart = f'```mermaid\npie showData title {title}\n'
        for label, value in data.items():
            if value > 0:
                chart += f'    "{label}" : {value:.1f}\n'
        chart += '```\n'
        return chart
    
    resource_pie = create_mermaid_pie_chart("Resource Utilization", {
        "CPU Used": avg_cpu,
        "CPU Idle": 100 - avg_cpu,
    })
    
    memory_pie = create_mermaid_pie_chart("Memory Utilization", {
        "Used": avg_mem,
        "Available": 100 - avg_mem,
    })
    
    # Create time series chart with every 6-second interval for clean labels
    sample_count = len(samples)
    interval = data.get("interval", 2)
    
    # Calculate indices for every 6 seconds (or skip if interval is different)
    label_interval_seconds = 6
    label_step = max(1, int(label_interval_seconds / interval))
    
    # Build label indices starting from 0 and going to end
    label_indices = list(range(0, sample_count, label_step))
    if label_indices[-1] != sample_count - 1:
        label_indices.append(sample_count - 1)
    
    # Generate labels for every 6-second point
    x_labels = [f'"{int(i * interval)}"' for i in label_indices]
    
    # All data points for smooth lines
    all_cpu_str = ", ".join([f"{v:.1f}" for v in cpu_values])
    all_mem_str = ", ".join([f"{v:.1f}" for v in mem_values])
    
    xy_chart = ""
    if len(x_labels) >= 2:
        xy_chart = f'''| 🔵 CPU % | 🟢 Memory % |
|:--------:|:-----------:|
| Peak: {max_cpu:.1f}% / Avg: {avg_cpu:.1f}% | Peak: {max_mem:.1f}% / Avg: {avg_mem:.1f}% |

```mermaid
xychart-beta
    title "CPU & Memory Usage Over Time"
    x-axis "Time (seconds)" [{", ".join(x_labels)}]
    y-axis "Usage %" 0 --> 100
    line [{all_cpu_str}]
    line [{all_mem_str}]
```

'''
    
    # Get context info
    ctx = data.get('github_context', {})
    initial = data.get('initial_snapshot', {})
    final_snapshot = data.get('final_snapshot', {})
    
    # Build report
    report = f'''# 🖥️ Runner Telemetry Dashboard

> **{overall_icon} Status: {overall_text}** • Duration: {format_duration(duration)} • Samples: {len(samples)}

---

## 📊 Quick Overview

| | Current | Peak | Average |
|:--|:-------:|:----:|:-------:|
| **CPU** {cpu_icon} | {cpu_bar} | {max_cpu:.1f}% | {avg_cpu:.1f}% |
| **Memory** {mem_icon} | {mem_bar} | {max_mem:.1f}% | {avg_mem:.1f}% |
| **Load** {load_icon} | {load_1m[-1]:.2f} | {max_load:.2f} | {avg_load:.2f} |

---

## 📈 Resource Usage Over Time

{xy_chart}

---

## 🔄 Resource Distribution

<table>
<tr>
<td width="50%">

{resource_pie}

</td>
<td width="50%">

{memory_pie}

</td>
</tr>
</table>

---

## ⚡ Performance Metrics

| Metric | Status | Peak | Average |
|:-------|:------:|:----:|:-------:|
| **I/O Wait** | {iowait_icon} | {max_iowait:.1f}% | {avg_iowait:.1f}% |
| **CPU Steal** | {steal_icon} | {max_steal:.1f}% | {avg_steal:.1f}% |
| **Swap Usage** | {swap_icon} | {max_swap:.1f}% | {avg_swap:.1f}% |

---

## 💾 I/O Summary

| Metric | Total | Avg Rate |
|:-------|------:|---------:|
| 📥 **Disk Read** | {format_bytes(total_disk_read * 1024 * 1024)} | {format_bytes(sum(disk_read) / len(disk_read) * 1024 * 1024)}/s |
| 📤 **Disk Write** | {format_bytes(total_disk_write * 1024 * 1024)} | {format_bytes(sum(disk_write) / len(disk_write) * 1024 * 1024)}/s |
| 🌐 **Network RX** | {format_bytes(total_net_rx * 1024 * 1024)} | {format_bytes(sum(net_rx) / len(net_rx) * 1024 * 1024)}/s |
| 🌐 **Network TX** | {format_bytes(total_net_tx * 1024 * 1024)} | {format_bytes(sum(net_tx) / len(net_tx) * 1024 * 1024)}/s |

'''

    # Add per-step analysis if we have steps
    analyzed_steps = analyze_steps(data)
    steps_section = generate_steps_section(data)
    if steps_section:
        report += steps_section
    
    # Add utilization and cost analysis section (KEY FEATURE)
    utilization_section = generate_utilization_section(data, analyzed_steps)
    if utilization_section:
        report += utilization_section
    
    # System information section
    report += f'''
---

## 🖥️ Runner Information

| Component | Details |
|:----------|:--------|
| **Runner** | {ctx.get('runner_name', 'GitHub Hosted')} |
| **OS** | {ctx.get('runner_os', 'Linux')} |
| **Architecture** | {ctx.get('runner_arch', 'X64')} |
| **Total Memory** | {initial.get('memory', {}).get('total_mb', 0):,} MB |
| **CPU Cores** | {initial.get('cpu_count', 'N/A')} |

'''
    
    # Top processes
    top_procs = final_snapshot.get('processes', initial.get('processes', {}))
    if top_procs.get('by_cpu'):
        report += '''
<details>
<summary>🔝 Top Processes</summary>

| Process | CPU % | Memory % |
|:--------|------:|---------:|
'''
        for p in top_procs.get('by_cpu', [])[:5]:
            cmd = p['command'].split('/')[-1].split()[0][:30]
            report += f"| `{cmd}` | {p['cpu']:.1f}% | {p['mem']:.1f}% |\n"
        report += '\n</details>\n'
    
    # Recommendations
    recommendations = []
    if max_cpu > THRESHOLDS['cpu_critical']:
        recommendations.append(f"⚠️ **High CPU Usage:** Peak reached {max_cpu:.1f}%. Consider using a larger runner or optimizing compute-heavy operations.")
    if max_mem > THRESHOLDS['mem_critical']:
        recommendations.append(f"⚠️ **High Memory Usage:** Peak reached {max_mem:.1f}%. Watch for OOM issues or consider runners with more RAM.")
    if max_iowait > THRESHOLDS['iowait_warning']:
        recommendations.append(f"⚠️ **High I/O Wait:** Disk operations may be bottlenecking performance.")
    if max_steal > THRESHOLDS['steal_warning']:
        recommendations.append(f"⚠️ **CPU Steal Detected:** The runner may be oversubscribed.")
    
    if recommendations:
        report += '\n---\n\n## 💡 Recommendations\n\n'
        for rec in recommendations:
            report += f"- {rec}\n"
    else:
        report += '\n---\n\n> ✅ **All metrics within healthy thresholds**\n'
    
    report += '''
---

<sub>Generated by [Runner Telemetry Action](https://github.com/tsviz/actions-runner-telemetry)</sub>
'''
    
    return report


def generate_html_dashboard(data):
    """Generate an interactive HTML dashboard with Chart.js."""
    samples = data.get('samples', [])
    
    if not samples:
        return "<html><body><h1>No data collected</h1></body></html>"
    
    # Extract data
    start_time = data.get('start_time', 0)
    timestamps = [(s['timestamp'] - start_time) for s in samples]
    cpu_values = [s['cpu_percent'] for s in samples]
    mem_values = [s['memory']['percent'] for s in samples]
    load_values = [s['load']['load_1m'] for s in samples]
    disk_read = [s['disk_io']['read_rate'] / (1024*1024) for s in samples]
    disk_write = [s['disk_io']['write_rate'] / (1024*1024) for s in samples]
    
    # Calculate stats
    avg_cpu = sum(cpu_values) / len(cpu_values)
    max_cpu = max(cpu_values)
    avg_mem = sum(mem_values) / len(mem_values)
    max_mem = max(mem_values)
    duration = data.get('duration', 0)
    
    ctx = data.get('github_context', {})
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Runner Telemetry Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --bg-primary: #0d1117;
            --bg-secondary: #161b22;
            --bg-tertiary: #21262d;
            --text-primary: #f0f6fc;
            --text-secondary: #8b949e;
            --border-color: #30363d;
            --accent-blue: #58a6ff;
            --accent-green: #3fb950;
            --accent-yellow: #d29922;
            --accent-red: #f85149;
            --accent-purple: #a371f7;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            padding: 24px;
            min-height: 100vh;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border-color);
        }}
        .header h1 {{ font-size: 24px; font-weight: 600; }}
        .header .meta {{ color: var(--text-secondary); font-size: 14px; }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .stat-card {{
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 16px;
        }}
        .stat-card .label {{ color: var(--text-secondary); font-size: 12px; text-transform: uppercase; }}
        .stat-card .value {{ font-size: 28px; font-weight: 600; margin-top: 4px; }}
        .stat-card .detail {{ color: var(--text-secondary); font-size: 13px; margin-top: 4px; }}
        .stat-card.good .value {{ color: var(--accent-green); }}
        .stat-card.warning .value {{ color: var(--accent-yellow); }}
        .stat-card.critical .value {{ color: var(--accent-red); }}
        .chart-container {{
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 16px;
        }}
        .chart-container h3 {{
            font-size: 14px;
            font-weight: 500;
            margin-bottom: 16px;
            color: var(--text-secondary);
        }}
        .chart-row {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 16px;
        }}
        canvas {{ max-height: 300px; }}
        .footer {{
            margin-top: 32px;
            padding-top: 16px;
            border-top: 1px solid var(--border-color);
            text-align: center;
            color: var(--text-secondary);
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🖥️ Runner Telemetry Dashboard</h1>
            <div class="meta">
                Duration: {format_duration(duration)} • 
                {len(samples)} samples • 
                {ctx.get('runner_os', 'Linux')} / {ctx.get('runner_arch', 'X64')}
            </div>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card {'critical' if max_cpu > 85 else 'warning' if max_cpu > 60 else 'good'}">
                <div class="label">Peak CPU</div>
                <div class="value">{max_cpu:.1f}%</div>
                <div class="detail">Avg: {avg_cpu:.1f}%</div>
            </div>
            <div class="stat-card {'critical' if max_mem > 90 else 'warning' if max_mem > 70 else 'good'}">
                <div class="label">Peak Memory</div>
                <div class="value">{max_mem:.1f}%</div>
                <div class="detail">Avg: {avg_mem:.1f}%</div>
            </div>
            <div class="stat-card good">
                <div class="label">Duration</div>
                <div class="value">{format_duration(duration)}</div>
                <div class="detail">{len(samples)} samples collected</div>
            </div>
            <div class="stat-card good">
                <div class="label">Max Load</div>
                <div class="value">{max(load_values):.2f}</div>
                <div class="detail">Avg: {sum(load_values)/len(load_values):.2f}</div>
            </div>
        </div>
        
        <div class="chart-container">
            <h3>📈 CPU & Memory Over Time</h3>
            <canvas id="cpuMemChart"></canvas>
        </div>
        
        <div class="chart-row">
            <div class="chart-container">
                <h3>⚡ System Load</h3>
                <canvas id="loadChart"></canvas>
            </div>
            <div class="chart-container">
                <h3>💾 Disk I/O (MB/s)</h3>
                <canvas id="diskChart"></canvas>
            </div>
        </div>
        
        <div class="footer">
            Generated by <a href="https://github.com/tsviz/actions-runner-telemetry" style="color: var(--accent-blue);">Runner Telemetry Action</a>
        </div>
    </div>
    
    <script>
        const timestamps = {json.dumps(timestamps)};
        const cpuData = {json.dumps(cpu_values)};
        const memData = {json.dumps(mem_values)};
        const loadData = {json.dumps(load_values)};
        const diskReadData = {json.dumps(disk_read)};
        const diskWriteData = {json.dumps(disk_write)};
        
        const chartDefaults = {{
            responsive: true,
            maintainAspectRatio: true,
            plugins: {{
                legend: {{ labels: {{ color: '#8b949e' }} }}
            }},
            scales: {{
                x: {{ 
                    grid: {{ color: '#21262d' }},
                    ticks: {{ color: '#8b949e' }}
                }},
                y: {{ 
                    grid: {{ color: '#21262d' }},
                    ticks: {{ color: '#8b949e' }}
                }}
            }}
        }};
        
        // CPU & Memory Chart
        new Chart(document.getElementById('cpuMemChart'), {{
            type: 'line',
            data: {{
                labels: timestamps.map(t => t.toFixed(0) + 's'),
                datasets: [
                    {{
                        label: 'CPU %',
                        data: cpuData,
                        borderColor: '#58a6ff',
                        backgroundColor: 'rgba(88, 166, 255, 0.1)',
                        fill: true,
                        tension: 0.3
                    }},
                    {{
                        label: 'Memory %',
                        data: memData,
                        borderColor: '#a371f7',
                        backgroundColor: 'rgba(163, 113, 247, 0.1)',
                        fill: true,
                        tension: 0.3
                    }}
                ]
            }},
            options: {{ ...chartDefaults, scales: {{ ...chartDefaults.scales, y: {{ ...chartDefaults.scales.y, max: 100 }} }} }}
        }});
        
        // Load Chart
        new Chart(document.getElementById('loadChart'), {{
            type: 'line',
            data: {{
                labels: timestamps.map(t => t.toFixed(0) + 's'),
                datasets: [{{
                    label: 'Load 1m',
                    data: loadData,
                    borderColor: '#d29922',
                    backgroundColor: 'rgba(210, 153, 34, 0.1)',
                    fill: true,
                    tension: 0.3
                }}]
            }},
            options: chartDefaults
        }});
        
        // Disk I/O Chart
        new Chart(document.getElementById('diskChart'), {{
            type: 'line',
            data: {{
                labels: timestamps.map(t => t.toFixed(0) + 's'),
                datasets: [
                    {{
                        label: 'Read MB/s',
                        data: diskReadData,
                        borderColor: '#3fb950',
                        tension: 0.3
                    }},
                    {{
                        label: 'Write MB/s',
                        data: diskWriteData,
                        borderColor: '#f85149',
                        tension: 0.3
                    }}
                ]
            }},
            options: chartDefaults
        }});
    </script>
</body>
</html>'''
    
    return html


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
    
    # Try to load JSON with robust error handling
    data = None
    try:
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        # Try to recover by reading line by line and finding valid JSON
        print(f"⚠️  Failed to read telemetry data, using partial data")
        print(f"   Error: {e}")
        try:
            with open(DATA_FILE, 'r') as f:
                content = f.read()
                # Try to find and parse the last complete JSON object
                for i in range(len(content) - 1, -1, -1):
                    if content[i] == '}':
                        try:
                            data = json.loads(content[:i+1])
                            print(f"✅ Recovered partial telemetry data")
                            break
                        except json.JSONDecodeError:
                            continue
        except Exception as e2:
            print(f"   Could not recover: {e2}")
    
    if data is None:
        print("Error: Could not load telemetry data")
        sys.exit(1)
    
    # Generate markdown report for step summary
    report = generate_report(data)
    
    # Write to GITHUB_STEP_SUMMARY if available
    summary_file = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary_file:
        with open(summary_file, 'a') as f:
            f.write(report)
        print("✅ Report written to GitHub Step Summary")
    
    # Save markdown report
    output_dir = os.environ.get('GITHUB_WORKSPACE', '/github/workspace')
    report_path = os.path.join(output_dir, 'telemetry-report.md')
    
    try:
        with open(report_path, 'w') as f:
            f.write(report)
        print(f"✅ Markdown report saved to {report_path}")
    except:
        with open('telemetry-report.md', 'w') as f:
            f.write(report)
    
    # Generate and save HTML dashboard
    html_dashboard = generate_html_dashboard(data)
    html_path = os.path.join(output_dir, 'telemetry-dashboard.html')
    try:
        with open(html_path, 'w') as f:
            f.write(html_dashboard)
        print(f"✅ HTML dashboard saved to {html_path}")
    except:
        with open('telemetry-dashboard.html', 'w') as f:
            f.write(html_dashboard)
    
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
