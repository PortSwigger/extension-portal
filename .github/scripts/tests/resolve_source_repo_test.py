#!/usr/bin/env python3

"""
Tests for resolve_source_repo.py
Run with: python resolve_source_repo_test.py

The GitHub API is mocked so the tests are deterministic and need no network.
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

# Make the script under test importable (it lives one directory up).
sys.path.insert(0, str(Path(__file__).parent.parent))

import resolve_source_repo as rsr


def fake_api(pull=None, base=None):
    """Build a github_api_get replacement that returns canned PR/repo payloads."""
    def _get(api_url, github_token=None):
        if '/pulls/' in api_url:
            return pull
        return base
    return _get


class ExtractPrRefTests(unittest.TestCase):
    def test_full_url(self):
        self.assertEqual(
            rsr.extract_pr_ref('https://github.com/PortSwigger/my-repo/pull/123'),
            ('PortSwigger', 'my-repo', '123'),
        )

    def test_without_scheme(self):
        self.assertEqual(
            rsr.extract_pr_ref('github.com/PortSwigger/my-repo/pull/5'),
            ('PortSwigger', 'my-repo', '5'),
        )

    def test_repo_url_without_pull_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            rsr.extract_pr_ref('https://github.com/PortSwigger/my-repo')
        self.assertIn('pull request reference', str(ctx.exception))

    def test_non_github_url_is_rejected(self):
        with self.assertRaises(ValueError):
            rsr.extract_pr_ref('not-a-github-url')


class NormalizeUrlTests(unittest.TestCase):
    def test_strips_git_suffix_slash_and_lowercases(self):
        self.assertEqual(
            rsr.normalize_url('https://github.com/PortSwigger/My-Repo.git/'),
            'https://github.com/portswigger/my-repo',
        )

    def test_handles_none(self):
        self.assertEqual(rsr.normalize_url(None), '')


class ResolveSourceRepoTests(unittest.TestCase):
    def test_fork_pr_from_parent_resolves_to_parent(self):
        pull = {'head': {'repo': {'html_url': 'https://github.com/author/widget'}}}
        base = {'fork': True, 'parent': {'html_url': 'https://github.com/author/widget'},
                'html_url': 'https://github.com/PortSwigger/widget'}
        with mock.patch.object(rsr, 'github_api_get', fake_api(pull, base)):
            self.assertEqual(
                rsr.resolve_source_repo('PortSwigger', 'widget', '1'),
                'https://github.com/author/widget',
            )

    def test_fork_pr_from_wrong_source_is_rejected(self):
        pull = {'head': {'repo': {'html_url': 'https://github.com/attacker/widget'}}}
        base = {'fork': True, 'parent': {'html_url': 'https://github.com/author/widget'},
                'html_url': 'https://github.com/PortSwigger/widget'}
        with mock.patch.object(rsr, 'github_api_get', fake_api(pull, base)):
            with self.assertRaises(ValueError) as ctx:
                rsr.resolve_source_repo('PortSwigger', 'widget', '1')
        self.assertIn('source repository', str(ctx.exception))

    def test_portswigger_owned_original_resolves_to_itself(self):
        pull = {'head': {'repo': {'html_url': 'https://github.com/PortSwigger/widget'}}}
        base = {'fork': False, 'parent': None,
                'html_url': 'https://github.com/PortSwigger/widget'}
        with mock.patch.object(rsr, 'github_api_get', fake_api(pull, base)):
            self.assertEqual(
                rsr.resolve_source_repo('PortSwigger', 'widget', '1'),
                'https://github.com/PortSwigger/widget',
            )

    def test_non_fork_pr_from_other_repo_is_rejected(self):
        pull = {'head': {'repo': {'html_url': 'https://github.com/someone/widget'}}}
        base = {'fork': False, 'parent': None,
                'html_url': 'https://github.com/PortSwigger/widget'}
        with mock.patch.object(rsr, 'github_api_get', fake_api(pull, base)):
            with self.assertRaises(ValueError):
                rsr.resolve_source_repo('PortSwigger', 'widget', '1')

    def test_deleted_head_repo_is_rejected(self):
        pull = {'head': {'repo': None}}
        base = {'fork': True, 'parent': {'html_url': 'https://github.com/author/widget'},
                'html_url': 'https://github.com/PortSwigger/widget'}
        with mock.patch.object(rsr, 'github_api_get', fake_api(pull, base)):
            with self.assertRaises(ValueError) as ctx:
                rsr.resolve_source_repo('PortSwigger', 'widget', '1')
        self.assertIn('source repository of the pull request', str(ctx.exception))

    def test_matching_ignores_git_suffix_and_case(self):
        pull = {'head': {'repo': {'html_url': 'https://github.com/Author/Widget.git'}}}
        base = {'fork': True, 'parent': {'html_url': 'https://github.com/author/widget'},
                'html_url': 'https://github.com/PortSwigger/widget'}
        with mock.patch.object(rsr, 'github_api_get', fake_api(pull, base)):
            self.assertEqual(
                rsr.resolve_source_repo('PortSwigger', 'widget', '1'),
                'https://github.com/author/widget',
            )


if __name__ == '__main__':
    unittest.main(verbosity=2)
