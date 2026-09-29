#!/usr/bin/env python3

"""
Finds the BAPP ticket that already covers an arriving submission.

A ticket holding this extension's repository - or, for an update, its pull
request - as its bapp url is the record of an earlier submission. What that
means depends on whether the ticket also names a portal issue:

  named      this submission duplicates that issue, and is closed as one.
  unnamed    the ticket was raised outside the portal, and the team is asked to
             link the two by hand. No second ticket is raised against the same
             url: two of those would leave every later update for the extension
             without an unambiguous parent.

Nothing is linked automatically, because a submission shows nothing about who
speaks for an extension - the repository need only exist - and the ticket it
would take over then follows that issue's own closing and reopening.

Running before the submission is validated turns a duplicate away without first
building a stranger's repository.

A search that cannot be completed lets the submission through untouched, since
refusing would turn a Jira outage into a wall of rejected first-time
submissions.

Reads TYPE, URL and ISSUE_URL from the environment and writes whichever of
original_issue_url and jira_key applies.
"""

import os

import jira
from github_actions_utils import set_output
from github_urls import normalize_url, repository_url

TICKET_TYPES = {
    'extension-submission': jira.SUBMISSION_ISSUE_TYPE,
    'extension-update': jira.UPDATE_SUBTASK_ISSUE_TYPE,
}


def bapp_url(submission_type, url):
    """The url a ticket for this submission would hold."""
    if submission_type == 'extension-submission':
        return repository_url(url)
    return url


def portal_issue(ticket):
    return (ticket.get('fields') or {}).get(jira.GITHUB_ISSUE_FIELD) or ''


def raised_first(tickets):
    return min(tickets, key=lambda ticket: int(ticket['key'].rpartition('-')[2]))


def earlier_submissions(client, submission_type, url, issue_url):
    """Tickets of this kind already holding `url`, less this issue's own."""
    tickets = client.find_by_url_field(
        TICKET_TYPES[submission_type], jira.BAPP_URL_FIELD, url,
        [jira.BAPP_URL_FIELD, jira.GITHUB_ISSUE_FIELD])
    return [ticket for ticket in tickets
            if normalize_url(portal_issue(ticket)) != normalize_url(issue_url)]


def main():
    submission_type = os.environ.get('TYPE', '')
    issue_url = os.environ.get('ISSUE_URL', '')
    url = bapp_url(submission_type, os.environ.get('URL', ''))

    if submission_type not in TICKET_TYPES or not url:
        return

    try:
        tickets = earlier_submissions(
            jira.JiraClient.from_environment(), submission_type, url, issue_url)
    except Exception as e:
        print(f'::warning::The search for earlier submissions failed: {e}')
        return

    on_the_portal = [ticket for ticket in tickets if portal_issue(ticket)]
    if on_the_portal:
        original = portal_issue(raised_first(on_the_portal))
        print(f'::notice::Already submitted as {original}.')
        set_output('original_issue_url', original)
    elif tickets:
        covering = raised_first(tickets)['key']
        print(f'::notice::{covering} already covers this submission.')
        set_output('jira_key', covering)


if __name__ == '__main__':
    main()
