#!/usr/bin/env python3
import sys
import json
import os

TELEMETRY_DATA_FILE = '/github/workspace/.telemetry_test.json'
os.environ['TELEMETRY_DATA_FILE'] = TELEMETRY_DATA_FILE

if os.path.exists(TELEMETRY_DATA_FILE):
    os.remove(TELEMETRY_DATA_FILE)

sys.path.insert(0, '/')
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

print('\nAnalyzing results...')
# Try to find the data file
possible_paths = [
    '/github/workspace/.telemetry_test.json',
    '/tmp/telemetry_data.json',
    os.environ.get('TELEMETRY_DATA_FILE', '')
]

data_file = None
for path in possible_paths:
    if path and os.path.exists(path):
        data_file = path
        break

if not data_file:
    print(f'ERROR: Could not find telemetry file. Checked: {possible_paths}')
    sys.exit(1)

print(f'Using data file: {data_file}')
with open(data_file, 'r') as f:
    data = json.load(f)

if 'samples' in data:
    print(f'\nFound {len(data["samples"])} samples:')
    for i, s in enumerate(data['samples']):
        mem_pct = s.get('memory', {}).get('process_percent', s.get('memory', {}).get('percent', 0))
        step_name = s.get('step_name', f'Sample {i+1}')
        print(f'  {step_name}: Memory={mem_pct}%')
        
    # Check if we have 2 samples with the peak being high memory
    if len(data['samples']) >= 2:
        last = data['samples'][-1]
        last_mem = last.get('memory', {}).get('process_percent', 0)
        if last_mem > 30:  # Peak should be >30% since we allocated ~10% of 15GB
            print(f'\n✅ SUCCESS: Peak memory is {last_mem}% (correct - marks during allocation)')
            sys.exit(0)
        else:
            print(f'\n❌ FAIL: Peak memory {last_mem}% is too low')
            sys.exit(1)
    else:
        print(f'\n❌ FAIL: Expected 2 samples, got {len(data["samples"])}')
        sys.exit(1)
else:
    print('ERROR: No samples in data')
    sys.exit(1)
