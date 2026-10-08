#!/usr/bin/env python3

"""
Tests for report_reopen.py
Run with: python report_reopen_test.py

A card left off the review board is invisible everywhere else - the submitter
is told the reopen worked either way - so these cover when that warning is
raised, and when the team is left in peace.
"""

import sys
import unittest
from pathlib import Path

# Make the script under test importable (it lives one directory up).
sys.path.insert(0, str(Path(__file__).parent.parent))

import notification as note
import report_reopen as rr
import slack_message

ISSUE = 'https://github.com/PortSwigger/extension-portal/issues/412'
OFF_THE_BOARD = 'Could not find the project board.'


def reopen(**overrides):
    env = {'COMMAND': 'reopen', 'ISSUE_URL': ISSUE, 'ISSUE_TITLE': 'Autorize',
           'ISSUE_TYPE_NAME': 'Extension', 'JIRA_KEY': 'BAPP-1234',
           'ACTOR_LOGIN': 'alice'}
    env.update(overrides)
    return rr.outcome(rr.Reopen(env))


def resubmit(**overrides):
    return reopen(COMMAND='resubmit', **overrides)


class ReopenTests(unittest.TestCase):
    def test_a_reopen_is_announced_even_when_all_went_well(self):
        reported = reopen()
        self.assertEqual(reported.alert, 'Submission reopened: extension')
        self.assertEqual(reported.severity, note.ROUTINE)
        self.assertEqual(reported.extension, 'Autorize')
        self.assertEqual(reported.issue_url, ISSUE)

    def test_a_reopen_that_went_well_says_nothing_about_the_board(self):
        self.assertEqual((reopen().reason, reopen().action), ('', ''))

    def test_whoever_ran_it_is_credited(self):
        reported = reopen()
        self.assertEqual(reported.actor, 'alice')
        self.assertEqual(reported.actor_did, 'Reopened')

    def test_a_card_left_off_the_board_asks_for_a_person(self):
        reported = reopen(BOARD_WARNING=OFF_THE_BOARD)
        self.assertEqual(reported.alert, 'Submission reopened: extension')
        self.assertEqual(reported.severity, note.ATTENTION)
        self.assertEqual(reported.reason, OFF_THE_BOARD)
        self.assertIn('by hand', reported.action)

    def test_an_actor_the_pipeline_could_not_name_is_simply_absent(self):
        self.assertEqual(reopen(ACTOR_LOGIN='').actor, '')


class ResubmitTests(unittest.TestCase):
    def test_a_resubmission_that_went_well_is_left_to_the_pipeline_to_announce(self):
        self.assertIsNone(resubmit())

    def test_a_card_left_off_the_board_asks_for_it_by_hand(self):
        reported = resubmit(BOARD_WARNING=OFF_THE_BOARD)
        self.assertEqual(reported.alert, 'Submission reopened: extension')
        self.assertEqual(reported.severity, note.ATTENTION)
        self.assertEqual(reported.reason, OFF_THE_BOARD)
        self.assertIn('Concept review', reported.action)

    def test_the_verb_says_it_was_a_resubmission(self):
        self.assertEqual(resubmit(BOARD_WARNING=OFF_THE_BOARD).actor_did, 'Resubmitted')

    def test_an_unrecognised_command_is_treated_as_a_reopen(self):
        self.assertEqual(reopen(COMMAND='').alert, 'Submission reopened: extension')


class TicketTests(unittest.TestCase):
    def test_the_reopened_ticket_is_named(self):
        self.assertEqual(reopen().ticket, 'BAPP-1234')

    def test_it_is_named_whether_or_not_the_board_kept_up(self):
        self.assertEqual(reopen(BOARD_WARNING=OFF_THE_BOARD).ticket, 'BAPP-1234')

    def test_a_ticket_the_pipeline_could_not_move_is_simply_absent(self):
        self.assertEqual(reopen(JIRA_KEY='').ticket, '')

    def test_the_ticket_reaches_the_subtitle_and_a_button(self):
        message = slack_message.message_for(reopen(), 'https://example.atlassian.net')
        [context] = [b for b in message['blocks'] if b['type'] == 'context'
                     and b['elements'][0]['type'] == 'mrkdwn']
        self.assertIn('BAPP-1234', context['elements'][0]['text'])
        [actions] = [b for b in message['blocks'] if b['type'] == 'actions']
        self.assertIn('View Jira', [e['text']['text'] for e in actions['elements']])


class SubjectTests(unittest.TestCase):
    """The headline names what was submitted, never the issue carrying it."""

    def test_an_update_is_called_an_update(self):
        self.assertEqual(reopen(ISSUE_TYPE_NAME='Update').alert, 'Submission reopened: update')

    def test_a_submission_github_did_not_type_is_still_not_called_an_issue(self):
        self.assertEqual(reopen(ISSUE_TYPE_NAME='').alert, 'Submission reopened')

    def test_no_headline_calls_the_submission_an_issue(self):
        for reported in (reopen(), reopen(ISSUE_TYPE_NAME='Update'),
                         reopen(ISSUE_TYPE_NAME=''),
                         resubmit(BOARD_WARNING=OFF_THE_BOARD),
                         resubmit(ISSUE_TYPE_NAME='', BOARD_WARNING=OFF_THE_BOARD)):
            self.assertNotIn('issue', reported.alert.lower(), reported.alert)


class RenderingTests(unittest.TestCase):
    def test_every_notification_renders_with_a_header_and_a_way_in(self):
        for reported in (reopen(), reopen(BOARD_WARNING=OFF_THE_BOARD),
                         resubmit(BOARD_WARNING=OFF_THE_BOARD)):
            types = [b['type'] for b in slack_message.message_for(reported)['blocks']]
            self.assertEqual(types[0], 'header', reported.alert)
            self.assertEqual(types[-1], 'actions', reported.alert)

    def test_a_board_warning_shows_as_work_to_do(self):
        quiet = slack_message.message_for(reopen())
        loud = slack_message.message_for(reopen(BOARD_WARNING=OFF_THE_BOARD))
        self.assertEqual(quiet['blocks'][0], loud['blocks'][0])
        self.assertNotIn('⚠️', str(quiet['blocks']))
        self.assertIn('⚠️', str(loud['blocks']))


if __name__ == '__main__':
    unittest.main()
