#!/usr/bin/env python3

"""
Tests for jira.py
Run with: python jira_test.py

Jira is mocked so the tests are deterministic and need no network.
"""

import sys
import unittest
from pathlib import Path
from urllib import error

# Make the script under test importable (it lives one directory up).
sys.path.insert(0, str(Path(__file__).parent.parent))

import jira


class RecordingClient(jira.JiraClient):
    """Stands in for Jira at the HTTP boundary only."""

    def __init__(self, responses=None, error_by_operator=None, transitions=None):
        self.responses = responses if responses is not None else []
        self.error_by_operator = error_by_operator or {}
        self.transitions_offered = transitions if transitions is not None else []
        self.searches = []
        self.sent = []

    def search(self, jql, fields):
        operator = '~' if ' ~ ' in jql else '='
        self.searches.append((operator, jql))
        if operator in self.error_by_operator:
            raise self.error_by_operator[operator]
        return {'issues': self.responses}

    def _send(self, method, path, payload=None):
        self.sent.append((method, path, payload))
        if method == 'GET':
            return {'transitions': self.transitions_offered}
        return {'key': 'BAPP-1'}


def http_error(code):
    return error.HTTPError('https://jira', code, 'boom', {}, None)


def ticket(key, url):
    return {'key': key, 'fields': {jira.BAPP_URL_FIELD: url}}


class JqlTests(unittest.TestCase):
    def test_field_reference_drops_the_customfield_prefix(self):
        self.assertEqual(jira.jql_field('customfield_10932'), 'cf[10932]')
        self.assertEqual(jira.jql_field('customfield_13486'), 'cf[13486]')

    def test_escaping_quotes_and_backslashes(self):
        self.assertEqual(jira.escape_jql(r'a"b\c'), r'a\"b\\c')

    def test_escaping_tolerates_empty_input(self):
        self.assertEqual(jira.escape_jql(None), '')


class FindByUrlFieldTests(unittest.TestCase):
    URL = 'https://github.com/acme/widget'

    def test_prefers_the_contains_operator(self):
        client = RecordingClient([ticket('BAPP-1', self.URL)])
        client.find_by_url_field(jira.SUBMISSION_ISSUE_TYPE, jira.BAPP_URL_FIELD,
                                 self.URL, [jira.BAPP_URL_FIELD])
        self.assertEqual([operator for operator, _ in client.searches], ['~'])

    def test_falls_back_to_exact_match_when_contains_is_rejected(self):
        client = RecordingClient([ticket('BAPP-1', self.URL)],
                                 error_by_operator={'~': http_error(400)})
        matches = client.find_by_url_field(jira.SUBMISSION_ISSUE_TYPE, jira.BAPP_URL_FIELD,
                                           self.URL, [jira.BAPP_URL_FIELD])
        self.assertEqual([operator for operator, _ in client.searches], ['~', '='])
        self.assertEqual(len(matches), 1)

    def test_other_search_errors_propagate(self):
        client = RecordingClient(error_by_operator={'~': http_error(503)})
        with self.assertRaises(error.HTTPError):
            client.find_by_url_field(jira.SUBMISSION_ISSUE_TYPE, jira.BAPP_URL_FIELD,
                                     self.URL, [jira.BAPP_URL_FIELD])

    def test_discards_loose_matches_on_a_different_url(self):
        client = RecordingClient([ticket('BAPP-1', self.URL + '-pro')])
        matches = client.find_by_url_field(jira.SUBMISSION_ISSUE_TYPE, jira.BAPP_URL_FIELD,
                                           self.URL, [jira.BAPP_URL_FIELD])
        self.assertEqual(matches, [])

    def test_keeps_matches_differing_only_in_formatting(self):
        client = RecordingClient([ticket('BAPP-1', 'https://github.com/Acme/Widget.git/')])
        matches = client.find_by_url_field(jira.SUBMISSION_ISSUE_TYPE, jira.BAPP_URL_FIELD,
                                           self.URL, [jira.BAPP_URL_FIELD])
        self.assertEqual(len(matches), 1)

    def test_the_query_names_the_project_issue_type_and_field(self):
        client = RecordingClient()
        client.find_by_url_field('10278', jira.GITHUB_ISSUE_FIELD, self.URL, [])
        _, jql = client.searches[0]
        self.assertIn('project = BAPP', jql)
        self.assertIn('issuetype = 10278', jql)
        self.assertIn('cf[13486]', jql)

    def test_the_url_is_escaped_into_the_query(self):
        client = RecordingClient()
        client.find_by_url_field('10278', jira.GITHUB_ISSUE_FIELD, 'a"b', [])
        _, jql = client.searches[0]
        self.assertIn(r'\"', jql)


class RequestTests(unittest.TestCase):
    def test_create_issue_returns_the_new_key(self):
        client = RecordingClient()
        self.assertEqual(client.create_issue({'summary': 'x'}), 'BAPP-1')
        method, path, payload = client.sent[0]
        self.assertEqual((method, path), ('POST', '/rest/api/3/issue'))
        self.assertEqual(payload, {'fields': {'summary': 'x'}})

    def test_update_issue_targets_the_key(self):
        client = RecordingClient()
        client.update_issue('BAPP-9', {'summary': 'x'})
        method, path, payload = client.sent[0]
        self.assertEqual((method, path), ('PUT', '/rest/api/3/issue/BAPP-9'))
        self.assertEqual(payload, {'fields': {'summary': 'x'}})

    def test_a_get_sends_no_body(self):
        client = jira.JiraClient('https://jira', 'a@b.c', 'token')
        sent = {}

        def capture(req, timeout=None):
            sent['data'] = req.data
            raise RuntimeError('stop here')

        import urllib.request as urllib_request
        original = urllib_request.urlopen
        urllib_request.urlopen = capture
        try:
            with self.assertRaises(RuntimeError):
                client._send('GET', '/rest/api/3/issue/BAPP-1/transitions')
        finally:
            urllib_request.urlopen = original

        self.assertIsNone(sent['data'])

    def test_from_environment_reads_the_credentials(self):
        client = jira.JiraClient.from_environment({
            'JIRA_BASE_URL': 'https://example.atlassian.net/',
            'JIRA_USER_EMAIL': 'someone@example.com',
            'JIRA_API_TOKEN': 'secret',
        })
        self.assertEqual(client._base_url, 'https://example.atlassian.net')
        self.assertTrue(client._headers['Authorization'].startswith('Basic '))


class AllowedFieldsTests(unittest.TestCase):
    def test_only_what_the_transition_screens_for_survives(self):
        transition = {'fields': {'resolution': {}}}
        self.assertEqual(
            jira.allowed_fields({'resolution': {'id': '1'}, 'summary': 'x'},
                                transition),
            {'resolution': {'id': '1'}})

    def test_a_transition_with_no_screen_takes_nothing(self):
        self.assertEqual(
            jira.allowed_fields({'resolution': {'id': '1'}}, {'fields': {}}), {})

    def test_missing_field_metadata_is_treated_as_no_screen(self):
        self.assertEqual(jira.allowed_fields({'resolution': {'id': '1'}}, {}), {})

    def test_asking_for_nothing_is_tolerated(self):
        self.assertEqual(jira.allowed_fields(None, {'fields': {'resolution': {}}}), {})


class TransitionTests(unittest.TestCase):
    CLOSE_UNSCREENED = {'id': '7', 'to': {'id': jira.REJECTED_STATUS},
                                 'fields': {}}
    CLOSE_SCREENED = {'id': '171', 'to': {'id': jira.REJECTED_STATUS},
                           'fields': {'resolution': {'required': True}}}
    DIRECT_APPROVAL = {'id': '151', 'to': {'id': jira.APPROVED_STATUS}, 'fields': {}}

    def test_transitions_are_read_from_the_ticket(self):
        client = RecordingClient(transitions=[self.DIRECT_APPROVAL])
        self.assertEqual(client.transitions('BAPP-9'), [self.DIRECT_APPROVAL])
        method, path, _ = client.sent[0]
        self.assertEqual(method, 'GET')
        self.assertTrue(path.startswith('/rest/api/3/issue/BAPP-9/transitions'))

    def test_a_ticket_offering_no_transitions_reads_as_empty(self):
        client = RecordingClient(transitions=None)
        self.assertEqual(client.transitions('BAPP-9'), [])

    def test_the_move_to_the_target_status_is_the_one_posted(self):
        client = RecordingClient(
            transitions=[self.DIRECT_APPROVAL, self.CLOSE_UNSCREENED])
        client.transition_to_status('BAPP-9', jira.REJECTED_STATUS)

        method, path, payload = client.sent[-1]
        self.assertEqual((method, path),
                         ('POST', '/rest/api/3/issue/BAPP-9/transitions'))
        self.assertEqual(payload, {'transition': {'id': '7'}})

    def test_a_field_the_transition_screens_for_is_carried_onto_it(self):
        client = RecordingClient(transitions=[self.CLOSE_SCREENED])
        client.transition_to_status('BAPP-9', jira.REJECTED_STATUS,
                                    {'resolution': {'id': jira.DECLINED_RESOLUTION}})

        _, _, payload = client.sent[-1]
        self.assertEqual(payload['fields'],
                         {'resolution': {'id': jira.DECLINED_RESOLUTION}})

    def test_a_field_the_transition_has_no_screen_for_is_dropped(self):
        client = RecordingClient(transitions=[self.CLOSE_UNSCREENED])
        client.transition_to_status('BAPP-9', jira.REJECTED_STATUS,
                                    {'resolution': {'id': jira.DECLINED_RESOLUTION}})

        _, _, payload = client.sent[-1]
        self.assertNotIn('fields', payload)

    def test_the_fields_expansion_is_asked_for(self):
        client = RecordingClient(transitions=[self.CLOSE_SCREENED])
        client.transitions('BAPP-9')
        self.assertIn('expand=transitions.fields', client.sent[0][1])

    def test_empty_fields_are_left_off_the_payload(self):
        client = RecordingClient(transitions=[self.CLOSE_SCREENED])
        client.transition_to_status('BAPP-9', jira.REJECTED_STATUS, {})

        _, _, payload = client.sent[-1]
        self.assertNotIn('fields', payload)

    def test_an_unreachable_status_raises_rather_than_guessing(self):
        client = RecordingClient(transitions=[self.DIRECT_APPROVAL])
        with self.assertRaises(jira.TransitionUnavailable):
            client.transition_to_status('BAPP-9', jira.REJECTED_STATUS)

        self.assertEqual([method for method, _, _ in client.sent], ['GET'])

    def test_a_transition_with_no_destination_is_ignored(self):
        client = RecordingClient(transitions=[{'id': '3', 'name': 'Odd'}])
        with self.assertRaises(jira.TransitionUnavailable):
            client.transition_to_status('BAPP-9', jira.REJECTED_STATUS)


if __name__ == '__main__':
    unittest.main(verbosity=2)
