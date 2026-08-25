#!/usr/bin/env python3

"""
Applies an edited issue to its associated Jira ticket, or flags it for the team.

The ticket takes its summary and its bapp url from the issue. The bapp url is
the artifact that was reviewed, so only a maintainer may change it; a submitter
doing so is flagged instead, because it makes this a new submission.

Outcomes go to Zoom and the run log, never to the issue.
"""

import base64
import json
import os
import sys
from dataclasses import dataclass, field
from urllib import error

import jira
from github_actions_utils import set_output
from github_urls import normalize_url, repository_url


class NeedsManualIntervention(Exception):
    """The edit could not be applied with confidence, so the team must decide."""


class TicketNotCreated(NeedsManualIntervention):
    """No ticket exists yet, which is expected rather than faulty."""


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
            validation_error=env.get('VALIDATION_ERROR', '').strip(),
        )

    @property
    def ticket_issue_type(self):
        return jira.UPDATE_SUBTASK_ISSUE_TYPE if self.is_update else jira.SUBMISSION_ISSUE_TYPE

    @property
    def url_label(self):
        return 'Pull request' if self.is_update else 'Extension URL'

    @property
    def summary_label(self):
        return 'Version' if self.is_update else 'Name'

    @property
    def desired_summary(self):
        return f'v{self.version_number}' if self.is_update else self.title

    @property
    def desired_bapp_url(self):
        return self.url if self.is_update else repository_url(self.url)


@dataclass(frozen=True)
class Outcome:
    status: str
    ticket_key: str = ''
    applied: tuple = ()
    reason: str = ''
    held: dict = field(default_factory=dict)


def find_ticket(client, edit):
    try:
        matches = client.find_by_url_field(
            edit.ticket_issue_type, jira.GITHUB_ISSUE_FIELD, edit.issue_url,
            ['summary', jira.BAPP_URL_FIELD, jira.GITHUB_ISSUE_FIELD])
    except error.HTTPError as e:
        raise NeedsManualIntervention(
            f'Jira search for the associated ticket failed: {e.code}.')

    if not matches:
        raise TicketNotCreated(
            f'No {jira.PROJECT} ticket has been created for {edit.issue_url} yet.')
    if len(matches) > 1:
        keys = ', '.join(ticket['key'] for ticket in matches)
        raise NeedsManualIntervention(
            f'Multiple {jira.PROJECT} tickets ({keys}) are associated with {edit.issue_url}.')
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
                f'The edited URL came through empty, so {ticket["key"]} has '
                f'been left as it was.')
        if normalize_url(held.get(jira.BAPP_URL_FIELD)) != normalize_url(bapp_url):
            fields[jira.BAPP_URL_FIELD] = bapp_url
            applied.append(edit.url_label)

    return fields, applied


def sync(client, edit):
    try:
        ticket = find_ticket(client, edit)

        held = ticket.get('fields', {})
        if edit.url_changed and not edit.is_maintainer:
            return Outcome('flagged', ticket_key=ticket['key'], held=held)

        fields, applied = changes_to_apply(edit, ticket)
        if not fields:
            return Outcome('unchanged', ticket_key=ticket['key'], held=held)

        try:
            client.update_issue(ticket['key'], fields)
        except error.HTTPError as e:
            raise NeedsManualIntervention(
                f'Failed to update {ticket["key"]}: {e.code} {e.read().decode(errors="replace")}')

        return Outcome('updated', ticket_key=ticket['key'],
                       applied=tuple(applied), held=held)

    except TicketNotCreated as e:
        return Outcome('absent', reason=str(e))
    except NeedsManualIntervention as e:
        return Outcome('manual', reason=str(e))
    except Exception as e:
        return Outcome(
            'manual', reason=f'Unexpected error while updating the associated ticket: {e}')


def changed_fields(edit, outcome):
    """
    What the edit did to each field, reading the before-value from the ticket so
    that no unsanitized issue content is quoted back to the team.
    """
    def moved(before, after):
        after = after or '(none)'
        return f'{before} -> {after}' if before else after

    fields = {}
    if edit.summary_changed:
        fields[edit.summary_label] = moved(outcome.held.get('summary'), edit.desired_summary)
    if edit.url_changed:
        fields[edit.url_label] = moved(outcome.held.get(jira.BAPP_URL_FIELD),
                                       edit.desired_bapp_url)
    return fields


def worth_reporting(edit, outcome):
    """A maintainer's edit passes quietly unless it could not be applied."""
    if edit.validation_error:
        return True
    if outcome.status not in ('updated', 'flagged', 'manual', 'absent'):
        return False
    return not edit.is_maintainer or outcome.status in ('manual', 'absent')


def zoom_payload(edit, outcome):
    """The notification for this outcome, or None when there is nothing to report."""
    if not worth_reporting(edit, outcome):
        return None

    alert = 'Submission details edited'

    if outcome.status == 'absent':
        alert = 'Submission edited before its ticket was created'
        detail = {'Action': 'No ticket exists for this submission yet - '
                            'use these details when creating it.'}
    elif edit.is_maintainer:
        alert = 'Maintainer edit could not be applied'
        detail = {'Reason': edit.validation_error or outcome.reason or 'Unknown.',
                  'Action': '⚠️ Apply the edit to the associated ticket by hand.'}
    elif edit.validation_error:
        detail = {'Validation Error': f'❌ {edit.validation_error}',
                  'Action': '⚠️ Ticket left unchanged - the edited details were rejected.'}
    elif outcome.status == 'flagged':
        alert = 'Submission repointed at different code'
        detail = {'Ticket': f'{outcome.ticket_key} (unchanged)',
                  'Action': '⚠️ Treat as a new submission - review has not been re-run '
                            'and the ticket has NOT been updated.'}
    elif outcome.status == 'updated':
        detail = {'Ticket': outcome.ticket_key,
                  'Updated': f'✅ {", ".join(outcome.applied)}'}
    else:
        detail = {'Action': '⚠️ Apply the edited details to the associated ticket.'}
        if outcome.reason:
            detail['Reason'] = outcome.reason

    return {
        'Alert': alert,
        'Extension': edit.title,
        'Issue': edit.issue_url,
        'Edited by': f'{edit.editor} ({edit.editor_access} access)',
        **changed_fields(edit, outcome),
        **detail,
    }


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
    elif outcome.status == 'absent':
        print(f'::notice::{outcome.reason}')
    else:
        print(f'::warning::{outcome.reason}')


if __name__ == '__main__':
    edit = Edit.from_environment()

    if edit.validation_error:
        print(f'::warning::{edit.validation_error}')
        outcome = Outcome('rejected')
    else:
        outcome = sync(jira.JiraClient.from_environment(), edit)
        report(outcome)

    payload = zoom_payload(edit, outcome)

    set_output('status', outcome.status)
    set_output('jira_key', outcome.ticket_key)
    set_output('zoom_payload', encode_payload(payload) if payload else '')

    sys.exit(0)
