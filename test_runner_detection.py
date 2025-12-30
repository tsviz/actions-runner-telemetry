#!/usr/bin/env python3
"""
Test suite for runner detection and normalization functions.
Tests the enhancements made to handle non-standard and randomized runner labels.
"""

import sys
import os
import unittest
from unittest.mock import patch

# Import the functions we're testing
from generate_report import (
    normalize_runner_label,
    detect_runner_type,
    is_runner_free
)


class TestNormalizeRunnerLabel(unittest.TestCase):
    """Test cases for normalize_runner_label function."""
    
    def test_standard_labels_unchanged(self):
        """Standard labels should normalize to themselves or proper canonical form."""
        self.assertEqual(normalize_runner_label('ubuntu-latest'), 'ubuntu-latest')
        self.assertEqual(normalize_runner_label('ubuntu-24.04'), 'ubuntu-24.04')
        self.assertEqual(normalize_runner_label('ubuntu-22.04'), 'ubuntu-22.04')
        self.assertEqual(normalize_runner_label('windows-latest'), 'windows-latest')
        self.assertEqual(normalize_runner_label('macos-latest'), 'macos-latest')
    
    def test_linux_large_runners(self):
        """Test normalization of Linux large runners."""
        self.assertEqual(normalize_runner_label('linux-8-core'), 'linux-8-core')
        self.assertEqual(normalize_runner_label('linux-4-core'), 'linux-4-core')
        # Non-standard variations
        self.assertEqual(normalize_runner_label('linux8cores'), 'linux-8-core')
        self.assertEqual(normalize_runner_label('linux-8c'), 'linux-8-core')
        self.assertEqual(normalize_runner_label('linux4core'), 'linux-4-core')
    
    def test_windows_large_runners(self):
        """Test normalization of Windows large runners."""
        self.assertEqual(normalize_runner_label('windows-8-core'), 'windows-8-core')
        self.assertEqual(normalize_runner_label('windows-4-core'), 'windows-4-core')
        # Non-standard variations
        self.assertEqual(normalize_runner_label('win8core'), 'windows-8-core')
        self.assertEqual(normalize_runner_label('windows-4c'), 'windows-4-core')
    
    def test_macos_large_runners(self):
        """Test normalization of macOS large runners."""
        self.assertEqual(normalize_runner_label('macos-13-large'), 'macos-13-large')
        self.assertEqual(normalize_runner_label('macos-latest-xlarge'), 'macos-latest-xlarge')
        # Non-standard variations
        self.assertEqual(normalize_runner_label('macos-xlarge'), 'macos-latest-xlarge')
        self.assertEqual(normalize_runner_label('macos-large'), 'macos-13-large')
    
    def test_randomized_large_runner_names(self):
        """Test handling of randomized large runner names (e.g., ubuntu-large-xyz123)."""
        # These should normalize to the generic large category
        self.assertEqual(normalize_runner_label('ubuntu-large-xyz123'), 'linux-large-generic')
        self.assertEqual(normalize_runner_label('linux-xlarge-abc456'), 'linux-large-generic')
        self.assertEqual(normalize_runner_label('ubuntu-bigger-random'), 'linux-large-generic')
        self.assertEqual(normalize_runner_label('linux-premium-runner'), 'linux-large-generic')
        
        # Windows randomized large runners
        self.assertEqual(normalize_runner_label('windows-large-xyz'), 'windows-4-core')
        self.assertEqual(normalize_runner_label('win-xlarge-123'), 'windows-4-core')
    
    def test_custom_runner_names(self):
        """Test custom/self-hosted runner names."""
        # Custom names with OS hints
        self.assertEqual(normalize_runner_label('tsvi-linux8cores'), 'linux-8-core')
        self.assertEqual(normalize_runner_label('custom-ubuntu-4c'), 'linux-4-core')
        
        # Names that can't be normalized return None
        self.assertIsNone(normalize_runner_label('my-custom-runner'))
        self.assertIsNone(normalize_runner_label('self-hosted-1'))
    
    def test_runner_os_hint(self):
        """Test OS hint parameter when name doesn't contain OS info."""
        # When name is ambiguous, OS hint should help
        result = normalize_runner_label('8-core-runner', runner_os_hint='Linux')
        self.assertEqual(result, 'linux-8-core')
        
        result = normalize_runner_label('4-core-runner', runner_os_hint='Windows')
        self.assertEqual(result, 'windows-4-core')
    
    def test_empty_or_none_input(self):
        """Test handling of empty or None input."""
        self.assertIsNone(normalize_runner_label(None))
        self.assertIsNone(normalize_runner_label(''))
        self.assertIsNone(normalize_runner_label('   '))
    
    def test_case_insensitivity(self):
        """Test that normalization is case-insensitive."""
        self.assertEqual(normalize_runner_label('UBUNTU-LATEST'), 'ubuntu-latest')
        self.assertEqual(normalize_runner_label('Linux-8-Core'), 'linux-8-core')
        self.assertEqual(normalize_runner_label('Windows-Latest'), 'windows-latest')


class TestDetectRunnerType(unittest.TestCase):
    """Test cases for detect_runner_type function."""
    
    def test_standard_ubuntu_runner(self):
        """Test detection of standard ubuntu-latest runner."""
        data = {
            'github_context': {
                'runner_os': 'Linux',
                'runner_name': 'ubuntu-latest'
            },
            'initial_snapshot': {
                'cpu_count': 4,
                'memory_total_mb': 16384
            }
        }
        result = detect_runner_type(data)
        self.assertEqual(result, 'ubuntu-latest')
    
    def test_linux_large_runner_by_specs(self):
        """Test detection of large Linux runner by specs when name is non-standard."""
        data = {
            'github_context': {
                'runner_os': 'Linux',
                'runner_name': 'custom-large-runner'
            },
            'initial_snapshot': {
                'cpu_count': 8,
                'memory_total_mb': 32768
            }
        }
        result = detect_runner_type(data)
        self.assertEqual(result, 'linux-8-core')
    
    def test_randomized_large_runner_name(self):
        """Test detection of randomized large runner name."""
        data = {
            'github_context': {
                'runner_os': 'Linux',
                'runner_name': 'ubuntu-large-xyz123'
            },
            'initial_snapshot': {
                'cpu_count': 4,
                'memory_total_mb': 16384
            }
        }
        result = detect_runner_type(data)
        # Should match to linux-4-core based on specs after normalization attempt
        self.assertIn(result, ['linux-4-core', 'ubuntu-latest'])
    
    def test_self_hosted_runner_fallback(self):
        """Test fallback for self-hosted runner with non-standard specs."""
        data = {
            'github_context': {
                'runner_os': 'Linux',
                'runner_name': 'self-hosted-custom'
            },
            'initial_snapshot': {
                'cpu_count': 16,
                'memory_total_mb': 65536
            }
        }
        result = detect_runner_type(data)
        # Should fall back to linux-8-core (closest match by CPU count)
        self.assertEqual(result, 'linux-8-core')
    
    def test_windows_runner_detection(self):
        """Test detection of Windows runners."""
        data = {
            'github_context': {
                'runner_os': 'Windows',
                'runner_name': 'windows-latest'
            },
            'initial_snapshot': {
                'cpu_count': 4,
                'memory_total_mb': 16384
            }
        }
        result = detect_runner_type(data)
        self.assertEqual(result, 'windows-latest')
    
    def test_macos_runner_detection(self):
        """Test detection of macOS runners."""
        data = {
            'github_context': {
                'runner_os': 'macOS',
                'runner_name': 'macos-latest'
            },
            'initial_snapshot': {
                'cpu_count': 3,
                'memory_total_mb': 7168
            }
        }
        result = detect_runner_type(data)
        self.assertEqual(result, 'macos-latest')
    
    def test_unknown_os_fallback(self):
        """Test fallback for unknown OS."""
        data = {
            'github_context': {
                'runner_os': 'FreeBSD',
                'runner_name': 'custom-runner'
            },
            'initial_snapshot': {
                'cpu_count': 4,
                'memory_total_mb': 16384
            }
        }
        result = detect_runner_type(data)
        # Should default to ubuntu-latest for unknown OS
        self.assertEqual(result, 'ubuntu-latest')


class TestIsRunnerFree(unittest.TestCase):
    """Test cases for is_runner_free function."""
    
    @patch.dict(os.environ, {'REPO_VISIBILITY': 'public'})
    def test_standard_runner_public_repo(self):
        """Test standard runner on public repo is free."""
        self.assertTrue(is_runner_free('ubuntu-latest', is_public_repo=True))
        self.assertTrue(is_runner_free('windows-latest', is_public_repo=True))
        self.assertTrue(is_runner_free('macos-latest', is_public_repo=True))
    
    @patch.dict(os.environ, {'REPO_VISIBILITY': 'private'})
    def test_standard_runner_private_repo(self):
        """Test standard runner on private repo is paid."""
        self.assertFalse(is_runner_free('ubuntu-latest', is_public_repo=False))
        self.assertFalse(is_runner_free('windows-latest', is_public_repo=False))
        self.assertFalse(is_runner_free('macos-latest', is_public_repo=False))
    
    def test_large_runner_always_paid(self):
        """Test that large runners are always paid regardless of repo visibility."""
        self.assertFalse(is_runner_free('linux-4-core', is_public_repo=True))
        self.assertFalse(is_runner_free('linux-8-core', is_public_repo=True))
        self.assertFalse(is_runner_free('windows-4-core', is_public_repo=True))
        self.assertFalse(is_runner_free('macos-13-large', is_public_repo=True))
    
    @patch.dict(os.environ, {'RUNNER_OS': 'Linux'})
    def test_randomized_large_runner_name_paid(self):
        """Test that randomized large runner names are treated as paid."""
        # Request name gets normalized to generic large category
        self.assertFalse(
            is_runner_free('ubuntu-latest', is_public_repo=True, 
                          requested_runner_name='ubuntu-large-xyz123')
        )
    
    @patch.dict(os.environ, {'RUNNER_OS': 'Linux'})
    def test_custom_runner_name_normalization(self):
        """Test that custom runner names are properly normalized for billing."""
        # Custom name that normalizes to large runner
        self.assertFalse(
            is_runner_free('ubuntu-latest', is_public_repo=True,
                          requested_runner_name='linux-8cores-custom')
        )
        
        # Custom name that normalizes to standard runner
        self.assertTrue(
            is_runner_free('ubuntu-latest', is_public_repo=True,
                          requested_runner_name='ubuntu-latest-custom')
        )
    
    def test_unknown_runner_defaults_to_paid(self):
        """Test that unknown runners default to paid."""
        self.assertFalse(is_runner_free('unknown-runner-type', is_public_repo=True))
        self.assertFalse(is_runner_free('self-hosted-custom', is_public_repo=False))


class TestIntegration(unittest.TestCase):
    """Integration tests combining multiple functions."""
    
    def test_large_runner_end_to_end(self):
        """Test complete flow for large runner with randomized name."""
        # Simulate a large runner with randomized name
        data = {
            'github_context': {
                'runner_os': 'Linux',
                'runner_name': 'ubuntu-large-abc123'
            },
            'initial_snapshot': {
                'cpu_count': 4,
                'memory_total_mb': 16384
            }
        }
        
        # Detect runner type
        runner_type = detect_runner_type(data)
        # Should detect as a 4-core runner based on specs
        self.assertIn(runner_type, ['linux-4-core', 'ubuntu-latest'])
        
        # Check if it's free (should be paid since it's a large runner)
        is_free = is_runner_free(runner_type, is_public_repo=True,
                                requested_runner_name='ubuntu-large-abc123')
        self.assertFalse(is_free)
    
    def test_standard_runner_end_to_end(self):
        """Test complete flow for standard runner."""
        data = {
            'github_context': {
                'runner_os': 'Linux',
                'runner_name': 'ubuntu-latest'
            },
            'initial_snapshot': {
                'cpu_count': 4,
                'memory_total_mb': 16384
            }
        }
        
        runner_type = detect_runner_type(data)
        self.assertEqual(runner_type, 'ubuntu-latest')
        
        # On public repo, should be free
        is_free = is_runner_free(runner_type, is_public_repo=True)
        self.assertTrue(is_free)
        
        # On private repo, should be paid
        is_free = is_runner_free(runner_type, is_public_repo=False)
        self.assertFalse(is_free)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
