#!/usr/bin/env python3

"""
Tests for sync_jira_ticket.py
Run with: python sync_jira_ticket_test.py

Jira is mocked so the tests are deterministic and need no network.
"""

import base64
import json
import sys
import unittest
from dataclasses import fields
from pathlib import Path
from urllib import error

# Make the script under test importable (it lives one directory up).
sys.path.insert(0, str(Path(__file__).parent.parent))

import jira
import sync_jira_ticket as sjt

ISSUE_URL = 'https://github.com/PortSwigger/extension-portal/issues/42'


class FakeJira(jira.JiraClient):
    """
    Stands in for Jira at the HTTP boundary only.

    Subclassing the real client means the JQL building and the exact-match
    filtering in find_by_url_field stay under test.
    """

    def __init__(self, tickets=None, search_error=None, update_error=None):
        self.tickets = tickets if tickets is not None else []
        self.search_error = search_error
        self.update_error = update_error
        self.updates = []
        self.searches = []

    def search(self, jql, fields):
        self.searches.append(jql)
        if self.search_error:
            raise self.search_error
        return {'issues': self.tickets}

    def update_issue(self, key, fields):
        self.updates.append((key, fields))
        if self.update_error:
            raise self.update_error


def http_error(code, body=b''):
    return error.HTTPError('https://jira', code, 'boom', {}, __import__('io').BytesIO(body))


def submission_ticket(key='BAPP-100', summary='Old Name',
                      bapp_url='https://github.com/acme/old', issue_url=ISSUE_URL):
    return {'key': key, 'fields': {'summary': summary,
                                   jira.BAPP_URL_FIELD: bapp_url,
                                   jira.GITHUB_ISSUE_FIELD: issue_url}}


def update_subtask(key='BAPP-200', summary='v2.0.0',
                   bapp_url='https://github.com/PortSwigger/w/pull/1'):
    return {'key': key, 'fields': {'summary': summary,
                                   jira.BAPP_URL_FIELD: bapp_url,
                                   jira.GITHUB_ISSUE_FIELD: ISSUE_URL}}


def edit(**overrides):
    defaults = {
        'ISSUE_URL': ISSUE_URL,
        'SUBMISSION_TYPE': 'extension-submission',
        'IS_MAINTAINER': 'false',
        'EDITOR_LOGIN': 'alice',
        'EDITOR_ACCESS': 'submitter',
        'SUMMARY_CHANGED': 'false',
        'URL_CHANGED': 'false',
        'ISSUE_TITLE': 'New Name',
        'VERSION_NUMBER': '2.1.0',
        'SUBMITTED_URL': 'https://github.com/acme/new',
        'VALIDATION_ERROR': '',
    }
    defaults.update(overrides)
    return sjt.Edit.from_environment(defaults)


class EscapeJqlTests(unittest.TestCase):
    def test_escapes_backslashes_and_quotes(self):
        self.assertEqual(jira.escape_jql(r'a"b\c'), r'a\"b\\c')

    def test_jql_field_drops_the_customfield_prefix(self):
        self.assertEqual(jira.jql_field('customfield_10932'), 'cf[10932]')


class SubmitterEditTests(unittest.TestCase):
    """A submitter must never be able to repoint the reviewed artifact."""

    def test_url_change_is_flagged_and_writes_nothing(self):
        client = FakeJira([submission_ticket()])
        outcome = sjt.sync(client, edit(URL_CHANGED='true'))
        self.assertEqual(outcome.status, 'flagged')
        self.assertEqual(client.updates, [])

    def test_url_and_summary_change_together_writes_nothing(self):
        client = FakeJira([submission_ticket()])
        outcome = sjt.sync(client, edit(URL_CHANGED='true', SUMMARY_CHANGED='true'))
        self.assertEqual(outcome.status, 'flagged')
        self.assertEqual(client.updates, [])

    def test_summary_change_is_applied(self):
        client = FakeJira([submission_ticket()])
        outcome = sjt.sync(client, edit(SUMMARY_CHANGED='true'))
        self.assertEqual(outcome.status, 'updated')
        self.assertEqual(client.updates, [('BAPP-100', {'summary': 'New Name'})])


class MaintainerEditTests(unittest.TestCase):
    def maintainer(self, **overrides):
        return edit(IS_MAINTAINER='true', EDITOR_LOGIN='bob',
                    EDITOR_ACCESS='write', **overrides)

    def test_url_change_is_applied_and_canonicalised(self):
        client = FakeJira([submission_ticket()])
        outcome = sjt.sync(client, self.maintainer(
            URL_CHANGED='true', SUBMITTED_URL='https://github.com/Acme/New.git/'))
        self.assertEqual(outcome.status, 'updated')
        self.assertEqual(
            client.updates,
            [('BAPP-100', {jira.BAPP_URL_FIELD: 'https://github.com/Acme/New'})])

    def test_url_and_summary_are_applied_in_one_update(self):
        client = FakeJira([submission_ticket()])
        sjt.sync(client, self.maintainer(URL_CHANGED='true', SUMMARY_CHANGED='true'))
        self.assertEqual(len(client.updates), 1)
        self.assertEqual(set(client.updates[0][1]), {'summary', jira.BAPP_URL_FIELD})

    def test_update_subtask_summary_becomes_the_version(self):
        client = FakeJira([update_subtask()])
        sjt.sync(client, self.maintainer(SUBMISSION_TYPE='extension-update',
                                         SUMMARY_CHANGED='true'))
        self.assertEqual(client.updates, [('BAPP-200', {'summary': 'v2.1.0'})])

    def test_update_subtask_records_the_pull_request_url_as_given(self):
        client = FakeJira([update_subtask()])
        sjt.sync(client, self.maintainer(
            SUBMISSION_TYPE='extension-update', URL_CHANGED='true',
            SUBMITTED_URL='https://github.com/PortSwigger/w/pull/9'))
        self.assertEqual(
            client.updates,
            [('BAPP-200', {jira.BAPP_URL_FIELD: 'https://github.com/PortSwigger/w/pull/9'})])


class NothingToDoTests(unittest.TestCase):
    def test_ticket_already_matches(self):
        client = FakeJira([submission_ticket(summary='New Name')])
        outcome = sjt.sync(client, edit(SUMMARY_CHANGED='true'))
        self.assertEqual(outcome.status, 'unchanged')
        self.assertEqual(client.updates, [])

    def test_url_matches_apart_from_formatting(self):
        client = FakeJira([submission_ticket(bapp_url='https://github.com/acme/new/')])
        outcome = sjt.sync(client, edit(IS_MAINTAINER='true', URL_CHANGED='true'))
        self.assertEqual(outcome.status, 'unchanged')
        self.assertEqual(client.updates, [])


class TicketLookupTests(unittest.TestCase):
    def test_no_ticket_yet_is_reported_as_absent_not_as_a_fault(self):
        outcome = sjt.sync(FakeJira([]), edit(SUMMARY_CHANGED='true'))
        self.assertEqual(outcome.status, 'absent')
        self.assertIn('has been created', outcome.reason)

    def test_several_tickets(self):
        client = FakeJira([submission_ticket(), submission_ticket(key='BAPP-101')])
        outcome = sjt.sync(client, edit(SUMMARY_CHANGED='true'))
        self.assertEqual(outcome.status, 'manual')
        self.assertIn('BAPP-100, BAPP-101', outcome.reason)

    def test_fuzzy_match_on_another_issue_is_discarded(self):
        client = FakeJira([submission_ticket(issue_url=ISSUE_URL + '9')])
        outcome = sjt.sync(client, edit(SUMMARY_CHANGED='true'))
        self.assertEqual(outcome.status, 'absent')

    def test_search_failure(self):
        client = FakeJira(search_error=http_error(503))
        outcome = sjt.sync(client, edit(SUMMARY_CHANGED='true'))
        self.assertEqual(outcome.status, 'manual')
        self.assertIn('503', outcome.reason)

    def test_search_falls_back_to_exact_match_on_400(self):
        class PickyJira(FakeJira):
            def __init__(self):
                super().__init__([submission_ticket()])
                self.operators = []

            def search(self, jql, fields):
                self.operators.append('~' if ' ~ ' in jql else '=')
                if self.operators[-1] == '~':
                    raise http_error(400)
                return {'issues': self.tickets}

        client = PickyJira()
        outcome = sjt.sync(client, edit(SUMMARY_CHANGED='true'))
        self.assertEqual(client.operators, ['~', '='])
        self.assertEqual(outcome.status, 'updated')

    def test_update_failure(self):
        client = FakeJira([submission_ticket()], update_error=http_error(400, b'bad field'))
        outcome = sjt.sync(client, edit(SUMMARY_CHANGED='true'))
        self.assertEqual(outcome.status, 'manual')
        self.assertIn('bad field', outcome.reason)

    def test_unexpected_error_is_contained(self):
        client = FakeJira(search_error=RuntimeError('socket exploded'))
        outcome = sjt.sync(client, edit(SUMMARY_CHANGED='true'))
        self.assertEqual(outcome.status, 'manual')
        self.assertIn('socket exploded', outcome.reason)


class EmptyValueGuardTests(unittest.TestCase):
    """A blank value must never overwrite a field that holds a good one."""

    def test_blank_title(self):
        client = FakeJira([submission_ticket()])
        outcome = sjt.sync(client, edit(SUMMARY_CHANGED='true', ISSUE_TITLE='   '))
        self.assertEqual(outcome.status, 'manual')
        self.assertEqual(client.updates, [])

    def test_blank_version_never_writes_a_bare_v(self):
        client = FakeJira([update_subtask()])
        outcome = sjt.sync(client, edit(SUBMISSION_TYPE='extension-update',
                                        SUMMARY_CHANGED='true', VERSION_NUMBER='  '))
        self.assertEqual(outcome.status, 'manual')
        self.assertEqual(client.updates, [])

    def test_unparseable_url(self):
        client = FakeJira([submission_ticket()])
        outcome = sjt.sync(client, edit(IS_MAINTAINER='true', URL_CHANGED='true',
                                        SUBMITTED_URL='not a url'))
        self.assertEqual(outcome.status, 'manual')
        self.assertEqual(client.updates, [])


class NoTicketYetTests(unittest.TestCase):
    """
    A submission that failed its checks is closed, so the edited-issue pipeline
    never runs for it. An update whose parent could not be matched stays open
    with no ticket, and editing it must read as expected, not as a fault.
    """

    def edited_with_no_ticket(self, **overrides):
        e = edit(SUMMARY_CHANGED='true', **overrides)
        return e, sjt.sync(FakeJira([]), e)

    def test_nothing_is_written(self):
        client = FakeJira([])
        sjt.sync(client, edit(SUMMARY_CHANGED='true'))
        self.assertEqual(client.updates, [])

    def test_the_team_is_told_and_the_wording_is_not_an_error(self):
        e, outcome = self.edited_with_no_ticket()
        payload = sjt.zoom_payload(e, outcome)
        self.assertEqual(payload['Alert'], 'Submission edited before its ticket was created')
        self.assertIn('use these details when creating it', payload['Action'])
        self.assertNotIn('Reason', payload)

    def test_the_edited_details_are_included(self):
        e, outcome = self.edited_with_no_ticket(SUBMISSION_TYPE='extension-update',
                                                URL_CHANGED='true')
        payload = sjt.zoom_payload(e, outcome)
        self.assertEqual(payload['Version'], 'v2.1.0')
        self.assertEqual(payload['Pull request'], 'https://github.com/acme/new')

    def test_a_maintainer_editing_is_told_too(self):
        e, outcome = self.edited_with_no_ticket(IS_MAINTAINER='true', EDITOR_ACCESS='admin')
        self.assertIsNotNone(sjt.zoom_payload(e, outcome))


class ZoomPayloadTests(unittest.TestCase):
    def payload(self, outcome, **overrides):
        return sjt.zoom_payload(edit(**overrides), outcome)

    @staticmethod
    def held(summary='Old Name', bapp_url='https://github.com/acme/old'):
        return {'summary': summary, jira.BAPP_URL_FIELD: bapp_url}

    def test_silent_when_the_ticket_already_matched(self):
        self.assertIsNone(self.payload(sjt.Outcome('unchanged', 'BAPP-100')))

    def test_silent_for_an_applied_maintainer_edit(self):
        self.assertIsNone(self.payload(sjt.Outcome('updated', 'BAPP-100', ('Summary',)),
                                       IS_MAINTAINER='true'))

    def test_reports_a_maintainer_edit_that_could_not_be_applied(self):
        payload = self.payload(sjt.Outcome('manual', reason='No ticket.'),
                               IS_MAINTAINER='true', EDITOR_LOGIN='bob', EDITOR_ACCESS='admin')
        self.assertEqual(payload['Alert'], 'Maintainer edit could not be applied')
        self.assertEqual(payload['Edited by'], 'bob (admin access)')
        self.assertEqual(payload['Reason'], 'No ticket.')

    def test_flagged_names_both_urls_and_the_untouched_ticket(self):
        payload = self.payload(sjt.Outcome('flagged', 'BAPP-100', held=self.held()),
                               URL_CHANGED='true')
        self.assertEqual(payload['Alert'], 'Submission repointed at different code')
        self.assertEqual(payload['Ticket'], 'BAPP-100 (unchanged)')
        self.assertEqual(
            payload['Extension URL'],
            'https://github.com/acme/old -> https://github.com/acme/new')

    def test_flagged_labels_an_update_as_a_pull_request(self):
        payload = self.payload(sjt.Outcome('flagged', 'BAPP-200', held=self.held()),
                               SUBMISSION_TYPE='extension-update', URL_CHANGED='true')
        self.assertIn('Pull request', payload)

    def test_reports_an_applied_submitter_edit(self):
        payload = self.payload(sjt.Outcome('updated', 'BAPP-100', ('Summary',)))
        self.assertEqual(payload['Updated'], '✅ Summary')

    def test_reports_a_validation_error(self):
        payload = self.payload(sjt.Outcome('rejected'), VALIDATION_ERROR='Bad URL')
        self.assertEqual(payload['Validation Error'], '❌ Bad URL')

    def test_every_payload_names_the_editor_and_their_access(self):
        for outcome, extra in [(sjt.Outcome('flagged', 'B-1'), {'URL_CHANGED': 'true'}),
                               (sjt.Outcome('updated', 'B-1', ('Summary',)), {}),
                               (sjt.Outcome('manual', reason='x'), {})]:
            payload = self.payload(outcome, **extra)
            self.assertEqual(payload['Edited by'], 'alice (submitter access)')

    def test_a_submitter_name_change_reports_both_values(self):
        payload = self.payload(sjt.Outcome('updated', 'BAPP-100', ('Summary',),
                                           held=self.held()),
                               SUMMARY_CHANGED='true')
        self.assertEqual(payload['Name'], 'Old Name -> New Name')

    def test_a_submitter_url_change_reports_both_values(self):
        payload = self.payload(sjt.Outcome('flagged', 'BAPP-100', held=self.held()),
                               URL_CHANGED='true')
        self.assertEqual(
            payload['Extension URL'],
            'https://github.com/acme/old -> https://github.com/acme/new')

    def test_a_submitter_changing_both_reports_both(self):
        payload = self.payload(sjt.Outcome('flagged', 'BAPP-100', held=self.held()),
                               SUMMARY_CHANGED='true', URL_CHANGED='true')
        self.assertEqual(payload['Name'], 'Old Name -> New Name')
        self.assertEqual(
            payload['Extension URL'],
            'https://github.com/acme/old -> https://github.com/acme/new')

    def test_an_update_reports_version_rather_than_name(self):
        payload = self.payload(sjt.Outcome('updated', 'BAPP-200', ('Summary',),
                                           held=self.held(summary='v2.0.0')),
                               SUBMISSION_TYPE='extension-update', SUMMARY_CHANGED='true')
        self.assertEqual(payload['Version'], 'v2.0.0 -> v2.1.0')
        self.assertNotIn('Name', payload)

    def test_an_unchanged_field_is_not_reported(self):
        payload = self.payload(sjt.Outcome('updated', 'BAPP-100', ('Summary',),
                                           held=self.held()),
                               SUMMARY_CHANGED='true')
        self.assertNotIn('Extension URL', payload)

    def test_when_the_ticket_has_no_before_value_only_the_new_one_is_shown(self):
        payload = self.payload(sjt.Outcome('flagged', 'BAPP-100'), URL_CHANGED='true')
        self.assertEqual(payload['Extension URL'], 'https://github.com/acme/new')

    def test_the_before_value_is_read_from_the_ticket_not_the_issue(self):
        """
        The issue's previous revision never reaches a notification. Only the
        current values do, and those have been through sanitize-inputs; what the
        ticket holds we wrote ourselves.
        """
        payload = self.payload(
            sjt.Outcome('updated', 'BAPP-100', ('Summary',),
                        held=self.held(summary='What the ticket holds')),
            SUMMARY_CHANGED='true')
        self.assertEqual(payload['Name'], 'What the ticket holds -> New Name')

    def test_the_edit_carries_no_previous_revision_at_all(self):
        self.assertNotIn('previous', ' '.join(f.name for f in fields(sjt.Edit)))

    def test_encoding_round_trips(self):
        payload = self.payload(sjt.Outcome('updated', 'BAPP-100', ('Summary',),
                                           held=self.held()))
        decoded = json.loads(base64.b64decode(sjt.encode_payload(payload)).decode())
        self.assertEqual(decoded, payload)


if __name__ == '__main__':
    unittest.main(verbosity=2)
