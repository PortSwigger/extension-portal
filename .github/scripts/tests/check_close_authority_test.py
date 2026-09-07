#!/usr/bin/env python3

"""
Tests for check_close_authority.py
Run with: python check_close_authority_test.py

The GitHub API is mocked so the tests are deterministic and need no network.
"""

import sys
import unittest
from pathlib import Path
from unittest import mock
from urllib import error

# Make the script under test importable (it lives one directory up).
sys.path.insert(0, str(Path(__file__).parent.parent))

import check_close_authority as cca
import check_editor_access as cea


class ClassifyCloseTests(unittest.TestCase):
    """
    Maintainers and bots close as they see fit; every other close as Completed
    is corrected. Write access is what makes a maintainer, with the reporter's
    association standing in when GitHub will not confirm it.
    """

    def classify(self, closer='alice', author='alice', association='NONE',
                 closer_type='User', repository='PortSwigger/extension-portal',
                 permission='none', role_name=None, raises=None):
        def fake_api(api_url, github_token=None):
            if raises:
                raise raises
            return {'permission': permission,
                    'role_name': role_name if role_name is not None else permission}
        with mock.patch.object(cea, 'github_api_get', fake_api):
            return cca.classify_close(closer, author, author_association=association,
                                      closer_type=closer_type, repository=repository,
                                      github_token='t')

    def corrected(self, **kwargs):
        return self.classify(**kwargs).needs_correction

    @staticmethod
    def http_error(code):
        return error.HTTPError('https://api.github.com', code, 'boom', {}, None)

    # --- the case the guard exists for ---

    def test_reporter_closing_their_own_submission_is_corrected(self):
        self.assertTrue(self.corrected())

    def test_an_outside_contributor_is_still_a_reporter(self):
        self.assertTrue(self.corrected(association='CONTRIBUTOR'))
        self.assertTrue(self.corrected(association='FIRST_TIME_CONTRIBUTOR'))

    def test_read_only_access_does_not_earn_a_completed_close(self):
        self.assertTrue(self.corrected(permission='read', role_name='read'))


    def test_a_non_collaborator_lookup_still_corrects(self):
        self.assertTrue(self.corrected(raises=self.http_error(404)))

    # --- maintainers are left alone ---

    def test_association_alone_spares_a_maintainer(self):
        for association in ['OWNER', 'MEMBER', 'COLLABORATOR']:
            self.assertFalse(self.corrected(association=association), association)

    def test_association_is_matched_regardless_of_case(self):
        self.assertFalse(self.corrected(association='member'))

    def test_confirmed_write_access_spares_a_maintainer_the_association_missed(self):
        # Private org membership can read as CONTRIBUTOR in the payload.
        self.assertFalse(self.corrected(association='CONTRIBUTOR', permission='write'))

    def test_triage_access_earns_a_completed_close(self):
        # Deliberately granted, and it carries the run of the queue.
        self.assertTrue(cca.grants_close_authority(cea.Access('triage', 'read')))
        self.assertFalse(self.corrected(permission='read', role_name='triage'))
        self.assertFalse(self.corrected(closer='bob', author='alice',
                                        permission='read', role_name='triage'))

    def test_triage_is_not_borrowed_from_the_edit_path(self):
        # Where an edit could redirect a submission, triage is still not trusted.
        self.assertNotIn('triage', cea.WRITE_ROLES)
        self.assertIn('triage', cca.CLOSE_ROLES)

    def test_plain_read_access_does_not_earn_a_completed_close(self):
        self.assertFalse(cca.grants_close_authority(cea.Access('read', 'read')))

    def test_admin_access_spares_a_maintainer(self):
        self.assertFalse(self.corrected(permission='admin', role_name='admin'))

    def test_a_custom_org_role_falls_back_to_the_coarse_permission(self):
        self.assertFalse(self.corrected(permission='write', role_name='bapp-reviewer'))

    def test_an_association_that_settles_it_needs_no_lookup(self):
        with mock.patch.object(cea, 'github_api_get', mock.Mock(side_effect=AssertionError)):
            self.assertFalse(cca.classify_close('alice', 'alice', author_association='MEMBER',
                                                closer_type='User', repository='o/r',
                                                github_token='t').needs_correction)

    # --- closes that are not the reporter's to answer for ---

    def test_a_maintainer_closing_someone_elses_issue_is_left_alone(self):
        self.assertFalse(self.corrected(closer='bob', author='alice', permission='write'))

    def test_an_unplaceable_account_closing_someone_elses_issue_is_left_to_the_team(self):
        self.assertFalse(self.corrected(closer='bob', author='alice',
                                        raises=self.http_error(403)))

    def test_the_reporters_association_is_not_read_as_someone_elses(self):
        # author_association describes the reporter, not whoever closed it.
        self.assertTrue(self.corrected(closer='bob', author='alice', association='MEMBER',
                                       permission='read', role_name='read'))

    def test_a_bot_close_is_never_corrected(self):
        self.assertFalse(self.corrected(closer='helpful-bot', author='helpful-bot',
                                        closer_type='Bot'))
        self.assertFalse(self.corrected(closer='helpful-bot[bot]', author='helpful-bot[bot]',
                                        closer_type='User'))

    def test_missing_logins_leave_the_close_alone(self):
        self.assertFalse(self.corrected(closer=None))
        self.assertFalse(self.corrected(author=None))
        self.assertFalse(self.corrected(closer='', author=''))

    # --- an unanswerable lookup leaves the payload check standing ---

    def test_an_inconclusive_lookup_does_not_rescue_a_reporter(self):
        for failure in [self.http_error(403),
                        error.URLError('connection reset'),
                        TimeoutError('timed out')]:
            self.assertTrue(self.corrected(raises=failure), repr(failure))

    def test_an_inconclusive_lookup_does_not_override_a_maintainer_association(self):
        self.assertFalse(self.corrected(association='MEMBER', raises=self.http_error(403)))

    def test_a_missing_repository_leaves_the_association_deciding(self):
        self.assertTrue(self.corrected(repository=''))
        self.assertFalse(self.corrected(repository='', association='OWNER'))

    def test_a_programming_error_is_not_swallowed(self):
        with self.assertRaises(AttributeError):
            self.corrected(raises=AttributeError('typo in the caller'))

    # --- the reason is reported for the run log ---

    def test_reports_why_a_close_was_left_alone(self):
        self.assertEqual(self.classify(closer='bob', author='alice',
                                       raises=self.http_error(403)).basis, 'access unconfirmed')
        self.assertEqual(self.classify(closer='helper[bot]', author='helper[bot]').basis, 'bot')
        self.assertEqual(self.classify(association='MEMBER').basis, 'association: MEMBER')
        self.assertEqual(self.classify(association='CONTRIBUTOR', permission='write').basis,
                         'access: write')
        self.assertEqual(self.classify(closer=None).basis, 'unidentified')

    def test_reports_both_checks_when_correcting(self):
        self.assertEqual(self.classify(association='CONTRIBUTOR', permission='read').basis,
                         'not a maintainer (association: CONTRIBUTOR, access: read)')

    def test_reports_a_blank_association_as_none(self):
        self.assertEqual(self.classify(association='', raises=self.http_error(403)).basis,
                         'not a maintainer (association: NONE, access: unknown)')


if __name__ == '__main__':
    unittest.main(verbosity=2)
