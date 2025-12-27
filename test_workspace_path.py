#!/usr/bin/env python3
"""Test the fixed workflow with workspace path"""
import sys
import os
import json

TELEMETRY_DATA_FILE = '/github/workspace/.telemetry_test.json'
os.environ['TELEMETRY_DATA_FILE'] = TELEMETRY_DATA_FILE

if os.path.exists(TELEMETRY_DATA_FILE):
    os.remove(TELEMETRY_DATA_FILE)

# Use workspace path like the workflow will
sys.path.insert(0, '/github/workspace')
from telemetry_collector import start_collection, stop_collection, mark_step

print('Starting collection...')
start_collection()

print('Marking baseline...')
mark_step('Baseline')

print('Allocating memory...')
arrays = [list(range(125000000)) for _ in range(3)]

print('Computing...')
result = sum(sum(arr[i] * (i % 10) for i in range(0, len(arr), 50000)) for arr in arrays)

print('Marking peak (memory allocated)...')
mark_step('Heavy Load Peak')

del arrays
print('Stopping...')
stop_collection()

print('\nChecking results...')
if os.path.exists(TELEMETRY_DATA_FILE):
    with open(TELEMETRY_DATA_FILE, 'r') as f:
        data = json.load(f)
    if 'samples' in data and len(data['samples']) >= 2:
        for i, s in enumerate(data['samples']):
            peak = s.get('memory', {}).get('process_percent', 0)
            print(f'  Sample {i+1}: {peak}%')
        peak = data['samples'][-1].get('memory', {}).get('process_percent', 0)
        if peak > 30:
            print(f'\n✅ SUCCESS: Peak memory {peak}%')
        else:
            print(f'\n❌ FAIL: Memory {peak}% too low')
    else:
        print(f'❌ FAIL: Only {len(data.get("samples", []))} samples')
else:
    print('❌ FAIL: No data file found')
