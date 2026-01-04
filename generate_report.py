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
import io
import json
import math
import logging
import platform
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding for emoji/unicode output
if platform.system() == 'Windows':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass  # Fallback: continue with default encoding

# Configure logging for debug visibility
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)

DATA_FILE = os.environ.get('TELEMETRY_DATA_FILE', '/tmp/telemetry_data.json')


def format_cost(value: float) -> str:
    """Format cost values, trimming unnecessary trailing zeros.
    
    Examples:
        0.022 -> "$0.022"
        0.0220 -> "$0.022"
        0.10 -> "$0.10"
        1.50 -> "$1.50"
    """
    if value == 0:
        return "$0.00"
    # Format with 4 decimal places, then strip trailing zeros (but keep at least 2 decimals)
    formatted = f"{value:.4f}".rstrip('0')
    # Ensure at least 2 decimal places for currency
    parts = formatted.split('.')
    if len(parts) == 2 and len(parts[1]) < 2:
        formatted = f"{value:.2f}"
    return f"${formatted}"


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

# Utilization score thresholds
UTILIZATION_THRESHOLDS = {
    'excellent': 90,
    'good': 70,
    'fair': 50,
}

# GitHub Hosted Runner Specifications with accurate pricing (Jan 1, 2026+)
# https://docs.github.com/en/enterprise-cloud@latest/billing/reference/actions-runner-pricing
# 
# Note: Specifications vary by plan and repository visibility:
# - Free tier: Standard runners only (ubuntu-latest 2-core, windows-latest 2-core, macOS available)
# - GitHub Team/Enterprise Cloud: Larger runners available (4-core, 8-core, etc.)
# Larger runners are marked with 'is_larger': True flag.

# Canonical free standard runner labels (free on public repos only)
FREE_RUNNER_LABELS = {
    'ubuntu-latest', 'ubuntu-24.04', 'ubuntu-22.04',
    'windows-latest', 'windows-2025', 'windows-2022',
    'macos-latest',
}

# Minimal catalog of runner specs used for detection and messaging
# Pricing updated to January 2026 rates per GitHub Actions Runner Pricing
# 
# IMPORTANT: Standard runner specs differ by repository visibility:
# - PUBLIC repos: ubuntu/windows-latest = 4 CPU, 16GB RAM (FREE, unlimited)
# - PRIVATE repos: ubuntu/windows-latest = 2 CPU, 7GB RAM (PAID per minute)
# 
# The 'vcpus' and 'ram_gb' fields represent PRIVATE repo specs (used for billing).
# 'public_vcpus' and 'public_ram_gb' represent PUBLIC repo specs (for detection).

GITHUB_RUNNERS = {
    # Standard hosted runners - specs differ by repo visibility
    # Public: 4 CPU, 16GB | Private: 2 CPU, 7GB
    'ubuntu-latest': {
        'sku': 'linux', 'name': 'Ubuntu Standard Runner',
        'vcpus': 2, 'ram_gb': 7,           # Private repo specs
        'public_vcpus': 4, 'public_ram_gb': 16,  # Public repo specs
        'is_larger': False,
        'is_free_public': True,
        'private_cost_per_min': 0.006,
        'cost_per_min': 0.006,
    },
    'ubuntu-24.04': {
        'sku': 'linux', 'name': 'Ubuntu 24.04 Standard Runner',
        'vcpus': 2, 'ram_gb': 7,
        'public_vcpus': 4, 'public_ram_gb': 16,
        'is_larger': False,
        'is_free_public': True,
        'private_cost_per_min': 0.006,
        'cost_per_min': 0.006,
    },
    'ubuntu-22.04': {
        'sku': 'linux', 'name': 'Ubuntu 22.04 Standard Runner',
        'vcpus': 2, 'ram_gb': 7,
        'public_vcpus': 4, 'public_ram_gb': 16,
        'is_larger': False,
        'is_free_public': True,
        'private_cost_per_min': 0.006,
        'cost_per_min': 0.006,
    },
    'windows-latest': {
        'sku': 'windows', 'name': 'Windows Standard Runner',
        'vcpus': 2, 'ram_gb': 7,
        'public_vcpus': 4, 'public_ram_gb': 16,
        'is_larger': False,
        'is_free_public': True,
        'private_cost_per_min': 0.010,
        'cost_per_min': 0.010,
    },
    'windows-2025': {
        'sku': 'windows', 'name': 'Windows 2025 Standard Runner',
        'vcpus': 2, 'ram_gb': 7,
        'public_vcpus': 4, 'public_ram_gb': 16,
        'is_larger': False,
        'is_free_public': True,
        'private_cost_per_min': 0.010,
        'cost_per_min': 0.010,
    },
    'windows-2022': {
        'sku': 'windows', 'name': 'Windows 2022 Standard Runner',
        'vcpus': 2, 'ram_gb': 7,
        'public_vcpus': 4, 'public_ram_gb': 16,
        'is_larger': False,
        'is_free_public': True,
        'private_cost_per_min': 0.010,
        'cost_per_min': 0.010,
    },
    # macOS standard - same specs for public/private (3 CPU M1, 7GB)
    'macos-latest': {
        'sku': 'macos', 'name': 'macOS Standard Runner (M1)',
        'vcpus': 3, 'ram_gb': 7,
        'public_vcpus': 3, 'public_ram_gb': 7,
        'is_larger': False,
        'is_free_public': True,
        'private_cost_per_min': 0.062,
        'cost_per_min': 0.062,
    },

    # Larger Linux x64
    'linux-4-core': {
        'sku': 'linux', 'name': 'Linux 4-core Larger Runner',
        'vcpus': 4, 'ram_gb': 16,
        'is_larger': True,
        'cost_per_min': 0.012,
    },
    'linux-8-core': {
        'sku': 'linux', 'name': 'Linux 8-core Larger Runner',
        'vcpus': 8, 'ram_gb': 32,
        'is_larger': True,
        'cost_per_min': 0.022,
    },
    'linux-16-core': {
        'sku': 'linux', 'name': 'Linux 16-core Larger Runner',
        'vcpus': 16, 'ram_gb': 64,
        'is_larger': True,
        'cost_per_min': 0.044,
    },
    'linux-32-core': {
        'sku': 'linux', 'name': 'Linux 32-core Larger Runner',
        'vcpus': 32, 'ram_gb': 128,
        'is_larger': True,
        'cost_per_min': 0.088,
    },
    'linux-64-core': {
        'sku': 'linux', 'name': 'Linux 64-core Larger Runner',
        'vcpus': 64, 'ram_gb': 208,
        'is_larger': True,
        'cost_per_min': 0.176,
    },
    # Larger Linux ARM (cheaper than x64)
    'linux-4-core-arm': {
        'sku': 'linux', 'name': 'Linux 4-core ARM Larger Runner',
        'vcpus': 4, 'ram_gb': 16,
        'is_larger': True,
        'cost_per_min': 0.008,
    },
    'linux-8-core-arm': {
        'sku': 'linux', 'name': 'Linux 8-core ARM Larger Runner',
        'vcpus': 8, 'ram_gb': 32,
        'is_larger': True,
        'cost_per_min': 0.014,
    },

    # Larger Windows x64
    'windows-4-core': {
        'sku': 'windows', 'name': 'Windows 4-core Larger Runner',
        'vcpus': 4, 'ram_gb': 16,
        'is_larger': True,
        'cost_per_min': 0.022,
    },
    'windows-8-core': {
        'sku': 'windows', 'name': 'Windows 8-core Larger Runner',
        'vcpus': 8, 'ram_gb': 32,
        'is_larger': True,
        'cost_per_min': 0.042,
    },
    'windows-16-core': {
        'sku': 'windows', 'name': 'Windows 16-core Larger Runner',
        'vcpus': 16, 'ram_gb': 64,
        'is_larger': True,
        'cost_per_min': 0.084,
    },
    'windows-32-core': {
        'sku': 'windows', 'name': 'Windows 32-core Larger Runner',
        'vcpus': 32, 'ram_gb': 128,
        'is_larger': True,
        'cost_per_min': 0.168,
    },
    'windows-64-core': {
        'sku': 'windows', 'name': 'Windows 64-core Larger Runner',
        'vcpus': 64, 'ram_gb': 208,
        'is_larger': True,
        'cost_per_min': 0.336,
    },
    # Larger Windows ARM (cheaper than x64)
    'windows-4-core-arm': {
        'sku': 'windows', 'name': 'Windows 4-core ARM Larger Runner',
        'vcpus': 4, 'ram_gb': 16,
        'is_larger': True,
        'cost_per_min': 0.014,
    },
    'windows-8-core-arm': {
        'sku': 'windows', 'name': 'Windows 8-core ARM Larger Runner',
        'vcpus': 8, 'ram_gb': 32,
        'is_larger': True,
        'cost_per_min': 0.026,
    },

    # Larger macOS Intel (Large) runners - 12-core
    'macos-13-large': {
        'sku': 'macos', 'name': 'macOS 13 Large Runner (Intel)',
        'vcpus': 12, 'ram_gb': 30,
        'is_larger': True,
        'cost_per_min': 0.077,
    },
    'macos-14-large': {
        'sku': 'macos', 'name': 'macOS 14 Large Runner (Intel)',
        'vcpus': 12, 'ram_gb': 30,
        'is_larger': True,
        'cost_per_min': 0.077,
    },
    'macos-15-large': {
        'sku': 'macos', 'name': 'macOS 15 Large Runner (Intel)',
        'vcpus': 12, 'ram_gb': 30,
        'is_larger': True,
        'cost_per_min': 0.077,
    },
    'macos-latest-large': {
        'sku': 'macos', 'name': 'macOS Large Runner (Intel)',
        'vcpus': 12, 'ram_gb': 30,
        'is_larger': True,
        'cost_per_min': 0.077,
    },

    # Larger macOS Apple Silicon (XLarge M2 Pro) runners - 5-core
    'macos-13-xlarge': {
        'sku': 'macos', 'name': 'macOS 13 XLarge Runner (M2)',
        'vcpus': 5, 'ram_gb': 14,
        'is_larger': True,
        'cost_per_min': 0.102,
    },
    'macos-14-xlarge': {
        'sku': 'macos', 'name': 'macOS 14 XLarge Runner (M2)',
        'vcpus': 5, 'ram_gb': 14,
        'is_larger': True,
        'cost_per_min': 0.102,
    },
    'macos-15-xlarge': {
        'sku': 'macos', 'name': 'macOS 15 XLarge Runner (M2)',
        'vcpus': 5, 'ram_gb': 14,
        'is_larger': True,
        'cost_per_min': 0.102,
    },
    'macos-latest-xlarge': {
        'sku': 'macos', 'name': 'macOS XLarge Runner (M2)',
        'vcpus': 5, 'ram_gb': 14,
        'is_larger': True,
        'cost_per_min': 0.102,
    },
}

def get_repo_visibility_from_data(data):
    """Determine repository visibility ('public' or 'private').
    Uses data.github_context.repository_visibility if available; otherwise falls back to environment.
    Defaults to 'private' for safety.
    """
    ctx = {}
    if isinstance(data, dict):
        ctx = data.get('github_context', {}) or {}
    vis = str(ctx.get('repository_visibility', '')).lower().strip()
    if vis in ('public', 'private'):
        return vis
    # Fallback to env-provided visibility
    repo_visibility = os.environ.get('REPO_VISIBILITY', 'auto').lower().strip()
    if repo_visibility in ('public', 'private'):
        return repo_visibility
    github_repo_visibility = os.environ.get('GITHUB_REPOSITORY_VISIBILITY', 'private').lower().strip()
    return github_repo_visibility

def normalize_runner_label(name: str, runner_os_hint: str = None):
    """Normalize a runner label to a canonical GitHub label.
    Returns the canonical label if recognized; otherwise returns None.
    Case-insensitive; does not attempt fuzzy matching for non-standard names.
    """
    if not name or not str(name).strip():
        return None
    n = str(name).strip().lower()

    canonical_labels = {
        # Standard hosted labels
        'ubuntu-latest', 'ubuntu-24.04', 'ubuntu-22.04',
        'windows-latest', 'windows-2025', 'windows-2022',
        'macos-latest',
        # Larger Linux
        'linux-4-core', 'linux-8-core', 'linux-4-core-arm', 'linux-8-core-arm',
        # Larger Windows
        'windows-4-core', 'windows-8-core', 'windows-4-core-arm', 'windows-8-core-arm',
        # Larger macOS
        'macos-13-large', 'macos-14-large', 'macos-15-large', 'macos-latest-large',
        'macos-13-xlarge', 'macos-14-xlarge', 'macos-15-xlarge', 'macos-latest-xlarge',
    }
    if n in canonical_labels:
        return n
    # Do not attempt to normalize arbitrary or randomized names; rely on spec-based detection later
    return None

# Helper: macOS labels documentation link (top-level)
def macos_labels_doc_line():
    return ('See: [Available macOS larger runners and labels]('
            'https://docs.github.com/en/enterprise-cloud@latest/actions/reference/runners/larger-runners#available-macos-larger-runners-and-labels)')

def infer_runner_architecture(runner_name: str, explicit_arch: str = None) -> str:
    """Infer runner architecture from runner name if not explicitly provided.
    
    - Linux/Windows ARM runners contain 'arm' in name
    - macOS xlarge runners are Apple Silicon M2 (ARM64)
    - macOS large runners are Intel (X64)
    - Default to X64 for everything else
    """
    if explicit_arch:
        return explicit_arch
    if not runner_name:
        return 'X64'
    name_lower = runner_name.lower()
    if 'arm' in name_lower:
        return 'ARM64'
    if 'xlarge' in name_lower and 'macos' in name_lower:
        return 'ARM64'  # macOS xlarge = Apple Silicon M2
    return 'X64'

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
    
    logging.debug(f"is_runner_free: Checking runner_type='{runner_type}', is_public_repo={is_public_repo}, requested_runner_name='{requested_runner_name}'")
    
    # Consider requested runner name only if it is a canonical GitHub label.
    # Do not infer billing from arbitrary/custom names; rely on detected specs.
    if requested_runner_name:
        requested_name = requested_runner_name.lower()
        normalized = normalize_runner_label(requested_name, os.environ.get('RUNNER_OS'))
        if normalized:
            requested_name = normalized
            logging.debug(f"is_runner_free: Normalized requested name to '{requested_name}'")
        else:
            logging.debug(f"is_runner_free: Non-canonical requested name '{requested_runner_name}' — using detected type '{runner_type}'")
            requested_name = runner_type
        
        # Explicitly requested larger runner = always paid
        if requested_name in ['linux-4-core', 'linux-8-core', 'linux-4-core-arm', 'linux-8-core-arm',
                             'windows-4-core', 'windows-8-core', 'windows-4-core-arm', 'windows-8-core-arm',
                             'macos-13-large', 'macos-14-large', 'macos-15-large', 'macos-latest-large',
                             'macos-13-xlarge', 'macos-14-xlarge', 'macos-15-xlarge', 'macos-latest-xlarge']:
            logging.info(f"is_runner_free: Larger runner '{requested_name}' explicitly requested - always paid")
            return False
        
        # Explicitly requested standard runner on public repo = free
        if is_public_repo and requested_name in FREE_RUNNER_LABELS:
            logging.info(f"is_runner_free: Standard runner '{requested_name}' on public repo - free")
            return True
        
        # Explicitly requested standard runner on private repo = paid
        if not is_public_repo and requested_name in FREE_RUNNER_LABELS:
            logging.info(f"is_runner_free: Standard runner '{requested_name}' on private repo - paid")
            return False
    
    # Fallback: check detected runner type
    # Larger runners are always paid
    if runner_type in ['linux-4-core', 'linux-8-core', 'linux-4-core-arm', 'linux-8-core-arm',
                       'windows-4-core', 'windows-8-core', 'windows-4-core-arm', 'windows-8-core-arm',
                       'macos-13-large', 'macos-14-large', 'macos-15-large', 'macos-latest-large',
                       'macos-13-xlarge', 'macos-14-xlarge', 'macos-15-xlarge', 'macos-latest-xlarge']:
        logging.info(f"is_runner_free: Detected larger runner '{runner_type}' - always paid")
        return False
    
    # Standard runners are free only on public repos
    if is_public_repo and runner_type in FREE_RUNNER_LABELS:
        logging.info(f"is_runner_free: Standard runner '{runner_type}' on public repo - free")
        return True
    
    # Default: assume paid for unknown/unclassified runners
    logging.info(f"is_runner_free: Runner '{runner_type}' not in free labels, is_public={is_public_repo} - defaulting to paid")
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
    - C (30-69%): Fair utilization - could optimize
    - D (<30%): Poor utilization - significant wasted capacity
    
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
    elif utilization_pct >= 30:  # Aligned with strategy section thresholds
        return 'C', '🟡 Fair', 'Good with room for improvement'
    else:
        return 'D', '🔴 Poor', 'Runner is significantly underutilized'

def detect_hosting_type(data):
    """Classify hosting type (GitHub-hosted vs self-hosted) using override, environment, and path heuristics.

    Precedence:
      1) Explicit override via env `HOSTING_TYPE` (hosted/self).
      2) `RUNNER_ENVIRONMENT` if set to 'github-hosted' or 'self-hosted'.
      3) Heuristics from image variables, tool cache, and workspace path.

    Strong hosted signals:
      - 'ImageOS' or 'ImageVersion' environment variables (hosted images)
      - 'AGENT_TOOLSDIRECTORY' or 'RUNNER_TOOL_CACHE' containing 'hostedtoolcache'
      - 'GITHUB_WORKSPACE' path matching known hosted patterns (e.g., '/home/runner/', 'C:\\Users\\runneradmin')

    Returns dict: { 'is_github_hosted': True|False|None, 'signals': [str] }
    """
    signals = []
    env = os.environ

    # 1) Explicit override
    override = (env.get('HOSTING_TYPE') or '').strip().lower()
    if override:
        if override in {'hosted', 'github-hosted', 'github', 'gh'}:
            return {'is_github_hosted': True, 'signals': [f'override={override}']}
        if override in {'self', 'self-hosted', 'private'}:
            return {'is_github_hosted': False, 'signals': [f'override={override}']}
        # Unrecognized values: keep for diagnostics, but continue heuristics
        signals.append(f'override_unrecognized={override}')

    # 2) Primary signal per Variables reference
    runner_env = (env.get('RUNNER_ENVIRONMENT') or '').lower()
    if runner_env in ['github-hosted', 'self-hosted']:
        return {
            'is_github_hosted': (runner_env == 'github-hosted'),
            'signals': [f'runner_environment={runner_env}']
        }

    # 3) Heuristics
    image_os = env.get('ImageOS') or env.get('IMAGE_OS')
    image_ver = env.get('ImageVersion') or env.get('IMAGE_VERSION')
    if image_os or image_ver:
        signals.append('image_vars')

    agent_tools = env.get('AGENT_TOOLSDIRECTORY', '')
    if agent_tools and 'hostedtoolcache' in agent_tools.lower():
        signals.append('hostedtoolcache')

    runner_tool_cache = env.get('RUNNER_TOOL_CACHE', '')
    if runner_tool_cache and 'hostedtoolcache' in runner_tool_cache.lower():
        signals.append('runner_tool_cache')

    workspace = env.get('GITHUB_WORKSPACE', '')
    ws_l = workspace.lower()
    if any(p in ws_l for p in ['/home/runner/', '/home/runner/work/', 'c:\\users\\runneradmin', '/users/runner/work']):
        signals.append('hosted_workspace_path')

    # Runner name patterns: only treat explicit 'self-hosted' as a negative signal
    rname = (data.get('github_context', {}).get('runner_name') or '').lower()
    if 'self-hosted' in rname and not signals:
        return {'is_github_hosted': False, 'signals': ['label_self_hosted']}
    
    # "GitHub Actions NNNNN" is a strong indicator of GitHub-hosted runners
    if rname.startswith('github actions') or rname.startswith('hosted agent'):
        signals.append('github_actions_runner_name')

    if signals:
        return {'is_github_hosted': True, 'signals': signals}

    return {'is_github_hosted': None, 'signals': signals if signals else []}

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
    
    logging.info(f"detect_runner_type: Starting detection for runner_name='{runner_name}', runner_os='{runner_os}'")

    hosting = detect_hosting_type(data)
    
    # First, try normalizing custom labels to known canonical types
    normalized = normalize_runner_label(runner_name, runner_os)
    if normalized:
        logging.info(f"detect_runner_type: Successfully normalized '{runner_name}' to '{normalized}'")
        return normalized
    
    initial = data.get('initial_snapshot', {})
    cpu_count = initial.get('cpu_count', 2)
    # Use total memory from the nested memory object; previous key was incorrect
    memory_mb = initial.get('memory', {}).get('total_mb', 7000)  # Default to ~7GB
    memory_gb = memory_mb / 1024
    
    logging.info(f"detect_runner_type: System specs - CPU cores: {cpu_count}, Memory: {memory_gb:.1f}GB")
    
    # For non-standard names, do not return the name directly. Prefer matching by stats
    # so that larger GitHub hosted runners (e.g., 4/8-core) are detected correctly.
    
    # Match based on actual system specs (CPU cores, memory, OS)
    # Find the best matching GitHub runner by specs
    best_match = None
    best_match_score = float('inf')

    # Heuristic: if the runner name looks self-hosted and OS is Linux/Windows,
    # avoid matching 16+ core tiers during detection to preserve fallback behavior.
    def _looks_self_hosted(name: str) -> bool:
        if not name:
            return False
        tokens = ['ubuntu', 'windows', 'macos', 'linux']
        return ('self-hosted' in name) or (not any(t in name for t in tokens))
    is_hosted_hint = hosting.get('is_github_hosted') is True
    restrict_to_upto_8 = (not is_hosted_hint) and _looks_self_hosted(runner_name) and (('linux' in runner_os) or ('windows' in runner_os))

    for runner_key, specs in GITHUB_RUNNERS.items():
        # Consider both standard and larger runners; billing is handled separately.
        if restrict_to_upto_8 and specs.get('vcpus', 0) > 8:
            sku_tmp = specs.get('sku', '').lower()
            if ('linux' in sku_tmp) or ('windows' in sku_tmp):
                continue
        
        # Match by SKU prefix (e.g., 'linux', 'windows', 'macos')
        sku = specs.get('sku', '')
        
        # Use public or private specs based on repo visibility
        # Standard runners have different specs: Public (4 CPU, 16GB) vs Private (2 CPU, 7GB)
        if is_public_repo and 'public_vcpus' in specs:
            spec_cores = specs.get('public_vcpus', specs.get('vcpus', 2))
            spec_memory = specs.get('public_ram_gb', specs.get('ram_gb', 7))
        else:
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
    
    # If we found a good match (score < 15 allows for some variance), use it
    if best_match and best_match_score < 15:
        logging.info(f"detect_runner_type: Matched to '{best_match}' with score {best_match_score:.2f}")
        
        # IMPORTANT: For public repos with GitHub-hosted runners and generic runner names,
        # GitHub often provisions beefier hardware (4-core) for standard runners like ubuntu-latest.
        # Billing is based on the REQUESTED label, not actual hardware specs.
        # If the runner name is generic (like "GitHub Actions NNNN") and doesn't indicate
        # a larger runner was explicitly requested, prefer standard label for billing accuracy.
        # HOWEVER: If the hardware specs EXCEED what standard runners get (even on public repos),
        # it MUST be a larger runner - don't downgrade to standard.
        matched_specs = GITHUB_RUNNERS.get(best_match, {})
        if matched_specs.get('is_larger') and is_public_repo and hosting.get('is_github_hosted') is True:
            # Get standard runner specs for public repos (the max a standard runner can have)
            # Linux/Windows public: 4 CPU, 16GB RAM
            # macOS public: varies by label, but standard is typically 3-4 cores
            if 'linux' in runner_os or 'windows' in runner_os:
                max_standard_cores = 4
                max_standard_ram_gb = 16
            else:  # macOS
                max_standard_cores = 4  # macOS-latest on public
                max_standard_ram_gb = 14
            
            # If actual hardware exceeds public standard runner specs, it's definitely a larger runner
            # regardless of the runner name (which is always "GitHub Actions NNNNN")
            hardware_exceeds_standard = (cpu_count > max_standard_cores) or (memory_gb > max_standard_ram_gb + 2)
            
            if hardware_exceeds_standard:
                # Specs exceed what any standard runner provides - this is definitely a larger runner
                logging.info(f"detect_runner_type: Hardware ({cpu_count} cores, {memory_gb:.1f}GB) exceeds standard runner max ({max_standard_cores} cores, {max_standard_ram_gb}GB) - using '{best_match}'")
                return best_match
            
            # Check if runner name indicates an explicitly requested larger runner
            name_indicates_larger = any(hint in runner_name for hint in [
                '4-core', '8-core', '16-core', '32-core', '64-core', '4core', '8core', '16core',
                '-large', '-xlarge', 'larger', 'premium', 'linux-', 'windows-'
            ])
            
            if not name_indicates_larger:
                # Hardware matches standard runner specs on public repo with generic name
                # This is likely a standard runner with upgraded hardware - use standard label (FREE)
                if 'linux' in runner_os:
                    standard_label = 'ubuntu-latest'
                elif 'windows' in runner_os:
                    standard_label = 'windows-latest'
                elif 'macos' in runner_os:
                    standard_label = 'macos-latest'
                else:
                    standard_label = best_match
                logging.info(f"detect_runner_type: Hardware matches public standard specs - using '{standard_label}' for billing (FREE)")
                return standard_label
        
        return best_match
    
    logging.warning(f"detect_runner_type: No good spec match found (best score: {best_match_score:.2f}), using fallback logic")
    
    # Fallback: determine runner by CPU cores if no good match found
    # This handles self-hosted runners or non-standard configurations
    fallback_runner = None
    if 'linux' in runner_os:
        if cpu_count <= 1:
            fallback_runner = 'ubuntu-slim'
        elif cpu_count >= 8:
            fallback_runner = 'linux-8-core'
        elif cpu_count >= 4:
            fallback_runner = 'linux-4-core'
        else:
            fallback_runner = 'ubuntu-latest'
    elif 'windows' in runner_os:
        if cpu_count >= 8:
            fallback_runner = 'windows-8-core'
        elif cpu_count >= 4:
            fallback_runner = 'windows-4-core'
        else:
            fallback_runner = 'windows-latest'
    elif 'macos' in runner_os:
        if cpu_count >= 12:
            fallback_runner = 'macos-13-large'
        elif cpu_count >= 5:
            fallback_runner = 'macos-latest-xlarge'
        else:
            fallback_runner = 'macos-latest'
    else:
        # Completely unknown OS - default to ubuntu-latest
        fallback_runner = 'ubuntu-latest'
        logging.warning(f"detect_runner_type: Unknown OS '{runner_os}', defaulting to 'ubuntu-latest'")
    
    # Check if this appears to be a self-hosted runner
    # Self-hosted runners typically have non-standard specs or runner names
    is_likely_self_hosted = (
        'self-hosted' in runner_name or 
        best_match_score >= 15 or
        runner_name not in ['', 'github actions'] and 
        not any(std in runner_name for std in ['ubuntu', 'windows', 'macos', 'linux'])
    )

    # Hosting-type hint can override label-based guess when strong signals exist
    if hosting.get('is_github_hosted') is True:
        logging.info("detect_runner_type: Hosting-type signals indicate GitHub-hosted")
        is_likely_self_hosted = False
    elif hosting.get('is_github_hosted') is False:
        logging.info("detect_runner_type: Hosting-type signals indicate Self-hosted")
        is_likely_self_hosted = True
    
    # For public repositories, prefer standard labels only when fallback is already standard.
    # Keep larger runner classification to ensure accurate paid billing guidance.
    if is_public_repo:
        fallback_specs = GITHUB_RUNNERS.get(fallback_runner, {})
        if not fallback_specs.get('is_larger'):
            if 'linux' in runner_os:
                fallback_runner = 'ubuntu-latest'
            elif 'windows' in runner_os:
                fallback_runner = 'windows-latest'
            elif 'macos' in runner_os:
                fallback_runner = 'macos-latest'
            logging.info(f"detect_runner_type: Public repo - preferring standard runner '{fallback_runner}' for billing/messaging")
        else:
            logging.info("detect_runner_type: Public repo - larger runner detected; keeping classification")

    if is_likely_self_hosted:
        logging.info(f"detect_runner_type: Detected likely self-hosted runner, using fallback '{fallback_runner}' (unclassified)")
    else:
        logging.info(f"detect_runner_type: Using fallback '{fallback_runner}' based on CPU cores")
    
    return fallback_runner

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
    
    # Determine repo visibility from telemetry data or environment
    repo_visibility_value = get_repo_visibility_from_data(data)
    is_public_repo = (repo_visibility_value == 'public')
    
    # Detect runner type, preferring standard runners for public repos
    detected_runner_type = detect_runner_type(data, is_public_repo=is_public_repo)
    runner_type = detected_runner_type
    
    runner_specs = GITHUB_RUNNERS.get(runner_type, GITHUB_RUNNERS['ubuntu-latest']).copy()

    # Determine whether this appears to be a self-hosted runner based on name patterns
    ctx = data.get('github_context', {})
    requested_name = (ctx.get('runner_name') or '').lower()
    def _is_self_hosted_name(name: str) -> bool:
        if not name:
            return False
        if 'self-hosted' in name:
            return True
        # If the name does not contain any canonical tokens, assume self-hosted
        tokens = ['ubuntu', 'windows', 'macos', 'linux']
        return not any(t in name for t in tokens)
    hosting = detect_hosting_type(data)
    if hosting.get('is_github_hosted') is True:
        is_self_hosted_context = False
    elif hosting.get('is_github_hosted') is False:
        is_self_hosted_context = True
    else:
        is_self_hosted_context = _is_self_hosted_name(requested_name)
    
    # For private repos with free public runners, use the private specs and cost
    if not is_public_repo and runner_specs.get('is_free_public'):
        # Override specs and cost for private repo
        runner_specs['vcpus'] = runner_specs.get('private_vcpus', runner_specs['vcpus'])
        runner_specs['ram_gb'] = runner_specs.get('private_ram_gb', runner_specs['ram_gb'])
        runner_specs['cost_per_min'] = runner_specs.get('private_cost_per_min', runner_specs['cost_per_min'])
        # Update name to reflect private repo specs
        if 'name' in runner_specs and '4-core' in runner_specs['name']:
            runner_specs['name'] = runner_specs['name'].replace('4-core', '2-core')
    
    # If self-hosted, we don't assume GitHub-hosted pricing for "current" cost
    current_cost = None if is_self_hosted_context else duration_minutes * runner_specs['cost_per_min']

    # Compute a true comparable (equal size) and nearest alternatives for self-hosted
    comparable_key = None
    nearest_larger_key = None
    nearest_smaller_key = None
    equivalent_key = None
    equivalent_reason = None
    if is_self_hosted_context:
        init = data.get('initial_snapshot', {})
        cpu_count = init.get('cpu_count') or init.get('cpus') or 0
        mem_mb = (init.get('memory') or {}).get('total_mb', 0)
        mem_gb = mem_mb / 1024 if mem_mb else 0

        # Determine OS family from detected label
        def _os_family(label: str) -> str:
            if label.startswith('windows'):
                return 'windows'
            if label.startswith('macos'):
                return 'macos'
            return 'linux'
        current_family = _os_family(detected_runner_type)

        # Filter catalog by OS family only (avoid cross-OS comparisons)
        catalog = {k: v for k, v in GITHUB_RUNNERS.items() if _os_family(k) == current_family}

        # Exact-core matches
        equal = [(k, v) for k, v in catalog.items() if v.get('vcpus') == cpu_count]
        if equal:
            # Choose closest RAM match
            comparable_key = min(equal, key=lambda kv: abs((kv[1].get('ram_gb') or 0) - mem_gb))[0]
        else:
            # Nearest smaller and larger by cores
            smaller = sorted([(k, v) for k, v in catalog.items() if v.get('vcpus', 0) < cpu_count], key=lambda kv: kv[1]['vcpus'], reverse=True)
            larger = sorted([(k, v) for k, v in catalog.items() if v.get('vcpus', 0) > cpu_count], key=lambda kv: kv[1]['vcpus'])
            if larger:
                nearest_larger_key = larger[0][0]
            if smaller:
                nearest_smaller_key = smaller[0][0]

        # Compute an "equivalent" hosted option that meets peak usage + headroom
        try:
            headroom = float(os.getenv('EQUIV_HEADROOM', '1.25'))
        except ValueError:
            headroom = 1.25
        # Use measured peak percentages from utilization to infer needed resources
        peak_cpu_pct = utilization.get('max_cpu_pct', 0)
        peak_mem_pct = utilization.get('max_mem_pct', 0)
        needed_vcpus = max(1, math.ceil((peak_cpu_pct / 100.0) * cpu_count * headroom)) if cpu_count else 1
        needed_ram_gb = 0
        if mem_gb:
            needed_ram_gb = math.ceil((peak_mem_pct / 100.0) * mem_gb * headroom)

        # Choose the smallest-cost option that satisfies both vCPU and RAM needs.
        def _effective_specs(label: str, specs: dict):
            v = specs.get('vcpus', 0)
            r = specs.get('ram_gb', 0)
            c = specs.get('cost_per_min', 0)
            # For private repos, standard public SKUs may have different effective specs and pricing
            if (not is_public_repo) and specs.get('is_free_public'):
                v = specs.get('private_vcpus', v)
                r = specs.get('private_ram_gb', r)
                # If no private price, skip by returning None
                priv = specs.get('private_cost_per_min')
                if priv is None:
                    return None
                c = priv
            return {'vcpus': v, 'ram_gb': r, 'cost_per_min': c, 'name': specs.get('name', label), 'label': label}

        candidates = []
        for k, v in catalog.items():
            eff = _effective_specs(k, v)
            if not eff:
                continue
            if eff['vcpus'] >= needed_vcpus and (needed_ram_gb == 0 or eff['ram_gb'] >= needed_ram_gb):
                candidates.append(eff)

        if candidates:
            # Prefer minimal vCPU, then lowest cost
            candidates.sort(key=lambda e: (e['vcpus'], e['cost_per_min']))
            chosen = candidates[0]
            equivalent_key = chosen['label']
            # Build reason string
            hr_pct = int((headroom - 1.0) * 100)
            reason_bits = [f"Needs ≥{needed_vcpus} vCPU"]
            if needed_ram_gb:
                reason_bits.append(f"and ≥{needed_ram_gb} GB RAM")
            reason_bits.append(f"(peak + {hr_pct}% headroom)")
            equivalent_reason = ' '.join(reason_bits)
    
    right_sized_runner = runner_type
    potential_savings = 0
    
    avg_cpu = utilization['avg_cpu_pct']
    avg_mem = utilization['avg_mem_pct']
    
    # Helper to derive OS family from label
    def _os_family(label: str) -> str:
        if label.startswith('windows'):
            return 'windows'
        if label.startswith('macos'):
            return 'macos'
        return 'linux'

    # Helper to derive arch family (x64 vs ARM vs mac variants)
    def _arch_family(label: str) -> str:
        l = label.lower()
        if 'arm' in l:
            return 'arm'
        # macOS: treat Apple Silicon as 'apple' and Intel as 'intel'
        if l.startswith('macos'):
            if 'intel' in l or '-13' in l or 'large' in l and 'xlarge' not in l:
                return 'intel'
            return 'apple'
        return 'x64'

    current_family = _os_family(runner_type)
    current_arch = _arch_family(runner_type)

    # Check for right-sizing opportunity (under 40% utilization)
    if avg_cpu < 40 and avg_mem < 40:
        # Find smaller runner in the SAME OS family that could work
        for name, specs in sorted(GITHUB_RUNNERS.items(), key=lambda x: x[1]['cost_per_min']):
            if _os_family(name) != current_family:
                continue
            # Enforce same architecture family to avoid cross-arch recommendations
            if _arch_family(name) != current_arch:
                continue
            # Skip public-only free SKUs when analyzing private repos (no valid private pricing)
            if (not is_public_repo) and specs.get('is_free_public') and not specs.get('private_cost_per_min'):
                continue
            # Compute effective candidate cost respecting repo visibility
            candidate_cost_per_min = specs['cost_per_min']
            if (not is_public_repo) and specs.get('is_free_public') and specs.get('private_cost_per_min') is not None:
                candidate_cost_per_min = specs['private_cost_per_min']
            # Avoid zero-cost placeholders for private repos
            if (not is_public_repo) and candidate_cost_per_min == 0:
                continue
            # Only consider cheaper runners
            if candidate_cost_per_min < runner_specs['cost_per_min']:
                new_cost = duration_minutes * candidate_cost_per_min
                if (current_cost is not None) and (new_cost < current_cost):
                    right_sized_runner = name
                    potential_savings = current_cost - new_cost
                    break
    
    # Check for parallelization opportunities
    parallelization_opportunity = None
    if analyzed_steps:
        for step in analyzed_steps:
            # Only consider steps with sample coverage; avoid misleading 0% when no samples
            if step.get('sample_count', 0) > 0 and step['avg_cpu'] < 25 and step['duration'] > 30:
                parallelization_opportunity = {
                    'step': step['name'],
                    'duration': step['duration'],
                    'avg_cpu': step['avg_cpu'],
                }
                break
    
    runs_per_day = 10
    monthly_runs = runs_per_day * 30
    
    # If self-hosted, also compute a comparative "what-if" cost on nearest GitHub-hosted SKU
    comparative_cost = None
    comparative_monthly = None
    comparable_specs = None
    nearest_larger_specs = None
    nearest_smaller_specs = None
    if is_self_hosted_context:
        # If exact comparable exists, base comparison on that; otherwise leave None
        if comparable_key:
            comparable_specs = GITHUB_RUNNERS.get(comparable_key)
            if comparable_specs:
                comparative_cost = duration_minutes * comparable_specs['cost_per_min']
                comparative_monthly = comparative_cost * monthly_runs
        # Also surface nearest alternatives for UI when no exact comparable
        if nearest_smaller_key:
            nearest_smaller_specs = GITHUB_RUNNERS.get(nearest_smaller_key)

    return {
        'runner_type': runner_type,
        'detected_runner_type': detected_runner_type,  # Include detected type for reference
        'runner_specs': runner_specs,
        'duration_minutes': duration_minutes,
        'current_cost': current_cost,
        'is_self_hosted': is_self_hosted_context,
        'comparable_runner_key': comparable_key,
        'nearest_larger_key': nearest_larger_key,
        'nearest_smaller_key': nearest_smaller_key,
        'equivalent_runner_key': equivalent_key,
        'comparable_runner_specs': comparable_specs,
        'nearest_larger_specs': nearest_larger_specs,
        'nearest_smaller_specs': nearest_smaller_specs,
        'equivalent_runner_specs': GITHUB_RUNNERS.get(equivalent_key) if equivalent_key else None,
        'equivalent_reason': equivalent_reason,
        'right_sized_runner': right_sized_runner,
        'potential_savings': potential_savings,
        'monthly_cost': (current_cost * monthly_runs) if current_cost is not None else None,
        'monthly_savings': potential_savings * monthly_runs,
        'parallelization_opportunity': parallelization_opportunity,
        'comparative_cost_if_gh_hosted': comparative_cost,
        'comparative_monthly_if_gh_hosted': comparative_monthly,
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

def recommend_runner_upgrade(max_cpu_pct, max_mem_pct, duration_seconds, current_runner_type='ubuntu-latest', is_public_repo=False):
    """Recommend a larger runner based on utilization, staying in same OS/arch family.
    
    Args:
        max_cpu_pct: Peak CPU usage percentage
        max_mem_pct: Peak memory usage percentage  
        duration_seconds: Job duration
        current_runner_type: Current runner label (e.g., 'ubuntu-latest')
        is_public_repo: Whether this is a public repo (affects specs - public gets 4-core/16GB)
    
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
    #
    # IMPORTANT: On PUBLIC repos, standard runners get UPGRADED specs:
    # - ubuntu-latest: 4 cores, 16GB (same as linux-4-core on private!)
    # - So upgrade path should go to 8-core, not 4-core
    
    # Build upgrade paths based on repo visibility
    if is_public_repo:
        # Public repos: standard runners already have 4-core/16GB
        # So upgrade path goes directly to 8-core
        upgrade_paths = {
            # Linux upgrades (public = 4-core already, go to 8-core)
            'ubuntu-slim': 'ubuntu-latest',  # 1-core to 4-core (free)
            'ubuntu-latest': 'linux-8-core',  # 4-core to 8-core (paid)
            'ubuntu-24.04': 'linux-8-core',
            'ubuntu-22.04': 'linux-8-core',
            
            # Windows upgrades (public = 4-core already, go to 8-core)
            'windows-latest': 'windows-8-core',
            'windows-2025': 'windows-8-core',
            'windows-2022': 'windows-8-core',
            
            # Larger Linux x64 upgrades
            'linux-4-core': 'linux-8-core',
            'linux-8-core': 'linux-16-core',
            'linux-16-core': 'linux-32-core',
            'linux-32-core': 'linux-64-core',
            'linux-64-core': 'linux-96-core',
            'linux-96-core': 'linux-96-core',  # cap
            
            # Larger Linux ARM upgrades
            'linux-4-core-arm': 'linux-8-core-arm',
            'linux-8-core-arm': 'linux-8-core-arm',
            
            # Larger Windows x64 upgrades
            'windows-4-core': 'windows-8-core',
            'windows-8-core': 'windows-16-core',
            'windows-16-core': 'windows-32-core',
            'windows-32-core': 'windows-64-core',
            'windows-64-core': 'windows-96-core',
            'windows-96-core': 'windows-96-core',  # cap
            
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
    else:
        # Private repos: standard runners have 2-core/7GB
        # Upgrade path goes to 4-core first
        upgrade_paths = {
            # Linux upgrades
            'ubuntu-slim': 'ubuntu-latest',  # 1-core to 2-core
            'ubuntu-latest': 'linux-4-core',  # 2-core to 4-core (requires GitHub Team+)
            'ubuntu-24.04': 'linux-4-core',
            'ubuntu-22.04': 'linux-4-core',
            
            # Larger Linux x64 upgrades
            'linux-4-core': 'linux-8-core',
            'linux-8-core': 'linux-16-core',
            'linux-16-core': 'linux-32-core',
            'linux-32-core': 'linux-64-core',
            'linux-64-core': 'linux-96-core',
            'linux-96-core': 'linux-96-core',  # cap
            
            # Larger Linux ARM upgrades
            'linux-4-core-arm': 'linux-8-core-arm',
            'linux-8-core-arm': 'linux-8-core-arm',
            
            # Windows upgrades
            'windows-latest': 'windows-4-core',  # 2-core to 4-core (requires GitHub Team+)
            'windows-2025': 'windows-4-core',
            'windows-2022': 'windows-4-core',
            
            # Larger Windows x64 upgrades
            'windows-4-core': 'windows-8-core',
            'windows-8-core': 'windows-16-core',
            'windows-16-core': 'windows-32-core',
            'windows-32-core': 'windows-64-core',
            'windows-64-core': 'windows-96-core',
            'windows-96-core': 'windows-96-core',  # cap
            
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

    # If the recommended runner is not strictly larger than current, escalate within same family
    if is_upgrade_possible and recommended_cores <= current_cores:
        if 'linux' in recommended:
            recommended = 'linux-8-core' if current_cores >= 4 else 'linux-4-core'
        elif 'windows' in recommended:
            recommended = 'windows-8-core' if current_cores >= 4 else 'windows-4-core'
        elif 'macos' in recommended:
            # Keep macOS xlarge recommendations even if core count appears lower (Apple Silicon)
            if 'xlarge' in recommended:
                pass  # keep the xlarge recommendation (stability/throughput benefits)
            else:
                # Prefer xlarge for modern macOS families
                if any(tok in current_runner_type for tok in ['latest', '14', '15']):
                    recommended = 'macos-15-xlarge'
                else:
                    recommended = 'macos-13-xlarge'
        # Refresh specs after escalation
        recommended_specs = GITHUB_RUNNERS.get(recommended, {})
        recommended_cores = recommended_specs.get('vcpus', recommended_cores)
        recommended_cost_per_min = recommended_specs.get('cost_per_min', recommended_cost_per_min)
    
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
    
    # Capacity guard: ensure recommended RAM can cover observed peak + headroom
    # Use current runner RAM as baseline to estimate peak GB from max_mem_pct
    current_ram_gb = current_specs.get('ram_gb', 0)
    observed_peak_gb = (current_ram_gb * (max_mem_pct / 100.0)) if current_ram_gb else 0
    required_ram_gb = observed_peak_gb * 1.25  # 25% headroom
    recommended_ram_gb = recommended_specs.get('ram_gb', 0)
    if is_upgrade_possible and recommended_ram_gb > 0 and required_ram_gb > 0:
        if recommended_ram_gb < required_ram_gb:
            # No suitable larger tier within same OS family for memory needs
            is_upgrade_possible = False
            # Keep current as effective recommendation to trigger optimization path
            recommended = current_runner_type
            recommended_specs = current_specs
            recommended_cores = current_cores
            recommended_cost_per_min = current_cost_per_min

    # Calculate speedup factor
    # Realistic speedup: assume near-linear scaling, but cap at 3x (diminishing returns)
    if is_upgrade_possible:
        # Special-case macOS xlarge (Apple Silicon) vs Intel 'large': treat as stability/throughput, not core-speedup
        if ('macos' in recommended) and ('xlarge' in recommended) and ('large' in current_runner_type):
            speedup_factor = 1.0
        else:
            core_ratio = recommended_cores / current_cores if current_cores > 0 else 1.0
            # Cap at 3x realistic speedup (not all workloads scale perfectly)
            speedup_factor = min(core_ratio, 3.0)
    else:
        speedup_factor = 1.0  # No upgrade available
    
    # Find reason based on what maxed out
    if max_cpu_pct >= 90 and max_mem_pct >= 90:
        reason = f'Both CPU ({max_cpu_pct:.0f}%) and memory ({max_mem_pct:.0f}%) are near limits.'
    elif max_cpu_pct >= 90:
        reason = f'CPU maxed out at {max_cpu_pct:.0f}%.'
    elif max_mem_pct >= 90:
        reason = f'Memory maxed out at {max_mem_pct:.0f}%.'
    else:
        reason = 'Resources constrained.'

    # If upgrade isn't possible due to capacity guard, clarify reasoning for macOS family
    if not is_upgrade_possible:
        # Tailor message when constrained by memory headroom
        if recommended == current_runner_type and current_ram_gb and required_ram_gb > current_ram_gb:
            reason += ' Observed memory usage exceeds available headroom for same-family upgrades; focus on optimization or increasing capacity.'
    
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
    """Generate the runner utilization and cost/performance section.

    For free GitHub-hosted runners (public repositories on standard runners),
    emphasize performance and faster feedback rather than cost savings.
    """
    utilization = calculate_utilization_score(data)
    if not utilization:
        return ""
    
    cost_analysis = calculate_cost_analysis(data, utilization, analyzed_steps)
    idle_analysis = detect_idle_time(data)

    # Determine runner billing context early to tailor messaging
    repo_visibility_value = get_repo_visibility_from_data(data)
    is_public_repo = (repo_visibility_value == 'public')
    current_runner_type = detect_runner_type(data, is_public_repo=is_public_repo)
    is_free_runner = is_runner_free(current_runner_type, is_public_repo=is_public_repo)
    
    # Self-hosted detection using hosting signals, not just runner name patterns.
    # Use detect_hosting_type() which checks environment variables, workspace paths, etc.
    hosting = detect_hosting_type(data)
    is_self_hosted_ctx = (hosting.get('is_github_hosted') is False)

    # Overutilization and suppression logic
    is_overutilized_now = (utilization['max_cpu_pct'] >= 90 or utilization['max_mem_pct'] >= 90)
    job_duration_sec = data.get('duration', 0)
    is_short_job = bool(job_duration_sec and job_duration_sec < 120)
    # Suppress optimization suggestions for free, underutilized, short jobs that are not straining resources
    should_suppress_suggestions = (is_free_runner and not is_overutilized_now and utilization['score'] < 30 and is_short_job)
    
    grade, grade_text, grade_desc = get_utilization_grade(
        utilization['score'],
        max_cpu_pct=utilization['max_cpu_pct'],
        max_mem_pct=utilization['max_mem_pct']
    )
    
    score = utilization['score']
    filled = int(score / 5)
    gauge = "█" * filled + "░" * (20 - filled)
    
    # Dynamic header and key question based on billing context
    if is_self_hosted_ctx:
        header_title = "Runner Utilization (Self-Hosted)"
        key_question = "Are you getting value from your self-hosted runner?"
    else:
        header_title = "Runner Utilization & Performance" if is_free_runner else "Runner Utilization & Cost Efficiency"
        key_question = (
            "Are you getting fast feedback from your GitHub-hosted runner?"
            if is_free_runner
            else "Are you getting maximum value from your GitHub hosted runner?"
        )

    section = f'''
---

## 💰 {header_title}

> **Key Question:** {key_question}

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
        # Determine if current runner is free or paid (prefer early detection result)
        is_free = is_free_runner
        
        # Self-hosted: show comparative "what-if" pricing with exact comparable if available
        if cost_analysis.get('is_self_hosted'):
            comp_cost = cost_analysis.get('comparative_cost_if_gh_hosted')
            comp_monthly = cost_analysis.get('comparative_monthly_if_gh_hosted')
            comp_specs = cost_analysis.get('comparable_runner_specs')
            nl_specs = cost_analysis.get('nearest_larger_specs')
            ns_specs = cost_analysis.get('nearest_smaller_specs')
            eq_specs = cost_analysis.get('equivalent_runner_specs')
            eq_reason = cost_analysis.get('equivalent_reason')

            section += "### 🧭 Cost Context\n\n"
            section += "This job ran on a **self-hosted runner**. We don't estimate your infrastructure cost.\n\n"

            # If we computed an equivalent suggestion, show it up front
            if eq_specs:
                section += "**Recommended equivalent GitHub-hosted option**\n\n"
                section += "| Runner | Cores | RAM | Cost/min | Why |\n|:--|--:|--:|--:|:--|\n"
                section += f"| `{eq_specs['name']}` | {eq_specs.get('vcpus','-')} | {eq_specs.get('ram_gb','-')} GB | {format_cost(eq_specs.get('cost_per_min',0))} | {eq_reason or ''} |\n\n"

            if comp_specs and comp_cost is not None:
                section += "**What if you used a comparable GitHub-hosted runner?**\n\n"
                section += "| Metric | Value |\n|:-------|------:|\n"
                section += f"| **Comparable Runner** | `{comp_specs['name']}` |\n"
                section += f"| **Est. Per Run** | {format_cost(comp_cost)} ({int(cost_analysis['duration_minutes'])} min) |\n"
                section += f"| **Est. Monthly** (10 runs/day) | ${comp_monthly:.2f} |\n\n"
            else:
                # Check if runner is overutilized (don't suggest smaller runners when already resource-constrained)
                is_overutilized = utilization.get('max_cpu_pct', 0) >= 90 or utilization.get('max_mem_pct', 0) >= 90
                
                section += "No exact same-size GitHub-hosted runner found. Closest options:\n\n"
                if nl_specs or (ns_specs and not is_overutilized):
                    section += "| Option | Runner | Cores | RAM | Cost/min |\n|:--|:--|--:|--:|--:|\n"
                    if nl_specs:
                        section += f"| Larger (upgrade) | `{nl_specs['name']}` | {nl_specs.get('vcpus','-')} | {nl_specs.get('ram_gb','-')} GB | {format_cost(nl_specs.get('cost_per_min',0))} |\n"
                    if ns_specs and not is_overutilized:
                        section += f"| Smaller (downgrade) | `{ns_specs['name']}` | {ns_specs.get('vcpus','-')} | {ns_specs.get('ram_gb','-')} GB | {format_cost(ns_specs.get('cost_per_min',0))} |\n"
                elif is_overutilized and not nl_specs:
                    section += "No larger GitHub-hosted runner available for this OS. Consider optimizing the workload or increasing self-hosted capacity.\n"
                section += "\n"

            section += "Benefits of GitHub-hosted runners:\n"
            section += "- Ephemeral, isolated VMs for clean, deterministic builds\n"
            section += "- OS images patched and maintained by GitHub (reduced ops burden)\n"
            section += "- Scales on demand; no capacity planning or host maintenance\n"
            section += "- Security-hardened images and regular updates\n\n"
            section += "> Pricing: [GitHub Actions Runner Pricing](https://docs.github.com/en/enterprise-cloud@latest/billing/reference/actions-runner-pricing)\n\n"
            section += "> Private networking: You can connect GitHub-hosted runners to resources on a private network (package registries, secret managers, on-prem services). See [Private networking for GitHub-hosted runners](https://docs.github.com/en/enterprise-cloud@latest/actions/concepts/runners/private-networking).\n\n"
        # Skip cost analysis for free runners - cost analysis doesn't apply when price is $0
        elif not is_free:
            cost_display = f"{format_cost(cost_analysis['current_cost'])} ({int(cost_analysis['duration_minutes'])} min)"
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
        
        # Only show cost-savings right-size recommendation when runner is paid
        if (not is_free) and cost_analysis['right_sized_runner'] != cost_analysis['runner_type'] and is_truly_underutilized:
            right_specs = GITHUB_RUNNERS.get(cost_analysis['right_sized_runner'], GITHUB_RUNNERS['ubuntu-latest'])
            savings_pct = (cost_analysis['potential_savings'] / cost_analysis['current_cost'] * 100) if cost_analysis['current_cost'] > 0 else 0
            section += f'''
> 💡 **Optimization Opportunity: Right-Size Your Runner**
>
> Based on your usage, `{right_specs['name']}` would be more cost-effective:
>
> | | Current | Right-Sized | Savings |
> |:--|--------:|----------:|--------:|
> | **Per Run** | {format_cost(cost_analysis['current_cost'])} | {format_cost(cost_analysis['current_cost'] - cost_analysis['potential_savings'])} | **{format_cost(cost_analysis['potential_savings'])}** ({savings_pct:.0f}%) |
> | **Monthly** | ${cost_analysis['monthly_cost']:.2f} | ${cost_analysis['monthly_cost'] - cost_analysis['monthly_savings']:.2f} | **${cost_analysis['monthly_savings']:.2f}** |
>
> If you choose to change runners, select an equivalent size in the same OS family. Typical availability:
> - Linux: standard (ubuntu-latest) and larger 4-core, 8-core sizes.
> - Windows: standard (windows-latest) and larger 4-core, 8-core sizes.
> - macOS: standard (macos-latest), larger (e.g., 12‑core), and xlarge options.
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

'''

        # Show potential causes only if we're not suppressing suggestions
        if not should_suppress_suggestions:
            section += "Common causes:\n- Waiting for package downloads (use caching)\n- Sequential steps that could be parallelized\n- Inefficient workflow design\n\n"

    # Add disclaimer for very short jobs where utilization/idle metrics can be noisy
    if job_duration_sec and job_duration_sec < 60:
        section += f"""
> ℹ️ **Note:** This job is short ({format_duration(job_duration_sec)}). Utilization and idle metrics can be skewed on brief runs.

"""
    
    # Decision helper - no self-hosted recommendation
    # Conditionally render optimization strategy. Omit for free, underutilized, short jobs.
    if not should_suppress_suggestions:
        section += '''
### 🎯 Optimization Strategy

GitHub hosted runners are most useful when jobs finish quickly and resources match the workload:

'''
    
    # Check for overutilization (CPU or Memory at 90%+)
    is_overutilized = (utilization['max_cpu_pct'] >= 90 or utilization['max_mem_pct'] >= 90)
    
    if is_overutilized:
        # Get specific runner recommendation (respecting OS/architecture)
        duration_sec = data.get('duration', 0)
        
        # Determine repo visibility for accurate detection
        repo_visibility_value = get_repo_visibility_from_data(data)
        is_public_repo = (repo_visibility_value == 'public')
        
        current_runner = detect_runner_type(data, is_public_repo=is_public_repo)
        
        upgrade_rec = recommend_runner_upgrade(
            utilization['max_cpu_pct'],
            utilization['max_mem_pct'],
            duration_sec,
            current_runner_type=current_runner,
            is_public_repo=is_public_repo
        )
        
        # FORCE upgrade if still not possible and current is small runner
        if not upgrade_rec['is_upgrade_possible']:
            current_specs = GITHUB_RUNNERS.get(current_runner, {})
            # For public repos, standard runners have 4 cores; for private, 2 cores
            effective_cores = current_specs.get('public_vcpus', current_specs.get('vcpus', 2)) if is_public_repo else current_specs.get('vcpus', 2)
            
            # Determine if we need to force an upgrade based on effective core count
            # Public repos with 4-core standard runners → go to 8-core
            # Private repos with 2-core standard runners → go to 4-core
            if effective_cores <= 4:
                if 'windows' in current_runner.lower():
                    upgrade_rec['recommended'] = 'windows-8-core' if is_public_repo else 'windows-4-core'
                elif 'macos' in current_runner.lower():
                    upgrade_rec['recommended'] = 'macos-13-large'
                else:
                    upgrade_rec['recommended'] = 'linux-8-core' if is_public_repo else 'linux-4-core'
                # Recalculate specs for forced upgrade
                new_specs = GITHUB_RUNNERS.get(upgrade_rec['recommended'], {})
                upgrade_rec['cores'] = new_specs.get('vcpus', 8 if is_public_repo else 4)
                upgrade_rec['ram_gb'] = new_specs.get('ram_gb', 32 if is_public_repo else 16)
                upgrade_rec['name'] = new_specs.get('name', upgrade_rec['recommended'])
                upgrade_rec['cost_per_min'] = new_specs.get('cost_per_min', 0.032 if is_public_repo else 0.012)
                upgrade_rec['is_upgrade_possible'] = True
        
        # Check if upgrade is actually possible
        # For custom runners (not in GITHUB_RUNNERS), skip standard upgrade recommendations
        is_custom_runner = upgrade_rec['recommended'] not in GITHUB_RUNNERS
        
        if upgrade_rec['is_upgrade_possible'] and not is_custom_runner:
            # macOS: reference official docs instead of prescribing a specific label
            if 'macos' in current_runner.lower():
                section += f'''
**Priority: Consider macOS Larger Runners ⚠️**

Your job is **straining resources** on the current runner:
- CPU peaked at **{utilization['max_cpu_pct']:.1f}%** (avg: {utilization['avg_cpu_pct']:.1f}%)
- Memory peaked at **{utilization['max_mem_pct']:.1f}%** (avg: {utilization['avg_mem_pct']:.1f}%)

For macOS, choose from larger runner families based on workload characteristics and memory needs:
- **Large (Intel):** 12 CPU, 30 GB RAM
- **XLarge (Apple Silicon M2):** 5 CPU (+8 GPU), 14 GB RAM

{macos_labels_doc_line()}
Pricing: [GitHub Actions Runner Pricing](https://docs.github.com/en/enterprise-cloud@latest/billing/reference/actions-runner-pricing)

**Note:** Larger runners require a **GitHub Team or GitHub Enterprise Cloud** plan.
'''
                # Skip prescriptive label and detailed cost calc for macOS per policy
                return section
            # Non-macOS path: show specific upgrade recommendation
            recommended_runner = GITHUB_RUNNERS.get(upgrade_rec['recommended'], {})
            current_cost_per_min = upgrade_rec['current_cost_per_min']
            # Adjust current cost for private repos on standard runners
            if not is_public_repo:
                current_specs_override = GITHUB_RUNNERS.get(current_runner, {})
                if current_specs_override.get('is_free_public') and current_specs_override.get('private_cost_per_min') is not None:
                    current_cost_per_min = current_specs_override['private_cost_per_min']
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
            repo_visibility_value = get_repo_visibility_from_data(data)
            is_public_repo = (repo_visibility_value == 'public')
            
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

**Reliability improvements:** Fewer timeouts saves ~${timeout_savings:.0f}/month {timeout_assumptions}

**Total hidden value: ~${total_hidden_value:.0f}/month** in productivity and reliability.

**Note:** You're currently using a free runner (public repo benefit). This recommendation requires switching to a paid larger runner.'''
            elif cost_diff < 0:
                savings_pct = abs(cost_diff / current_run_cost * 100)
                upgrade_note = f'**✅ Cost Savings!** The faster runner saves ~{format_cost(abs(cost_diff))}/run ({savings_pct:.0f}% cheaper). Plus ${hidden_value_saved:.0f}/month in developer productivity and ${timeout_savings:.0f}/month from fewer timeouts.'
            elif abs(cost_diff) < 0.0001:  # Same cost (within rounding)
                upgrade_note = f'**✅ Same Cost, {speedup_factor:.1f}x Faster!** Get {speedup_factor:.1f}x faster job execution at the same price.\n\n**Hidden Value Breakdown:**\n- Developer waiting time: {time_saved_per_month_hours:.1f} hours/month = **${hidden_value_saved:.0f}/month**\n- Fewer timeouts: {timeouts_per_month_current:.0f}→{timeouts_per_month_new:.0f} per month = **${timeout_savings:.0f}/month savings** {timeout_assumptions}\n\n**Total Hidden Value: ~${total_hidden_value:.0f}/month** in productivity and reliability improvements!'
            elif speedup_factor > 1.5:
                upgrade_note = f'**💡 Fast Execution:** {speedup_factor:.1f}x faster = quicker feedback. Additional cost of {format_cost(abs(cost_diff))}/run is more than offset by {time_saved_per_month_hours:.1f} hours of saved developer time (~${hidden_value_saved:.0f}/month) and ${timeout_savings:.0f}/month from improved reliability {timeout_assumptions}.'
            else:
                upgrade_note = '**💡 Trade-off:** Slightly higher cost, but better reliability and resource availability.'
            
            section += f'''
**Priority: Upgrade to Larger Runner ⚠️**

Your job is **straining resources** on the current runner:
- CPU peaked at **{utilization['max_cpu_pct']:.1f}%** (avg: {utilization['avg_cpu_pct']:.1f}%)
- Memory peaked at **{utilization['max_mem_pct']:.1f}%** (avg: {utilization['avg_mem_pct']:.1f}%)

**Recommended Runner: {upgrade_rec['name']} ({upgrade_rec['cores']}-core, {upgrade_rec['ram_gb']}GB RAM)**

**Why:** {upgrade_rec['reason']}

'''
            # Only show core comparison when increasing cores
            # Use measured cores from telemetry for the current runner
            current_specs_for_msg = GITHUB_RUNNERS.get(current_runner, {})
            current_cores_for_msg = utilization.get('total_cpu_cores', current_specs_for_msg.get('vcpus', 0))
            if upgrade_rec['cores'] > current_cores_for_msg:
                section += f"**Expected Performance:** {upgrade_rec['speedup_estimate']} (upgrade from {current_cores_for_msg} to {upgrade_rec['cores']} cores)\n\n"
            else:
                section += f"**Expected Performance:** {upgrade_rec['speedup_estimate']}\n\n"

            section += """
**Cost Impact (accounting for faster execution):**
"""
            
            # Different cost display based on billing context
            if current_is_free and not new_is_free:
                section += f'''- **Current: FREE** ({duration_min:.0f} min @ $0.00/min on public repository)
- **Recommended: {format_cost(new_run_cost)}/run** (est. {estimated_new_duration_min:.1f} min @ {format_cost(new_cost_per_min)}/min)
- **Additional cost per run: +{format_cost(new_run_cost)}**

**Monthly Cost Comparison** (if you run 10 times/day, 300 runs/month):
- **Current: FREE** ($0/month on free tier)
- **Recommended: ${new_monthly:.2f}/month** ({format_cost(new_run_cost)}/run × 300 runs)

⚠️ **Important Trade-off:** You're currently using GitHub's free runners available to public repositories. Upgrading to a larger runner means incurring costs, but you gain significant speed and reliability benefits listed above.
'''
            else:
                # Calculate percentage changes safely (avoid division by zero for free runners)
                cost_diff_pct = (cost_diff/current_run_cost*100) if current_run_cost > 0 else 0
                monthly_diff_pct = (monthly_diff/current_monthly*100) if current_monthly > 0 else 0
                
                section += f'''- Current: {format_cost(current_run_cost)}/run ({duration_min:.0f} min @ {format_cost(current_cost_per_min)}/min)
- Recommended: {format_cost(new_run_cost)}/run (est. {estimated_new_duration_min:.1f} min @ {format_cost(new_cost_per_min)}/min)
 - **Per-run difference: {'-' if cost_diff < 0 else '+'}{format_cost(abs(cost_diff))}** ({'-' if cost_diff < 0 else '+'}{abs(cost_diff_pct):.0f}%)

**Monthly Cost Comparison** (10 runs/day, 300 runs/month):
- Current: ${current_monthly:.2f}
- Recommended: ${new_monthly:.2f}
 - **Monthly difference: {'-$' if monthly_diff < 0 else '+$'}{abs(monthly_diff):.2f}** ({'-' if monthly_diff < 0 else '+'}{abs(monthly_diff_pct):.0f}%)
'''
            
            # Append upgrade note and avoid duplicating plan availability messaging
            section += f'''
{upgrade_note}{plan_note}

**How to Switch:**
{'' if plan_note else '**Note:** Larger runners require a GitHub Team or GitHub Enterprise Cloud plan and must be set up by your organization administrator.'}

To change runners, choose a label in the same OS family. Typical availability:
- Linux: standard (ubuntu-latest) and larger 4-core, 8-core sizes.
- Windows: standard (windows-latest) and larger 4-core, 8-core sizes.
- macOS: standard (macos-latest), larger (e.g., 12‑core), and xlarge options.

For setup instructions, see: [GitHub Actions - Manage Larger Runners](https://docs.github.com/en/enterprise-cloud@latest/actions/how-tos/manage-runners/larger-runners/manage-larger-runners)

For pricing details, see: [GitHub Actions Runner Pricing](https://docs.github.com/en/enterprise-cloud@latest/billing/reference/actions-runner-pricing)

'''
        else:
            # No standard upgrade available, or this is a custom runner
            # For custom/self-hosted runners, provide two clear avenues
            if is_custom_runner or is_self_hosted_ctx:
                # Choose a reasonable hosted label to suggest if available
                hosted_suggestion = cost_analysis.get('equivalent_runner_key') or cost_analysis.get('comparable_runner_key') or cost_analysis.get('nearest_larger_key') or cost_analysis.get('nearest_smaller_key')
                section += f'''
**Priority: Optimize or Consider Hosted Option**

Your job is **straining resources** on the current runner:
- CPU peaked at **{utilization['max_cpu_pct']:.1f}%** (avg: {utilization['avg_cpu_pct']:.1f}%)
- Memory peaked at **{utilization['max_mem_pct']:.1f}%** (avg: {utilization['avg_mem_pct']:.1f}%)

**Option A — Increase self-hosted capacity:**
- Scale the machine or VM backing your runner (more vCPU/RAM).
- Restart the runner service so jobs pick up the new resources.

**Option B — Use a comparable GitHub-hosted runner:**
- Switch to a hosted label sized for your job.
Typical availability by OS family:
- Linux: standard (ubuntu-latest) and larger 4-core, 8-core sizes.
- Windows: standard (windows-latest) and larger 4-core, 8-core sizes.
- macOS: standard (macos-latest), larger (e.g., 12‑core), and xlarge options.

**Near-term optimizations:**

1. **Parallelize jobs** - Split work across parallel jobs using a matrix strategy.
2. **Improve caching** - Cache dependencies to reduce build time

3. **Profile slow steps** - Identify and optimize bottlenecks

4. **Run targeted tests** - Only test changed modules, not full suite

**Alternative to explore:** If resource needs remain high after optimization, consider using a **GitHub-hosted runner** family (standard or larger, depending on utilization). Hosted runners provide predictable capacity and simplified management.

Pricing: [GitHub Actions Runner Pricing](https://docs.github.com/en/enterprise-cloud@latest/billing/reference/actions-runner-pricing)
Setup: [Manage Larger Runners](https://docs.github.com/en/enterprise-cloud@latest/actions/how-tos/manage-runners/larger-runners/manage-larger-runners)

'''
                if 'macos' in current_runner.lower():
                    section += macos_labels_doc_line() + "\n\n"

            elif current_runner in ['ubuntu-latest', 'ubuntu-24.04', 'ubuntu-22.04']:
                section += f'''
**Priority: Optimize Build (or Upgrade to Larger Runner) ⚠️**

Your job is **straining resources** on the current runner:
- CPU peaked at **{utilization['max_cpu_pct']:.1f}%** (avg: {utilization['avg_cpu_pct']:.1f}%)
- Memory peaked at **{utilization['max_mem_pct']:.1f}%** (avg: {utilization['avg_mem_pct']:.1f}%)

**Limitation:** GitHub's **free tier** standard Linux runners max out at **2 cores** (`ubuntu-latest`, `ubuntu-24.04`, `ubuntu-22.04`).

**Option 1: Optimize your build first** (recommended, free tier-friendly) - Most cost-effective solution:

1. **Parallelize jobs** - Split work across a build/test matrix.

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
            elif 'macos' in current_runner.lower():
                # macOS-specific optimize path (when no upgrade available or already on large tier)
                section += f'''
**Priority: Optimize Build ⚠️**

Your job is **straining resources** on the current runner:
- CPU peaked at **{utilization['max_cpu_pct']:.1f}%** (avg: {utilization['avg_cpu_pct']:.1f}%)
- Memory peaked at **{utilization['max_mem_pct']:.1f}%** (avg: {utilization['avg_mem_pct']:.1f}%)

You're already on a larger macOS runner. Focus on optimization strategies:

1. **Parallelize** - Use matrix strategy for independent jobs
2. **Cache** - Improve dependency caching to reduce download time
3. **Profile** - Identify and optimize slowest steps (especially Xcode builds)
4. **Simplify** - Remove unnecessary dependencies and tools

If you need more capacity, check available macOS runner tiers:
{macos_labels_doc_line()}

**More options:** [GitHub Actions Runner Pricing](https://docs.github.com/en/enterprise-cloud@latest/billing/reference/actions-runner-pricing)

'''
            else:
                # Non-macOS generic optimize path
                section += f'''
**Priority: Optimize Build ⚠️**

Your job is **straining resources** on the current runner:
- CPU peaked at **{utilization['max_cpu_pct']:.1f}%** (avg: {utilization['avg_cpu_pct']:.1f}%)
- Memory peaked at **{utilization['max_mem_pct']:.1f}%** (avg: {utilization['avg_mem_pct']:.1f}%)

Larger GitHub-hosted runners are available; consider upgrading to a higher vCPU/RAM tier if performance is constrained.
Examples (subject to plan availability): Linux/Windows offer 16, 32, 64, or 96 vCPU tiers. See documentation for the full list and current pricing.

**Options to address overutilization:**

1. **Parallelize** - Use matrix strategy for independent jobs
2. **Cache** - Improve dependency caching to reduce download time
3. **Profile** - Identify and optimize slowest steps
4. **Simplify** - Remove unnecessary dependencies and tools

**More options:** [GitHub Actions Runner Pricing](https://docs.github.com/en/enterprise-cloud@latest/billing/reference/actions-runner-pricing)

'''

    elif utilization['score'] < 30 and not should_suppress_suggestions:
        # Determine if downsizing is possible (paid runner with cheaper same-family option)
        downsizing_possible = False
        downsizing_label = None
        if cost_analysis and (not is_free_runner):
            if cost_analysis.get('right_sized_runner') and cost_analysis.get('runner_type'):
                if cost_analysis['right_sized_runner'] != cost_analysis['runner_type'] and cost_analysis.get('potential_savings', 0) > 0:
                    downsizing_possible = True
                    downsizing_label = GITHUB_RUNNERS.get(cost_analysis['right_sized_runner'], {}).get('name', cost_analysis['right_sized_runner'])

        section += """
**Priority: High Utilization Improvement**

"""
        if downsizing_possible:
            section += f"- **Right-size runner:** Switch to `{downsizing_label}` to cut cost per run.\n"
        else:
            section += "- **Right-size workflow:** Already on the smallest tier? Focus on workflow efficiency over runner size.\n"

        section += """
- **Parallelize jobs:** Use matrix builds for independent steps  
- **Optimize caching:** Cache dependencies to reduce download time
- **Check for bottlenecks:** Identify and optimize slow sequential steps

With these optimizations, you can typically achieve 50-70% utilization and {benefit} by 30-50%.

""".format(benefit=('reduce build time' if is_free_runner else 'reduce costs'))
        # macOS: include official labels documentation link across optimize guidance
        if 'macos' in current_runner_type.lower():
            section += macos_labels_doc_line() + "\n\n"
    elif utilization['score'] >= 70 and not should_suppress_suggestions:
        section += f'''
**Status: Well-Optimized ✅**

Your runner utilization is excellent at {utilization['score']:.0f}%. Continue:
- Monitoring trends over time
- Considering larger runners only if hitting resource limits
- Regular performance reviews

'''
    elif not should_suppress_suggestions:
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

    # --- Fallback estimation (populate sections by default) ---
    # If I/O and performance metrics are entirely zero, estimate light baseline
    # so the tables are informative. Can be disabled with IO_FALLBACK=off.
    fallback_enabled = os.environ.get('IO_FALLBACK', 'on').lower() not in ['off', '0', 'false']
    profile = os.environ.get('IO_FALLBACK_PROFILE', 'light').lower()
    fallback_applied_io = False
    fallback_applied_perf = False
    interval = data.get('interval', 2)
    effective_duration = duration if duration and duration > 0 else (len(samples) * interval)

    def _profile_rates_mb_s(p):
        # Conservative baseline rates
        if p == 'heavy':
            return {
                'disk_read': 4.0, 'disk_write': 2.5,
                'net_rx': 3.0, 'net_tx': 1.8
            }
        # default light
        return {
            'disk_read': 1.0, 'disk_write': 0.7,
            'net_rx': 0.8, 'net_tx': 0.5
        }

    def _profile_perf_pct(p):
        if p == 'heavy':
            return {'iowait': 2.0, 'steal': 0.6, 'swap': 1.5}
        return {'iowait': 0.6, 'steal': 0.2, 'swap': 0.8}

    if fallback_enabled:
        # I/O Summary fallback when all streams are zero
        if (sum(disk_read) == 0 and sum(disk_write) == 0 and sum(net_rx) == 0 and sum(net_tx) == 0):
            rates = _profile_rates_mb_s(profile)
            n = max(1, len(samples))
            disk_read = [rates['disk_read']] * n
            disk_write = [rates['disk_write']] * n
            net_rx = [rates['net_rx']] * n
            net_tx = [rates['net_tx']] * n
            total_disk_read = rates['disk_read'] * effective_duration
            total_disk_write = rates['disk_write'] * effective_duration
            total_net_rx = rates['net_rx'] * effective_duration
            total_net_tx = rates['net_tx'] * effective_duration
            fallback_applied_io = True

        # Performance Metrics fallback when all are zero
        if (max_iowait == 0 and max_steal == 0 and max_swap == 0):
            perf = _profile_perf_pct(profile)
            n = max(1, len(samples))
            iowait_values = [perf['iowait']] * n
            steal_values = [perf['steal']] * n
            swap_values = [perf['swap']] * n
            avg_iowait = sum(iowait_values) / len(iowait_values)
            max_iowait = max(iowait_values)
            avg_steal = sum(steal_values) / len(steal_values)
            max_steal = max(steal_values)
            avg_swap = sum(swap_values) / len(swap_values)
            max_swap = max(swap_values)
            fallback_applied_perf = True
    
    # Avoid backslashes inside f-string expressions: precompute baseline notes
    baseline_perf_note = "> ℹ️ Estimated baseline shown (no telemetry for I/O/CPU wait).\n" if fallback_applied_perf else ""
    baseline_io_note = "> ℹ️ Estimated baseline shown (no I/O telemetry captured).\n" if fallback_applied_io else ""

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

{baseline_perf_note}

## 💾 I/O Summary

| Metric | Total | Avg Rate |
|:-------|------:|---------:|
| 📥 **Disk Read** | {format_bytes(total_disk_read * 1024 * 1024)} | {format_bytes(sum(disk_read) / len(disk_read) * 1024 * 1024)}/s |
| 📤 **Disk Write** | {format_bytes(total_disk_write * 1024 * 1024)} | {format_bytes(sum(disk_write) / len(disk_write) * 1024 * 1024)}/s |
| 🌐 **Network RX** | {format_bytes(total_net_rx * 1024 * 1024)} | {format_bytes(sum(net_rx) / len(net_rx) * 1024 * 1024)}/s |
| 🌐 **Network TX** | {format_bytes(total_net_tx * 1024 * 1024)} | {format_bytes(sum(net_tx) / len(net_tx) * 1024 * 1024)}/s |

{baseline_io_note}
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
    runner_name = ctx.get('runner_name', 'GitHub Hosted')
    runner_arch = infer_runner_architecture(runner_name, ctx.get('runner_arch'))
    report += f'''
---

## 🖥️ Runner Information

| Component | Details |
|:----------|:--------|
| **Runner** | {runner_name} |
| **OS** | {ctx.get('runner_os', 'Linux')} |
| **Architecture** | {runner_arch} |
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
            raw_cmd = p.get('command') or ''
            raw_cmd = str(raw_cmd).strip()
            if not raw_cmd:
                cmd = 'unknown'
            else:
                base = raw_cmd.split('/')[-1]
                tokens = base.split()
                cmd = (tokens[0] if tokens else base)[:30] or 'unknown'
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
                {ctx.get('runner_os', 'Linux')} / {infer_runner_architecture(ctx.get('runner_name', ''), ctx.get('runner_arch'))}
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
        hosting = detect_hosting_type(data)
        
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
            'environment_signals': {
                'hosting_override': os.environ.get('HOSTING_TYPE'),
                'runner_environment': os.environ.get('RUNNER_ENVIRONMENT'),
                'runner_tool_cache': os.environ.get('RUNNER_TOOL_CACHE'),
                'is_github_hosted': hosting.get('is_github_hosted'),
                'signals': hosting.get('signals', []),
            },
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
