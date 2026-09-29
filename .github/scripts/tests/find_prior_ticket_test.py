#!/usr/bin/env python3

"""
Tests for find_prior_ticket.py
Run with: python find_prior_ticket_test.py
"""

import sys
import unittest
from pathlib import Path
from urllib import error

# Make the script under test importable (it lives one directory up).
sys.path.insert(0, str(Path(__file__).parent.parent))

import find_prior_ticket as fpt
import jira

REPO_URL = 'https://github.com/acme/widget'
PR_URL = 'https://github.com/PortSwigger/widget/pull/7'
ISSUE_URL = 'https://github.com/PortSwigger/extension-portal/issues/42'
ORIGINAL_URL = 'https://github.com/PortSwigger/extension-portal/issues/11'


class FakeJira(jira.JiraClient):
    """Stands in for Jira at the HTTP boundary only."""

    def __init__(self, tickets=None, search_error=None):
        self.tickets = tickets if tickets is not None else []
        self.search_error = search_error
        self.searches = []

    def search(self, jql, fields):
        self.searches.append(jql)
        if self.search_error:
            raise self.search_error
        return {'issues': self.tickets}


def ticket(key='BAPP-100', url=REPO_URL, issue_url=''):
    return {'key': key, 'fields': {jira.BAPP_URL_FIELD: url,
                                   jira.GITHUB_ISSUE_FIELD: issue_url}}


def earlier(client, submission_type='extension-submission', url=REPO_URL):
    return fpt.earlier_submissions(client, submission_type, url, ISSUE_URL)


class EarlierSubmissionTests(unittest.TestCase):
    def test_a_ticket_holding_this_url_is_an_earlier_submission(self):
        self.assertEqual(len(earlier(FakeJira([ticket()]))), 1)

    def test_a_loose_match_on_another_repository_is_discarded(self):
        self.assertEqual(earlier(FakeJira([ticket(url=REPO_URL + '-pro')])), [])

    def test_the_issue_being_processed_is_not_its_own_earlier_submission(self):
        self.assertEqual(earlier(FakeJira([ticket(issue_url=ISSUE_URL)])), [])

    def test_the_issue_being_processed_is_matched_loosely(self):
        client = FakeJira([ticket(issue_url=ISSUE_URL.upper() + '/')])
        self.assertEqual(earlier(client), [])

    def test_an_update_is_matched_against_update_subtasks(self):
        client = FakeJira([ticket(url=PR_URL)])
        earlier(client, submission_type='extension-update', url=PR_URL)
        self.assertIn(jira.UPDATE_SUBTASK_ISSUE_TYPE, client.searches[0])

    def test_a_failed_search_is_raised(self):
        client = FakeJira(search_error=error.HTTPError('u', 503, 'x', {}, None))
        with self.assertRaises(error.HTTPError):
            earlier(client)


class RaisedFirstTests(unittest.TestCase):
    def test_orders_by_number_rather_than_by_key(self):
        tickets = [ticket(key='BAPP-100'), ticket(key='BAPP-9')]
        self.assertEqual(fpt.raised_first(tickets)['key'], 'BAPP-9')


class PortalIssueTests(unittest.TestCase):
    def test_reads_the_issue_the_ticket_names(self):
        self.assertEqual(fpt.portal_issue(ticket(issue_url=ORIGINAL_URL)),
                         ORIGINAL_URL)

    def test_a_ticket_naming_none_reads_as_empty(self):
        self.assertEqual(fpt.portal_issue(ticket()), '')


class BappUrlTests(unittest.TestCase):
    def test_a_submission_is_reduced_to_its_repository(self):
        self.assertEqual(
            fpt.bapp_url('extension-submission', REPO_URL + '/tree/main'),
            REPO_URL)

    def test_an_update_keeps_its_pull_request_path(self):
        self.assertEqual(fpt.bapp_url('extension-update', PR_URL), PR_URL)


if __name__ == '__main__':
    unittest.main(verbosity=2)
