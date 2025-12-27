#!/bin/bash
# Test the heavy-workload scenario locally with the new approach

set -e

echo "Building Docker image..."
docker build -t test-telemetry . > /dev/null 2>&1

echo "Running test in Docker container..."
docker run --rm \
  -v "$(pwd):/github/workspace" \
  -w "/github/workspace" \
  test-telemetry \
  python3 << 'DOCKER_PYTHON'
import sys
import json
import os

# Set up telemetry data file
TELEMETRY_DATA_FILE = "/github/workspace/.telemetry_test_data.json"
os.environ['TELEMETRY_DATA_FILE'] = TELEMETRY_DATA_FILE

sys.path.insert(0, "/")
from telemetry_collector import start_collection, stop_collection, mark_step

# Clean old data
if os.path.exists(TELEMETRY_DATA_FILE):
    os.remove(TELEMETRY_DATA_FILE)

print("\n" + "=" * 70)
print("DOCKER TEST: Heavy Workload with Direct mark_step() Calls")
print("=" * 70)

# Start collection
start_collection()
print("✅ Collection started")

# Mark baseline BEFORE heavy work
print("\n📍 Marking baseline...")
mark_step("Baseline")

# Run heavy workload with memory allocation
print("\n💾 Pre-allocating memory (1.5GB sustained)...")
huge_arrays = []
for idx in range(3):
    arr = list(range(125000000))  # 125M integers = ~500MB
    huge_arrays.append(arr)
    print(f"   Array {idx+1}/3 allocated (~500MB)")

print("⚡ Starting intensive CPU work...")
result = 0
for arr in huge_arrays:
    result += sum(arr[i] * (i % 10) for i in range(0, len(arr), 50000))

# CRITICAL: Mark WHILE memory is still allocated in this process
print("\n📍 Marking heavy load peak (memory still allocated)...")
mark_step("Heavy Load Peak")

# Release memory
print("💾 Releasing memory...")
del huge_arrays

# Stop collection
print("\n🛑 Stopping collection...")
stop_collection()

# Read and analyze results
print("\n" + "=" * 70)
print("RESULTS:")
print("=" * 70)

# Check if we're still using the data file or if it's been written elsewhere
if os.path.exists(TELEMETRY_DATA_FILE):
    with open(TELEMETRY_DATA_FILE, 'r') as f:
        data = json.load(f)
elif os.path.exists('/tmp/telemetry_data.json'):
    with open('/tmp/telemetry_data.json', 'r') as f:
        data = json.load(f)
else:
    print("❌ ERROR: No telemetry data file found")
    sys.exit(1)

if 'samples' not in data or len(data['samples']) == 0:
    print("❌ ERROR: No samples collected!")
    sys.exit(1)

samples = data['samples']
print(f"Total samples: {len(samples)}")

for i, sample in enumerate(samples):
    step_name = sample.get('step_name', 'N/A')
    mem = sample.get('memory', {})
    cpu = sample.get('cpu', {})
    
    process_pct = mem.get('process_percent', mem.get('percent', 0))
    cpu_pct = cpu.get('percent', 0)
    
    print(f"\n📊 Sample {i+1}: {step_name}")
    print(f"   CPU: {cpu_pct}%")
    print(f"   Memory: {process_pct}%")

# Validate results
peak_sample = samples[-1]
peak_memory = peak_sample.get('memory', {}).get('process_percent', 0)
peak_step = peak_sample.get('step_name', '')

print(f"\n{'=' * 70}")
print(f"VALIDATION:")
print(f"Last sample step: {peak_step}")
print(f"Last sample memory: {peak_memory}%")

if peak_step == 'Heavy Load Peak' and peak_memory > 5:
    print(f"✅ SUCCESS: Peak memory ({peak_memory}%) is > 5% as expected!")
    sys.exit(0)
else:
    print(f"❌ FAIL: Expected 'Heavy Load Peak' with >5% memory")
    sys.exit(1)
DOCKER_PYTHON
