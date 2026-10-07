#!/usr/bin/env python3

"""Reports what the pipeline made of a new submission."""

import os
import sys
from dataclasses import replace

import notification as note
from github_actions_utils import set_output

UPDATE = 'extension-update'


class Submission:
    def __init__(self, env=None):
        env = os.environ if env is None else env

        def value(name):
            return env.get(name, '').strip()

        self.is_update = value('SUBMISSION_TYPE') == UPDATE
        self.issue_url = value('ISSUE_URL')
        self.title = value('TITLE')
        self.version_number = value('VERSION_NUMBER')
        self.pr_url = value('PR_URL')
        self.submitter = value('SUBMITTER_LOGIN')
        self.jira_key = value('JIRA_KEY')
        self.status = value('STATUS')
        self.reason = value('REASON')
        self.review_outcome = value('REVIEW_OUTCOME')
        self.validation_error = value('VALIDATION_ERROR')
        self.duplicate_of = value('ORIGINAL_ISSUE_URL')
        self.prior_ticket = value('PRIOR_TICKET')

    @property
    def subject(self):
        return note.UPDATE if self.is_update else note.EXTENSION

    @property
    def review_started(self):
        return self.review_outcome == 'success'

    @property
    def subtask_was_raised(self):
        return self.status == 'automated'


def about(submission, event, severity, **extra):
    return note.Notification(
        event, submission.subject, severity,
        extension=submission.title,
        version=submission.version_number,
        issue_url=submission.issue_url,
        pr_url=submission.pr_url if submission.is_update else '',
        actor=submission.submitter,
        actor_did='Submitted',
        **extra)


def reached_the_queue(submission):
    if not submission.is_update and not submission.jira_key:
        return about(submission, note.FAILED, note.FAILURE).because(
            reason='The ticket could not be created.',
            action='Raise it by hand - this submission is not in the review queue.')

    if submission.is_update and not submission.subtask_was_raised:
        return about(submission, note.FAILED, note.ATTENTION).because(
            reason=submission.reason or 'No single parent ticket matched this update.',
            action='Create the update ticket by hand.')

    arrived = about(submission, note.SUBMITTED, note.ROUTINE, ticket=submission.jira_key)
    if submission.review_started:
        return arrived

    return replace(arrived, severity=note.ATTENTION).because(
        reason='The review workflow was not triggered.',
        action='Start the review by hand.')


def outcome(submission):
    if submission.duplicate_of:
        return about(submission, note.FAILED, note.ROUTINE,
                     duplicate_url=submission.duplicate_of).because(
            reason='This has already been submitted.')

    if submission.validation_error:
        return about(submission, note.FAILED, note.ROUTINE).because(
            reason=submission.validation_error)

    if submission.prior_ticket:
        return about(submission, note.FAILED, note.ATTENTION,
                     ticket=submission.prior_ticket).because(
            reason=f'{submission.prior_ticket} already covers this '
                   f'{submission.subject.lower()}.',
            action='Link it to this submission by hand.')

    return reached_the_queue(submission)


if __name__ == '__main__':
    set_output('notification', note.encode(outcome(Submission())))

    sys.exit(0)
