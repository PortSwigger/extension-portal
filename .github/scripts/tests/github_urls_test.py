#!/usr/bin/env python3

"""
Tests for github_urls.py
Run with: python github_urls_test.py

Which URLs are acceptable is sanitize-inputs' decision, not this module's, so
these cover only what it leaves us: extracting the parts the GitHub API needs,
and reducing URLs to a single spelling.
"""

import sys
import unittest
from pathlib import Path

# Make the script under test importable (it lives one directory up).
sys.path.insert(0, str(Path(__file__).parent.parent))

from github_urls import (normalize_url, pull_request_parts, repository_parts,
                         repository_url)


class NormalizeUrlTests(unittest.TestCase):
    def test_equivalent_forms_compare_equal(self):
        canonical = normalize_url('https://github.com/Acme/Widget')
        for variant in ['https://github.com/acme/widget/',
                        'https://github.com/Acme/Widget.git',
                        'https://github.com/Acme/Widget.git/',
                        'https://github.com/Acme/Widget.GIT',
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


class RepositoryPartsTests(unittest.TestCase):
    def test_splits_the_shapes_sanitize_inputs_accepts(self):
        for given in ['https://github.com/Acme/Widget',
                      'https://github.com/Acme/Widget/',
                      'https://github.com/Acme/Widget.git',
                      '  https://github.com/Acme/Widget  ']:
            self.assertEqual(repository_parts(given), ('Acme', 'Widget'), given)

    def test_keeps_the_punctuation_github_allows_in_names(self):
        self.assertEqual(repository_parts('https://github.com/a-co/my.widget-2_0'),
                         ('a-co', 'my.widget-2_0'))

    def test_a_query_string_never_leaks_into_the_repository_name(self):
        self.assertEqual(repository_parts('https://github.com/Acme/Widget?tab=readme'),
                         ('Acme', 'Widget'))
        self.assertEqual(repository_parts('https://github.com/Acme/Widget#install'),
                         ('Acme', 'Widget'))

    def test_no_repository_to_find(self):
        for given in ['not a url', '', None, 'https://github.com/only-an-owner']:
            self.assertIsNone(repository_parts(given), repr(given))


class PullRequestPartsTests(unittest.TestCase):
    def test_splits_the_shapes_sanitize_inputs_accepts(self):
        for given in ['https://github.com/PortSwigger/Widget/pull/12',
                      'https://github.com/PortSwigger/Widget/pull/12/',
                      '  https://github.com/PortSwigger/Widget/pull/12  ']:
            self.assertEqual(pull_request_parts(given), ('PortSwigger', 'Widget', '12'), given)

    def test_no_pull_request_to_find(self):
        for given in ['https://github.com/PortSwigger/Widget',
                      'https://github.com/PortSwigger/Widget/pull/abc', '', None]:
            self.assertIsNone(pull_request_parts(given), repr(given))


class RepositoryUrlTests(unittest.TestCase):
    def test_reduces_a_repository_to_one_spelling(self):
        for given in ['https://github.com/Acme/Widget',
                      'https://github.com/Acme/Widget/',
                      'https://github.com/Acme/Widget.git',
                      'github.com/Acme/Widget']:
            self.assertEqual(repository_url(given), 'https://github.com/Acme/Widget', given)

    def test_preserves_owner_and_repository_casing(self):
        self.assertEqual(repository_url('https://github.com/Acme/Widget'),
                         'https://github.com/Acme/Widget')

    def test_empty_when_there_is_no_repository(self):
        self.assertEqual(repository_url('not a url'), '')
        self.assertEqual(repository_url(None), '')


if __name__ == '__main__':
    unittest.main(verbosity=2)
