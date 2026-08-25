#!/usr/bin/env python3

"""
Creates the "BApp update" subtask under the submission ticket for the extension
being updated, found by the source repository recorded as its bapp url.

Anything other than exactly one matching parent hands over to the team, who are
alerted via Zoom. This never fails the submission.
"""

import os

import jira
from github_actions_utils import set_output


class NeedsManualIntervention(Exception):
    """The subtask could not be created with confidence, so the team must do it."""


def find_parent(client, source_url):
    try:
        matches = client.find_by_url_field(
            jira.SUBMISSION_ISSUE_TYPE, jira.BAPP_URL_FIELD, source_url,
            [jira.BAPP_URL_FIELD])
    except Exception as e:
        raise NeedsManualIntervention(f'Jira search for the parent ticket failed: {e}')

    if not matches:
        raise NeedsManualIntervention(
            f'No parent {jira.PROJECT} ticket found with bapp url {source_url}.')
    if len(matches) > 1:
        keys = ', '.join(ticket['key'] for ticket in matches)
        raise NeedsManualIntervention(
            f'Multiple parent {jira.PROJECT} tickets found ({keys}) '
            f'for bapp url {source_url}.')
    return matches[0]['key']


def create_subtask(client, parent_key, version, pull_request_url, issue_url):
    try:
        return client.create_issue({
            'project': {'key': jira.PROJECT},
            'issuetype': {'id': jira.UPDATE_SUBTASK_ISSUE_TYPE},
            'parent': {'key': parent_key},
            'summary': f'v{version}',
            jira.BAPP_URL_FIELD: pull_request_url,
            jira.GITHUB_ISSUE_FIELD: issue_url,
        })
    except Exception as e:
        raise NeedsManualIntervention(f'Failed to create the BApp update subtask: {e}')


def hand_over(reason):
    """Leave the subtask to the team, who are alerted by the Zoom notification."""
    print(f'::warning::{reason}')
    set_output('status', 'manual')
    set_output('reason', reason)


def main():
    source_url = os.environ.get('SOURCE_URL', '')
    try:
        client = jira.JiraClient.from_environment()
        parent_key = find_parent(client, source_url)
        print(f'::notice::Parent {jira.PROJECT} ticket: {parent_key}.')

        key = create_subtask(
            client, parent_key,
            os.environ.get('VERSION_NUMBER', '').strip(),
            os.environ.get('PR_URL', ''),
            os.environ.get('ISSUE_URL', ''))
    except NeedsManualIntervention as e:
        return hand_over(str(e))
    except Exception as e:
        return hand_over(f'Unexpected error while creating the update ticket: {e}')

    print(f'::notice::Created BApp update subtask {key}.')
    set_output('status', 'automated')
    set_output('jira_key', key)


if __name__ == '__main__':
    main()
