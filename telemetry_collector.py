#!/usr/bin/env python3
"""
Telemetry Collector - Collects system metrics over time.
Runs in background and samples metrics at regular intervals.

Supports Linux, macOS, and Windows platforms.
"""

import os
import sys
import json
import time
import subprocess
import platform
import re
import io
from datetime import datetime
from pathlib import Path

# Detect platform once at module load
PLATFORM = platform.system()  # 'Linux', 'Darwin' (macOS), or 'Windows'
IS_LINUX = PLATFORM == 'Linux'
IS_MACOS = PLATFORM == 'Darwin'
IS_WINDOWS = PLATFORM == 'Windows'

# Fix Windows console encoding for emoji/unicode output
if IS_WINDOWS:
    # Reconfigure stdout/stderr to use UTF-8 with error replacement
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass  # Fallback: continue with default encoding

# Platform-specific data file path
if IS_WINDOWS:
    _default_data_file = os.path.join(os.environ.get('TEMP', 'C:\\Temp'), 'telemetry_data.json')
else:
    _default_data_file = '/tmp/telemetry_data.json'

DATA_FILE = os.environ.get('TELEMETRY_DATA_FILE', _default_data_file)
SAMPLE_INTERVAL = float(os.environ.get('TELEMETRY_INTERVAL', '2'))  # seconds


# ============================================================================
# PLATFORM-SPECIFIC IMPLEMENTATIONS
# ============================================================================

# --- macOS implementations ---

def _macos_get_cpu_usage():
    """Get CPU usage on macOS using top command.
    
    Returns (cpu_percent, -1) to signal direct percentage mode.
    The -1 as second value tells collect_sample to use the first value directly.
    """
    try:
        # Use top in logging mode for a quick sample
        # -l 2 takes two samples (first is since boot, second is interval-based)
        result = subprocess.run(
            ['top', '-l', '2', '-n', '0', '-s', '1'],
            capture_output=True, text=True, timeout=10
        )
        # top -l 2 gives two samples - use the second one for accurate reading
        lines = result.stdout.split('\n')
        for line in reversed(lines):  # Get the last (second) CPU usage line
            if 'CPU usage' in line:
                # "CPU usage: 10.0% user, 5.0% sys, 85.0% idle"
                user_match = re.search(r'(\d+\.?\d*)% user', line)
                sys_match = re.search(r'(\d+\.?\d*)% sys', line)
                if user_match and sys_match:
                    cpu_pct = float(user_match.group(1)) + float(sys_match.group(1))
                    return cpu_pct, -1  # -1 signals direct percentage mode
                break
        return 0, -1
    except:
        return 0, -1


def _macos_get_memory_info():
    """Get memory info on macOS using vm_stat and sysctl."""
    try:
        # Get total memory
        result = subprocess.run(
            ['sysctl', '-n', 'hw.memsize'],
            capture_output=True, text=True, timeout=5
        )
        total_bytes = int(result.stdout.strip())
        total_mb = total_bytes // (1024 * 1024)
        
        # Get memory stats from vm_stat
        result = subprocess.run(['vm_stat'], capture_output=True, text=True, timeout=5)
        
        # Parse vm_stat output
        page_size = 4096  # Default page size
        stats = {}
        for line in result.stdout.split('\n'):
            if 'page size of' in line:
                match = re.search(r'page size of (\d+) bytes', line)
                if match:
                    page_size = int(match.group(1))
            elif ':' in line:
                key, value = line.split(':')
                value = value.strip().rstrip('.')
                if value.isdigit():
                    stats[key.strip()] = int(value)
        
        # Calculate used memory
        free_pages = stats.get('Pages free', 0)
        inactive_pages = stats.get('Pages inactive', 0)
        speculative_pages = stats.get('Pages speculative', 0)
        
        available_pages = free_pages + inactive_pages + speculative_pages
        available_mb = (available_pages * page_size) // (1024 * 1024)
        used_mb = total_mb - available_mb
        
        return {
            'total_mb': total_mb,
            'used_mb': used_mb,
            'available_mb': available_mb,
            'buffers_mb': 0,
            'cached_mb': 0,
            'percent': round((used_mb / total_mb) * 100, 2) if total_mb > 0 else 0
        }
    except:
        return {'total_mb': 0, 'used_mb': 0, 'available_mb': 0, 'percent': 0}


def _macos_get_disk_io():
    """Get disk I/O on macOS using iostat."""
    try:
        result = subprocess.run(
            ['iostat', '-d', '-c', '1'],
            capture_output=True, text=True, timeout=5
        )
        # iostat output varies, return cumulative bytes if available
        # For now, return zeros - iostat on macOS doesn't easily give cumulative
        return {'read_bytes': 0, 'write_bytes': 0}
    except:
        return {'read_bytes': 0, 'write_bytes': 0}


def _macos_get_network_io():
    """Get network I/O on macOS using netstat."""
    try:
        result = subprocess.run(
            ['netstat', '-ib'],
            capture_output=True, text=True, timeout=5
        )
        lines = result.stdout.strip().split('\n')
        total_rx = 0
        total_tx = 0
        
        for line in lines[1:]:  # Skip header
            parts = line.split()
            if len(parts) >= 10 and parts[0] != 'lo0':
                # Name Mtu Network Address Ipkts Ierrs Ibytes Opkts Oerrs Obytes
                try:
                    # Find columns with bytes (usually Ibytes=6, Obytes=9)
                    ibytes_idx = 6
                    obytes_idx = 9
                    if parts[ibytes_idx].isdigit() and parts[obytes_idx].isdigit():
                        total_rx += int(parts[ibytes_idx])
                        total_tx += int(parts[obytes_idx])
                except (IndexError, ValueError):
                    pass
        
        return {'rx_bytes': total_rx, 'tx_bytes': total_tx}
    except:
        return {'rx_bytes': 0, 'tx_bytes': 0}


def _macos_get_load_average():
    """Get load average on macOS using sysctl."""
    try:
        result = subprocess.run(
            ['sysctl', '-n', 'vm.loadavg'],
            capture_output=True, text=True, timeout=5
        )
        # Output: "{ 1.52 1.67 1.89 }"
        match = re.search(r'\{\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)', result.stdout)
        if match:
            return {
                'load_1m': float(match.group(1)),
                'load_5m': float(match.group(2)),
                'load_15m': float(match.group(3)),
                'running_procs': 'N/A'
            }
        return {'load_1m': 0, 'load_5m': 0, 'load_15m': 0, 'running_procs': 'N/A'}
    except:
        return {'load_1m': 0, 'load_5m': 0, 'load_15m': 0, 'running_procs': 'N/A'}


def _macos_get_cpu_detailed():
    """Get detailed CPU metrics on macOS."""
    try:
        result = subprocess.run(
            ['top', '-l', '1', '-n', '0'],
            capture_output=True, text=True, timeout=5
        )
        user = sys_pct = idle = 0
        for line in result.stdout.split('\n'):
            if 'CPU usage' in line:
                match = re.search(r'(\d+\.?\d*)% user.*?(\d+\.?\d*)% sys.*?(\d+\.?\d*)% idle', line)
                if match:
                    user = int(float(match.group(1)) * 100)
                    sys_pct = int(float(match.group(2)) * 100)
                    idle = int(float(match.group(3)) * 100)
        
        total = user + sys_pct + idle
        return {
            'user': user,
            'nice': 0,
            'system': sys_pct,
            'idle': idle,
            'iowait': 0,  # Not available on macOS
            'irq': 0,
            'softirq': 0,
            'steal': 0,   # Not available on macOS
            'total': total if total > 0 else 10000
        }
    except:
        return {'user': 0, 'nice': 0, 'system': 0, 'idle': 0, 'iowait': 0, 'steal': 0, 'total': 1}


def _macos_get_swap_info():
    """Get swap info on macOS."""
    try:
        result = subprocess.run(
            ['sysctl', '-n', 'vm.swapusage'],
            capture_output=True, text=True, timeout=5
        )
        # Output: "total = 2048.00M  used = 1024.00M  free = 1024.00M  (encrypted)"
        total = used = free = 0
        match = re.search(r'total\s*=\s*([\d.]+)M.*used\s*=\s*([\d.]+)M.*free\s*=\s*([\d.]+)M', result.stdout)
        if match:
            total = int(float(match.group(1)))
            used = int(float(match.group(2)))
            free = int(float(match.group(3)))
        
        return {
            'total_mb': total,
            'used_mb': used,
            'free_mb': free,
            'percent': round((used / total) * 100, 2) if total > 0 else 0
        }
    except:
        return {'total_mb': 0, 'used_mb': 0, 'free_mb': 0, 'percent': 0}


# --- Windows implementations ---

def _windows_get_cpu_usage():
    """Get CPU usage on Windows using wmic.
    
    Returns (cpu_percent, -1) to signal direct percentage mode.
    The -1 as second value tells collect_sample to use the first value directly.
    """
    try:
        result = subprocess.run(
            ['wmic', 'cpu', 'get', 'loadpercentage'],
            capture_output=True, text=True, timeout=10, shell=True
        )
        lines = [l.strip() for l in result.stdout.strip().split('\n') if l.strip()]
        if len(lines) >= 2 and lines[1].isdigit():
            cpu_pct = int(lines[1])
            return cpu_pct, -1  # -1 signals direct percentage mode
        return 0, -1
    except:
        return 0, -1


def _windows_get_memory_info():
    """Get memory info on Windows using wmic."""
    try:
        # Get total and free memory
        result = subprocess.run(
            ['wmic', 'OS', 'get', 'TotalVisibleMemorySize,FreePhysicalMemory'],
            capture_output=True, text=True, timeout=10, shell=True
        )
        lines = [l.strip() for l in result.stdout.strip().split('\n') if l.strip()]
        
        if len(lines) >= 2:
            parts = lines[1].split()
            if len(parts) >= 2:
                free_kb = int(parts[0])
                total_kb = int(parts[1])
                used_kb = total_kb - free_kb
                
                return {
                    'total_mb': total_kb // 1024,
                    'used_mb': used_kb // 1024,
                    'available_mb': free_kb // 1024,
                    'buffers_mb': 0,
                    'cached_mb': 0,
                    'percent': round((used_kb / total_kb) * 100, 2) if total_kb > 0 else 0
                }
        return {'total_mb': 0, 'used_mb': 0, 'available_mb': 0, 'percent': 0}
    except:
        return {'total_mb': 0, 'used_mb': 0, 'available_mb': 0, 'percent': 0}


def _windows_get_disk_io():
    """Get disk I/O on Windows - limited support."""
    # Windows doesn't easily expose cumulative I/O via command line
    return {'read_bytes': 0, 'write_bytes': 0}


def _windows_get_network_io():
    """Get network I/O on Windows using netstat."""
    try:
        result = subprocess.run(
            ['netstat', '-e'],
            capture_output=True, text=True, timeout=10, shell=True
        )
        lines = result.stdout.strip().split('\n')
        
        for line in lines:
            if 'Bytes' in line:
                parts = line.split()
                if len(parts) >= 3:
                    rx = int(parts[1])
                    tx = int(parts[2])
                    return {'rx_bytes': rx, 'tx_bytes': tx}
        
        return {'rx_bytes': 0, 'tx_bytes': 0}
    except:
        return {'rx_bytes': 0, 'tx_bytes': 0}


def _windows_get_load_average():
    """Windows doesn't have load average concept."""
    return {'load_1m': 0, 'load_5m': 0, 'load_15m': 0, 'running_procs': 'N/A'}


def _windows_get_cpu_detailed():
    """Get detailed CPU metrics on Windows."""
    try:
        result = subprocess.run(
            ['wmic', 'cpu', 'get', 'loadpercentage'],
            capture_output=True, text=True, timeout=10, shell=True
        )
        lines = [l.strip() for l in result.stdout.strip().split('\n') if l.strip()]
        
        cpu_pct = 0
        if len(lines) >= 2 and lines[1].isdigit():
            cpu_pct = int(lines[1])
        
        user = cpu_pct * 100
        idle = (100 - cpu_pct) * 100
        
        return {
            'user': user,
            'nice': 0,
            'system': 0,
            'idle': idle,
            'iowait': 0,
            'irq': 0,
            'softirq': 0,
            'steal': 0,
            'total': 10000
        }
    except:
        return {'user': 0, 'nice': 0, 'system': 0, 'idle': 0, 'iowait': 0, 'steal': 0, 'total': 1}


def _windows_get_swap_info():
    """Get swap/page file info on Windows."""
    try:
        result = subprocess.run(
            ['wmic', 'pagefile', 'get', 'AllocatedBaseSize,CurrentUsage'],
            capture_output=True, text=True, timeout=10, shell=True
        )
        lines = [l.strip() for l in result.stdout.strip().split('\n') if l.strip()]
        
        if len(lines) >= 2:
            parts = lines[1].split()
            if len(parts) >= 2:
                total_mb = int(parts[0])
                used_mb = int(parts[1])
                free_mb = total_mb - used_mb
                return {
                    'total_mb': total_mb,
                    'used_mb': used_mb,
                    'free_mb': free_mb,
                    'percent': round((used_mb / total_mb) * 100, 2) if total_mb > 0 else 0
                }
        return {'total_mb': 0, 'used_mb': 0, 'free_mb': 0, 'percent': 0}
    except:
        return {'total_mb': 0, 'used_mb': 0, 'free_mb': 0, 'percent': 0}


# --- Linux implementations (original) ---

def _linux_get_cpu_usage():
    """Get CPU usage percentage."""
    try:
        with open('/proc/stat', 'r') as f:
            line = f.readline()
            parts = line.split()[1:]
            values = [int(x) for x in parts]
            idle = values[3] + values[4]  # idle + iowait
            total = sum(values)
            return idle, total
    except:
        return 0, 1

def _linux_get_memory_info():
    """Get memory usage information."""
    try:
        with open('/proc/meminfo', 'r') as f:
            meminfo = {}
            for line in f:
                parts = line.split(':')
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip().split()[0]
                    meminfo[key] = int(value)
            
            total = meminfo.get('MemTotal', 0)
            available = meminfo.get('MemAvailable', meminfo.get('MemFree', 0))
            buffers = meminfo.get('Buffers', 0)
            cached = meminfo.get('Cached', 0)
            used = total - available
            
            return {
                'total_mb': total // 1024,
                'used_mb': used // 1024,
                'available_mb': available // 1024,
                'buffers_mb': buffers // 1024,
                'cached_mb': cached // 1024,
                'percent': round((used / total) * 100, 2) if total > 0 else 0
            }
    except:
        return {'total_mb': 0, 'used_mb': 0, 'available_mb': 0, 'percent': 0}

def _linux_get_disk_io():
    """Get disk I/O statistics."""
    try:
        with open('/proc/diskstats', 'r') as f:
            total_read = 0
            total_write = 0
            for line in f:
                parts = line.split()
                if len(parts) >= 14:
                    # sectors read (index 5) and written (index 9)
                    total_read += int(parts[5]) * 512  # Convert sectors to bytes
                    total_write += int(parts[9]) * 512
            return {
                'read_bytes': total_read,
                'write_bytes': total_write
            }
    except:
        return {'read_bytes': 0, 'write_bytes': 0}

def _linux_get_network_io():
    """Get network I/O statistics."""
    try:
        with open('/proc/net/dev', 'r') as f:
            lines = f.readlines()[2:]  # Skip headers
            total_rx = 0
            total_tx = 0
            for line in lines:
                parts = line.split()
                if len(parts) >= 10:
                    iface = parts[0].rstrip(':')
                    if iface != 'lo':  # Skip loopback
                        total_rx += int(parts[1])
                        total_tx += int(parts[9])
            return {
                'rx_bytes': total_rx,
                'tx_bytes': total_tx
            }
    except:
        return {'rx_bytes': 0, 'tx_bytes': 0}

def _linux_get_load_average():
    """Get system load average."""
    try:
        with open('/proc/loadavg', 'r') as f:
            parts = f.read().split()
            return {
                'load_1m': float(parts[0]),
                'load_5m': float(parts[1]),
                'load_15m': float(parts[2]),
                'running_procs': parts[3]
            }
    except:
        return {'load_1m': 0, 'load_5m': 0, 'load_15m': 0}

def _linux_get_cpu_detailed():
    """Get detailed CPU metrics including iowait and steal."""
    try:
        with open('/proc/stat', 'r') as f:
            line = f.readline()
            parts = line.split()[1:]
            # user, nice, system, idle, iowait, irq, softirq, steal, guest, guest_nice
            values = [int(x) for x in parts]
            total = sum(values[:8])  # Exclude guest times (already in user/nice)
            
            return {
                'user': values[0],
                'nice': values[1],
                'system': values[2],
                'idle': values[3],
                'iowait': values[4] if len(values) > 4 else 0,
                'irq': values[5] if len(values) > 5 else 0,
                'softirq': values[6] if len(values) > 6 else 0,
                'steal': values[7] if len(values) > 7 else 0,
                'total': total
            }
    except:
        return {'user': 0, 'nice': 0, 'system': 0, 'idle': 0, 'iowait': 0, 'steal': 0, 'total': 1}

def _linux_get_context_switches():
    """Get context switch count from /proc/stat."""
    try:
        with open('/proc/stat', 'r') as f:
            for line in f:
                if line.startswith('ctxt '):
                    return int(line.split()[1])
        return 0
    except:
        return 0

def _linux_get_swap_info():
    """Get swap usage information."""
    try:
        with open('/proc/meminfo', 'r') as f:
            meminfo = {}
            for line in f:
                parts = line.split(':')
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip().split()[0]
                    meminfo[key] = int(value)
            
            swap_total = meminfo.get('SwapTotal', 0)
            swap_free = meminfo.get('SwapFree', 0)
            swap_used = swap_total - swap_free
            
            return {
                'total_mb': swap_total // 1024,
                'used_mb': swap_used // 1024,
                'free_mb': swap_free // 1024,
                'percent': round((swap_used / swap_total) * 100, 2) if swap_total > 0 else 0
            }
    except:
        return {'total_mb': 0, 'used_mb': 0, 'free_mb': 0, 'percent': 0}


# ============================================================================
# PLATFORM DISPATCH FUNCTIONS
# ============================================================================

def get_cpu_usage():
    """Get CPU usage percentage - dispatches to platform-specific implementation."""
    if IS_LINUX:
        return _linux_get_cpu_usage()
    elif IS_MACOS:
        return _macos_get_cpu_usage()
    elif IS_WINDOWS:
        return _windows_get_cpu_usage()
    return 0, 1


def get_memory_info():
    """Get memory usage information - dispatches to platform-specific implementation."""
    if IS_LINUX:
        return _linux_get_memory_info()
    elif IS_MACOS:
        return _macos_get_memory_info()
    elif IS_WINDOWS:
        return _windows_get_memory_info()
    return {'total_mb': 0, 'used_mb': 0, 'available_mb': 0, 'percent': 0}


def get_disk_io():
    """Get disk I/O statistics - dispatches to platform-specific implementation."""
    if IS_LINUX:
        return _linux_get_disk_io()
    elif IS_MACOS:
        return _macos_get_disk_io()
    elif IS_WINDOWS:
        return _windows_get_disk_io()
    return {'read_bytes': 0, 'write_bytes': 0}


def get_network_io():
    """Get network I/O statistics - dispatches to platform-specific implementation."""
    if IS_LINUX:
        return _linux_get_network_io()
    elif IS_MACOS:
        return _macos_get_network_io()
    elif IS_WINDOWS:
        return _windows_get_network_io()
    return {'rx_bytes': 0, 'tx_bytes': 0}


def get_load_average():
    """Get system load average - dispatches to platform-specific implementation."""
    if IS_LINUX:
        return _linux_get_load_average()
    elif IS_MACOS:
        return _macos_get_load_average()
    elif IS_WINDOWS:
        return _windows_get_load_average()
    return {'load_1m': 0, 'load_5m': 0, 'load_15m': 0, 'running_procs': 'N/A'}


def get_cpu_detailed():
    """Get detailed CPU metrics - dispatches to platform-specific implementation."""
    if IS_LINUX:
        return _linux_get_cpu_detailed()
    elif IS_MACOS:
        return _macos_get_cpu_detailed()
    elif IS_WINDOWS:
        return _windows_get_cpu_detailed()
    return {'user': 0, 'nice': 0, 'system': 0, 'idle': 0, 'iowait': 0, 'steal': 0, 'total': 1}


def get_context_switches():
    """Get context switch count - Linux only, returns 0 on other platforms."""
    if IS_LINUX:
        return _linux_get_context_switches()
    # Context switches not easily available on macOS/Windows
    return 0


def get_swap_info():
    """Get swap usage information - dispatches to platform-specific implementation."""
    if IS_LINUX:
        return _linux_get_swap_info()
    elif IS_MACOS:
        return _macos_get_swap_info()
    elif IS_WINDOWS:
        return _windows_get_swap_info()
    return {'total_mb': 0, 'used_mb': 0, 'free_mb': 0, 'percent': 0}


def get_disk_space(path='/github/workspace'):
    """Get disk space for the workspace - cross-platform."""
    try:
        if IS_WINDOWS:
            # Windows: use wmic or PowerShell
            check_path = path if os.path.exists(path) else 'C:\\'
            drive = os.path.splitdrive(check_path)[0] or 'C:'
            result = subprocess.run(
                ['wmic', 'logicaldisk', 'where', f'DeviceID="{drive}"', 'get', 'Size,FreeSpace'],
                capture_output=True, text=True, timeout=10, shell=True
            )
            lines = [l.strip() for l in result.stdout.strip().split('\n') if l.strip()]
            if len(lines) >= 2:
                parts = lines[1].split()
                if len(parts) >= 2:
                    free = int(parts[0])
                    total = int(parts[1])
                    used = total - free
                    return {
                        'total_gb': round(total / (1024**3), 2),
                        'used_gb': round(used / (1024**3), 2),
                        'available_gb': round(free / (1024**3), 2),
                        'percent': round((used / total) * 100, 2) if total > 0 else 0
                    }
        else:
            # Linux/macOS: use df
            check_path = path if os.path.exists(path) else '/'
            # macOS df doesn't support -B1, use -k for kilobytes
            df_args = ['df', '-k', check_path] if IS_MACOS else ['df', '-B1', check_path]
            result = subprocess.run(df_args, capture_output=True, text=True)
            lines = result.stdout.strip().split('\n')
            if len(lines) >= 2:
                parts = lines[1].split()
                if IS_MACOS:
                    # macOS df output: Filesystem 1024-blocks Used Available Capacity Mounted
                    total = int(parts[1]) * 1024  # Convert KB to bytes
                    used = int(parts[2]) * 1024
                    available = int(parts[3]) * 1024
                else:
                    total = int(parts[1])
                    used = int(parts[2])
                    available = int(parts[3])
                return {
                    'total_gb': round(total / (1024**3), 2),
                    'used_gb': round(used / (1024**3), 2),
                    'available_gb': round(available / (1024**3), 2),
                    'percent': round((used / total) * 100, 2) if total > 0 else 0
                }
    except:
        pass
    return {'total_gb': 0, 'used_gb': 0, 'available_gb': 0, 'percent': 0}

def get_file_descriptors():
    """Get system-wide file descriptor usage - Linux only."""
    if not IS_LINUX:
        return {'allocated': 0, 'free': 0, 'max': 0, 'percent': 0}
    try:
        with open('/proc/sys/fs/file-nr', 'r') as f:
            parts = f.read().strip().split()
            allocated = int(parts[0])
            free = int(parts[1]) if len(parts) > 1 else 0
            max_fds = int(parts[2]) if len(parts) > 2 else 0
            return {
                'allocated': allocated,
                'free': free,
                'max': max_fds,
                'percent': round((allocated / max_fds) * 100, 2) if max_fds > 0 else 0
            }
    except:
        return {'allocated': 0, 'free': 0, 'max': 0, 'percent': 0}

def get_thread_count():
    """Get total thread count - Linux only."""
    if not IS_LINUX:
        return 0
    try:
        with open('/proc/stat', 'r') as f:
            for line in f:
                if line.startswith('processes '):
                    # This is cumulative forks, not current - use different method
                    break
        # Count threads from /proc
        thread_count = 0
        for pid in os.listdir('/proc'):
            if pid.isdigit():
                try:
                    task_path = f'/proc/{pid}/task'
                    if os.path.exists(task_path):
                        thread_count += len(os.listdir(task_path))
                except:
                    pass
        return thread_count
    except:
        return 0

def get_tcp_connections():
    """Get TCP connection counts - cross-platform."""
    counts = {'total': 0, 'established': 0, 'time_wait': 0, 'listen': 0, 'other': 0}
    
    if IS_LINUX:
        try:
            with open('/proc/net/tcp', 'r') as f:
                lines = f.readlines()[1:]  # Skip header
                
            with open('/proc/net/tcp6', 'r') as f:
                lines += f.readlines()[1:]  # Skip header
            
            for line in lines:
                parts = line.split()
                if len(parts) >= 4:
                    state = parts[3].upper()
                    counts['total'] += 1
                    if state == '01':
                        counts['established'] += 1
                    elif state == '06':
                        counts['time_wait'] += 1
                    elif state == '0A':
                        counts['listen'] += 1
                    else:
                        counts['other'] += 1
        except:
            pass
    elif IS_MACOS or IS_WINDOWS:
        try:
            result = subprocess.run(
                ['netstat', '-an'],
                capture_output=True, text=True, timeout=10
            )
            for line in result.stdout.split('\n'):
                if 'tcp' in line.lower():
                    counts['total'] += 1
                    upper = line.upper()
                    if 'ESTABLISHED' in upper:
                        counts['established'] += 1
                    elif 'TIME_WAIT' in upper:
                        counts['time_wait'] += 1
                    elif 'LISTEN' in upper:
                        counts['listen'] += 1
                    else:
                        counts['other'] += 1
        except:
            pass
    
    return counts

def get_process_count():
    """Get number of running processes - cross-platform."""
    try:
        if IS_WINDOWS:
            result = subprocess.run(
                ['wmic', 'process', 'get', 'processid'],
                capture_output=True, text=True, timeout=10, shell=True
            )
            lines = [l.strip() for l in result.stdout.strip().split('\n') if l.strip()]
            return len(lines) - 1  # Subtract header
        else:
            # Linux and macOS
            result = subprocess.run(['ps', 'aux'], capture_output=True, text=True, timeout=10)
            return len(result.stdout.strip().split('\n')) - 1
    except:
        return 0

def get_top_processes(n=10):
    """Get top N processes by CPU and memory - cross-platform."""
    cpu_procs = []
    mem_procs = []
    
    try:
        if IS_WINDOWS:
            # Windows: use wmic
            result = subprocess.run(
                ['wmic', 'process', 'get', 'ProcessId,Name,PercentProcessorTime,WorkingSetSize'],
                capture_output=True, text=True, timeout=15, shell=True
            )
            # Windows process info is limited via wmic, return empty for now
            return {'by_cpu': [], 'by_mem': []}
        elif IS_MACOS:
            # macOS: ps doesn't support --sort, use different approach
            result = subprocess.run(
                ['ps', '-Ao', 'pid,%cpu,%mem,comm'],
                capture_output=True, text=True, timeout=10
            )
            lines = result.stdout.strip().split('\n')[1:]  # Skip header
            procs = []
            for line in lines:
                parts = line.split(None, 3)
                if len(parts) >= 4:
                    procs.append({
                        'pid': parts[0],
                        'cpu': float(parts[1]),
                        'mem': float(parts[2]),
                        'command': parts[3][:50]
                    })
            # Sort by CPU and memory
            cpu_procs = sorted(procs, key=lambda x: x['cpu'], reverse=True)[:n]
            mem_procs = sorted(procs, key=lambda x: x['mem'], reverse=True)[:n]
        else:
            # Linux
            result = subprocess.run(
                ['ps', 'aux', '--sort=-%cpu'],
                capture_output=True, text=True, timeout=10
            )
            lines = result.stdout.strip().split('\n')[1:n+1]
            for line in lines:
                parts = line.split(None, 10)
                if len(parts) >= 11:
                    cpu_procs.append({
                        'pid': parts[1],
                        'cpu': float(parts[2]),
                        'mem': float(parts[3]),
                        'command': parts[10][:50]
                    })
            
            result = subprocess.run(
                ['ps', 'aux', '--sort=-%mem'],
                capture_output=True, text=True, timeout=10
            )
            lines = result.stdout.strip().split('\n')[1:n+1]
            for line in lines:
                parts = line.split(None, 10)
                if len(parts) >= 11:
                    mem_procs.append({
                        'pid': parts[1],
                        'cpu': float(parts[2]),
                        'mem': float(parts[3]),
                        'command': parts[10][:50]
                    })
    except:
        pass
    
    return {'by_cpu': cpu_procs, 'by_mem': mem_procs}

def collect_sample(prev_cpu=None, prev_cpu_detailed=None, prev_disk=None, prev_net=None, prev_ctxt=None):
    """Collect a single sample of all metrics."""
    timestamp = time.time()
    
    # CPU (calculate delta)
    cpu_idle, cpu_total = get_cpu_usage()
    cpu_percent = 0
    # CPU: handle both delta-based (Linux) and direct percentage (macOS/Windows)
    cpu_val1, cpu_val2 = get_cpu_usage()
    cpu_percent = 0
    
    if cpu_val2 == -1:
        # Direct percentage mode (macOS/Windows): cpu_val1 is the CPU percentage
        cpu_percent = round(cpu_val1, 2)
        # Store as tuple for consistency, but we don't use prev_cpu in this mode
        prev_cpu_new = (cpu_val1, cpu_val2)
    else:
        # Delta-based mode (Linux): cpu_val1=idle, cpu_val2=total (cumulative)
        cpu_idle, cpu_total = cpu_val1, cpu_val2
        if prev_cpu and prev_cpu[1] != -1:
            idle_delta = cpu_idle - prev_cpu[0]
            total_delta = cpu_total - prev_cpu[1]
            if total_delta > 0:
                cpu_percent = round(100 * (1 - idle_delta / total_delta), 2)
        prev_cpu_new = (cpu_idle, cpu_total)
    
    # Detailed CPU (iowait, steal)
    cpu_detailed = get_cpu_detailed()
    iowait_percent = 0
    steal_percent = 0
    if prev_cpu_detailed:
        total_delta = cpu_detailed['total'] - prev_cpu_detailed['total']
        if total_delta > 0:
            iowait_percent = round(100 * (cpu_detailed['iowait'] - prev_cpu_detailed['iowait']) / total_delta, 2)
            steal_percent = round(100 * (cpu_detailed['steal'] - prev_cpu_detailed['steal']) / total_delta, 2)
    
    # Context switches (rate)
    ctxt_count = get_context_switches()
    ctxt_rate = 0
    if prev_ctxt:
        time_delta = timestamp - prev_ctxt['timestamp']
        if time_delta > 0:
            ctxt_rate = round((ctxt_count - prev_ctxt['count']) / time_delta)
    
    # Memory
    memory = get_memory_info()
    
    # Swap
    swap = get_swap_info()
    
    # Disk I/O (calculate rate)
    disk_io = get_disk_io()
    disk_read_rate = 0
    disk_write_rate = 0
    if prev_disk:
        time_delta = timestamp - prev_disk['timestamp']
        if time_delta > 0:
            disk_read_rate = (disk_io['read_bytes'] - prev_disk['read_bytes']) / time_delta
            disk_write_rate = (disk_io['write_bytes'] - prev_disk['write_bytes']) / time_delta
    
    # Disk space
    disk_space = get_disk_space()
    
    # Network I/O (calculate rate)
    net_io = get_network_io()
    net_rx_rate = 0
    net_tx_rate = 0
    if prev_net:
        time_delta = timestamp - prev_net['timestamp']
        if time_delta > 0:
            net_rx_rate = (net_io['rx_bytes'] - prev_net['rx_bytes']) / time_delta
            net_tx_rate = (net_io['tx_bytes'] - prev_net['tx_bytes']) / time_delta
    
    # Load average
    load = get_load_average()
    
    # Additional metrics
    file_descriptors = get_file_descriptors()
    thread_count = get_thread_count()
    tcp_connections = get_tcp_connections()
    
    sample = {
        'timestamp': timestamp,
        'datetime': datetime.now().isoformat(),
        'cpu_percent': cpu_percent,
        'cpu_iowait_percent': iowait_percent,
        'cpu_steal_percent': steal_percent,
        'context_switches_rate': ctxt_rate,
        'memory': memory,
        'swap': swap,
        'disk_io': {
            **disk_io,
            'read_rate': disk_read_rate,
            'write_rate': disk_write_rate,
            'timestamp': timestamp
        },
        'disk_space': disk_space,
        'network_io': {
            **net_io,
            'rx_rate': net_rx_rate,
            'tx_rate': net_tx_rate,
            'timestamp': timestamp
        },
        'load': load,
        'process_count': get_process_count(),
        'thread_count': thread_count,
        'file_descriptors': file_descriptors,
        'tcp_connections': tcp_connections,
    }
    
    return (sample, 
            prev_cpu_new, 
            cpu_detailed,
            disk_io | {'timestamp': timestamp}, 
            net_io | {'timestamp': timestamp},
            {'count': ctxt_count, 'timestamp': timestamp})

def start_collection():
    """Start collecting metrics."""
    print(f"📊 Starting telemetry collection (interval: {SAMPLE_INTERVAL}s)")
    
    # Initial metadata
    data = {
        'start_time': time.time(),
        'start_datetime': datetime.now().isoformat(),
        'interval': SAMPLE_INTERVAL,
        'samples': [],
        'initial_snapshot': {
            'cpu_count': os.cpu_count(),
            'memory': get_memory_info(),
            'swap': get_swap_info(),
            'disk_space': get_disk_space(),
            'file_descriptors': get_file_descriptors(),
            'tcp_connections': get_tcp_connections(),
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
            'repository_visibility': os.environ.get('GITHUB_REPOSITORY_VISIBILITY', 'N/A'),
        }
    }
    
    # Save initial data
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)
    
    # Collection loop
    prev_cpu = None
    prev_cpu_detailed = None
    prev_disk = None
    prev_net = None
    prev_ctxt = None
    
    try:
        while True:
            sample, prev_cpu, prev_cpu_detailed, prev_disk, prev_net, prev_ctxt = collect_sample(
                prev_cpu, prev_cpu_detailed, prev_disk, prev_net, prev_ctxt
            )
            
            # Load existing data with error handling
            try:
                with open(DATA_FILE, 'r') as f:
                    data = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"  ⚠️  Failed to read data file, retrying: {e}")
                time.sleep(0.1)
                continue
            
            # Append sample
            data['samples'].append(sample)
            data['last_update'] = time.time()
            
            # Save with atomic write (write to temp file, then rename)
            temp_file = DATA_FILE + '.tmp'
            try:
                with open(temp_file, 'w') as f:
                    json.dump(data, f, indent=2)
                os.replace(temp_file, DATA_FILE)
            except (IOError, OSError) as e:
                print(f"  ⚠️  Failed to write data file: {e}")
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            
            iowait = sample.get('cpu_iowait_percent', 0)
            steal = sample.get('cpu_steal_percent', 0)
            print(f"  Sample {len(data['samples'])}: CPU={sample['cpu_percent']:.1f}% MEM={sample['memory']['percent']:.1f}% IO={iowait:.1f}% Steal={steal:.1f}%")
            
            time.sleep(SAMPLE_INTERVAL)
    except KeyboardInterrupt:
        print("\n📊 Collection stopped")

def stop_collection():
    """Stop collection and finalize data."""
    if not os.path.exists(DATA_FILE):
        print("No telemetry data found")
        return None
    
    # Retry logic for race conditions
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
            break
        except json.JSONDecodeError:
            if attempt < max_retries - 1:
                time.sleep(0.1)
                continue
            else:
                print("⚠️  Failed to read telemetry data, using partial data")
                return None
    
    data['end_time'] = time.time()
    data['end_datetime'] = datetime.now().isoformat()
    data['duration'] = data['end_time'] - data['start_time']
    data['final_snapshot'] = {
        'processes': get_top_processes(10),
        'memory': get_memory_info()
    }
    
    # Close any open step
    if 'steps' in data and data['steps']:
        last_step = data['steps'][-1]
        if 'end_time' not in last_step:
            last_step['end_time'] = time.time()
            last_step['end_datetime'] = datetime.now().isoformat()
            last_step['duration'] = last_step['end_time'] - last_step['start_time']
    
    # Atomic write
    temp_file = DATA_FILE + '.tmp'
    try:
        with open(temp_file, 'w') as f:
            json.dump(data, f, indent=2)
        os.replace(temp_file, DATA_FILE)
    except (IOError, OSError) as e:
        print(f"⚠️  Failed to finalize data: {e}")
        if os.path.exists(temp_file):
            os.remove(temp_file)
        return None
    
    print(f"📊 Collection complete: {len(data['samples'])} samples over {data['duration']:.1f}s")
    return data

def mark_step(step_name):
    """Mark the beginning of a new step."""
    if not os.path.exists(DATA_FILE):
        print(f"⚠️  No telemetry data file found. Start collection first.")
        return
    
    # Retry logic for race conditions
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
            break
        except json.JSONDecodeError:
            if attempt < max_retries - 1:
                time.sleep(0.05)
                continue
            else:
                print(f"⚠️  Failed to read telemetry data after {max_retries} attempts")
                return
    
    current_time = time.time()
    current_datetime = datetime.now().isoformat()
    
    # Initialize steps list if not exists
    if 'steps' not in data:
        data['steps'] = []
    
    # Close previous step if exists
    if data['steps']:
        last_step = data['steps'][-1]
        if 'end_time' not in last_step:
            last_step['end_time'] = current_time
            last_step['end_datetime'] = current_datetime
            last_step['duration'] = last_step['end_time'] - last_step['start_time']
            # Calculate sample range for this step
            last_step['sample_end_idx'] = len(data.get('samples', [])) - 1
    
    # Add new step
    new_step = {
        'name': step_name,
        'start_time': current_time,
        'start_datetime': current_datetime,
        'sample_start_idx': len(data.get('samples', []))
    }
    data['steps'].append(new_step)
    
    # Atomic write
    temp_file = DATA_FILE + '.tmp'
    try:
        with open(temp_file, 'w') as f:
            json.dump(data, f, indent=2)
        os.replace(temp_file, DATA_FILE)
    except (IOError, OSError) as e:
        print(f"⚠️  Failed to write step marker: {e}")
        if os.path.exists(temp_file):
            os.remove(temp_file)
        return
    
    print(f"📍 Step marked: {step_name}")


def snapshot_collection():
    """Quick snapshot mode - collect a few samples and save."""
    print("📸 Taking telemetry snapshot...")
    
    interval = int(os.environ.get('TELEMETRY_INTERVAL', '2'))
    
    data = {
        'start_time': time.time(),
        'start_datetime': datetime.now().isoformat(),
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
            'repository_visibility': os.environ.get('GITHUB_REPOSITORY_VISIBILITY', 'N/A'),
        }
    }
    
    prev_cpu = prev_cpu_detailed = prev_disk = prev_net = prev_ctxt = None
    for i in range(6):
        sample, prev_cpu, prev_cpu_detailed, prev_disk, prev_net, prev_ctxt = collect_sample(
            prev_cpu, prev_cpu_detailed, prev_disk, prev_net, prev_ctxt
        )
        data['samples'].append(sample)
        print(f'  Sample {i+1}/6: CPU={sample["cpu_percent"]:.1f}% MEM={sample["memory"]["percent"]:.1f}%')
        if i < 5:
            time.sleep(interval)
    
    data['end_time'] = time.time()
    data['end_datetime'] = datetime.now().isoformat()
    data['duration'] = data['end_time'] - data['start_time']
    data['final_snapshot'] = {
        'processes': get_top_processes(10),
        'memory': get_memory_info()
    }
    
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f'\n✅ Collected {len(data["samples"])} samples over {data["duration"]:.1f}s')


if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == 'start':
            start_collection()
        elif sys.argv[1] == 'stop':
            stop_collection()
        elif sys.argv[1] == 'snapshot':
            snapshot_collection()
        elif sys.argv[1] == 'step' and len(sys.argv) > 2:
            step_name = ' '.join(sys.argv[2:])
            mark_step(step_name)
        elif sys.argv[1] == 'sample':
            # Single sample mode
            sample, _, _, _, _, _ = collect_sample()
            print(json.dumps(sample, indent=2))
        else:
            print("Usage: telemetry_collector.py [start|stop|snapshot|step <name>|sample]")
    else:
        print("Usage: telemetry_collector.py [start|stop|snapshot|step <name>|sample]")
