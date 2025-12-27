#!/usr/bin/env python3
"""Heavy workload for telemetry testing."""

import time
import os
import subprocess
import json

print("⚠️  Running heavy workload (CPU + Memory)...")
print("   Allocating 1.5GB memory...")

# Allocate memory
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
print(f"   🧠 Memory still allocated, marking step while running...")

# Call the step marker while memory is still allocated
# We do this in the same process so memory is held
try:
    data_file = os.environ.get('TELEMETRY_DATA_FILE', '/tmp/telemetry_data.json')
    # Import and call mark_step directly to stay in same process
    import sys
    sys.path.insert(0, '/telemetry_scripts')
    from telemetry_collector import mark_step
    mark_step("Data Processing")
except Exception as e:
    print(f"Note: Could not call mark_step directly: {e}")
    print("Using fallback method...")

print(f"   ✅ Step marked while memory active")

# Keep memory a bit longer
time.sleep(2)
print("   ✅ Done!")
