#!/usr/bin/env python3
"""
Integrated telemetry test - workload + step marker in single container.
This simulates what actually happens during the heavy-workload job.
"""

import sys
import os
import time

# Add scripts to path
sys.path.insert(0, '/telemetry_scripts')

# Set data file
data_file = '/github/workspace/.telemetry_data.json'
os.environ['TELEMETRY_DATA_FILE'] = data_file
os.environ['TELEMETRY_INTERVAL'] = '2'

# Import telemetry functions
from telemetry_collector import start_collection, mark_step, stop_collection
from generate_report import generate_report, generate_html_dashboard

def main():
    print("🧪 Integrated Docker Test")
    print("=" * 60)
    
    # Start collection
    print("\n1️⃣  Starting telemetry...")
    start_collection()
    time.sleep(1)
    
    # Mark baseline
    print("2️⃣  Marking baseline...")
    mark_step("Before Heavy Load")
    time.sleep(1)
    
    # Run heavy workload
    print("\n3️⃣  Running heavy workload with memory allocation...")
    print("   Allocating 1.5GB memory...")
    
    huge_arrays = []
    for idx in range(3):
        arr = list(range(125000000))  # 125M integers = ~500MB
        huge_arrays.append(arr)
        print(f"   ✓ Array {idx+1}/3 allocated (~500MB)")
    
    print("   ⚡ Starting CPU work...")
    start = time.time()
    
    # CPU work
    for arr in huge_arrays:
        computation = 0
        for i in range(0, len(arr), 50000):
            computation += arr[i] * (i % 10)
    
    elapsed = time.time() - start
    print(f"   ✅ Computation complete ({elapsed:.1f}s)")
    
    # Mark while memory is STILL allocated
    print("\n4️⃣  Marking step WHILE memory still allocated...")
    mark_step("Data Processing")
    
    # Now release
    del huge_arrays
    print("5️⃣  Released memory\n")
    
    # Stop
    print("6️⃣  Stopping telemetry...")
    stop_collection()
    
    # Generate reports
    print("7️⃣  Generating reports...")
    try:
        import json
        with open(data_file, 'r') as f:
            data = json.load(f)
        
        output_dir = '/github/workspace'
        
        # Generate markdown report
        md_path = os.path.join(output_dir, 'telemetry-report.md')
        with open(md_path, 'w') as f:
            f.write(generate_report(data))
        print(f"   ✅ Markdown report: {md_path}")
        
        # Generate HTML dashboard
        html_path = os.path.join(output_dir, 'telemetry-dashboard.html')
        with open(html_path, 'w') as f:
            f.write(generate_html_dashboard(data))
        print(f"   ✅ HTML dashboard: {html_path}")
    except Exception as e:
        print(f"   ⚠️  Report generation warning: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("✅ Test complete!")

if __name__ == '__main__':
    main()
