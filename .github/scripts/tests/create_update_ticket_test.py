#!/usr/bin/env python3

"""
Tests for create_update_ticket.py
Run with: python create_update_ticket_test.py
"""

import sys
import unittest
from pathlib import Path
from urllib import error

# Make the script under test importable (it lives one directory up).
sys.path.insert(0, str(Path(__file__).parent.parent))

import create_update_ticket as cut
import jira

SOURCE_URL = 'https://github.com/acme/widget'


class FakeJira(jira.JiraClient):
    """Stands in for Jira at the HTTP boundary only."""

    def __init__(self, parents=None, search_error=None, create_error=None):
        self.parents = parents if parents is not None else []
        self.search_error = search_error
        self.create_error = create_error
        self.created = []

    def search(self, jql, fields):
        if self.search_error:
            raise self.search_error
        return {'issues': self.parents}

    def create_issue(self, fields):
        self.created.append(fields)
        if self.create_error:
            raise self.create_error
        return 'BAPP-200'


def parent(key='BAPP-100', url=SOURCE_URL):
    return {'key': key, 'fields': {jira.BAPP_URL_FIELD: url}}


class FindParentTests(unittest.TestCase):
    def test_single_match(self):
        self.assertEqual(cut.find_parent(FakeJira([parent()]), SOURCE_URL), 'BAPP-100')

    def test_match_differing_only_in_formatting(self):
        client = FakeJira([parent(url='https://github.com/Acme/Widget.git/')])
        self.assertEqual(cut.find_parent(client, SOURCE_URL), 'BAPP-100')

    def test_no_match_hands_over(self):
        with self.assertRaises(cut.NeedsManualIntervention) as caught:
            cut.find_parent(FakeJira([]), SOURCE_URL)
        self.assertIn('No parent BAPP ticket', str(caught.exception))

    def test_ambiguous_match_hands_over_and_names_the_candidates(self):
        client = FakeJira([parent(), parent(key='BAPP-101')])
        with self.assertRaises(cut.NeedsManualIntervention) as caught:
            cut.find_parent(client, SOURCE_URL)
        self.assertIn('BAPP-100, BAPP-101', str(caught.exception))

    def test_loose_match_on_another_repository_is_discarded(self):
        client = FakeJira([parent(url=SOURCE_URL + '-pro')])
        with self.assertRaises(cut.NeedsManualIntervention):
            cut.find_parent(client, SOURCE_URL)

    def test_search_failure_hands_over(self):
        client = FakeJira(search_error=error.HTTPError('u', 503, 'x', {}, None))
        with self.assertRaises(cut.NeedsManualIntervention) as caught:
            cut.find_parent(client, SOURCE_URL)
        self.assertIn('search for the parent ticket failed', str(caught.exception))


class CreateSubtaskTests(unittest.TestCase):
    def test_records_the_version_parent_and_urls(self):
        client = FakeJira()
        key = cut.create_subtask(client, 'BAPP-100', '2.1.0',
                                 'https://github.com/PortSwigger/w/pull/9',
                                 'https://github.com/PortSwigger/portal/issues/42')
        self.assertEqual(key, 'BAPP-200')
        self.assertEqual(client.created, [{
            'project': {'key': 'BAPP'},
            'issuetype': {'id': jira.UPDATE_SUBTASK_ISSUE_TYPE},
            'parent': {'key': 'BAPP-100'},
            'summary': 'v2.1.0',
            jira.BAPP_URL_FIELD: 'https://github.com/PortSwigger/w/pull/9',
            jira.GITHUB_ISSUE_FIELD: 'https://github.com/PortSwigger/portal/issues/42',
        }])

    def test_creation_failure_hands_over(self):
        client = FakeJira(create_error=error.HTTPError('u', 400, 'x', {}, None))
        with self.assertRaises(cut.NeedsManualIntervention) as caught:
            cut.create_subtask(client, 'BAPP-100', '1.0', 'pr', 'issue')
        self.assertIn('Failed to create the BApp update subtask', str(caught.exception))


if __name__ == '__main__':
    unittest.main(verbosity=2)
