#!/usr/bin/env python3
"""
Telemetry Collector - Collects system metrics over time.
Runs in background and samples metrics at regular intervals.
"""

import os
import sys
import json
import time
import subprocess
from datetime import datetime
from pathlib import Path

DATA_FILE = os.environ.get('TELEMETRY_DATA_FILE', '/tmp/telemetry_data.json')
SAMPLE_INTERVAL = float(os.environ.get('TELEMETRY_INTERVAL', '2'))  # seconds

def get_cpu_usage():
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

def get_memory_info():
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

def get_disk_io():
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

def get_network_io():
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

def get_load_average():
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

def get_cpu_detailed():
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

def get_context_switches():
    """Get context switch count from /proc/stat."""
    try:
        with open('/proc/stat', 'r') as f:
            for line in f:
                if line.startswith('ctxt '):
                    return int(line.split()[1])
        return 0
    except:
        return 0

def get_swap_info():
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

def get_disk_space(path='/github/workspace'):
    """Get disk space for the workspace."""
    try:
        # Try specified path first, fall back to current directory
        check_path = path if os.path.exists(path) else '/'
        result = subprocess.run(
            ['df', '-B1', check_path],
            capture_output=True, text=True
        )
        lines = result.stdout.strip().split('\n')
        if len(lines) >= 2:
            parts = lines[1].split()
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
    """Get system-wide file descriptor usage."""
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
    """Get total thread count from /proc/stat."""
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
    """Get TCP connection counts."""
    try:
        with open('/proc/net/tcp', 'r') as f:
            lines = f.readlines()[1:]  # Skip header
            
        with open('/proc/net/tcp6', 'r') as f:
            lines += f.readlines()[1:]  # Skip header
        
        # TCP states (from hex status in column 3)
        states = {
            '01': 'ESTABLISHED',
            '02': 'SYN_SENT', 
            '03': 'SYN_RECV',
            '04': 'FIN_WAIT1',
            '05': 'FIN_WAIT2',
            '06': 'TIME_WAIT',
            '07': 'CLOSE',
            '08': 'CLOSE_WAIT',
            '09': 'LAST_ACK',
            '0A': 'LISTEN',
            '0B': 'CLOSING'
        }
        
        counts = {'total': 0, 'established': 0, 'time_wait': 0, 'listen': 0, 'other': 0}
        
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
        
        return counts
    except:
        return {'total': 0, 'established': 0, 'time_wait': 0, 'listen': 0, 'other': 0}

def get_process_count():
    """Get number of running processes."""
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        return len(result.stdout.strip().split('\n')) - 1
    except:
        return 0

def get_top_processes(n=10):
    """Get top N processes by CPU and memory."""
    try:
        result = subprocess.run(
            ['ps', 'aux', '--sort=-%cpu'],
            capture_output=True, text=True
        )
        lines = result.stdout.strip().split('\n')[1:n+1]
        cpu_procs = []
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
            capture_output=True, text=True
        )
        lines = result.stdout.strip().split('\n')[1:n+1]
        mem_procs = []
        for line in lines:
            parts = line.split(None, 10)
            if len(parts) >= 11:
                mem_procs.append({
                    'pid': parts[1],
                    'cpu': float(parts[2]),
                    'mem': float(parts[3]),
                    'command': parts[10][:50]
                })
        
        return {'by_cpu': cpu_procs, 'by_mem': mem_procs}
    except:
        return {'by_cpu': [], 'by_mem': []}

def collect_sample(prev_cpu=None, prev_cpu_detailed=None, prev_disk=None, prev_net=None, prev_ctxt=None):
    """Collect a single sample of all metrics."""
    timestamp = time.time()
    
    # CPU (calculate delta)
    cpu_idle, cpu_total = get_cpu_usage()
    cpu_percent = 0
    if prev_cpu:
        idle_delta = cpu_idle - prev_cpu[0]
        total_delta = cpu_total - prev_cpu[1]
        if total_delta > 0:
            cpu_percent = round(100 * (1 - idle_delta / total_delta), 2)
    
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
            (cpu_idle, cpu_total), 
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
            
            # Load existing data
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
            
            # Append sample
            data['samples'].append(sample)
            data['last_update'] = time.time()
            
            # Save
            with open(DATA_FILE, 'w') as f:
                json.dump(data, f)
            
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
    
    with open(DATA_FILE, 'r') as f:
        data = json.load(f)
    
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
    
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"📊 Collection complete: {len(data['samples'])} samples over {data['duration']:.1f}s")
    return data

def mark_step(step_name):
    """Mark the beginning of a new step."""
    if not os.path.exists(DATA_FILE):
        print(f"⚠️  No telemetry data file found. Start collection first.")
        return
    
    with open(DATA_FILE, 'r') as f:
        data = json.load(f)
    
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
    
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)
    
    print(f"📍 Step marked: {step_name}")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == 'start':
            start_collection()
        elif sys.argv[1] == 'stop':
            stop_collection()
        elif sys.argv[1] == 'step' and len(sys.argv) > 2:
            step_name = ' '.join(sys.argv[2:])
            mark_step(step_name)
        elif sys.argv[1] == 'sample':
            # Single sample mode
            sample, _, _, _ = collect_sample()
            print(json.dumps(sample, indent=2))
        else:
            print("Usage: telemetry_collector.py [start|stop|step <name>|sample]")
    else:
        print("Usage: telemetry_collector.py [start|stop|step <name>|sample]")
