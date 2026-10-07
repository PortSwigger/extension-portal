#!/usr/bin/env python3

"""What a producer reports; slack_message.py decides how it looks."""

import base64
import json
from dataclasses import asdict, dataclass, field, replace

EXTENSION = 'Extension'
UPDATE = 'Update'
UNTYPED = 'Submission'

ROUTINE = 'routine'
ATTENTION = 'attention'
FAILURE = 'failure'

SUBMITTED = 'submitted'
FAILED = 'failed'
REOPENED = 'reopened'
CHANGED = 'changed'
CLOSED = 'closed'

HEADLINES = {
    SUBMITTED: 'New submission',
    FAILED: 'Submission failed',
    REOPENED: 'Submission reopened',
    CHANGED: 'Submission changed',
    CLOSED: 'Submission closed',
}


def subject_of(issue_type_name):
    # GitHub records no type unless the submitter has push access.
    name = (issue_type_name or '').strip()
    return name if name in (EXTENSION, UPDATE) else UNTYPED


@dataclass(frozen=True)
class Notification:
    event: str
    subject: str = UNTYPED
    severity: str = ROUTINE

    extension: str = ''
    version: str = ''
    ticket: str = ''

    issue_url: str = ''
    pr_url: str = ''
    duplicate_url: str = ''

    actor: str = ''
    actor_did: str = ''
    actor_note: str = ''

    reason: str = ''
    action: str = ''
    changes: dict = field(default_factory=dict)

    @property
    def alert(self):
        said = HEADLINES.get(self.event, HEADLINES[SUBMITTED])
        return said if self.subject == UNTYPED else f'{said}: {self.subject.lower()}'

    def because(self, reason='', action=''):
        return replace(self, reason=reason.strip() or self.reason,
                       action=action.strip() or self.action)

    def moving(self, changes):
        moved = {label: str(value).strip() for label, value in changes.items()
                 if str(value).strip()}
        return replace(self, changes={**self.changes, **moved})


def encode(notification):
    # Base64 so that GitHub's secret masking cannot corrupt fragments of it.
    return base64.b64encode(json.dumps(asdict(notification)).encode()).decode()


def decode(encoded):
    return Notification(**json.loads(base64.b64decode(encoded).decode()))
