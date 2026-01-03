#!/usr/bin/env python3
import os
import unittest

# Import the report generator module
import generate_report as gr


def build_samples(duration=20, interval=1, cpu_low=2.4, cpu_peak=4.0, mem_low=7.8, mem_peak=10.0,
                  iowait=0.6, steal=0.2, swap=0.8):
    """Create a simple set of samples for report generation."""
    samples = []
    start = 0.0
    ts = start
    for i in range(int(duration / interval)):
        # Alternate low and peak values to populate averages and peaks
        cpu = cpu_peak if (i % 4 == 0) else cpu_low
        mem = mem_peak if (i % 4 == 0) else mem_low
        samples.append({
            'timestamp': ts,
            'cpu_percent': float(cpu),
            'memory': {
                'percent': float(mem),
                'used_mb': int(mem / 100.0 * 16384),
            },
            'load': {'load_1m': 0.5},
            'disk_io': {'read_rate': 1024 * 1024, 'write_rate': int(0.7 * 1024 * 1024)},
            'network_io': {'rx_rate': int(0.8 * 1024 * 1024), 'tx_rate': int(0.5 * 1024 * 1024)},
            'cpu_iowait_percent': float(iowait),
            'cpu_steal_percent': float(steal),
            'swap': {'percent': float(swap)},
        })
        ts += interval
    return samples


def build_data(runner_name, runner_os, cpu_cores, mem_mb, duration_sec, interval_sec, repo_visibility):
    return {
        'duration': duration_sec,
        'interval': interval_sec,
        'start_time': 0.0,
        'end_time': float(duration_sec),
        'samples': build_samples(duration=duration_sec, interval=interval_sec),
        'initial_snapshot': {
            'cpu_count': cpu_cores,
            'memory': {'total_mb': mem_mb},
        },
        'final_snapshot': {},
        'github_context': {
            'runner_name': runner_name,
            'runner_os': runner_os,
            'runner_arch': 'X64',
            'repository_visibility': repo_visibility,
        },
    }


class TestReportGeneration(unittest.TestCase):
    def test_public_standard_free_runner(self):
        data = build_data('ubuntu-latest', 'Linux', 4, 16384, 20, 1, 'public')
        report = gr.generate_report(data)
        self.assertIn('🎉 Free Runner', report)
        self.assertIn('Runner Utilization & Performance', report)
        self.assertNotIn('Cost Analysis (Jan 2026+ Pricing)', report)

    def test_private_standard_cost_analysis(self):
        data = build_data('ubuntu-latest', 'Linux', 2, 7168, 60, 3, 'private')
        report = gr.generate_report(data)
        self.assertIn('Runner Utilization & Cost Efficiency', report)
        self.assertIn('Cost Analysis (Jan 2026+ Pricing)', report)
        self.assertIn('This Run', report)
        self.assertIn('Est. Monthly', report)

    def test_public_larger_runner_paid(self):
        data = build_data('linux-8-core', 'Linux', 8, 32768, 300, 15, 'public')
        report = gr.generate_report(data)
        # Larger runners should not show free runner notice
        self.assertNotIn('🎉 Free Runner', report)
        self.assertIn('Runner Utilization & Cost Efficiency', report)

    def test_private_larger_runner_cost_analysis(self):
        data = build_data('linux-8-core', 'Linux', 8, 32768, 300, 15, 'private')
        report = gr.generate_report(data)
        self.assertIn('Runner Utilization & Cost Efficiency', report)
        self.assertIn('Cost Analysis (Jan 2026+ Pricing)', report)
        self.assertIn('Linux 8-core Larger Runner', report)

    def test_self_hosted_cost_context(self):
        # Mark as self-hosted by name and override
        os.environ['HOSTING_TYPE'] = 'self-hosted'
        try:
            data = build_data('self-hosted-custom', 'Linux', 8, 32768, 300, 15, 'private')
            report = gr.generate_report(data)
            self.assertIn('This job ran on a **self-hosted runner**', report)
            self.assertIn('Recommended equivalent GitHub-hosted option', report)
        finally:
            os.environ.pop('HOSTING_TYPE', None)

    def test_public_repo_upgrade_recommends_8core(self):
        """Test that public repo with maxed-out 4-core runner recommends 8-core, not 4-core.
        
        On public repos, ubuntu-latest already has 4-core/16GB.
        So when it's maxed out, the recommendation should be 8-core, not 4-core.
        """
        # Test the upgrade recommendation function directly
        rec = gr.recommend_runner_upgrade(
            max_cpu_pct=95,  # High utilization
            max_mem_pct=90,
            duration_seconds=120,
            current_runner_type='ubuntu-latest',
            is_public_repo=True  # Public repo = already has 4-core
        )
        
        # Should recommend 8-core, not 4-core (since public already has 4-core)
        self.assertEqual(rec['recommended'], 'linux-8-core')
        self.assertEqual(rec['cores'], 8)
        self.assertTrue(rec['is_upgrade_possible'])
    
    def test_private_repo_upgrade_recommends_4core(self):
        """Test that private repo with maxed-out 2-core runner recommends 4-core.
        
        On private repos, ubuntu-latest has 2-core/7GB.
        So when it's maxed out, the recommendation should be 4-core.
        """
        rec = gr.recommend_runner_upgrade(
            max_cpu_pct=95,
            max_mem_pct=90,
            duration_seconds=120,
            current_runner_type='ubuntu-latest',
            is_public_repo=False  # Private repo = 2-core
        )
        
        # Should recommend 4-core for private repos
        self.assertEqual(rec['recommended'], 'linux-4-core')
        self.assertEqual(rec['cores'], 4)
        self.assertTrue(rec['is_upgrade_possible'])


if __name__ == '__main__':
    unittest.main()
