#!/usr/bin/env python3

"""
Creates the Jira ticket for a new extension submission, recording the repository
as its bapp url so update subtasks can later find it as their parent.

Exits non-zero if the ticket cannot be created, so the submission is reported as
failed rather than silently going unreviewed.
"""

import os
import sys

import jira
from github_actions_utils import set_output


def main():
    fields = {
        'project': {'key': jira.PROJECT},
        'issuetype': {'id': jira.SUBMISSION_ISSUE_TYPE},
        'summary': os.environ.get('TITLE', ''),
        jira.BAPP_URL_FIELD: os.environ.get('REPO_URL', ''),
        jira.GITHUB_ISSUE_FIELD: os.environ.get('ISSUE_URL', ''),
    }

    try:
        key = jira.JiraClient.from_environment().create_issue(fields)
    except Exception as e:
        print(f'::error::Failed to create the Jira ticket: {e}', file=sys.stderr)
        sys.exit(1)

    print(f'::notice::Created Jira ticket {key}.')
    set_output('jira_key', key)


if __name__ == '__main__':
    main()
