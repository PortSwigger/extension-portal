#!/usr/bin/env python3

"""
Applies an edited issue to its associated Jira ticket, or flags it for the team.

Two fields on the ticket come from the issue:

    summary   - the issue title for submissions, the version number for updates.
    bapp url  - the extension repository for submissions, the pull request for
                updates.

The bapp url is the artifact that was reviewed. A submitter repointing it makes
this, in effect, a new submission, so the ticket is left untouched and the team
is asked to decide; a maintainer repointing it is a deliberate correction and is
applied. Everything the pipeline decides is reported to Zoom and to the run log,
never on the issue itself.

Reads the edit from the environment and writes the outcome, plus a Zoom payload
when one is warranted, as GitHub Actions outputs.
"""

import base64
import json
import os
import sys
from dataclasses import dataclass
from urllib import error, request

from github_actions_utils import set_output
from github_urls import canonical_repository_url, normalize_url

JIRA_PROJECT = 'BAPP'
SUBMISSION_ISSUE_TYPE = '10278'
UPDATE_SUBTASK_ISSUE_TYPE = '10279'
BAPP_URL_FIELD = 'customfield_10932'
GITHUB_ISSUE_FIELD = 'customfield_13486'


class NeedsManualIntervention(Exception):
    """The edit could not be applied with confidence, so the team must decide."""


def jql_field(field):
    return f"cf[{field.removeprefix('customfield_')}]"


def escape_jql(value):
    return (value or '').replace('\\', '\\\\').replace('"', '\\"')


@dataclass(frozen=True)
class Edit:
    issue_url: str
    is_update: bool
    is_maintainer: bool
    editor: str
    editor_access: str
    summary_changed: bool
    url_changed: bool
    title: str
    version_number: str
    url: str
    previous_url: str
    validation_error: str

    @classmethod
    def from_environment(cls, env=None):
        env = os.environ if env is None else env

        def flag(name):
            return env.get(name, '').strip().lower() == 'true'

        return cls(
            issue_url=env.get('ISSUE_URL', '').strip(),
            is_update=env.get('SUBMISSION_TYPE', '') == 'extension-update',
            is_maintainer=flag('IS_MAINTAINER'),
            editor=env.get('EDITOR_LOGIN', '').strip() or '(unknown)',
            editor_access=env.get('EDITOR_ACCESS', '').strip() or 'unknown',
            summary_changed=flag('SUMMARY_CHANGED'),
            url_changed=flag('URL_CHANGED'),
            title=env.get('ISSUE_TITLE', '').strip(),
            version_number=env.get('VERSION_NUMBER', '').strip(),
            url=env.get('SUBMITTED_URL', '').strip(),
            previous_url=env.get('PREVIOUS_URL', '').strip(),
            validation_error=env.get('VALIDATION_ERROR', '').strip(),
        )

    @property
    def ticket_issue_type(self):
        return UPDATE_SUBTASK_ISSUE_TYPE if self.is_update else SUBMISSION_ISSUE_TYPE

    @property
    def url_label(self):
        return 'Pull request' if self.is_update else 'Extension URL'

    @property
    def desired_summary(self):
        return f'v{self.version_number}' if self.is_update else self.title

    @property
    def desired_bapp_url(self):
        return self.url if self.is_update else canonical_repository_url(self.url)


@dataclass(frozen=True)
class Outcome:
    status: str
    ticket_key: str = ''
    applied: tuple = ()
    reason: str = ''


class JiraClient:
    def __init__(self, base_url, email, token):
        self._base_url = (base_url or '').rstrip('/')
        credentials = base64.b64encode(f'{email}:{token}'.encode()).decode()
        self._headers = {
            'Authorization': f'Basic {credentials}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

    def _send(self, method, path, payload):
        req = request.Request(f'{self._base_url}{path}', method=method,
                              data=json.dumps(payload).encode())
        for name, value in self._headers.items():
            req.add_header(name, value)
        with request.urlopen(req) as response:
            body = response.read().decode()
        return json.loads(body) if body else {}

    def search(self, jql, fields):
        return self._send('POST', '/rest/api/3/search/jql',
                          {'jql': jql, 'fields': fields, 'maxResults': 50})

    def find_by_url_field(self, issue_type, field, url, fields):
        """
        Tickets of this type whose `field` holds this URL.

        Jira matches URL fields loosely, so the search asks for "contains" - falling
        back to exact match if the field rejects that - and the results are then
        compared properly.
        """
        def jql(operator):
            return (f'project = {JIRA_PROJECT} AND issuetype = {issue_type} '
                    f'AND {jql_field(field)} {operator} "{escape_jql(url)}"')

        try:
            results = self.search(jql('~'), fields)
        except error.HTTPError as e:
            if e.code != 400:
                raise
            results = self.search(jql('='), fields)

        return [ticket for ticket in results.get('issues', [])
                if normalize_url(ticket.get('fields', {}).get(field)) == normalize_url(url)]

    def update_issue(self, key, fields):
        self._send('PUT', f'/rest/api/3/issue/{key}', {'fields': fields})


def find_ticket(jira, edit):
    try:
        matches = jira.find_by_url_field(
            edit.ticket_issue_type, GITHUB_ISSUE_FIELD, edit.issue_url,
            ['summary', BAPP_URL_FIELD, GITHUB_ISSUE_FIELD])
    except error.HTTPError as e:
        raise NeedsManualIntervention(
            f'Jira search for the associated ticket failed: {e.code}.')

    if not matches:
        raise NeedsManualIntervention(
            f'No {JIRA_PROJECT} ticket is associated with {edit.issue_url}.')
    if len(matches) > 1:
        keys = ', '.join(ticket['key'] for ticket in matches)
        raise NeedsManualIntervention(
            f'Multiple {JIRA_PROJECT} tickets ({keys}) are associated with {edit.issue_url}.')
    return matches[0]


def changes_to_apply(edit, ticket):
    """The Jira fields that differ from what the ticket already holds."""
    held = ticket.get('fields', {})
    fields, applied = {}, []

    if edit.summary_changed:
        summary = edit.desired_summary
        if not summary or (edit.is_update and not edit.version_number):
            raise NeedsManualIntervention(
                f'The edited {"version number" if edit.is_update else "title"} came through '
                f'empty, so {ticket["key"]} has been left as it was.')
        if (held.get('summary') or '') != summary:
            fields['summary'] = summary
            applied.append('Summary')

    if edit.url_changed:
        bapp_url = edit.desired_bapp_url
        if not bapp_url:
            raise NeedsManualIntervention(
                f'"{edit.url}" is not a URL we can record, so {ticket["key"]} has been '
                f'left as it was.')
        if normalize_url(held.get(BAPP_URL_FIELD)) != normalize_url(bapp_url):
            fields[BAPP_URL_FIELD] = bapp_url
            applied.append(edit.url_label)

    return fields, applied


def sync(jira, edit):
    try:
        ticket = find_ticket(jira, edit)

        if edit.url_changed and not edit.is_maintainer:
            return Outcome('flagged', ticket_key=ticket['key'])

        fields, applied = changes_to_apply(edit, ticket)
        if not fields:
            return Outcome('unchanged', ticket_key=ticket['key'])

        try:
            jira.update_issue(ticket['key'], fields)
        except error.HTTPError as e:
            raise NeedsManualIntervention(
                f'Failed to update {ticket["key"]}: {e.code} {e.read().decode(errors="replace")}')

        return Outcome('updated', ticket_key=ticket['key'], applied=tuple(applied))

    except NeedsManualIntervention as e:
        return Outcome('manual', reason=str(e))
    except Exception as e:
        return Outcome(
            'manual', reason=f'Unexpected error while updating the associated ticket: {e}')


def zoom_payload(edit, outcome):
    """The notification for this outcome, or None when there is nothing to report."""
    if not edit.validation_error and outcome.status not in ('updated', 'flagged', 'manual'):
        return None
    if edit.is_maintainer and not edit.validation_error and outcome.status != 'manual':
        return None

    payload = {
        'Alert': ('Submission repointed at different code' if outcome.status == 'flagged'
                  else 'Submission details edited'),
        'Extension': edit.title,
        'Issue': edit.issue_url,
        'Edited by': f'{edit.editor} ({edit.editor_access} access)',
    }

    if edit.is_maintainer:
        payload['Alert'] = 'Maintainer edit could not be applied'
        payload['Reason'] = edit.validation_error or outcome.reason or 'Unknown.'
        payload['Action'] = '⚠️ Apply the edit to the associated ticket by hand.'
    elif edit.validation_error:
        payload['Validation Error'] = f'❌ {edit.validation_error}'
        payload['Action'] = '⚠️ Ticket left unchanged - the edited details were rejected.'
    elif outcome.status == 'flagged':
        payload['Ticket'] = f'{outcome.ticket_key} (unchanged)'
        payload[f'Previous {edit.url_label}'] = edit.previous_url or '(none)'
        payload[f'New {edit.url_label}'] = edit.url or '(none)'
        payload['Action'] = ('⚠️ Treat as a new submission - review has not been re-run '
                             'and the ticket has NOT been updated.')
    elif outcome.status == 'updated':
        payload['Ticket'] = outcome.ticket_key
        payload['Updated'] = f'✅ {", ".join(outcome.applied)}'
    else:
        payload['Action'] = '⚠️ Apply the edited details to the associated ticket.'
        if outcome.reason:
            payload['Reason'] = outcome.reason

    return payload


def encode_payload(payload):
    """Base64 so that GitHub does not mask fragments of the output."""
    return base64.b64encode(json.dumps(payload).encode()).decode()


def report(outcome):
    if outcome.status == 'flagged':
        print(f'::warning::{outcome.ticket_key} left unchanged: '
              f'the submitter edited the URL.')
    elif outcome.status == 'updated':
        print(f'::notice::Updated {outcome.ticket_key}: {", ".join(outcome.applied)}.')
    elif outcome.status == 'unchanged':
        print(f'::notice::{outcome.ticket_key} already matches the issue.')
    else:
        print(f'::warning::{outcome.reason}')


if __name__ == '__main__':
    edit = Edit.from_environment()

    if edit.validation_error:
        print(f'::warning::{edit.validation_error}')
        outcome = Outcome('rejected')
    else:
        jira = JiraClient(os.environ.get('JIRA_BASE_URL'),
                          os.environ.get('JIRA_USER_EMAIL'),
                          os.environ.get('JIRA_API_TOKEN'))
        outcome = sync(jira, edit)
        report(outcome)

    payload = zoom_payload(edit, outcome)

    set_output('status', outcome.status)
    set_output('jira_key', outcome.ticket_key)
    set_output('zoom_payload', encode_payload(payload) if payload else '')

    sys.exit(0)
