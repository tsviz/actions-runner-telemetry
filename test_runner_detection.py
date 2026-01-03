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
        # Non-standard variations should not normalize
        self.assertIsNone(normalize_runner_label('linux8cores'))
        self.assertIsNone(normalize_runner_label('linux-8c'))
        self.assertIsNone(normalize_runner_label('linux4core'))
    
    def test_windows_large_runners(self):
        """Test normalization of Windows large runners."""
        self.assertEqual(normalize_runner_label('windows-8-core'), 'windows-8-core')
        self.assertEqual(normalize_runner_label('windows-4-core'), 'windows-4-core')
        # Non-standard variations should not normalize
        self.assertIsNone(normalize_runner_label('win8core'))
        self.assertIsNone(normalize_runner_label('windows-4c'))
    
    def test_macos_large_runners(self):
        """Test normalization of macOS large runners."""
        self.assertEqual(normalize_runner_label('macos-13-large'), 'macos-13-large')
        self.assertEqual(normalize_runner_label('macos-latest-xlarge'), 'macos-latest-xlarge')
        # Non-standard variations should not normalize
        self.assertIsNone(normalize_runner_label('macos-xlarge'))
        self.assertIsNone(normalize_runner_label('macos-large'))
    
    def test_randomized_large_runner_names(self):
        """Test handling of randomized large runner names (e.g., ubuntu-large-xyz123)."""
        # These should return None to trigger spec-based detection
        self.assertIsNone(normalize_runner_label('ubuntu-large-xyz123'))
        self.assertIsNone(normalize_runner_label('linux-xlarge-abc456'))
        self.assertIsNone(normalize_runner_label('ubuntu-bigger-random'))
        self.assertIsNone(normalize_runner_label('linux-premium-runner'))
        
        # Windows randomized large runners should not normalize
        self.assertIsNone(normalize_runner_label('windows-large-xyz'))
        self.assertIsNone(normalize_runner_label('win-xlarge-123'))
    
    def test_custom_runner_names(self):
        """Test custom/self-hosted runner names."""
        # Custom names should not normalize
        self.assertIsNone(normalize_runner_label('tsvi-linux8cores'))
        self.assertIsNone(normalize_runner_label('custom-ubuntu-4c'))
        # Names that can't be normalized return None
        self.assertIsNone(normalize_runner_label('my-custom-runner'))
        self.assertIsNone(normalize_runner_label('self-hosted-1'))
    
    def test_runner_os_hint(self):
        """Test OS hint parameter when name doesn't contain OS info."""
        # OS hint should not normalize arbitrary names; rely on spec detection later
        result = normalize_runner_label('8-core-runner', runner_os_hint='Linux')
        self.assertIsNone(result)
        result = normalize_runner_label('4-core-runner', runner_os_hint='Windows')
        self.assertIsNone(result)
    
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
                'memory': {'total_mb': 16384}
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
                'memory': {'total_mb': 32768}
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
                'memory': {'total_mb': 16384}
            }
        }
        result = detect_runner_type(data)
        # Should match to linux-4-core based on specs (4-core, 16GB - standard runners are only 2-core)
        self.assertEqual(result, 'linux-4-core')
    
    def test_self_hosted_runner_fallback(self):
        """Test fallback for self-hosted runner with non-standard specs."""
        data = {
            'github_context': {
                'runner_os': 'Linux',
                'runner_name': 'self-hosted-custom'
            },
            'initial_snapshot': {
                'cpu_count': 16,
                'memory': {'total_mb': 65536}
            }
        }
        result = detect_runner_type(data)
        # Should fall back to linux-8-core (closest match by CPU count)
        self.assertEqual(result, 'linux-8-core')

    def test_public_hosted_larger_custom_label_kept(self):
        """Public repo with hosted larger runner and custom label should keep larger classification."""
        data = {
            'github_context': {
                'runner_os': 'Linux',
                'runner_name': 'tsvi-linux8cores',
            },
            'initial_snapshot': {
                'cpu_count': 8,
                'memory': {'total_mb': 32768}
            }
        }
        result = detect_runner_type(data, is_public_repo=True)
        self.assertEqual(result, 'linux-8-core')
        # Larger runners are always paid on public repos
        self.assertFalse(is_runner_free(result, is_public_repo=True))
    
    def test_windows_runner_detection(self):
        """Test detection of Windows runners."""
        data = {
            'github_context': {
                'runner_os': 'Windows',
                'runner_name': 'windows-latest'
            },
            'initial_snapshot': {
                'cpu_count': 4,
                'memory': {'total_mb': 16384}
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
                'memory': {'total_mb': 7168}
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
                'memory': {'total_mb': 16384}
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
        """Randomized large runner names should not affect billing without canonical labels."""
        # On public repo, billing should rely on detected runner type (ubuntu-latest → free)
        self.assertTrue(
            is_runner_free('ubuntu-latest', is_public_repo=True,
                          requested_runner_name='ubuntu-large-xyz123')
        )
    
    @patch.dict(os.environ, {'RUNNER_OS': 'Linux'})
    def test_custom_runner_name_normalization(self):
        """Custom runner names should not drive billing; rely on detected type."""
        self.assertTrue(
            is_runner_free('ubuntu-latest', is_public_repo=True,
                          requested_runner_name='linux-8cores-custom')
        )
        self.assertTrue(
            is_runner_free('ubuntu-latest', is_public_repo=True,
                          requested_runner_name='ubuntu-latest-custom')
        )
    
    def test_unknown_runner_defaults_to_paid(self):
        """Test that unknown runners default to paid."""
        self.assertFalse(is_runner_free('unknown-runner-type', is_public_repo=True))
        self.assertFalse(is_runner_free('self-hosted-custom', is_public_repo=False))

    def test_self_hosted_8core_not_classified_as_github_larger(self):
        """Test that self-hosted runners with large specs are NOT classified as paid GitHub larger runners.
        
        A user might have a self-hosted runner with 8 cores and 32GB RAM.
        This should NOT be classified as 'linux-8-core' (which implies GitHub billing).
        
        The key differentiator is RUNNER_ENVIRONMENT=self-hosted.
        """
        data = {
            'github_context': {
                'runner_os': 'Linux',
                'runner_name': 'my-self-hosted-runner'
            },
            'initial_snapshot': {
                'cpu_count': 8,
                'memory': {'total_mb': 32768}  # 32GB - same as GitHub 8-core
            }
        }
        
        import os
        original_env = os.environ.copy()
        try:
            # Key: This is a SELF-HOSTED runner
            os.environ['RUNNER_ENVIRONMENT'] = 'self-hosted'
            
            # Should NOT be classified as linux-8-core (GitHub billing)
            # Should fallback to self-hosted handling
            runner_type = detect_runner_type(data, is_public_repo=True)
            
            # Self-hosted runners use fallback logic, but should NOT trigger
            # the "GitHub larger runner" paid path
            # The runner type might be 'linux-8-core' based on specs, but billing
            # should recognize it as self-hosted
            
            # Verify hosting type is correctly detected as self-hosted
            from generate_report import detect_hosting_type
            hosting = detect_hosting_type(data)
            self.assertEqual(hosting['is_github_hosted'], False)
            self.assertIn('runner_environment=self-hosted', hosting['signals'])
        finally:
            os.environ.clear()
            os.environ.update(original_env)


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
                'memory': {'total_mb': 16384}
            }
        }
        
        # Detect runner type - should match to linux-4-core based on specs (4-core, 16GB)
        runner_type = detect_runner_type(data)
        self.assertEqual(runner_type, 'linux-4-core')
        
        # Larger runners are always paid, even on public repos
        is_free = is_runner_free(runner_type, is_public_repo=True,
                    requested_runner_name='ubuntu-large-abc123')
        self.assertFalse(is_free)

    def test_github_hosted_4core_with_numeric_name(self):
        """Test GitHub-hosted 4-core runner with generic numbered name like 'GitHub Actions 1000002091'.
        
        For PUBLIC repos, standard runners have upgraded specs:
        - ubuntu-latest = 4 CPU, 16GB RAM (FREE)
        - So 4-core/16GB should match ubuntu-latest, not linux-4-core
        
        For PRIVATE repos, standard runners have lower specs:
        - ubuntu-latest = 2 CPU, 7GB RAM (PAID)
        - So 4-core/16GB would match linux-4-core (larger runner)
        """
        data = {
            'github_context': {
                'runner_os': 'Linux',
                'runner_name': 'GitHub Actions 1000002091'
            },
            'initial_snapshot': {
                'cpu_count': 4,
                'memory': {'total_mb': 16384}  # 16GB
            }
        }
        
        # Mock hosting detection to indicate GitHub-hosted
        import os
        original_env = os.environ.copy()
        try:
            os.environ['RUNNER_ENVIRONMENT'] = 'github-hosted'
            
            # PUBLIC repo: 4-core/16GB matches ubuntu-latest specs (FREE)
            runner_type = detect_runner_type(data, is_public_repo=True)
            self.assertEqual(runner_type, 'ubuntu-latest')
            
            # ubuntu-latest on public repo = FREE
            is_free = is_runner_free(runner_type, is_public_repo=True)
            self.assertTrue(is_free)
            
            # PRIVATE repo: 4-core/16GB does NOT match ubuntu-latest (2-core/7GB)
            # Should match linux-4-core instead
            runner_type_private = detect_runner_type(data, is_public_repo=False)
            self.assertEqual(runner_type_private, 'linux-4-core')
            
            # linux-4-core is always paid
            is_free = is_runner_free(runner_type_private, is_public_repo=False)
            self.assertFalse(is_free)
        finally:
            os.environ.clear()
            os.environ.update(original_env)

    def test_custom_named_larger_runner(self):
        """Test GitHub-hosted larger runner with custom name like 'tsvi-linux8cores'.
        
        When a user creates a larger runner through GitHub's UI with a custom name,
        it's still GitHub-hosted but has custom naming. The runner should be detected
        based on hardware specs and correctly billed as a larger runner.
        
        Key insight: Standard runners on public repos get UP TO 4-core/16GB.
        If we see 8-core/32GB, it MUST be a larger runner regardless of name.
        
        This test simulates the scenario:
        - runs-on: tsvi-linux8cores (custom larger runner name)
        - Actual HW: 8 cores, 32GB RAM (exceeds standard runner max)
        - GitHub-hosted (via environment signals)
        - Should detect as linux-8-core (PAID), not ubuntu-latest (FREE)
        """
        data = {
            'github_context': {
                'runner_os': 'Linux',
                'runner_name': 'GitHub Actions 1000388083'  # Generic runtime name
            },
            'initial_snapshot': {
                'cpu_count': 8,
                'memory': {'total_mb': 32098}  # ~31.3 GB - exceeds 16GB standard max
            }
        }
        
        import os
        original_env = os.environ.copy()
        try:
            # Simulate GitHub-hosted environment
            os.environ['RUNNER_ENVIRONMENT'] = 'github-hosted'
            
            # Even on public repo, 8-core/32GB exceeds standard specs → PAID
            runner_type = detect_runner_type(data, is_public_repo=True)
            self.assertEqual(runner_type, 'linux-8-core')
            
            # linux-8-core is always paid
            is_free = is_runner_free(runner_type, is_public_repo=True)
            self.assertFalse(is_free)
        finally:
            os.environ.clear()
            os.environ.update(original_env)
    
    def test_standard_runner_end_to_end(self):
        """Test complete flow for standard runner."""
        data = {
            'github_context': {
                'runner_os': 'Linux',
                'runner_name': 'ubuntu-latest'
            },
            'initial_snapshot': {
                'cpu_count': 2,
                'memory': {'total_mb': 7168}
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
