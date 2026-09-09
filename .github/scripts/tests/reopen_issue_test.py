#!/usr/bin/env python3

"""
Tests for reopen_issue.py
Run with: python reopen_issue_test.py

Two callers share this script and differ only in TARGET_COLUMN, so the order
it does things in is the whole design: the card is restored before the reopen
so the board's "item reopened" automation has something to act on, and any
column change lands after the reopen so it beats that automation. Getting
either backwards silently misplaces cards.

The other rule is that the reopen is the part that matters. A board that will
not answer must not stop it, and must not be quietly reported as success.
"""

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

# Make the script under test importable (it lives one directory up).
sys.path.insert(0, str(Path(__file__).parent.parent))

import project_board as pb
import reopen_issue as ri

PROJECT = pb.Project(id='PROJ', status_field_id='FIELD',
                     status_options={'concept review': 'OPT'})


class MainHarness:
    """Drives main() with the board and the REST call stubbed out."""

    def run_main(self, item=None, column=None, project=PROJECT,
                 board_raises=None, reopen_raises=None, new_item_id='NEW'):
        steps = []

        def record(name, result=None, raises=None):
            def fake(*args, **kwargs):
                steps.append(name)
                if raises:
                    raise raises
                return result
            return fake

        env = {'PROJECT_TOKEN': 'app', 'GITHUB_TOKEN': 'gh',
               'ISSUE_NODE_ID': 'ISSUE_1', 'PROJECT_OWNER': 'PortSwigger',
               'REPOSITORY': 'PortSwigger/extension-portal', 'ISSUE_NUMBER': '7'}
        if column is not None:
            env['TARGET_COLUMN'] = column

        self.outputs = {}
        with mock.patch.dict('os.environ', env, clear=True), \
             mock.patch.object(ri, 'set_output',
                               lambda k, v: self.outputs.__setitem__(k, v)), \
             mock.patch.object(pb, 'GraphQLClient'), \
             mock.patch.object(pb, 'resolve_project',
                               side_effect=board_raises, return_value=project), \
             mock.patch.object(pb, 'find_item', return_value=item), \
             mock.patch.object(pb, 'add_item', record('add', new_item_id)), \
             mock.patch.object(pb, 'unarchive_item', record('unarchive')), \
             mock.patch.object(pb, 'set_status', record('set_status')), \
             mock.patch.object(ri, 'reopen',
                               record('reopen', raises=reopen_raises)):
            ri.main()

        return steps


class ReopenIssueTests(MainHarness, unittest.TestCase):
    # --- the ordering both callers depend on ---

    def test_an_archived_card_is_restored_before_the_reopen(self):
        self.assertEqual(self.run_main(item={'id': 'I', 'isArchived': True}),
                         ['unarchive', 'reopen'])

    def test_a_removed_card_is_re_added_before_the_reopen(self):
        self.assertEqual(self.run_main(item=None), ['add', 'reopen'])

    def test_a_column_change_lands_after_the_reopen(self):
        for item in [None,
                     {'id': 'I', 'isArchived': True},
                     {'id': 'I', 'isArchived': False}]:
            with self.subTest(item=item):
                steps = self.run_main(item=item, column='Concept review')
                self.assertEqual(steps[-1], 'set_status')
                self.assertLess(steps.index('reopen'), steps.index('set_status'))

    # --- /reopen leaves placement to the board ---

    def test_without_a_column_the_status_is_never_touched(self):
        for item in [None,
                     {'id': 'I', 'isArchived': True},
                     {'id': 'I', 'isArchived': False}]:
            with self.subTest(item=item):
                self.assertNotIn('set_status', self.run_main(item=item))

    def test_an_empty_column_counts_as_no_column(self):
        self.assertNotIn('set_status', self.run_main(item=None, column='  '))

    def test_a_live_card_is_only_reopened(self):
        self.assertEqual(self.run_main(item={'id': 'I', 'isArchived': False}),
                         ['reopen'])

    # --- the reopen happens regardless of the board ---

    def test_an_unreachable_board_still_reopens(self):
        for failure in [pb.GraphQLError('rate limited'),
                        OSError('connection reset'),
                        TimeoutError('timed out'),
                        ValueError('not json')]:
            with self.subTest(failure=repr(failure)):
                self.assertEqual(self.run_main(board_raises=failure), ['reopen'])

    def test_an_invisible_project_still_reopens(self):
        self.assertEqual(self.run_main(project=None), ['reopen'])

    def test_an_invisible_project_skips_the_column_rather_than_crashing(self):
        self.assertEqual(self.run_main(project=None, column='Concept review'),
                         ['reopen'])

    def test_a_renamed_column_does_not_undo_the_reopen(self):
        self.assertEqual(self.run_main(item=None, column='Nonexistent'),
                         ['add', 'reopen'])

    # --- but a failed reopen is a failed step ---

    def test_a_failed_reopen_is_not_swallowed(self):
        with self.assertRaises(OSError):
            self.run_main(item=None, reopen_raises=OSError('502'))

    def test_a_programming_error_is_not_swallowed(self):
        with self.assertRaises(AttributeError):
            self.run_main(board_raises=AttributeError('typo in the caller'))


class BoardWarningTests(MainHarness, unittest.TestCase):
    """What the team is told when the reopen worked but the board did not.

    The submitter is told the issue is reopened, which is true, so a board
    left in the wrong state is invisible unless it is reported here.
    """

    def warning(self, **kwargs):
        self.run_main(**kwargs)
        return self.outputs.get('board_warning')

    def test_a_clean_run_reports_nothing(self):
        for item in [None,
                     {'id': 'I', 'isArchived': True},
                     {'id': 'I', 'isArchived': False}]:
            with self.subTest(item=item):
                self.assertEqual(self.warning(item=item), '')
                self.assertEqual(
                    self.warning(item=item, column='Concept review'), '')

    def test_an_unreachable_board_is_reported(self):
        for failure in [pb.GraphQLError('rate limited'),
                        OSError('connection reset'),
                        TimeoutError('timed out')]:
            with self.subTest(failure=repr(failure)):
                self.assertIn('Unable to restore',
                              self.warning(board_raises=failure))

    def test_an_invisible_project_is_reported(self):
        self.assertIn('not visible', self.warning(project=None))

    def test_a_renamed_column_is_reported(self):
        self.assertIn('not found',
                      self.warning(item=None, column='Nonexistent'))

    def test_a_card_the_board_would_not_name_is_reported(self):
        # add_item can come back without an item id; the column change is then
        # skipped, and silence would leave the card wherever it landed.
        self.assertIn('did not say which card',
                      self.warning(item=None, new_item_id=None,
                                   column='Concept review'))

    def test_the_warning_is_always_set_even_when_empty(self):
        self.run_main(item=None)
        self.assertIn('board_warning', self.outputs)


class ReopenRequestTests(unittest.TestCase):
    """The REST call itself, which is the part that must not fail silently."""

    def send(self, status_ok=True):
        response = mock.MagicMock()
        response.read.return_value = b'{}'
        response.__enter__.return_value = response
        with mock.patch.object(ri.request, 'urlopen',
                               return_value=response) as urlopen:
            ri.reopen('PortSwigger/extension-portal', '7', 'gh-token')
        return urlopen.call_args

    def test_patches_the_issue_to_open(self):
        call = self.send()
        sent = call.args[0]
        self.assertEqual(sent.full_url,
                         'https://api.github.com/repos/PortSwigger/'
                         'extension-portal/issues/7')
        self.assertEqual(sent.get_method(), 'PATCH')
        self.assertEqual(json.loads(sent.data), {'state': 'open'})

    def test_authenticates_and_sets_a_timeout(self):
        call = self.send()
        self.assertEqual(call.args[0].get_header('Authorization'), 'token gh-token')
        self.assertEqual(call.kwargs['timeout'], ri.HTTP_TIMEOUT_SECONDS)


if __name__ == '__main__':
    unittest.main(verbosity=2)
