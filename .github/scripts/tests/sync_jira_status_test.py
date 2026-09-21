#!/usr/bin/env python3

"""
Tests for sync_jira_status.py
Run with: python sync_jira_status_test.py

Jira is mocked so the tests are deterministic and need no network.
"""

import base64
import io
import json
import sys
import unittest
from pathlib import Path
from urllib import error

# Make the script under test importable (it lives one directory up).
sys.path.insert(0, str(Path(__file__).parent.parent))

import jira
import sync_jira_status as sjs

ISSUE_URL = 'https://github.com/PortSwigger/extension-portal/issues/42'

OPEN_STATUS = '11026'
LATER_OPEN_STATUS = '11027'

RESOLUTION_SCREEN = {'resolution': {'required': True},
                     'customfield_12030': {'required': False}}

FROM_OPEN = [
    {'id': '7', 'to': {'id': jira.REJECTED_STATUS},
     'fields': {}},
    {'id': '151', 'to': {'id': jira.APPROVED_STATUS},
     'fields': {}},
]
FROM_LATER_OPEN = [
    {'id': '8', 'to': {'id': jira.REJECTED_STATUS},
     'fields': {}},
]
FROM_REOPENED = [
    {'id': '171', 'to': {'id': jira.REJECTED_STATUS},
     'fields': RESOLUTION_SCREEN},
    {'id': '121', 'to': {'id': OPEN_STATUS}, 'fields': {}},
]
FROM_SUBTASK_OPEN = [
    {'id': '4', 'to': {'id': jira.REJECTED_STATUS},
     'fields': RESOLUTION_SCREEN},
]
FROM_CLOSED = [
    {'id': '161', 'to': {'id': jira.FEEDBACK_STATUS},
     'fields': {}},
]
FROM_SUBTASK_CLOSED = [
    {'id': '2', 'to': {'id': jira.FEEDBACK_STATUS},
     'fields': {}},
]
FROM_APPROVED = [
    {'id': '5', 'to': {'id': jira.FEEDBACK_STATUS},
     'fields': {}},
]


class FakeJira(jira.JiraClient):
    """
    Stands in for Jira at the HTTP boundary only, so that the JQL building, the
    exact-match filtering in find_by_url_field and the transition lookup all stay
    under test.
    """

    def __init__(self, tickets=None, transitions=None, search_error=None,
                 transition_error=None, tickets_are_type=jira.SUBMISSION_ISSUE_TYPE):
        self.tickets = tickets if tickets is not None else []
        self._transitions = transitions if transitions is not None else []
        self.search_error = search_error
        self.transition_error = transition_error
        self.tickets_are_type = tickets_are_type
        self.searches = []
        self.sent = []

    def search(self, jql, fields):
        self.searches.append(jql)
        if self.search_error:
            raise self.search_error
        if f'issuetype = {self.tickets_are_type}' not in jql:
            return {'issues': []}
        return {'issues': self.tickets}

    def _send(self, method, path, payload=None):
        self.sent.append((method, path, payload))
        if method == 'GET':
            return {'transitions': self._transitions}
        if self.transition_error:
            raise self.transition_error
        return {}

    @property
    def posts(self):
        return [(path, payload) for method, path, payload in self.sent
                if method == 'POST']


def http_error(code, body=b''):
    return error.HTTPError('https://jira', code, 'boom', {}, io.BytesIO(body))


OPEN_STATUS = OPEN_STATUS
LATER_OPEN_STATUS = LATER_OPEN_STATUS


def ticket(key='BAPP-100', status_id=jira.REJECTED_STATUS, issue_url=ISSUE_URL):
    return {'key': key,
            'fields': {'summary': 'Widget',
                       'status': {'id': status_id},
                       jira.GITHUB_ISSUE_FIELD: issue_url}}


def change(**overrides):
    defaults = {
        'ISSUE_URL': ISSUE_URL,
        'ISSUE_ACTION': 'closed',
        'STATE_REASON': 'not_planned',
        'ISSUE_TYPE_NAME': 'Extension',
        'ISSUE_TITLE': 'Widget',
        'ACTOR_LOGIN': 'alice',
    }
    defaults.update(overrides)
    return sjs.StateChange.from_environment(defaults)


class StateChangeTests(unittest.TestCase):
    def test_an_update_issue_looks_for_the_subtask_type(self):
        self.assertEqual(change(ISSUE_TYPE_NAME='Update').ticket_issue_types,
                         (jira.UPDATE_SUBTASK_ISSUE_TYPE,))

    def test_a_submission_issue_looks_for_the_submission_type(self):
        self.assertEqual(change().ticket_issue_types,
                         (jira.SUBMISSION_ISSUE_TYPE,))

    def test_an_issue_whose_type_github_dropped_looks_for_both(self):
        self.assertEqual(change(ISSUE_TYPE_NAME='').ticket_issue_types,
                         (jira.SUBMISSION_ISSUE_TYPE, jira.UPDATE_SUBTASK_ISSUE_TYPE))

    def test_a_reopen_is_recognised_whatever_its_case(self):
        self.assertTrue(change(ISSUE_ACTION='Reopened').reopens_the_submission)

    def test_every_close_reason_but_completed_parks_the_submission(self):
        for reason in ('not_planned', 'duplicate', ''):
            self.assertTrue(change(STATE_REASON=reason).parks_the_submission, reason)

    def test_a_close_as_completed_does_not_park_the_submission(self):
        self.assertFalse(change(STATE_REASON='completed').parks_the_submission)

    def test_a_reopen_never_counts_as_parking(self):
        self.assertFalse(change(ISSUE_ACTION='reopened').parks_the_submission)

    def test_a_missing_actor_is_named_rather_than_left_blank(self):
        self.assertEqual(change(ACTOR_LOGIN='').actor, '(unknown)')


class CloseTests(unittest.TestCase):
    def test_a_submission_in_concept_review_is_closed_to_rejected(self):
        client = FakeJira([ticket(status_id=OPEN_STATUS)], FROM_OPEN)
        outcome = sjs.sync(client, change())

        self.assertEqual(outcome.status, 'moved')
        self.assertEqual(outcome.ticket_key, 'BAPP-100')
        self.assertEqual(outcome.moved_to, jira.REJECTED_STATUS)

    def test_a_close_that_screens_for_a_resolution_records_declined(self):
        client = FakeJira([ticket(status_id=jira.FEEDBACK_STATUS)], FROM_REOPENED)
        sjs.sync(client, change())

        path, payload = client.posts[0]
        self.assertEqual(path, '/rest/api/3/issue/BAPP-100/transitions')
        self.assertEqual(payload, {'transition': {'id': '171'},
                                   'fields': {'resolution': {
                                       'id': jira.DECLINED_RESOLUTION}}})

    def test_a_close_with_no_screen_sends_no_resolution(self):
        for transitions, expected_id in ((FROM_OPEN, '7'),
                                         (FROM_LATER_OPEN, '8')):
            client = FakeJira([ticket(status_id=OPEN_STATUS)], transitions)
            outcome = sjs.sync(client, change())

            self.assertEqual(outcome.status, 'moved')
            _, payload = client.posts[0]
            self.assertEqual(payload, {'transition': {'id': expected_id}})

    def test_an_update_subtask_close_records_the_resolution_it_screens_for(self):
        client = FakeJira([ticket(status_id=LATER_OPEN_STATUS)], FROM_SUBTASK_OPEN,
                          tickets_are_type=jira.UPDATE_SUBTASK_ISSUE_TYPE)
        sjs.sync(client, change(ISSUE_TYPE_NAME='Update'))

        _, payload = client.posts[0]
        self.assertEqual(payload, {'transition': {'id': '4'},
                                   'fields': {'resolution': {
                                       'id': jira.DECLINED_RESOLUTION}}})

    def test_the_transition_id_comes_from_the_ticket_not_a_constant(self):
        client = FakeJira([ticket(status_id=LATER_OPEN_STATUS)], FROM_LATER_OPEN)
        sjs.sync(client, change())

        _, payload = client.posts[0]
        self.assertEqual(payload['transition']['id'], '8')

    def test_a_ticket_already_rejected_is_left_alone(self):
        client = FakeJira([ticket(status_id=jira.REJECTED_STATUS)], [])
        outcome = sjs.sync(client, change())

        self.assertEqual(outcome.status, 'unchanged')
        self.assertEqual(client.posts, [])

    def test_an_approved_submission_is_left_alone(self):
        client = FakeJira([ticket(status_id=jira.APPROVED_STATUS)], FROM_APPROVED)
        outcome = sjs.sync(client, change())

        self.assertEqual(outcome.status, 'skipped')
        self.assertEqual(client.posts, [])

    def test_a_close_as_completed_does_not_even_look_for_a_ticket(self):
        client = FakeJira([ticket(status_id=OPEN_STATUS)], FROM_OPEN)
        outcome = sjs.sync(client, change(STATE_REASON='completed'))

        self.assertEqual(outcome.status, 'skipped')
        self.assertEqual(client.searches, [])

    def test_a_submission_with_no_ticket_yet_passes_quietly(self):
        outcome = sjs.sync(FakeJira([]), change())

        self.assertEqual(outcome.status, 'absent')
        self.assertIsNone(sjs.zoom_payload(change(), outcome))


class ReopenTests(unittest.TestCase):
    def test_a_rejected_submission_comes_back_to_feedback(self):
        client = FakeJira([ticket(status_id=jira.REJECTED_STATUS)],
                          FROM_CLOSED)
        outcome = sjs.sync(client, change(ISSUE_ACTION='reopened'))

        self.assertEqual(outcome.status, 'moved')
        self.assertEqual(outcome.moved_to, jira.FEEDBACK_STATUS)

    def test_the_reopen_records_no_resolution(self):
        client = FakeJira([ticket(status_id=jira.REJECTED_STATUS)],
                          FROM_CLOSED)
        sjs.sync(client, change(ISSUE_ACTION='reopened'))

        _, payload = client.posts[0]
        self.assertEqual(payload, {'transition': {'id': '161'}})

    def test_an_update_subtask_uses_its_own_workflows_reopen_id(self):
        client = FakeJira([ticket(status_id=jira.REJECTED_STATUS)],
                          FROM_SUBTASK_CLOSED,
                          tickets_are_type=jira.UPDATE_SUBTASK_ISSUE_TYPE)
        sjs.sync(client, change(ISSUE_ACTION='reopened', ISSUE_TYPE_NAME='Update'))

        _, payload = client.posts[0]
        self.assertEqual(payload['transition']['id'], '2')

    def test_a_ticket_still_in_the_queue_is_left_alone(self):
        for status_id in (OPEN_STATUS, LATER_OPEN_STATUS, jira.FEEDBACK_STATUS):
            client = FakeJira([ticket(status_id=status_id)], [])
            outcome = sjs.sync(client, change(ISSUE_ACTION='reopened'))

            self.assertEqual(outcome.status, 'unchanged', status_id)
            self.assertEqual(client.posts, [])

    def test_reopening_an_approved_submission_is_flagged_not_undone(self):
        client = FakeJira([ticket(status_id=jira.APPROVED_STATUS)], FROM_APPROVED)
        outcome = sjs.sync(client, change(ISSUE_ACTION='reopened'))

        self.assertEqual(outcome.status, 'flagged')
        self.assertEqual(client.posts, [])


class FailureTests(unittest.TestCase):
    def test_a_failed_search_asks_for_a_person(self):
        outcome = sjs.sync(FakeJira(search_error=http_error(503)), change())

        self.assertEqual(outcome.status, 'manual')
        self.assertIn('503', outcome.reason)

    def test_two_tickets_for_one_issue_ask_for_a_person(self):
        client = FakeJira([ticket('BAPP-1'), ticket('BAPP-2')])
        outcome = sjs.sync(client, change())

        self.assertEqual(outcome.status, 'manual')
        self.assertIn('BAPP-1, BAPP-2', outcome.reason)

    def test_a_workflow_with_no_way_to_the_target_asks_for_a_person(self):
        client = FakeJira([ticket(status_id=OPEN_STATUS)],
                          [{'id': '151', 'name': 'Direct approval',
                            'to': {'id': jira.APPROVED_STATUS}}])
        outcome = sjs.sync(client, change())

        self.assertEqual(outcome.status, 'manual')
        self.assertIn('BAPP-100', outcome.reason)
        self.assertEqual(client.posts, [])

    def test_a_rejected_transition_asks_for_a_person(self):
        client = FakeJira([ticket(status_id=OPEN_STATUS)], FROM_OPEN,
                          transition_error=http_error(400, b'resolution required'))
        outcome = sjs.sync(client, change())

        self.assertEqual(outcome.status, 'manual')
        self.assertIn('400', outcome.reason)
        self.assertIn('resolution required', outcome.reason)

    def test_an_unexpected_error_is_caught_rather_than_failing_the_run(self):
        class Exploding(FakeJira):
            def search(self, jql, fields):
                raise RuntimeError('boom')

        outcome = sjs.sync(Exploding(), change())
        self.assertEqual(outcome.status, 'manual')
        self.assertIn('boom', outcome.reason)


class DecisionTests(unittest.TestCase):
    def close(self, status_id):
        return sjs.decide(change(), status_id)

    def reopen(self, status_id):
        return sjs.decide(change(ISSUE_ACTION='reopened'), status_id)

    def test_a_close_parks_a_live_ticket_and_records_declined(self):
        decision = self.close(OPEN_STATUS)
        self.assertEqual(decision.move_to, jira.REJECTED_STATUS)
        self.assertEqual(decision.fields, sjs.DECLINED)

    def test_a_close_leaves_a_parked_ticket_where_it_is(self):
        self.assertFalse(self.close(jira.REJECTED_STATUS).moves)

    def test_a_close_leaves_an_approved_ticket_where_it_is(self):
        self.assertEqual(self.close(jira.APPROVED_STATUS).outcome, 'skipped')

    def test_a_reopen_returns_a_parked_ticket_to_feedback_with_no_fields(self):
        decision = self.reopen(jira.REJECTED_STATUS)
        self.assertEqual(decision.move_to, jira.FEEDBACK_STATUS)
        self.assertIsNone(decision.fields)

    def test_a_reopen_leaves_a_live_ticket_where_it_is(self):
        self.assertEqual(self.reopen(LATER_OPEN_STATUS).outcome, 'unchanged')

    def test_a_reopen_refuses_to_undo_an_approval(self):
        self.assertEqual(self.reopen(jira.APPROVED_STATUS).outcome, 'flagged')

    def test_every_standstill_says_why(self):
        for decision in (self.close(jira.REJECTED_STATUS),
                         self.close(jira.APPROVED_STATUS),
                         self.reopen(LATER_OPEN_STATUS),
                         self.reopen(jira.APPROVED_STATUS)):
            self.assertTrue(decision.because, decision)


class ReportingTests(unittest.TestCase):
    def payload(self, outcome, **overrides):
        return sjs.zoom_payload(change(**overrides), outcome)

    def test_a_move_that_worked_is_not_reported(self):
        self.assertIsNone(self.payload(sjs.Outcome('moved', ticket_key='BAPP-1')))

    def test_a_ticket_already_in_place_is_not_reported(self):
        self.assertIsNone(self.payload(sjs.Outcome('unchanged', ticket_key='BAPP-1')))

    def test_a_completed_close_is_not_reported(self):
        self.assertIsNone(self.payload(sjs.Outcome('skipped')))

    def test_a_move_that_failed_names_the_status_to_set_by_hand(self):
        payload = self.payload(sjs.Outcome('manual', ticket_key='BAPP-1',
                                           reason='Jira said no.',
))
        self.assertIn('out of the review queue', payload['Action'])
        self.assertEqual(payload['Ticket'], 'BAPP-1 (unchanged)')
        self.assertEqual(payload['Closed by'], 'alice')
        self.assertEqual(payload['Reason'], 'Jira said no.')

    def test_a_failed_reopen_names_feedback_instead(self):
        payload = self.payload(sjs.Outcome('manual', ticket_key='BAPP-1',
                                           reason='Jira said no.'),
                               ISSUE_ACTION='reopened')
        self.assertIn('back into the review queue', payload['Action'])
        self.assertEqual(payload['Reopened by'], 'alice')

    def test_a_failure_before_the_ticket_was_found_names_no_ticket(self):
        payload = self.payload(sjs.Outcome('manual', reason='Search failed.'))
        self.assertNotIn('Ticket', payload)

    def test_reopening_an_approved_submission_is_reported(self):
        payload = self.payload(sjs.Outcome('flagged', ticket_key='BAPP-1',
),
                               ISSUE_ACTION='reopened')
        self.assertEqual(payload['Alert'], 'Approved submission was reopened')
        self.assertEqual(payload['Ticket'], 'BAPP-1 (unchanged)')

    def test_the_payload_survives_the_round_trip_through_base64(self):
        payload = self.payload(sjs.Outcome('manual', reason='Search failed.'))
        decoded = json.loads(base64.b64decode(sjs.encode_payload(payload)))
        self.assertEqual(decoded, payload)

    def test_no_issue_content_is_quoted_back_beyond_its_title_and_url(self):
        payload = self.payload(sjs.Outcome('manual', reason='Search failed.'))
        self.assertEqual(payload['Extension'], 'Widget')
        self.assertEqual(payload['Issue'], ISSUE_URL)


class TicketLookupTests(unittest.TestCase):
    def test_the_search_asks_for_the_status_it_decides_on(self):
        client = FakeJira([ticket(status_id=OPEN_STATUS)], FROM_OPEN)
        sjs.sync(client, change())
        self.assertIn('cf[13486]', client.searches[0])

    def test_an_untyped_issue_searches_both_types_before_giving_up(self):
        client = FakeJira([])
        outcome = sjs.sync(client, change(ISSUE_TYPE_NAME=''))

        self.assertEqual(outcome.status, 'absent')
        self.assertEqual(len(client.searches), 2)
        self.assertIn(f'issuetype = {jira.SUBMISSION_ISSUE_TYPE}', client.searches[0])
        self.assertIn(f'issuetype = {jira.UPDATE_SUBTASK_ISSUE_TYPE}', client.searches[1])

    def test_a_typed_issue_searches_only_its_own_type(self):
        client = FakeJira([ticket(status_id=OPEN_STATUS)], FROM_OPEN)
        sjs.sync(client, change())
        self.assertEqual(len(client.searches), 1)

    def test_an_untyped_issue_is_moved_once_found_under_either_type(self):
        client = FakeJira([ticket(status_id=OPEN_STATUS)], FROM_OPEN)
        outcome = sjs.sync(client, change(ISSUE_TYPE_NAME=''))

        self.assertEqual(outcome.status, 'moved')
        self.assertEqual(len(client.searches), 2)

    def test_an_untyped_update_is_found_under_the_subtask_type(self):
        client = FakeJira([ticket(status_id=jira.REJECTED_STATUS)],
                          FROM_SUBTASK_CLOSED,
                          tickets_are_type=jira.UPDATE_SUBTASK_ISSUE_TYPE)
        outcome = sjs.sync(client, change(ISSUE_ACTION='reopened',
                                          ISSUE_TYPE_NAME=''))

        self.assertEqual(outcome.status, 'moved')
        self.assertEqual(outcome.moved_to, jira.FEEDBACK_STATUS)

    def test_a_loose_match_on_another_issue_is_not_treated_as_the_ticket(self):
        client = FakeJira([ticket(issue_url=ISSUE_URL + '0')])
        outcome = sjs.sync(client, change())
        self.assertEqual(outcome.status, 'absent')


if __name__ == '__main__':
    unittest.main(verbosity=2)
