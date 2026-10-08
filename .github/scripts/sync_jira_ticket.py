#!/usr/bin/env python3

"""
Applies an edited issue to its associated Jira ticket, or flags it for the team.

Only a maintainer may change the bapp url: it is the artifact that was
reviewed, so a submitter changing it makes this a new submission.
"""

import os
import sys
from dataclasses import dataclass, field, replace
from urllib import error

import jira
import notification as note
from github_actions_utils import set_output
from github_urls import normalize_url, repository_url


class NeedsManualIntervention(Exception):
    def __init__(self, message, ticket_key=''):
        super().__init__(message)
        self.ticket_key = ticket_key



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
    def subject(self):
        return note.UPDATE if self.is_update else note.EXTENSION

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
                f'empty, so {ticket["key"]} has been left as it was.', ticket['key'])
        if (held.get('summary') or '') != summary:
            fields['summary'] = summary
            applied.append('Summary')

    if edit.url_changed:
        bapp_url = edit.desired_bapp_url
        if not bapp_url:
            raise NeedsManualIntervention(
                f'The edited URL came through empty, so {ticket["key"]} has '
                f'been left as it was.', ticket['key'])
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
                f'Failed to update {ticket["key"]}: {e.code} '
                f'{e.read().decode(errors="replace")}', ticket['key'])

        return Outcome('updated', ticket_key=ticket['key'],
                       applied=tuple(applied), held=held)

    except TicketNotCreated as e:
        return Outcome('absent', reason=str(e))
    except NeedsManualIntervention as e:
        return Outcome('manual', ticket_key=e.ticket_key, reason=str(e))
    except Exception as e:
        return Outcome(
            'manual', reason=f'Unexpected error while updating the associated ticket: {e}')


def changed_fields(edit, outcome):
    """Read from the ticket, so no unsanitized issue content is quoted back."""
    def moved(before, after):
        after = after or '(none)'
        return f'{before} → {after}' if before else after

    fields = {}
    if edit.summary_changed:
        fields[edit.summary_label] = moved(outcome.held.get('summary'), edit.desired_summary)
    if edit.url_changed:
        fields[edit.url_label] = moved(outcome.held.get(jira.BAPP_URL_FIELD),
                                       edit.desired_bapp_url)
    return fields


def worth_reporting(edit, outcome):
    if edit.validation_error:
        return True
    if outcome.status not in ('updated', 'flagged', 'manual', 'absent'):
        return False
    return not edit.is_maintainer or outcome.status in ('manual', 'absent')


def notification_for(edit, outcome):
    if not worth_reporting(edit, outcome):
        return None

    edited = note.Notification(
        note.CHANGED, edit.subject, note.ATTENTION,
        extension=edit.title,
        version=edit.version_number if edit.is_update else '',
        issue_url=edit.issue_url,
        ticket=outcome.ticket_key,
        actor=edit.editor,
        actor_did='Edited',
        actor_note=f'{edit.editor_access} access',
    ).moving(changed_fields(edit, outcome))

    if outcome.status == 'absent':
        return edited.because(
            reason='No ticket exists for this submission yet.',
            action='Use these details when creating it.')

    if edit.is_maintainer:
        return edited.because(
            reason=edit.validation_error or outcome.reason or 'Unknown.',
            action='Apply the edit to the associated ticket by hand.')

    if edit.validation_error:
        return edited.because(
            reason=edit.validation_error,
            action='Ticket left unchanged - the edited details were rejected.')

    if outcome.status == 'flagged':
        return edited.because(
            reason='The submitter pointed this at different code, so the ticket was '
                   'left where it is and the review has not been re-run.',
            action='Treat it as a new submission.')

    if outcome.status == 'updated':
        return replace(edited, severity=note.ROUTINE)

    return edited.because(
        reason=outcome.reason or 'Unknown.',
        action='Apply the edited details to the associated ticket.')


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

    reported = notification_for(edit, outcome)

    set_output('status', outcome.status)
    set_output('jira_key', outcome.ticket_key)
    set_output('notification', note.encode(reported) if reported else '')

    sys.exit(0)
