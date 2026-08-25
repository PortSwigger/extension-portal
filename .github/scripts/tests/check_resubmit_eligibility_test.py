#!/usr/bin/env python3

"""
Tests for check_resubmit_eligibility.py
Run with: python check_resubmit_eligibility_test.py
"""

import sys
import unittest
from pathlib import Path
from urllib import error

# Make the script under test importable (it lives one directory up).
sys.path.insert(0, str(Path(__file__).parent.parent))

import check_resubmit_eligibility as cre
import jira

ISSUE_URL = 'https://github.com/PortSwigger/extension-portal/issues/42'


class FakeJira(jira.JiraClient):
    """Stands in for Jira at the HTTP boundary only."""

    def __init__(self, tickets=None, search_error=None):
        self.tickets = tickets if tickets is not None else []
        self.search_error = search_error

    def search(self, jql, fields):
        if self.search_error:
            raise self.search_error
        return {'issues': self.tickets}


def ticket(issue_url=ISSUE_URL):
    return {'key': 'BAPP-100', 'fields': {jira.GITHUB_ISSUE_FIELD: issue_url}}


def decide(commenter='alice', author='alice', association='NONE',
           issue_type_name='Extension', client=None):
    return cre.decide(commenter, author, association, issue_type_name,
                      ISSUE_URL, client if client is not None else FakeJira())


class AuthorisationTests(unittest.TestCase):
    def test_the_submitter_may_resubmit(self):
        self.assertEqual(decide(commenter='alice', author='alice'), cre.APPROVED)

    def test_maintainers_may_resubmit(self):
        for association in ['OWNER', 'MEMBER', 'COLLABORATOR']:
            self.assertEqual(decide(commenter='bob', association=association),
                             cre.APPROVED, association)

    def test_anyone_else_may_not(self):
        for association in ['NONE', 'CONTRIBUTOR', 'FIRST_TIME_CONTRIBUTOR']:
            self.assertEqual(decide(commenter='mallory', association=association),
                             cre.NOT_AUTHORIZED, association)


class EligibilityTests(unittest.TestCase):
    def test_only_extension_submissions_are_resubmittable(self):
        self.assertEqual(decide(issue_type_name='Update'), cre.NOT_ELIGIBLE)
        self.assertEqual(decide(issue_type_name=''), cre.NOT_ELIGIBLE)

    def test_authorisation_is_checked_before_eligibility(self):
        self.assertEqual(decide(commenter='mallory', issue_type_name='Update'),
                         cre.NOT_AUTHORIZED)


class DuplicateGuardTests(unittest.TestCase):
    def test_an_existing_ticket_blocks_the_resubmission(self):
        self.assertEqual(decide(client=FakeJira([ticket()])), cre.ALREADY_PROCESSED)

    def test_a_ticket_for_another_issue_does_not_block(self):
        self.assertEqual(decide(client=FakeJira([ticket(ISSUE_URL + '9')])), cre.APPROVED)

    def test_a_failed_lookup_refuses_rather_than_risking_a_duplicate(self):
        client = FakeJira(search_error=error.HTTPError('u', 503, 'x', {}, None))
        self.assertEqual(decide(client=client), cre.LOOKUP_FAILED)

    def test_an_unexpected_error_also_refuses(self):
        self.assertEqual(decide(client=FakeJira(search_error=RuntimeError('boom'))),
                         cre.LOOKUP_FAILED)


if __name__ == '__main__':
    unittest.main(verbosity=2)
