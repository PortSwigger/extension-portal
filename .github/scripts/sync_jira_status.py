#!/usr/bin/env python3

"""Moves a submission's Jira ticket when its portal issue is closed or reopened."""

import os
import sys
from dataclasses import dataclass
from urllib import error

import jira
import notification as note
from github_actions_utils import set_output

DECLINED = {'resolution': {'id': jira.DECLINED_RESOLUTION}}
EITHER_TICKET_TYPE = (jira.SUBMISSION_ISSUE_TYPE, jira.UPDATE_SUBTASK_ISSUE_TYPE)
OUTCOMES_NEEDING_A_PERSON = ('manual', 'flagged')


class NeedsManualIntervention(Exception):
    def __init__(self, message, ticket_key=''):
        super().__init__(message)
        self.ticket_key = ticket_key

    pass


class TicketNotCreated(NeedsManualIntervention):
    pass


@dataclass(frozen=True)
class StateChange:
    issue_url: str
    action: str
    state_reason: str
    issue_type_name: str
    title: str
    actor: str

    @classmethod
    def from_environment(cls, env=None):
        env = os.environ if env is None else env
        return cls(
            issue_url=env.get('ISSUE_URL', '').strip(),
            action=env.get('ISSUE_ACTION', '').strip().lower(),
            state_reason=env.get('STATE_REASON', '').strip().lower(),
            issue_type_name=env.get('ISSUE_TYPE_NAME', '').strip(),
            title=env.get('ISSUE_TITLE', '').strip(),
            actor=env.get('ACTOR_LOGIN', '').strip() or '(unknown)',
        )

    @property
    def subject(self):
        return note.subject_of(self.issue_type_name)

    @property
    def ticket_issue_types(self):
        if self.issue_type_name == 'Update':
            return (jira.UPDATE_SUBTASK_ISSUE_TYPE,)
        if self.issue_type_name == 'Extension':
            return (jira.SUBMISSION_ISSUE_TYPE,)
        return EITHER_TICKET_TYPE

    @property
    def reopens_the_submission(self):
        return self.action == 'reopened'

    @property
    def parks_the_submission(self):
        return self.action == 'closed' and self.state_reason != 'completed'


@dataclass(frozen=True)
class Decision:
    move_to: str = ''
    fields: dict = None
    outcome: str = ''
    because: str = ''

    @classmethod
    def move(cls, status, fields=None):
        return cls(move_to=status, fields=fields)

    @classmethod
    def leave(cls, outcome, because):
        return cls(outcome=outcome, because=because)

    @property
    def moves(self):
        return bool(self.move_to)


@dataclass(frozen=True)
class Outcome:
    status: str
    ticket_key: str = ''
    moved_to: str = ''
    reason: str = ''


def decide(change, status_id):
    if change.reopens_the_submission:
        if status_id == jira.REJECTED_STATUS:
            return Decision.move(jira.FEEDBACK_STATUS)
        if status_id == jira.APPROVED_STATUS:
            return Decision.leave('flagged', 'it was already approved')
        return Decision.leave('unchanged', 'it is already open')

    if status_id == jira.REJECTED_STATUS:
        return Decision.leave('unchanged', 'it is already closed')
    if status_id == jira.APPROVED_STATUS:
        return Decision.leave('skipped', 'it was already approved')
    return Decision.move(jira.REJECTED_STATUS, DECLINED)


def find_ticket(client, change):
    matches = []
    try:
        for issue_type in change.ticket_issue_types:
            matches += client.find_by_url_field(
                issue_type, jira.GITHUB_ISSUE_FIELD, change.issue_url,
                ['status', jira.GITHUB_ISSUE_FIELD])
    except error.HTTPError as e:
        raise NeedsManualIntervention(
            f'Jira search for the associated ticket failed: {e.code}.')

    if not matches:
        raise TicketNotCreated(
            f'No {jira.PROJECT} ticket has been created for {change.issue_url} yet.')
    if len(matches) > 1:
        keys = ', '.join(ticket['key'] for ticket in matches)
        raise NeedsManualIntervention(
            f'Multiple {jira.PROJECT} tickets ({keys}) are associated with {change.issue_url}.')
    return matches[0]


def current_status(ticket):
    return ((ticket.get('fields') or {}).get('status') or {}).get('id')


def apply_decision(client, change, ticket, decision):
    try:
        client.transition_to_status(ticket['key'], decision.move_to, decision.fields)
    except jira.TransitionUnavailable:
        raise NeedsManualIntervention(
            f'{ticket["key"]} offers no transition to where this '
            f'{change.action} issue belongs.', ticket['key'])
    except error.HTTPError as e:
        raise NeedsManualIntervention(
            f'Failed to move {ticket["key"]}: {e.code} '
            f'{e.read().decode(errors="replace")}', ticket['key'])

    return Outcome('moved', ticket_key=ticket['key'], moved_to=decision.move_to)


def sync(client, change):
    if not change.reopens_the_submission and not change.parks_the_submission:
        return Outcome('skipped', reason='the close is recorded in Jira by hand')

    try:
        ticket = find_ticket(client, change)

        decision = decide(change, current_status(ticket))
        if not decision.moves:
            return Outcome(decision.outcome, ticket_key=ticket['key'],
                           reason=decision.because)

        return apply_decision(client, change, ticket, decision)

    except TicketNotCreated as e:
        return Outcome('absent', reason=str(e))
    except NeedsManualIntervention as e:
        return Outcome('manual', ticket_key=e.ticket_key, reason=str(e))
    except Exception as e:
        return Outcome(
            'manual', reason=f'Unexpected error while moving the associated ticket: {e}')


def worth_reporting(outcome):
    return outcome.status in OUTCOMES_NEEDING_A_PERSON


def notification_for(change, outcome):
    if not worth_reporting(outcome):
        return None

    event = note.REOPENED if change.reopens_the_submission else note.CLOSED
    reported = note.Notification(
        event, change.subject, note.ATTENTION,
        extension=change.title,
        issue_url=change.issue_url,
        ticket=outcome.ticket_key,
        actor=change.actor,
        actor_did=change.action.capitalize())

    if outcome.status == 'flagged':
        return reported.because(
            reason='This BApp was already approved, so its ticket was left where it is.',
            action='Decide whether the ticket should come back too.')

    moved = 'back into' if change.reopens_the_submission else 'out of'
    return reported.because(
        reason=outcome.reason or 'Unknown.',
        action=f'Move the associated ticket {moved} the review queue by hand.')


def report(outcome):
    if outcome.status == 'moved':
        print(f'::notice::Moved {outcome.ticket_key} to {outcome.moved_to}.')
    elif outcome.status in ('unchanged', 'skipped'):
        print(f'::notice::{outcome.ticket_key or "The associated ticket"} was '
              f'left as it is: {outcome.reason}.')
    elif outcome.status == 'absent':
        print(f'::notice::{outcome.reason}')
    elif outcome.status == 'flagged':
        print(f'::warning::{outcome.ticket_key} left unchanged: {outcome.reason}.')
    else:
        print(f'::warning::{outcome.reason}')


if __name__ == '__main__':
    change = StateChange.from_environment()
    outcome = sync(jira.JiraClient.from_environment(), change)
    report(outcome)

    reported = notification_for(change, outcome)

    set_output('status', outcome.status)
    set_output('jira_key', outcome.ticket_key)
    set_output('notification', note.encode(reported) if reported else '')

    sys.exit(0)
