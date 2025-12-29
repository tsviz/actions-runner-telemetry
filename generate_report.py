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

# GitHub Hosted Runner Specifications with accurate pricing (Jan 1, 2026+)
# https://docs.github.com/en/enterprise-cloud@latest/billing/reference/actions-runner-pricing
# 
# Note: Specifications vary by plan and repository visibility:
# - Free tier: Standard runners only (ubuntu-latest 2-core, windows-latest 2-core, macOS available)
# - GitHub Team/Enterprise Cloud: Larger runners available (4-core, 8-core, etc.)
# Larger runners are marked with 'is_larger': True flag.
GITHUB_RUNNERS = {
    # Standard Linux runners
    # NOTE: Specs vary by repo visibility:
    # - Public repos: 4 cores, 16GB RAM (free)
    # - Private repos: 2 cores, 7GB RAM (paid, $0.006/min)
    # The specs below are for PUBLIC repos (larger resources, zero cost).
    # For private repos, adjust the cost_per_min based on repo visibility.
    'ubuntu-slim': {'vcpus': 1, 'ram_gb': 5, 'cost_per_min': 0, 'storage_gb': 14, 'name': 'Linux 1-core (ubuntu-slim)', 'sku': 'linux_slim', 'is_free_public': True},
    'ubuntu-latest': {'vcpus': 4, 'ram_gb': 16, 'cost_per_min': 0, 'storage_gb': 14, 'name': 'Linux 4-core (ubuntu-latest)', 'sku': 'linux', 'is_free_public': True, 'private_vcpus': 2, 'private_ram_gb': 7, 'private_cost_per_min': 0.006},
    'ubuntu-24.04': {'vcpus': 4, 'ram_gb': 16, 'cost_per_min': 0, 'storage_gb': 14, 'name': 'Linux 4-core (ubuntu-24.04)', 'sku': 'linux', 'is_free_public': True, 'private_vcpus': 2, 'private_ram_gb': 7, 'private_cost_per_min': 0.006},
    'ubuntu-22.04': {'vcpus': 4, 'ram_gb': 16, 'cost_per_min': 0, 'storage_gb': 14, 'name': 'Linux 4-core (ubuntu-22.04)', 'sku': 'linux', 'is_free_public': True, 'private_vcpus': 2, 'private_ram_gb': 7, 'private_cost_per_min': 0.006},
    
    # Larger Linux x64 runners (GitHub Team/Enterprise Cloud)
    'linux-4-core': {'vcpus': 4, 'ram_gb': 16, 'cost_per_min': 0.012, 'storage_gb': 14, 'name': 'Linux 4-core Larger Runner', 'sku': 'linux_4_core', 'is_larger': True},
    'linux-8-core': {'vcpus': 8, 'ram_gb': 32, 'cost_per_min': 0.022, 'storage_gb': 14, 'name': 'Linux 8-core Larger Runner', 'sku': 'linux_8_core', 'is_larger': True},
    
    # Larger Linux ARM64 runners (GitHub Team/Enterprise Cloud)
    'linux-4-core-arm': {'vcpus': 4, 'ram_gb': 16, 'cost_per_min': 0.008, 'storage_gb': 14, 'name': 'Linux ARM 4-core Larger Runner', 'sku': 'linux_4_core_arm', 'is_larger': True},
    'linux-8-core-arm': {'vcpus': 8, 'ram_gb': 32, 'cost_per_min': 0.014, 'storage_gb': 14, 'name': 'Linux ARM 8-core Larger Runner', 'sku': 'linux_8_core_arm', 'is_larger': True},
    
    # Standard Windows runners
    # NOTE: Specs vary by repo visibility:
    # - Public repos: 4 cores, 16GB RAM (free)
    # - Private repos: 2 cores, 7GB RAM (paid, $0.010/min)
    'windows-latest': {'vcpus': 4, 'ram_gb': 16, 'cost_per_min': 0, 'storage_gb': 14, 'name': 'Windows 4-core (windows-latest)', 'sku': 'windows', 'is_free_public': True, 'private_vcpus': 2, 'private_ram_gb': 7, 'private_cost_per_min': 0.010},
    'windows-2025': {'vcpus': 4, 'ram_gb': 16, 'cost_per_min': 0, 'storage_gb': 14, 'name': 'Windows 4-core (windows-2025)', 'sku': 'windows', 'is_free_public': True, 'private_vcpus': 2, 'private_ram_gb': 7, 'private_cost_per_min': 0.010},
    'windows-2022': {'vcpus': 4, 'ram_gb': 16, 'cost_per_min': 0, 'storage_gb': 14, 'name': 'Windows 4-core (windows-2022)', 'sku': 'windows', 'is_free_public': True, 'private_vcpus': 2, 'private_ram_gb': 7, 'private_cost_per_min': 0.010},
    
    # Larger Windows x64 runners (GitHub Team/Enterprise Cloud)
    'windows-4-core': {'vcpus': 4, 'ram_gb': 16, 'cost_per_min': 0.022, 'storage_gb': 14, 'name': 'Windows 4-core Larger Runner', 'sku': 'windows_4_core', 'is_larger': True},
    'windows-8-core': {'vcpus': 8, 'ram_gb': 32, 'cost_per_min': 0.042, 'storage_gb': 14, 'name': 'Windows 8-core Larger Runner', 'sku': 'windows_8_core', 'is_larger': True},
    
    # Larger Windows ARM64 runners (GitHub Team/Enterprise Cloud)
    'windows-4-core-arm': {'vcpus': 4, 'ram_gb': 16, 'cost_per_min': 0.014, 'storage_gb': 14, 'name': 'Windows ARM 4-core Larger Runner', 'sku': 'windows_4_core_arm', 'is_larger': True},
    'windows-8-core-arm': {'vcpus': 8, 'ram_gb': 32, 'cost_per_min': 0.026, 'storage_gb': 14, 'name': 'Windows ARM 8-core Larger Runner', 'sku': 'windows_8_core_arm', 'is_larger': True},
    
    # Standard macOS Intel runners (free tier, all repositories)
    'macos-13': {'vcpus': 4, 'ram_gb': 14, 'cost_per_min': 0.062, 'storage_gb': 14, 'name': 'macOS 4-core Intel (macos-13)', 'sku': 'macos'},
    'macos-15-intel': {'vcpus': 4, 'ram_gb': 14, 'cost_per_min': 0.062, 'storage_gb': 14, 'name': 'macOS 4-core Intel (macos-15-intel)', 'sku': 'macos'},
    
    # Standard macOS Apple Silicon (M1) runners (free tier, all repositories)
    'macos-latest': {'vcpus': 3, 'ram_gb': 7, 'cost_per_min': 0.028, 'storage_gb': 14, 'name': 'macOS 3-core M1 (macos-latest)', 'sku': 'macos'},
    'macos-14': {'vcpus': 3, 'ram_gb': 7, 'cost_per_min': 0.028, 'storage_gb': 14, 'name': 'macOS 3-core M1 (macos-14)', 'sku': 'macos'},
    'macos-15': {'vcpus': 3, 'ram_gb': 7, 'cost_per_min': 0.028, 'storage_gb': 14, 'name': 'macOS 3-core M1 (macos-15)', 'sku': 'macos'},
    
    # Larger macOS Intel runners (GitHub Team/Enterprise Cloud)
    'macos-13-large': {'vcpus': 12, 'ram_gb': 30, 'cost_per_min': 0.077, 'storage_gb': 14, 'name': 'macOS 12-core Large Intel (macos-13-large)', 'sku': 'macos_l', 'is_larger': True},
    'macos-14-large': {'vcpus': 12, 'ram_gb': 30, 'cost_per_min': 0.077, 'storage_gb': 14, 'name': 'macOS 12-core Large Intel (macos-14-large)', 'sku': 'macos_l', 'is_larger': True},
    'macos-15-large': {'vcpus': 12, 'ram_gb': 30, 'cost_per_min': 0.077, 'storage_gb': 14, 'name': 'macOS 12-core Large Intel (macos-15-large)', 'sku': 'macos_l', 'is_larger': True},
    'macos-latest-large': {'vcpus': 12, 'ram_gb': 30, 'cost_per_min': 0.077, 'storage_gb': 14, 'name': 'macOS 12-core Large Intel (macos-latest-large)', 'sku': 'macos_l', 'is_larger': True},
    
    # Larger macOS Apple Silicon (M2) XLarge runners (GitHub Team/Enterprise Cloud)
    'macos-13-xlarge': {'vcpus': 5, 'ram_gb': 14, 'cost_per_min': 0.102, 'storage_gb': 14, 'name': 'macOS 5-core XLarge M2 (macos-13-xlarge)', 'sku': 'macos_xl', 'is_larger': True},
    'macos-14-xlarge': {'vcpus': 5, 'ram_gb': 14, 'cost_per_min': 0.102, 'storage_gb': 14, 'name': 'macOS 5-core XLarge M2 (macos-14-xlarge)', 'sku': 'macos_xl', 'is_larger': True},
    'macos-15-xlarge': {'vcpus': 5, 'ram_gb': 14, 'cost_per_min': 0.102, 'storage_gb': 14, 'name': 'macOS 5-core XLarge M2 (macos-15-xlarge)', 'sku': 'macos_xl', 'is_larger': True},
    'macos-latest-xlarge': {'vcpus': 5, 'ram_gb': 14, 'cost_per_min': 0.102, 'storage_gb': 14, 'name': 'macOS 5-core XLarge M2 (macos-latest-xlarge)', 'sku': 'macos_xl', 'is_larger': True},
}

# Utilization thresholds for scoring
UTILIZATION_THRESHOLDS = {
    'excellent': 70,  # 70%+ utilization = excellent
    'good': 50,       # 50-70% = good
    'fair': 30,       # 30-50% = fair
    'poor': 0,        # <30% = poor (wasting resources)
}

# Free (public repo) runner labels - these are free on public repos
FREE_RUNNER_LABELS = {
    'ubuntu-latest', 'ubuntu-24.04', 'ubuntu-22.04',
    'windows-latest', 'windows-2025', 'windows-2022',
    'macos-latest', 'macos-14', 'macos-15', 'macos-26',
    'macos-13', 'macos-15-intel',
    'ubuntu-slim', 'ubuntu-24.04-arm', 'ubuntu-22.04-arm',
    'windows-11-arm'
}

def is_runner_free(runner_type, is_public_repo=None, requested_runner_name=None):
    """Determine if a runner is free to use (public repo on standard runner).
    
    Args:
        runner_type: The detected runner type name (e.g., 'ubuntu-latest', 'linux-4-core')
        is_public_repo: Optional boolean. If None, auto-detect from GitHub context.
        requested_runner_name: Optional name of the requested runner (from RUNNER_NAME env).
                              If provided and matches a standard runner, use that for billing.
    
    Returns:
        True if runner is free, False if paid.
    """
    # Auto-detect repo visibility from GitHub context if not provided
    if is_public_repo is None:
        # Check environment variables set by GitHub Actions
        repo_visibility = os.environ.get('REPO_VISIBILITY', 'auto')
        if repo_visibility == 'public':
            is_public_repo = True
        elif repo_visibility == 'private':
            is_public_repo = False
        else:
            # Auto-detect: use GitHub's environment variable (defaults to private for safety)
            github_repo_visibility = os.environ.get('GITHUB_REPOSITORY_VISIBILITY', 'private').lower()
            is_public_repo = (github_repo_visibility == 'public')
    
    # Check requested runner name first (what they asked for, not what we detected)
    # This takes precedence because billing is based on what they requested
    if requested_runner_name:
        requested_name = requested_runner_name.lower()
        # Explicitly requested larger runner = always paid
        if requested_name in ['linux-4-core', 'linux-8-core', 'linux-4-core-arm', 'linux-8-core-arm',
                             'windows-4-core', 'windows-8-core', 'windows-4-core-arm', 'windows-8-core-arm',
                             'macos-13-large', 'macos-14-large', 'macos-15-large', 'macos-latest-large',
                             'macos-13-xlarge', 'macos-14-xlarge', 'macos-15-xlarge', 'macos-latest-xlarge']:
            return False
        # Explicitly requested standard runner on public repo = free
        if is_public_repo and requested_name in FREE_RUNNER_LABELS:
            return True
        # Explicitly requested standard runner on private repo = paid
        if not is_public_repo and requested_name in FREE_RUNNER_LABELS:
            return False
    
    # Fallback: check detected runner type
    # Larger runners are always paid
    if runner_type in ['linux-4-core', 'linux-8-core', 'linux-4-core-arm', 'linux-8-core-arm',
                       'windows-4-core', 'windows-8-core', 'windows-4-core-arm', 'windows-8-core-arm',
                       'macos-13-large', 'macos-14-large', 'macos-15-large', 'macos-latest-large',
                       'macos-13-xlarge', 'macos-14-xlarge', 'macos-15-xlarge', 'macos-latest-xlarge']:
        return False
    
    # Standard runners are free only on public repos
    if is_public_repo and runner_type in FREE_RUNNER_LABELS:
        return True
    
    return False

def get_runner_billing_context(runner_type, is_public_repo=None, requested_runner_name=None):
    """Get billing information for the runner context.
    
    Returns:
        dict with keys: is_free, is_paid, repo_type, recommendation_type
    """
    is_free = is_runner_free(runner_type, is_public_repo, requested_runner_name)
    
    if is_public_repo is None:
        repo_visibility = os.environ.get('REPO_VISIBILITY', 'auto')
        if repo_visibility == 'public':
            is_public_repo = True
        elif repo_visibility == 'private':
            is_public_repo = False
        else:
            is_public_repo = False
    
    return {
        'is_free': is_free,
        'is_paid': not is_free,
        'repo_type': 'public' if is_public_repo else 'private',
        'recommendation_type': 'speed' if is_free else 'cost-savings'
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

def detect_runner_type(data, is_public_repo=None):
    """Detect the runner type by matching actual system specs to known GitHub runners.
    
    Uses CPU cores, memory, and OS to find the best match in GITHUB_RUNNERS.
    Returns either a known GitHub runner key (e.g. 'linux-4-core') or 
    a custom runner identifier for self-hosted runners.
    
    Args:
        data: Telemetry data dict
        is_public_repo: Optional bool. If True, prefer standard runners for public repos
                        (since GitHub gives standard runners even if HW has more cores)
    """
    ctx = data.get('github_context', {})
    runner_os = ctx.get('runner_os', 'Linux').lower()
    runner_name = ctx.get('runner_name', '').lower()
    initial = data.get('initial_snapshot', {})
    cpu_count = initial.get('cpu_count', 2)
    memory_mb = initial.get('memory_total_mb', 7000)  # Default to ~7GB
    memory_gb = memory_mb / 1024
    
    # Check if this is a known custom/self-hosted runner
    # Custom runner names typically won't match GitHub's standard patterns
    is_custom_runner = (
        runner_name and 
        runner_name not in GITHUB_RUNNERS and
        'github actions' not in runner_name  # GitHub Actions runners have generic names
    )
    
    if is_custom_runner:
        # For custom runners, return the runner name as identifier
        return runner_name
    
    # Match based on actual system specs (CPU cores, memory, OS)
    # Find the best matching GitHub runner by specs
    best_match = None
    best_match_score = float('inf')
    
    for runner_key, specs in GITHUB_RUNNERS.items():
        # For public repos, skip larger runners - assume standard runner if it's the best match
        if is_public_repo and specs.get('is_larger'):
            continue
        
        # Match by SKU prefix (e.g., 'linux', 'windows', 'macos')
        sku = specs.get('sku', '')
        spec_cores = specs.get('vcpus', 2)
        spec_memory = specs.get('ram_gb', 7)
        
        # Check OS match - be flexible with SKU parsing
        sku_lower = sku.lower()
        if 'linux' in sku_lower:
            os_matches = 'linux' in runner_os
        elif 'windows' in sku_lower:
            os_matches = 'windows' in runner_os
        elif 'macos' in sku_lower:
            os_matches = 'macos' in runner_os
        else:
            os_matches = False
        
        # Only match same OS type
        if not os_matches:
            continue
        
        # Score based on how close the specs are
        # Prefer exact matches, but also consider close matches
        core_diff = abs(spec_cores - cpu_count)
        memory_diff = abs(spec_memory - memory_gb)
        
        # Lower score = better match
        # Weight core matching more heavily than memory (3x weight on exact core matches)
        # If cores match exactly, heavily favor that runner
        if core_diff == 0:
            match_score = memory_diff * 0.1  # Cores match exactly, just fine-tune with memory
        else:
            match_score = (core_diff * 3) + (memory_diff * 0.5)
        
        if match_score < best_match_score:
            best_match_score = match_score
            best_match = runner_key
    
    # If we found a good match (score < 15 allows for some variance), return it
    if best_match and best_match_score < 15:
        return best_match
    
    # Fallback: determine runner by CPU cores if no good match found
    # For public repos, default to standard runners
    if 'linux' in runner_os:
        if is_public_repo:
            # Public repos get standard runners - default to ubuntu-latest
            if cpu_count <= 1:
                return 'ubuntu-slim'
            else:
                return 'ubuntu-latest'
        else:
            # Private repos could be using larger runners
            if cpu_count <= 1:
                return 'ubuntu-slim'
            elif cpu_count >= 8:
                return 'linux-8-core'
            elif cpu_count >= 4:
                return 'linux-4-core'
            else:
                return 'ubuntu-latest'
    elif 'windows' in runner_os:
        if cpu_count >= 8:
            return 'windows-8-core'
        elif cpu_count >= 4:
            return 'windows-4-core'
        else:
            return 'windows-latest'
    elif 'macos' in runner_os:
        if cpu_count >= 12:
            return 'macos-13-large'
        elif cpu_count >= 5:
            return 'macos-latest-xlarge'
        else:
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
    """Calculate cost analysis and potential savings.
    
    Uses the REQUESTED runner type (what they asked for in runs-on:) for billing,
    not the detected type (which might be different hardware).
    """
    if not utilization:
        return None
    
    duration_seconds = data.get('duration', 0)
    duration_minutes = max(1, math.ceil(duration_seconds / 60))  # GitHub rounds up to nearest minute
    
    # Determine repo visibility for runner detection
    ctx = data.get('github_context', {})
    repo_visibility = os.environ.get('REPO_VISIBILITY', 'auto').lower()
    
    # Determine if public or private repo
    if repo_visibility == 'public':
        is_public_repo = True
    elif repo_visibility == 'private':
        is_public_repo = False
    else:
        # Auto-detect: check GitHub's environment variable
        github_repo_visibility = os.environ.get('GITHUB_REPOSITORY_VISIBILITY', 'private').lower()
        is_public_repo = (github_repo_visibility == 'public')
    
    # Detect runner type, preferring standard runners for public repos
    detected_runner_type = detect_runner_type(data, is_public_repo=is_public_repo)
    runner_type = detected_runner_type
    
    runner_specs = GITHUB_RUNNERS.get(runner_type, GITHUB_RUNNERS['ubuntu-latest']).copy()
    
    # For private repos with free public runners, use the private specs and cost
    if not is_public_repo and runner_specs.get('is_free_public'):
        # Override specs and cost for private repo
        runner_specs['vcpus'] = runner_specs.get('private_vcpus', runner_specs['vcpus'])
        runner_specs['ram_gb'] = runner_specs.get('private_ram_gb', runner_specs['ram_gb'])
        runner_specs['cost_per_min'] = runner_specs.get('private_cost_per_min', runner_specs['cost_per_min'])
        # Update name to reflect private repo specs
        if 'name' in runner_specs and '4-core' in runner_specs['name']:
            runner_specs['name'] = runner_specs['name'].replace('4-core', '2-core')
    
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
        'detected_runner_type': detected_runner_type,  # Include detected type for reference
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

def recommend_runner_upgrade(max_cpu_pct, max_mem_pct, duration_seconds, current_runner_type='ubuntu-latest'):
    """Recommend a larger runner based on utilization, staying in same OS/arch family.
    
    Returns dict with:
    - recommended_runner: key in GITHUB_RUNNERS
    - reason: explanation
    - estimated_speedup: rough time savings estimate
    - cost_per_min: cost of recommended runner
    - current_cost_per_min: cost of current runner
    - speedup_factor: multiplier for speedup (e.g., 2.0 = 2x faster)
    - is_upgrade_possible: whether an upgrade is available
    """
    
    # Map current runner to upgrade path (same OS, larger size when available)
    # Note: GitHub's runner availability varies by plan:
    # - Free tier (standard): Ubuntu max 2 cores, Windows max 2 cores
    # - GitHub Team/Enterprise Cloud: Larger runners available (4-core, 8-core, etc.)
    upgrade_paths = {
        # Linux upgrades
        'ubuntu-slim': 'ubuntu-latest',  # 1-core to 2-core (always available)
        'ubuntu-latest': 'linux-4-core',  # 2-core to 4-core (requires GitHub Team+)
        'ubuntu-24.04': 'linux-4-core',   # 2-core to 4-core (requires GitHub Team+)
        'ubuntu-22.04': 'linux-4-core',   # 2-core to 4-core (requires GitHub Team+)
        
        # Larger Linux x64 upgrades
        'linux-4-core': 'linux-8-core',
        'linux-8-core': 'linux-8-core',  # Max standard larger runner
        
        # Larger Linux ARM upgrades
        'linux-4-core-arm': 'linux-8-core-arm',
        'linux-8-core-arm': 'linux-8-core-arm',
        
        # Windows upgrades
        'windows-latest': 'windows-4-core',  # 2-core to 4-core (requires GitHub Team+)
        'windows-2025': 'windows-4-core',    # 2-core to 4-core (requires GitHub Team+)
        'windows-2022': 'windows-4-core',    # 2-core to 4-core (requires GitHub Team+)
        
        # Larger Windows x64 upgrades
        'windows-4-core': 'windows-8-core',
        'windows-8-core': 'windows-8-core',  # Max standard larger runner
        
        # Larger Windows ARM upgrades
        'windows-4-core-arm': 'windows-8-core-arm',
        'windows-8-core-arm': 'windows-8-core-arm',
        
        # macOS Intel upgrades
        'macos-13': 'macos-13-large',
        'macos-15-intel': 'macos-15-large',
        
        # macOS Apple Silicon upgrades
        'macos-latest': 'macos-latest-xlarge',
        'macos-14': 'macos-14-xlarge',
        'macos-15': 'macos-15-xlarge',
        
        # macOS Large → XLarge
        'macos-13-large': 'macos-13-xlarge',
        'macos-14-large': 'macos-14-xlarge',
        'macos-15-large': 'macos-15-xlarge',
        'macos-latest-large': 'macos-latest-xlarge',
    }
    
    recommended = upgrade_paths.get(current_runner_type, None)
    
    # If upgrade path not found, try to intelligently suggest one
    if recommended is None:
        # Fallback: for any 2-core runner, suggest 4-core
        if 'windows' in current_runner_type.lower():
            recommended = 'windows-4-core'
        elif 'macos' in current_runner_type.lower():
            recommended = 'macos-13-large'
        else:
            # Default to linux 4-core for unknown runners
            recommended = 'linux-4-core'
    
    # Get current and recommended runner specs
    current_specs = GITHUB_RUNNERS.get(current_runner_type, {})
    recommended_specs = GITHUB_RUNNERS.get(recommended, {})
    
    # Get actual core counts
    current_cores = current_specs.get('vcpus', 2)
    recommended_cores = recommended_specs.get('vcpus', 2)
    current_cost_per_min = current_specs.get('cost_per_min', 0.006)
    recommended_cost_per_min = recommended_specs.get('cost_per_min', 0.006)
    
    # Check if upgrade is actually possible (recommended != current)
    is_upgrade_possible = recommended != current_runner_type
    
    # Additional fallback: if current is 2-core and recommended is also 2-core, force 4-core upgrade
    if not is_upgrade_possible and current_cores <= 2:
        # Current is a 2-core runner but couldn't find upgrade path
        # Force upgrade to 4-core variant
        if 'ubuntu' in current_runner_type.lower():
            recommended = 'linux-4-core'
        elif 'windows' in current_runner_type.lower():
            recommended = 'windows-4-core'
        # Re-fetch specs
        recommended_specs = GITHUB_RUNNERS.get(recommended, {})
        recommended_cores = recommended_specs.get('vcpus', 2)
        recommended_cost_per_min = recommended_specs.get('cost_per_min', 0.006)
        is_upgrade_possible = recommended != current_runner_type
    
    # Calculate speedup factor
    # Realistic speedup: assume near-linear scaling, but cap at 3x (diminishing returns)
    if is_upgrade_possible:
        core_ratio = recommended_cores / current_cores if current_cores > 0 else 1.0
        # Cap at 3x realistic speedup (not all workloads scale perfectly)
        speedup_factor = min(core_ratio, 3.0)
    else:
        speedup_factor = 1.0  # No upgrade available
    
    # Find reason based on what maxed out
    if max_cpu_pct >= 90 and max_mem_pct >= 90:
        reason = f'Both CPU ({max_cpu_pct:.0f}%) and memory ({max_mem_pct:.0f}%) maxed - needs more resources'
    elif max_cpu_pct >= 90:
        reason = f'CPU maxed out at {max_cpu_pct:.0f}% - needs more compute cores'
    elif max_mem_pct >= 90:
        reason = f'Memory maxed out at {max_mem_pct:.0f}% - needs more RAM'
    else:
        reason = 'Resources constrained - recommend upgrade'
    
    # Determine speedup messaging based on core upgrade
    if speedup_factor >= 3.0:
        speedup_estimate = '~3x faster'
    elif speedup_factor >= 2.0:
        speedup_estimate = f'~{speedup_factor:.1f}x faster'
    elif speedup_factor > 1.0:
        speedup_estimate = f'~{speedup_factor:.1f}x faster'
    else:
        speedup_estimate = 'Better stability, same speed'
    
    return {
        'recommended': recommended,
        'cores': recommended_cores,
        'ram_gb': recommended_specs.get('ram_gb', 7),
        'reason': reason,
        'speedup_estimate': speedup_estimate,
        'speedup_factor': speedup_factor,
        'cost_per_min': recommended_cost_per_min,
        'current_cost_per_min': current_cost_per_min,
        'name': recommended_specs.get('name', 'larger runner'),
        'is_upgrade_possible': is_upgrade_possible,
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
        # Determine if current runner is free or paid
        ctx = data.get('github_context', {})
        repo_visibility = os.environ.get('REPO_VISIBILITY', 'auto').lower()
        
        # Determine if public or private repo
        if repo_visibility == 'public':
            is_public_repo = True
        elif repo_visibility == 'private':
            is_public_repo = False
        else:
            # Auto-detect: check GitHub's environment variable
            github_repo_visibility = os.environ.get('GITHUB_REPOSITORY_VISIBILITY', 'private').lower()
            is_public_repo = (github_repo_visibility == 'public')
        
        is_free = is_runner_free(cost_analysis['runner_type'], is_public_repo=is_public_repo)
        
        # Skip cost analysis for free runners - cost analysis doesn't apply when price is $0
        if not is_free:
            cost_display = f"${cost_analysis['current_cost']:.4f} ({int(cost_analysis['duration_minutes'])} min)"
            monthly_cost_display = f"${cost_analysis['monthly_cost']:.2f}"
            
            section += f'''### 💵 Cost Analysis (Jan 2026+ Pricing)

> 📖 Pricing reference: [GitHub Actions Runner Pricing](https://docs.github.com/en/enterprise-cloud@latest/billing/reference/actions-runner-pricing)

| Metric | Value |
|:-------|------:|
| **Runner Type** | `{cost_analysis['runner_specs']['name']}` |
| **This Run** | {cost_display} |
| **Est. Monthly** (10 runs/day) | {monthly_cost_display} |

'''
        else:
            # For free runners, show a simple notice instead of cost analysis
            visibility_note = "public repository" if is_public_repo else "private repository"
            section += f'''### 🎉 Free Runner

This job ran on `{cost_analysis['runner_specs']['name']}` at **no cost** (standard GitHub-hosted runner on {visibility_note}).

'''
        
        # Only recommend downgrading if BOTH conditions are met:
        # 1. Average utilization is low (< 40%)
        # 2. Peak utilization is also reasonable (< 70%) - no spiky overload
        # Do NOT recommend downgrading if peak shows overutilization (>= 70%), even if avg is low
        has_spiky_usage = (utilization['max_cpu_pct'] >= 70 or utilization['max_mem_pct'] >= 70)
        is_truly_underutilized = (utilization['avg_cpu_pct'] < 40 and utilization['avg_mem_pct'] < 40 and not has_spiky_usage)
        
        if cost_analysis['right_sized_runner'] != cost_analysis['runner_type'] and is_truly_underutilized:
            right_specs = GITHUB_RUNNERS.get(cost_analysis['right_sized_runner'], GITHUB_RUNNERS['ubuntu-latest'])
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
> To make this change, update your workflow's `runs-on:` configuration.
>
> **Learn more:** 
> - [GitHub Actions Runner Pricing](https://docs.github.com/en/enterprise-cloud@latest/billing/reference/actions-runner-pricing)
> - [Manage Larger Runners](https://docs.github.com/en/enterprise-cloud@latest/actions/how-tos/manage-runners/larger-runners/manage-larger-runners)

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
        # Get specific runner recommendation (respecting OS/architecture)
        duration_sec = data.get('duration', 0)
        
        # Determine repo visibility for accurate detection
        repo_visibility = os.environ.get('REPO_VISIBILITY', 'auto').lower()
        if repo_visibility == 'public':
            is_public_repo = True
        elif repo_visibility == 'private':
            is_public_repo = False
        else:
            github_repo_visibility = os.environ.get('GITHUB_REPOSITORY_VISIBILITY', 'private').lower()
            is_public_repo = (github_repo_visibility == 'public')
        
        current_runner = detect_runner_type(data, is_public_repo=is_public_repo)
        
        upgrade_rec = recommend_runner_upgrade(
            utilization['max_cpu_pct'],
            utilization['max_mem_pct'],
            duration_sec,
            current_runner_type=current_runner
        )
        
        # FORCE upgrade if still not possible and current is small runner
        if not upgrade_rec['is_upgrade_possible']:
            current_specs = GITHUB_RUNNERS.get(current_runner, {})
            current_cores = current_specs.get('vcpus', 2)
            # If current is 2-core and not marked as upgrade possible, force it
            if current_cores <= 2:
                if 'windows' in current_runner.lower():
                    upgrade_rec['recommended'] = 'windows-4-core'
                elif 'macos' in current_runner.lower():
                    upgrade_rec['recommended'] = 'macos-13-large'
                else:
                    upgrade_rec['recommended'] = 'linux-4-core'
                # Recalculate specs for forced upgrade
                new_specs = GITHUB_RUNNERS.get(upgrade_rec['recommended'], {})
                upgrade_rec['cores'] = new_specs.get('vcpus', 4)
                upgrade_rec['ram_gb'] = new_specs.get('ram_gb', 16)
                upgrade_rec['name'] = new_specs.get('name', 'linux-4-core')
                upgrade_rec['cost_per_min'] = new_specs.get('cost_per_min', 0.012)
                upgrade_rec['is_upgrade_possible'] = True
        
        # Check if upgrade is actually possible
        # For custom runners (not in GITHUB_RUNNERS), skip standard upgrade recommendations
        is_custom_runner = upgrade_rec['recommended'] not in GITHUB_RUNNERS
        
        if upgrade_rec['is_upgrade_possible'] and not is_custom_runner:
            # Show upgrade recommendation
            recommended_runner = GITHUB_RUNNERS.get(upgrade_rec['recommended'], {})
            current_cost_per_min = upgrade_rec['current_cost_per_min']
            new_cost_per_min = upgrade_rec['cost_per_min']
            speedup_factor = upgrade_rec['speedup_factor']
            duration_min = max(1, math.ceil(duration_sec / 60))
            
            # Estimate duration on new runner
            estimated_new_duration_min = duration_min / speedup_factor
            
            # Cost calculations
            current_run_cost = current_cost_per_min * duration_min
            new_run_cost = new_cost_per_min * estimated_new_duration_min  # With speed benefit
            cost_diff = new_run_cost - current_run_cost
            
            # Monthly costs (10 runs/day = 300 runs/month)
            current_monthly = current_cost_per_min * duration_min * 10 * 30
            new_monthly = new_cost_per_min * estimated_new_duration_min * 10 * 30
            monthly_diff = new_monthly - current_monthly
            
            # Determine if this is a larger runner upgrade (requires GitHub Team+)
            is_larger_upgrade = recommended_runner.get('is_larger', False)
            plan_note = ''
            if is_larger_upgrade:
                plan_note = '\n\n**Note:** Larger runners require a **GitHub Team or GitHub Enterprise Cloud** plan. Not available on free tier.'
            
            # Calculate hidden costs: developer waiting time, timeouts, context switching
            # Assume average developer hourly rate: $75/hr, context switch cost: 20 min
            time_saved_per_month_min = (duration_min - estimated_new_duration_min) * 10 * 30  # Per month
            time_saved_per_month_hours = time_saved_per_month_min / 60
            dev_cost_per_hour = 75  # Conservative estimate for dev productivity
            hidden_value_saved = time_saved_per_month_hours * dev_cost_per_hour
            
            # Additionally: timeout risk reduction based on actual utilization
            # High utilization (95%+) = high timeout risk (20%)
            # Medium utilization (85-95%) = medium risk (10%)
            # Lower utilization (70-85%) = lower risk (5%)
            max_util = max(utilization['max_cpu_pct'], utilization['max_mem_pct'])
            if max_util >= 95:
                current_timeout_rate = 0.20  # 20% chance of timeout when straining resources
                new_timeout_rate = 0.02      # Much safer with proper resources
            elif max_util >= 85:
                current_timeout_rate = 0.10
                new_timeout_rate = 0.01
            else:
                current_timeout_rate = 0.05
                new_timeout_rate = 0.01
            
            # Cost of each timeout: runner cost + dev time to investigate and re-run
            # Assumption: ~5 min average dev time per timeout (investigation + rerun)
            dev_time_per_timeout_min = 5  # Minutes to investigate and rerun
            dev_time_per_timeout_hours = dev_time_per_timeout_min / 60
            dev_time_per_timeout_cost = dev_time_per_timeout_hours * dev_cost_per_hour  # ~$6.25 per timeout
            timeout_cost_current = current_run_cost + dev_time_per_timeout_cost
            timeout_cost_new = new_run_cost + dev_time_per_timeout_cost
            
            # Monthly timeout costs (300 runs/month)
            timeouts_per_month_current = 300 * current_timeout_rate
            timeouts_per_month_new = 300 * new_timeout_rate
            timeout_cost_monthly_current = timeouts_per_month_current * timeout_cost_current
            timeout_cost_monthly_new = timeouts_per_month_new * timeout_cost_new
            timeout_savings = timeout_cost_monthly_current - timeout_cost_monthly_new
            
            # Show assumptions in message
            timeout_assumptions = f'(Assuming {current_timeout_rate*100:.0f}% timeout rate at current utilization, ~{dev_time_per_timeout_min} min dev time per timeout)'
            
            total_hidden_value = hidden_value_saved + timeout_savings
            
            # Get billing context - are we upgrading from free to paid?
            # Determine repo visibility for accurate billing detection
            repo_visibility = os.environ.get('REPO_VISIBILITY', 'auto').lower()
            if repo_visibility == 'public':
                is_public_repo = True
            elif repo_visibility == 'private':
                is_public_repo = False
            else:
                github_repo_visibility = os.environ.get('GITHUB_REPOSITORY_VISIBILITY', 'private').lower()
                is_public_repo = (github_repo_visibility == 'public')
            
            current_runner_type = detect_runner_type(data, is_public_repo=is_public_repo)
            billing_context = get_runner_billing_context(current_runner_type)
            current_is_free = billing_context['is_free']
            new_is_free = is_runner_free(upgrade_rec['recommended'])
            
            # Value messaging - emphasize the speedup benefit AND hidden costs
            # Special case: upgrading from free to paid runner - don't claim cost savings
            if current_is_free and not new_is_free:
                # Public repo on free runner → upgrading to paid larger runner
                # Cannot claim "cost savings" because going from $0 to >$0
                upgrade_note = f'''**💡 Performance Improvement Available:** {speedup_factor:.1f}x faster execution on a paid larger runner.

**Developer productivity value:** {time_saved_per_month_hours:.1f} hours/month saved = **${hidden_value_saved:.0f}/month**

**Reliability improvements:** Fewer timeouts saves ~{timeout_savings:.0f}/month {timeout_assumptions}

**Total hidden value: ~${total_hidden_value:.0f}/month** in productivity and reliability.

**Note:** You're currently using a free runner (public repo benefit). This recommendation requires switching to a paid larger runner.'''
            elif cost_diff < 0:
                savings_pct = abs(cost_diff / current_run_cost * 100)
                upgrade_note = f'**✅ Cost Savings!** The faster runner saves ~${abs(cost_diff):.4f}/run ({savings_pct:.0f}% cheaper). Plus ${hidden_value_saved:.0f}/month in developer productivity and ${timeout_savings:.0f}/month from fewer timeouts.'
            elif abs(cost_diff) < 0.0001:  # Same cost (within rounding)
                upgrade_note = f'**✅ Same Cost, {speedup_factor:.1f}x Faster!** Get {speedup_factor:.1f}x faster job execution at the same price.\n\n**Hidden Value Breakdown:**\n- Developer waiting time: {time_saved_per_month_hours:.1f} hours/month = **${hidden_value_saved:.0f}/month**\n- Fewer timeouts: {timeouts_per_month_current:.0f}→{timeouts_per_month_new:.0f} per month = **${timeout_savings:.0f}/month savings** {timeout_assumptions}\n\n**Total Hidden Value: ~${total_hidden_value:.0f}/month** in productivity and reliability improvements!'
            elif speedup_factor > 1.5:
                upgrade_note = f'**💡 Fast Execution:** {speedup_factor:.1f}x faster = quicker feedback. Additional cost of ${abs(cost_diff):.4f}/run is more than offset by {time_saved_per_month_hours:.1f} hours of saved developer time (~${hidden_value_saved:.0f}/month) and ${timeout_savings:.0f}/month from improved reliability {timeout_assumptions}.'
            else:
                upgrade_note = '**💡 Trade-off:** Slightly higher cost, but better reliability and resource availability.'
            
            section += f'''
**Priority: Upgrade to Larger Runner ⚠️**

Your job is **straining resources** on the current runner:
- CPU peaked at **{utilization['max_cpu_pct']:.1f}%** (avg: {utilization['avg_cpu_pct']:.1f}%)
- Memory peaked at **{utilization['max_mem_pct']:.1f}%** (avg: {utilization['avg_mem_pct']:.1f}%)

**Recommended Runner: {upgrade_rec['name']} ({upgrade_rec['cores']}-core, {upgrade_rec['ram_gb']}GB RAM)**

**Why:** {upgrade_rec['reason']}

**Expected Performance:** {upgrade_rec['speedup_estimate']} (upgrade from {upgrade_rec['cores'] / speedup_factor:.0f} to {upgrade_rec['cores']} cores)

**Cost Impact (accounting for faster execution):**
'''
            
            # Different cost display based on billing context
            if current_is_free and not new_is_free:
                section += f'''- **Current: FREE** (0 min @ $0.00/min on public repository)
- **Recommended: ${new_run_cost:.4f}/run** (est. {estimated_new_duration_min:.1f} min @ ${new_cost_per_min:.4f}/min)
- **Additional cost per run: +${new_run_cost:.4f}**

**Monthly Cost Comparison** (if you run 10 times/day, 300 runs/month):
- **Current: FREE** ($0/month on free tier)
- **Recommended: ${new_monthly:.2f}/month** (${new_run_cost:.4f}/run × 300 runs)

⚠️ **Important Trade-off:** You're currently using GitHub's free runners available to public repositories. Upgrading to a larger runner means incurring costs, but you gain significant speed and reliability benefits listed above.
'''
            else:
                section += f'''- Current: ${current_run_cost:.4f}/run ({duration_min:.0f} min @ ${current_cost_per_min:.4f}/min)
- Recommended: ${new_run_cost:.4f}/run (est. {estimated_new_duration_min:.1f} min @ ${new_cost_per_min:.4f}/min)
- **Per-run difference: {'-$' if cost_diff < 0 else '+$'}{abs(cost_diff):.4f}** ({'-' if cost_diff < 0 else '+'}{(cost_diff/current_run_cost*100):.0f}%)

**Monthly Cost Comparison** (10 runs/day, 300 runs/month):
- Current: ${current_monthly:.2f}
- Recommended: ${new_monthly:.2f}
- **Monthly difference: {'-$' if monthly_diff < 0 else '+$'}{abs(monthly_diff):.2f}** ({'-' if monthly_diff < 0 else '+'}{(monthly_diff/current_monthly*100):.0f}%)
'''
            
            section += f'''
{upgrade_note}{plan_note}

**How to Switch:**

**Note:** Larger runners require a GitHub Team or GitHub Enterprise Cloud plan and must be set up by your organization administrator.

For setup instructions, see: [GitHub Actions - Manage Larger Runners](https://docs.github.com/en/enterprise-cloud@latest/actions/how-tos/manage-runners/larger-runners/manage-larger-runners)

For pricing details, see: [GitHub Actions Runner Pricing](https://docs.github.com/en/enterprise-cloud@latest/billing/reference/actions-runner-pricing)

'''
        else:
            # No standard upgrade available, or this is a custom runner
            # For custom runners, recommend contacting org admin to increase resources
            if is_custom_runner:
                section += f'''
**Priority: Contact Your Organization ⚠️**

Your job is **straining resources** on the custom runner **`{current_runner}`**:
- CPU peaked at **{utilization['max_cpu_pct']:.1f}%** (avg: {utilization['avg_cpu_pct']:.1f}%)
- Memory peaked at **{utilization['max_mem_pct']:.1f}%** (avg: {utilization['avg_mem_pct']:.1f}%)

**Recommendation:** Contact your organization administrator to:
1. Increase the resources (CPU cores / RAM) allocated to this runner
2. Create a larger runner specifically for high-resource workloads
3. Distribute your workload across multiple runners using workflow matrix

**In the meantime, optimize your build:**

1. **Parallelize jobs** - Split work across parallel jobs using workflow matrix:
   ```yaml
   strategy:
     matrix:
       shard: [1, 2, 3, 4]
   ```

2. **Improve caching** - Cache dependencies to reduce build time

3. **Profile slow steps** - Identify and optimize bottlenecks

4. **Run targeted tests** - Only test changed modules, not full suite

**Your Runner Details:**
- Name: `{current_runner}`
- CPU Cores: {utilization['total_cpu_cores']}
- Total RAM: {utilization['total_ram_gb']:.1f} GB

**For your organization admin:** This runner needs upgrade due to consistent 95%+ utilization during regular workloads.

'''
            elif current_runner in ['ubuntu-latest', 'ubuntu-24.04', 'ubuntu-22.04']:
                section += f'''
**Priority: Optimize Build (or Upgrade to Larger Runner) ⚠️**

Your job is **straining resources** on the current runner:
- CPU peaked at **{utilization['max_cpu_pct']:.1f}%** (avg: {utilization['avg_cpu_pct']:.1f}%)
- Memory peaked at **{utilization['max_mem_pct']:.1f}%** (avg: {utilization['avg_mem_pct']:.1f}%)

**Limitation:** GitHub's **free tier** standard Linux runners max out at **2 cores** (`ubuntu-latest`, `ubuntu-24.04`, `ubuntu-22.04`).

**Option 1: Optimize your build first** (recommended, free tier-friendly) - Most cost-effective solution:

1. **Parallelize jobs** - Split work across parallel jobs using workflow matrix:
   ```yaml
   strategy:
     matrix:
       node-version: [18, 20, 22]
   ```

2. **Improve caching** - Cache dependencies to reduce install time:
   - npm: Use `actions/setup-node@v4` with `cache: npm`
   - pip: Use `actions/setup-python@v4` with `cache: pip`
   - apt: Pre-build custom Docker images with dependencies

3. **Remove unnecessary dependencies** - Audit and eliminate unused packages

4. **Optimize slow steps** - Profile per-step execution:
   - Identify bottleneck steps with `time` command
   - Use faster alternatives (e.g., `esbuild` vs Webpack, `swc` vs Babel)

5. **Run targeted tests** - Only run tests for changed modules, not full suite

**Option 2: Upgrade to a Larger Runner** (if optimization isn't enough):

If you have a **GitHub Team or GitHub Enterprise Cloud** plan, you can use larger runners:
- **linux-4-core** - 4-core runner at $0.012/min (2x faster, $0.006 more per minute)
- **linux-8-core** - 8-core runner at $0.022/min (4x faster, faster feedback)

See [GitHub Actions Runner Pricing](https://docs.github.com/en/enterprise-cloud@latest/billing/reference/actions-runner-pricing) for complete options.

**Summary:**
- Start with optimization (builds faster, lower cost)
- If optimization hits a wall, consider larger runners (GitHub Team+ plans)

'''
            elif current_runner in ['windows-latest', 'windows-2025', 'windows-2022']:
                section += f'''
**Priority: Optimize Build (or Upgrade to Larger Runner) ⚠️**

Your job is **straining resources** on the current runner:
- CPU peaked at **{utilization['max_cpu_pct']:.1f}%** (avg: {utilization['avg_cpu_pct']:.1f}%)
- Memory peaked at **{utilization['max_mem_pct']:.1f}%** (avg: {utilization['avg_mem_pct']:.1f}%)

**Limitation:** GitHub's **free tier** standard Windows runners max out at **2 cores** (`windows-latest`, `windows-2025`, `windows-2022`).

**Option 1: Optimize your build first** (recommended, free tier-friendly) - Most cost-effective solution:

1. **Parallelize jobs** - Split work across parallel jobs using workflow matrix

2. **Improve caching** - Cache dependencies to reduce install time:
   - NuGet: Enable project-level caching
   - npm/yarn: Cache node_modules or use lock files
   - Pre-warm build artifacts for incremental builds

3. **Remove unnecessary dependencies** - Audit and eliminate unused NuGet packages

4. **Optimize slow steps** - Profile build per-step:
   - Enable parallel compilation flags (`/m` for MSBuild)
   - Use incremental builds where possible
   - Identify and optimize slowest test suites

5. **Run targeted tests** - Only run tests for changed code, not full suite

**Option 2: Upgrade to a Larger Runner** (if optimization isn't enough):

If you have a **GitHub Team or GitHub Enterprise Cloud** plan, you can use larger runners:
- **windows-4-core** - 4-core runner at $0.022/min (2x faster)
- **windows-8-core** - 8-core runner at $0.042/min (4x faster)

See [GitHub Actions Runner Pricing](https://docs.github.com/en/enterprise-cloud@latest/billing/reference/actions-runner-pricing) for complete options.

**Summary:**
- Start with optimization (builds faster, lower cost, free tier-friendly)
- If optimization hits a wall, consider larger runners (GitHub Team+ plans)

'''
            else:
                section += f'''
**Priority: Optimize Build ⚠️**

Your job is **straining resources** on the current runner:
- CPU peaked at **{utilization['max_cpu_pct']:.1f}%** (avg: {utilization['avg_cpu_pct']:.1f}%)
- Memory peaked at **{utilization['max_mem_pct']:.1f}%** (avg: {utilization['avg_mem_pct']:.1f}%)

This runner is already at the maximum size in its family.

**Options to address overutilization:**

1. **Parallelize** - Use matrix strategy for independent jobs
2. **Cache** - Improve dependency caching to reduce download time
3. **Profile** - Identify and optimize slowest steps
4. **Simplify** - Remove unnecessary dependencies and tools

**More options:** [GitHub Actions Runner Pricing](https://docs.github.com/en/enterprise-cloud@latest/billing/reference/actions-runner-pricing)

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
    
    # Create time series chart with downsampling for readability
    sample_count = len(samples)
    interval = data.get("interval", 2)
    
    # Downsample data for Mermaid chart to max 50 points (Mermaid rendering limit)
    max_mermaid_points = 50
    mermaid_step = max(1, math.ceil(sample_count / max_mermaid_points))
    
    # Get downsampled data while preserving max values
    downsampled_indices = list(range(0, sample_count, mermaid_step))
    if sample_count - 1 not in downsampled_indices:
        downsampled_indices.append(sample_count - 1)
    
    downsampled_cpu = [cpu_values[i] for i in downsampled_indices]
    downsampled_mem = [mem_values[i] for i in downsampled_indices]
    
    # Generate time labels for downsampled points
    x_labels = [f'"{int(downsampled_indices[i] * interval)}"' for i in range(len(downsampled_indices))]
    
    # Downsampled data for smooth lines (Mermaid chart)
    all_cpu_str = ", ".join([f"{v:.1f}" for v in downsampled_cpu])
    all_mem_str = ", ".join([f"{v:.1f}" for v in downsampled_mem])
    
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

## 🔄 Average Resource Utilization

This shows the average CPU and memory usage during your job:

<table>
<tr>
<td width="50%">

**CPU Usage** - Average across all cores

{resource_pie}

</td>
<td width="50%">

**Memory Usage** - Average RAM consumption

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
    
    # Top processes with descriptions
    process_descriptions = {
        # GitHub Actions core
        'actions-r': 'GitHub Actions Runner - coordinates job execution',
        'Runner.Work': 'Executes your job steps (build, test, deploy commands)',
        'Runner.Listener': 'Listens for new jobs from GitHub',
        'Runner.List': 'Tracks and manages running processes',
        
        # Container & virtualization
        'docker': 'Docker daemon - if using containers',
        'containerd': 'Container runtime - Docker or Kubernetes operations',
        
        # Languages & runtimes
        'python': 'Python interpreter - running Python scripts',
        'node': 'Node.js runtime - npm/yarn builds or JS execution',
        'ruby': 'Ruby interpreter - running Ruby/Rails apps',
        'java': 'Java Virtual Machine - Maven/Gradle builds or Java apps',
        'go': 'Go runtime - building Go applications',
        'dotnet': '.NET runtime - running C# or F# builds',
        'php': 'PHP interpreter - running PHP code',
        
        # Build tools & package managers
        'gradle': 'Gradle build system - Java/Kotlin builds',
        'maven': 'Maven - Java/Kotlin build and dependency management',
        'npm': 'Node Package Manager - installing/running JS dependencies',
        'pip': 'Python Package Manager - installing Python packages',
        'gem': 'Ruby Package Manager - installing gems',
        'cargo': 'Rust package manager and build system',
        'gcc': 'GNU C Compiler - compiling C/C++ code',
        'clang': 'Clang compiler - compiling C/C++ code',
        'rustc': 'Rust compiler - compiling Rust code',
        
        # Version control & utilities
        'git': 'Git operations - cloning, fetching, pushing code',
        'curl': 'Transfer data utility - downloading files/APIs',
        'tar': 'Archive tool - extracting/compressing files',
        'jq': 'JSON processor - parsing/transforming JSON data',
        
        # System
        'kswapd': 'Kernel swap daemon - if high, job ran out of RAM',
    }
    
    top_procs = final_snapshot.get('processes', initial.get('processes', {}))
    if top_procs.get('by_cpu'):
        report += '''
<details>
<summary>🔝 Top Processes</summary>

| Process | CPU % | Memory % | What it does |
|:--------|------:|--------:|:-------------|
'''
        for p in top_procs.get('by_cpu', [])[:5]:
            cmd = p['command'].split('/')[-1].split()[0][:30]
            # Find matching description
            desc = ''
            for key, val in process_descriptions.items():
                if key in cmd.lower():
                    desc = val
                    break
            if not desc:
                desc = 'Process consuming resources'
            report += f"| `{cmd}` | {p['cpu']:.1f}% | {p['mem']:.1f}% | {desc} |\n"
        report += '\n**Note:** High CPU on `actions-r` and `Runner.Work` is normal. High `kswapd` indicates memory pressure.\n\n</details>\n'
    
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
                    ticks: {{ color: '#8b949e' }},
                    beginAtZero: true,
                    min: 0
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
