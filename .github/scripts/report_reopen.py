#!/usr/bin/env python3

"""Reports how the review board fared when a command reopened a submission."""

import os
import sys

import notification as note
from github_actions_utils import set_output

RESUBMIT = 'resubmit'


class Reopen:
    def __init__(self, env=None):
        env = os.environ if env is None else env

        def value(name):
            return env.get(name, '').strip()

        self.command = value('COMMAND').lower()
        self.subject = note.subject_of(value('ISSUE_TYPE_NAME'))
        self.issue_url = value('ISSUE_URL')
        self.title = value('ISSUE_TITLE')
        self.version_number = value('VERSION_NUMBER')
        self.ticket = value('JIRA_KEY')
        self.actor = value('ACTOR_LOGIN')
        self.board_warning = value('BOARD_WARNING')

    @property
    def is_resubmit(self):
        return self.command == RESUBMIT

    @property
    def already_announced_by_the_pipeline_it_restarts(self):
        return self.is_resubmit

    @property
    def target_column(self):
        return 'Concept review' if self.is_resubmit else 'the review board'


def about(reopen, severity):
    return note.Notification(
        note.REOPENED, reopen.subject, severity,
        extension=reopen.title,
        version=reopen.version_number,
        issue_url=reopen.issue_url,
        ticket=reopen.ticket,
        actor=reopen.actor,
        actor_did='Resubmitted' if reopen.is_resubmit else 'Reopened')


def outcome(reopen):
    if reopen.board_warning:
        return about(reopen, note.ATTENTION).because(
            reason=reopen.board_warning,
            action=f'Put the card back in {reopen.target_column} by hand.')

    if reopen.already_announced_by_the_pipeline_it_restarts:
        return None

    return about(reopen, note.ROUTINE)


if __name__ == '__main__':
    reported = outcome(Reopen())
    set_output('notification', note.encode(reported) if reported else '')

    sys.exit(0)
