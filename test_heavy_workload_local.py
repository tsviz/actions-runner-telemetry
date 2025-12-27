#!/usr/bin/env python3
"""
Test the heavy-workload scenario with proper memory tracking.
This simulates what SHOULD happen in GitHub Actions.
"""

import os
import sys
import json
import tempfile
from pathlib import Path

# Add current directory to path to import telemetry_collector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from telemetry_collector import start_collection, mark_step, stop_collection

def test_heavy_workload_with_markers():
    """Test that markers in the same process capture memory correctly."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        data_file = os.path.join(tmpdir, '.telemetry_data.json')
        os.environ['TELEMETRY_DATA_FILE'] = data_file
        
        print("\n" + "=" * 70)
        print("TEST: Heavy Workload with Same-Process Markers")
        print("=" * 70)
        
        # Start collection
        start_collection()
        print(f"✅ Collection started, data file: {data_file}")
        
        # Mark baseline
        print("\n📍 Marking baseline (before heavy work)...")
        mark_step("Baseline")
        
        # Run heavy workload with memory allocation
        print("\n⚠️  Starting heavy workload...")
        print("💾 Pre-allocating 1.5GB of memory...")
        huge_arrays = []
        for idx in range(3):
            arr = list(range(125000000))  # 125M integers = ~500MB
            huge_arrays.append(arr)
            print(f"   Array {idx+1}/3 allocated (~500MB)")
        
        print("⚡ Running CPU-intensive computation...")
        result = 0
        for arr in huge_arrays:
            # Compute on the arrays while holding them
            result += sum(arr[i] * (i % 10) for i in range(0, len(arr), 50000))
        
        # CRITICAL: Mark WHILE memory is still allocated in this process
        print("\n📍 Marking peak (WHILE memory still allocated in same process)...")
        mark_step("Heavy Load Peak")
        
        # Now release memory
        print("\n💾 Releasing memory...")
        del huge_arrays
        
        # Stop collection
        print("\n🛑 Stopping collection...")
        stop_collection()
        
        # Find the actual data file (might be in /tmp/)
        import glob
        possible_files = [data_file, '/tmp/telemetry_data.json', '/tmp/.telemetry_data.json']
        actual_data_file = None
        for f in possible_files:
            if os.path.exists(f):
                actual_data_file = f
                print(f"Found data file: {actual_data_file}")
                break
        
        if not actual_data_file:
            print(f"❌ ERROR: Could not find telemetry data file")
            print(f"Searched: {possible_files}")
            return False
        
        # Read and analyze results
        print("\n" + "=" * 70)
        print("RESULTS:")
        print("=" * 70)
        
        with open(actual_data_file, 'r') as f:
            data = json.load(f)
        
        if 'samples' not in data or len(data['samples']) == 0:
            print("❌ ERROR: No samples collected!")
            return False
        
        samples = data['samples']
        print(f"Total samples: {len(samples)}")
        
        for i, sample in enumerate(samples):
            step_name = sample.get('step_name', 'N/A')
            mem = sample.get('memory', {})
            cpu = sample.get('cpu', {})
            
            process_pct = mem.get('process_percent', mem.get('percent', 0))
            cpu_pct = cpu.get('percent', 0)
            process_rss = mem.get('process_rss_mb', 0)
            
            print(f"\n📊 Sample {i+1}: {step_name}")
            print(f"   CPU: {cpu_pct}%")
            print(f"   Memory (process): {process_pct}%")
            print(f"   Memory (process RSS): {process_rss}MB")
        
        # Validate that peak memory > 5%
        peak_sample = samples[-1]  # Last sample should be "Heavy Load Peak"
        peak_memory = peak_sample.get('memory', {}).get('process_percent', 0)
        
        print(f"\n{'=' * 70}")
        print(f"VALIDATION:")
        print(f"Peak memory: {peak_memory}%")
        
        if peak_sample.get('step_name') == 'Heavy Load Peak':
            if peak_memory > 5:
                print(f"✅ SUCCESS: Peak memory ({peak_memory}%) is > 5%")
                return True
            else:
                print(f"❌ FAIL: Peak memory ({peak_memory}%) is too low (expected > 5%)")
                return False
        else:
            print(f"❌ FAIL: Last sample is '{peak_sample.get('step_name')}', expected 'Heavy Load Peak'")
            return False

if __name__ == '__main__':
    success = test_heavy_workload_with_markers()
    sys.exit(0 if success else 1)
