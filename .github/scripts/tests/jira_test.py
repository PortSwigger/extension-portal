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

    def __init__(self, responses=None, error_by_operator=None):
        self.responses = responses if responses is not None else []
        self.error_by_operator = error_by_operator or {}
        self.searches = []
        self.sent = []

    def search(self, jql, fields):
        operator = '~' if ' ~ ' in jql else '='
        self.searches.append((operator, jql))
        if operator in self.error_by_operator:
            raise self.error_by_operator[operator]
        return {'issues': self.responses}

    def _send(self, method, path, payload):
        self.sent.append((method, path, payload))
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

    def test_from_environment_reads_the_credentials(self):
        client = jira.JiraClient.from_environment({
            'JIRA_BASE_URL': 'https://example.atlassian.net/',
            'JIRA_USER_EMAIL': 'someone@example.com',
            'JIRA_API_TOKEN': 'secret',
        })
        self.assertEqual(client._base_url, 'https://example.atlassian.net')
        self.assertTrue(client._headers['Authorization'].startswith('Basic '))


if __name__ == '__main__':
    unittest.main(verbosity=2)
