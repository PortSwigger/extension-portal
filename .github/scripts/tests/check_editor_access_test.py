#!/usr/bin/env python3

"""
Tests for check_editor_access.py
Run with: python check_editor_access_test.py

The GitHub API is mocked so the tests are deterministic and need no network.
"""

import json
import sys
import unittest
from http.client import IncompleteRead
from pathlib import Path
from unittest import mock
from urllib import error

# Make the script under test importable (it lives one directory up).
sys.path.insert(0, str(Path(__file__).parent.parent))

import check_editor_access as cea


class ClassifyEditorTests(unittest.TestCase):
    """
    The submitter and bot checks are free and decisive. The write-access lookup
    refines the rest: a definite answer either way is trusted, and an
    inconclusive one leaves the free checks standing.
    """

    def classify(self, editor='bob', author='alice', editor_type='User',
                 repository='PortSwigger/extension-portal', permission='write',
                 role_name=None, raises=None):
        def fake_api(api_url, github_token=None):
            if raises:
                raise raises
            return {'permission': permission,
                    'role_name': role_name if role_name is not None else permission}
        with mock.patch.object(cea, 'github_api_get', fake_api):
            return cea.classify_editor(editor, author, editor_type=editor_type,
                                       repository=repository, github_token='t')

    def maintainer(self, **kwargs):
        return self.classify(**kwargs).is_maintainer

    def access_level(self, **kwargs):
        return self.classify(**kwargs).access

    @staticmethod
    def http_error(code):
        return error.HTTPError('https://api.github.com', code, 'boom', {}, None)

    # --- confirmed maintainers ---

    def test_write_access(self):
        self.assertTrue(self.maintainer(permission='write'))

    def test_admin_access(self):
        self.assertTrue(self.maintainer(permission='admin', role_name='admin'))

    def test_maintain_role(self):
        self.assertTrue(self.maintainer(permission='write', role_name='maintain'))

    def test_custom_org_role_falls_back_to_the_coarse_permission(self):
        self.assertTrue(self.maintainer(permission='write', role_name='bapp-reviewer'))

    # --- everything else is the submitter ---

    def test_author_editing_their_own_issue_is_never_a_maintainer(self):
        # No API call should even be needed here.
        with mock.patch.object(cea, 'github_api_get', mock.Mock(side_effect=AssertionError)):
            self.assertFalse(cea.classify_editor('alice', 'alice', editor_type='User',
                                                 repository='o/r', github_token='t').is_maintainer)

    def test_triage_only_account_is_not_trusted_to_redirect_a_submission(self):
        self.assertFalse(self.maintainer(permission='read', role_name='triage'))

    def test_read_access(self):
        self.assertFalse(self.maintainer(permission='read', role_name='read'))

    def test_no_access(self):
        self.assertFalse(self.maintainer(permission='none', role_name='none'))

    def test_bot_by_sender_type(self):
        self.assertFalse(self.maintainer(editor='helpful-bot', editor_type='Bot'))

    def test_bot_by_login_suffix_even_if_it_has_write(self):
        self.assertFalse(self.maintainer(editor='helpful-bot[bot]', editor_type='User',
                                         permission='admin'))

    def test_404_means_not_a_collaborator_and_is_trusted(self):
        self.assertFalse(self.maintainer(raises=self.http_error(404)))

    def test_missing_logins_fall_back_to_submitter(self):
        self.assertFalse(self.maintainer(editor=None))
        self.assertFalse(self.maintainer(author=None))
        self.assertFalse(self.maintainer(editor='', author=''))

    def test_malformed_api_response_is_not_write_access(self):
        with mock.patch.object(cea, 'github_api_get', lambda *a, **k: {}):
            self.assertFalse(cea.classify_editor('bob', 'alice', editor_type='User',
                                                 repository='o/r', github_token='t').is_maintainer)

    # --- inconclusive lookups leave the free checks standing ---

    def test_403_leaves_a_non_bot_non_submitter_edit_as_a_maintainer_edit(self):
        self.assertTrue(self.maintainer(raises=self.http_error(403)))

    def test_network_failures_leave_a_non_bot_non_submitter_edit_as_a_maintainer_edit(self):
        for failure in [error.URLError('connection reset'),
                        TimeoutError('timed out'),
                        IncompleteRead(b''),
                        json.JSONDecodeError('not json', '', 0)]:
            self.assertTrue(self.maintainer(raises=failure), repr(failure))

    def test_a_programming_error_is_not_swallowed(self):
        with self.assertRaises(AttributeError):
            self.maintainer(raises=AttributeError('typo in the caller'))

    def test_missing_repository_leaves_the_free_checks_standing(self):
        self.assertTrue(self.maintainer(repository=''))

    def test_a_bot_stays_disqualified_even_when_the_lookup_is_inconclusive(self):
        self.assertFalse(self.maintainer(editor='helper[bot]', raises=self.http_error(403)))
        self.assertFalse(self.maintainer(editor='helper', editor_type='Bot',
                                         raises=self.http_error(403)))

    def test_the_submitter_stays_disqualified_when_the_lookup_is_inconclusive(self):
        self.assertFalse(self.maintainer(editor='alice', author='alice',
                                         raises=self.http_error(403)))

    # --- the access level is reported for the run log ---

    def test_reports_the_role_when_it_matches_the_permission(self):
        self.assertEqual(self.access_level(permission='write', role_name='write'), 'write')

    def test_reports_both_when_the_role_is_more_specific(self):
        self.assertEqual(self.access_level(permission='read', role_name='triage'),
                         'triage (permission: read)')

    def test_reports_a_custom_org_role_alongside_its_permission(self):
        self.assertEqual(self.access_level(permission='write', role_name='bapp-reviewer'),
                         'bapp-reviewer (permission: write)')

    def test_reports_none_for_a_non_collaborator(self):
        self.assertEqual(self.access_level(raises=self.http_error(404)), 'none')

    def test_reports_unknown_when_the_lookup_is_inconclusive(self):
        self.assertEqual(self.access_level(raises=self.http_error(403)), 'unknown')

    def test_reports_the_reason_a_lookup_was_skipped(self):
        self.assertEqual(self.access_level(editor='alice', author='alice'), 'submitter')
        self.assertEqual(self.access_level(editor='helper[bot]'), 'bot')
        self.assertEqual(self.access_level(editor=None), 'unidentified')

    def test_login_is_url_encoded_into_the_permission_endpoint(self):
        seen = {}

        def fake_api(api_url, github_token=None):
            seen['url'] = api_url
            return {'permission': 'write', 'role_name': 'write'}

        with mock.patch.object(cea, 'github_api_get', fake_api):
            cea.classify_editor('od d/name', 'alice', editor_type='User',
                                repository='o/r', github_token='t')
        self.assertIn('/collaborators/od%20d%2Fname/permission', seen['url'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
