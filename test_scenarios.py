#!/usr/bin/env python3
"""
Comprehensive telemetry test scenarios.
Tests various workload types to ensure accurate metrics.
"""

import sys
import os
import time
import json

# Setup path
sys.path.insert(0, '/telemetry_scripts')
os.environ['TELEMETRY_INTERVAL'] = '1'

from telemetry_collector import start_collection, mark_step, stop_collection

def scenario_1_heavy_memory():
    """Scenario 1: Heavy memory allocation"""
    print("\n" + "=" * 70)
    print("SCENARIO 1: Heavy Memory Allocation (1.5GB)")
    print("=" * 70)
    
    start_collection()
    mark_step("Baseline")
    
    # Allocate memory
    print("Allocating 1.5GB...")
    arrays = [list(range(125000000)) for _ in range(3)]
    
    mark_step("Heavy Memory")
    del arrays
    
    print("✅ Scenario 1 complete")
    return "Memory"

def scenario_2_heavy_cpu():
    """Scenario 2: Heavy CPU computation"""
    print("\n" + "=" * 70)
    print("SCENARIO 2: Heavy CPU Computation")
    print("=" * 70)
    
    start_collection()
    mark_step("Baseline")
    
    # CPU work
    print("Running CPU-intensive work...")
    result = 0
    for i in range(100000000):
        result += (i * i) % 1000000
    
    mark_step("Heavy CPU")
    print(f"✅ Scenario 2 complete (result: {result})")
    return "CPU"

def scenario_3_balanced():
    """Scenario 3: Balanced CPU + Memory"""
    print("\n" + "=" * 70)
    print("SCENARIO 3: Balanced CPU + Memory Load")
    print("=" * 70)
    
    start_collection()
    mark_step("Start")
    
    # Allocate memory
    arrays = [list(range(62500000)) for _ in range(2)]  # 1GB
    
    # CPU work on arrays
    print("Running balanced workload...")
    for arr in arrays:
        result = sum(arr[i] * (i % 10) for i in range(0, len(arr), 50000))
    
    mark_step("Balanced Load")
    del arrays
    
    print("✅ Scenario 3 complete")
    return "Balanced"

def scenario_4_multi_step():
    """Scenario 4: Multiple sequential steps"""
    print("\n" + "=" * 70)
    print("SCENARIO 4: Multiple Sequential Steps")
    print("=" * 70)
    
    start_collection()
    
    steps = ["Compile", "Test", "Build", "Deploy"]
    for i, step_name in enumerate(steps):
        mark_step(step_name)
        time.sleep(1)
        print(f"  ✓ {step_name} complete")
    
    print("✅ Scenario 4 complete")
    return "MultiStep"

def scenario_5_light():
    """Scenario 5: Light workload"""
    print("\n" + "=" * 70)
    print("SCENARIO 5: Light Workload")
    print("=" * 70)
    
    start_collection()
    mark_step("Start")
    
    # Minimal work
    time.sleep(2)
    small_list = list(range(1000000))
    _ = sum(small_list)
    
    mark_step("Done")
    print("✅ Scenario 5 complete")
    return "Light"

def run_scenario(scenario_func, data_file):
    """Run a scenario and return results"""
    os.environ['TELEMETRY_DATA_FILE'] = data_file
    
    # Clean old data
    if os.path.exists(data_file):
        os.remove(data_file)
    
    try:
        name = scenario_func()
        stop_collection()
        
        # Wait for file to be written
        time.sleep(0.5)
        
        # Read results - check multiple possible locations
        possible_paths = [data_file, '/tmp/telemetry_data.json', '/github/workspace/telemetry_data.json']
        
        for possible_path in possible_paths:
            if os.path.exists(possible_path):
                try:
                    with open(possible_path, 'r') as f:
                        data = json.load(f)
                    
                    samples = data.get('samples', [])
                    if samples:
                        mem_values = [s.get('memory', {}).get('process_percent', 0) for s in samples]
                        cpu_values = [s.get('cpu_percent', 0) for s in samples]
                        
                        return {
                            'name': name,
                            'samples': len(samples),
                            'max_memory': max(mem_values) if mem_values else 0,
                            'max_cpu': max(cpu_values) if cpu_values else 0,
                            'avg_memory': sum(mem_values) / len(mem_values) if mem_values else 0,
                            'avg_cpu': sum(cpu_values) / len(cpu_values) if cpu_values else 0,
                        }
                except json.JSONDecodeError:
                    continue
        
        return {'name': name, 'error': 'No data file found'}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {'name': scenario_func.__name__, 'error': str(e)}

def main():
    print("🧪 Running Comprehensive Telemetry Test Suite")
    print("=" * 70)
    
    data_file = '/github/workspace/.telemetry_test.json'
    os.makedirs('/github/workspace', exist_ok=True)
    
    scenarios = [
        scenario_1_heavy_memory,
        scenario_2_heavy_cpu,
        scenario_3_balanced,
        scenario_4_multi_step,
        scenario_5_light,
    ]
    
    results = []
    for scenario in scenarios:
        result = run_scenario(scenario, data_file)
        results.append(result)
        
        # Print result
        if 'error' in result:
            print(f"\n❌ {result['name']}: {result['error']}")
        else:
            print(f"\n✅ {result['name']}:")
            print(f"   Samples: {result['samples']}")
            print(f"   Memory: max={result['max_memory']:.1f}%, avg={result['avg_memory']:.1f}%")
            print(f"   CPU: max={result['max_cpu']:.1f}%, avg={result['avg_cpu']:.1f}%")
    
    print("\n" + "=" * 70)
    print("📊 Summary of All Scenarios")
    print("=" * 70)
    
    for result in results:
        if 'error' not in result:
            status = "✅" if result['max_memory'] > 0 or result['max_cpu'] > 0 else "⚠️"
            print(f"{status} {result['name']}: Mem={result['max_memory']:.1f}% CPU={result['max_cpu']:.1f}%")
    
    print("\n✅ All scenarios tested!")

if __name__ == '__main__':
    main()
