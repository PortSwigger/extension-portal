#!/usr/bin/env python3

"""
Tests for report_submission.py
Run with: python report_submission_test.py

This is the team's only account of what the pipeline did with a submission, so
what matters is that each outcome is distinguishable from the others, that the
ones needing a person say so in their severity, and that an extension and an
update are told apart.
"""

import sys
import unittest
from pathlib import Path

# Make the script under test importable (it lives one directory up).
sys.path.insert(0, str(Path(__file__).parent.parent))

import notification as note
import report_submission as rs
import slack_message

ISSUE = 'https://github.com/PortSwigger/extension-portal/issues/412'
PR = 'https://github.com/PortSwigger/autorize/pull/7'


def submission(**overrides):
    env = {
        'SUBMISSION_TYPE': 'extension-submission',
        'ISSUE_URL': ISSUE,
        'TITLE': 'Autorize',
        'VERSION_NUMBER': '1.0.0',
        'SUBMITTER_LOGIN': 'carol',
        'JIRA_KEY': 'BAPP-1234',
        'REVIEW_OUTCOME': 'success',
    }
    env.update(overrides)
    return rs.outcome(rs.Submission(env))


def update(**overrides):
    env = {'SUBMISSION_TYPE': 'extension-update', 'PR_URL': PR,
           'VERSION_NUMBER': '1.2.3', 'STATUS': 'automated'}
    env.update(overrides)
    return submission(**env)


class ExtensionTests(unittest.TestCase):
    def test_a_clean_submission_names_its_ticket_and_asks_for_nothing(self):
        reported = submission()
        self.assertEqual(reported.event, note.SUBMITTED)
        self.assertEqual(reported.severity, note.ROUTINE)
        self.assertEqual(reported.ticket, 'BAPP-1234')
        self.assertEqual((reported.reason, reported.action), ('', ''))

    def test_a_ticket_that_was_not_created_is_not_passed_off_as_success(self):
        reported = submission(JIRA_KEY='')
        self.assertEqual(reported.event, note.FAILED)
        self.assertEqual(reported.severity, note.FAILURE)
        self.assertIn('could not be created', reported.reason)
        self.assertIn('Raise it by hand', reported.action)

    def test_the_submission_is_identified(self):
        reported = submission()
        self.assertEqual(reported.extension, 'Autorize')
        self.assertEqual(reported.version, '1.0.0')
        self.assertEqual(reported.issue_url, ISSUE)

    def test_the_submitter_is_credited(self):
        reported = submission()
        self.assertEqual(reported.actor, 'carol')
        self.assertEqual(reported.actor_did, 'Submitted')

    def test_no_pull_request_is_reported_for_a_new_extension(self):
        self.assertEqual(submission(PR_URL=PR).pr_url, '')


class ReviewTests(unittest.TestCase):
    """A review that fails to start is the whole reason to look at the message."""

    def test_a_review_that_started_is_not_worth_a_line(self):
        for reported in (submission(), update()):
            self.assertEqual(reported.reason, '', reported.alert)
            self.assertEqual(reported.severity, note.ROUTINE)

    def test_a_review_that_did_not_start_asks_for_a_person(self):
        for reported in (submission(REVIEW_OUTCOME='failure'),
                         update(REVIEW_OUTCOME='failure')):
            self.assertIn('not triggered', reported.reason.lower(), reported.alert)
            self.assertEqual(reported.severity, note.ATTENTION, reported.alert)

    def test_an_extension_is_not_quieter_about_it_than_an_update(self):
        self.assertEqual(submission(REVIEW_OUTCOME='failure').reason,
                         update(REVIEW_OUTCOME='failure').reason)


class UpdateTests(unittest.TestCase):
    def test_an_automated_update_names_its_subtask(self):
        reported = update()
        self.assertEqual(reported.alert, 'New submission: update')
        self.assertEqual(reported.ticket, 'BAPP-1234')

    def test_an_unmatched_parent_says_why_and_leaves_the_rest_to_the_headline(self):
        reported = update(STATUS='manual', REASON='Two parents matched.')
        self.assertEqual(reported.event, note.FAILED)
        self.assertEqual(reported.severity, note.ATTENTION)
        self.assertEqual(reported.reason, 'Two parents matched.')
        self.assertIn('Create the update ticket', reported.action)

    def test_an_unmatched_parent_with_no_reason_still_says_something(self):
        self.assertIn('No single parent ticket', update(STATUS='manual').reason)

    def test_the_pull_request_is_reported(self):
        self.assertEqual(update().pr_url, PR)


class RejectionTests(unittest.TestCase):
    """The three ways a submission goes wrong read the same for both forms."""

    def test_a_duplicate_points_at_what_it_duplicates(self):
        for reported in (submission(ORIGINAL_ISSUE_URL='https://x/1'),
                         update(ORIGINAL_ISSUE_URL='https://x/1')):
            self.assertEqual(reported.event, note.FAILED)
            self.assertIn('already been submitted', reported.reason)
            self.assertEqual(reported.duplicate_url, 'https://x/1')
            self.assertEqual(reported.severity, note.ROUTINE)

    def test_a_failed_check_is_reported_as_a_failure(self):
        for reported, alert in ((submission(VALIDATION_ERROR='Not a repository.'),
                                 'Submission failed: extension'),
                                (update(VALIDATION_ERROR='Not a repository.'),
                                 'Submission failed: update')):
            self.assertEqual(reported.alert, alert)
            self.assertEqual(reported.severity, note.ROUTINE)
            self.assertEqual(reported.reason, 'Not a repository.')

    def test_an_extension_already_ticketed_asks_for_the_link_by_hand(self):
        reported = submission(PRIOR_TICKET='BAPP-9')
        self.assertEqual(reported.event, note.FAILED)
        self.assertEqual(reported.ticket, 'BAPP-9')
        self.assertIn('extension', reported.reason)
        self.assertIn('Link it', reported.action)

    def test_an_update_already_ticketed_says_update_not_extension(self):
        self.assertIn('update', update(PRIOR_TICKET='BAPP-9').reason)

    def test_a_duplicate_outranks_everything_else(self):
        reported = submission(ORIGINAL_ISSUE_URL='https://x/1',
                              VALIDATION_ERROR='Not a repository.', PRIOR_TICKET='BAPP-9')
        self.assertIn('already been submitted', reported.reason)
        self.assertEqual(reported.duplicate_url, 'https://x/1')

    def test_a_failed_check_outranks_a_prior_ticket(self):
        reported = submission(VALIDATION_ERROR='Not a repository.', PRIOR_TICKET='BAPP-9')
        self.assertEqual(reported.reason, 'Not a repository.')
        self.assertEqual(reported.action, '')

    def test_a_rejected_submission_never_claims_a_ticket_was_made(self):
        for reported in (submission(ORIGINAL_ISSUE_URL='https://x/1'),
                         submission(VALIDATION_ERROR='Not a repository.')):
            self.assertEqual(reported.ticket, '')


class RenderingTests(unittest.TestCase):
    """Every outcome has to survive the renderer, so it is exercised here."""

    EVERY_OUTCOME = None

    def setUp(self):
        self.EVERY_OUTCOME = [
            submission(), submission(JIRA_KEY=''), submission(REVIEW_OUTCOME='failure'),
            update(), update(REVIEW_OUTCOME='failure'),
            update(STATUS='manual', REASON='Two parents matched.'),
            submission(ORIGINAL_ISSUE_URL='https://x/1'),
            submission(VALIDATION_ERROR='Not a repository.'),
            update(PRIOR_TICKET='BAPP-9'),
        ]

    def test_the_headline_reaches_the_slack_header(self):
        blocks = slack_message.message_for(submission())['blocks']
        self.assertIn('New submission: extension', blocks[0]['text']['text'])

    def test_a_failure_reads_as_one_once_rendered(self):
        message = slack_message.message_for(submission(JIRA_KEY=''))
        self.assertIn('Submission failed', message['blocks'][0]['text']['text'])
        self.assertIn('🚨', str(message['blocks']))

    def test_every_outcome_renders_with_a_header_and_a_way_in(self):
        for reported in self.EVERY_OUTCOME:
            types = [b['type'] for b in slack_message.message_for(reported)['blocks']]
            self.assertEqual(types[0], 'header', reported.alert)
            self.assertEqual(types[-1], 'actions', reported.alert)

    def test_no_headline_calls_the_submission_an_issue(self):
        for reported in self.EVERY_OUTCOME:
            self.assertNotIn('issue', reported.alert.lower(), reported.alert)


if __name__ == '__main__':
    unittest.main()
