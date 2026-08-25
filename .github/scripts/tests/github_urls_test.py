#!/usr/bin/env python3

"""
Tests for github_urls.py
Run with: python github_urls_test.py
"""

import sys
import unittest
from pathlib import Path

# Make the script under test importable (it lives one directory up).
sys.path.insert(0, str(Path(__file__).parent.parent))

from github_urls import canonical_repository_url, normalize_url


class NormalizeUrlTests(unittest.TestCase):
    def test_equivalent_forms_compare_equal(self):
        canonical = normalize_url('https://github.com/Acme/Widget')
        for variant in ['https://github.com/acme/widget/',
                        'https://github.com/Acme/Widget.git',
                        'https://github.com/Acme/Widget.git/',
                        'https://github.com/Acme/Widget.GIT',
                        'https://github.com/Acme/Widget.Git/',
                        '  https://github.com/ACME/WIDGET  ']:
            self.assertEqual(normalize_url(variant), canonical, variant)

    def test_different_repositories_differ(self):
        self.assertNotEqual(normalize_url('https://github.com/a/b'),
                            normalize_url('https://github.com/a/c'))

    def test_empty_input(self):
        self.assertEqual(normalize_url(None), '')
        self.assertEqual(normalize_url('   '), '')

    def test_a_repository_named_git_is_not_truncated(self):
        self.assertEqual(normalize_url('https://github.com/a/git'), 'https://github.com/a/git')


class CanonicalRepositoryUrlTests(unittest.TestCase):
    def test_reduces_to_owner_and_repository(self):
        for given in ['https://github.com/Acme/Widget',
                      'https://github.com/Acme/Widget/',
                      'https://github.com/Acme/Widget.git',
                      'https://github.com/Acme/Widget.GIT/',
                      'github.com/Acme/Widget',
                      'http://github.com/Acme/Widget',
                      'https://www.github.com/Acme/Widget',
                      'https://github.com/Acme/Widget/tree/main/src']:
            self.assertEqual(canonical_repository_url(given),
                             'https://github.com/Acme/Widget', given)

    def test_preserves_the_owner_and_repository_casing(self):
        self.assertEqual(canonical_repository_url('https://github.com/Acme/Widget'),
                         'https://github.com/Acme/Widget')

    def test_rejects_anything_that_is_not_a_github_repository(self):
        for given in ['not a url', '', None, 'https://gitlab.com/a/b',
                      'https://github.com/only-an-owner']:
            self.assertEqual(canonical_repository_url(given), '', repr(given))


if __name__ == '__main__':
    unittest.main(verbosity=2)
