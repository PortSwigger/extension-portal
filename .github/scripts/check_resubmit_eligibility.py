#!/usr/bin/env python3

"""
Decides whether a /resubmit comment should re-run the submission pipeline.

Three things must hold: the comment came from the submitter or a maintainer,
the issue is an extension submission, and no ticket exists for it yet. That
last check is what stops a resubmission duplicating a submission that already
succeeded, so a Jira lookup that cannot be completed refuses rather than risks
the duplicate.
"""

import os

import jira
from github_actions_utils import output_flag, set_output

MAINTAINER_ASSOCIATIONS = frozenset({'OWNER', 'MEMBER', 'COLLABORATOR'})

APPROVED = ''
NOT_AUTHORIZED = 'resubmit.not-authorized'
NOT_ELIGIBLE = 'resubmit.not-eligible'
LOOKUP_FAILED = 'resubmit.lookup-failed'
ALREADY_PROCESSED = 'resubmit.already-processed'


def already_has_a_ticket(client, issue_url):
    return bool(client.find_by_url_field(
        jira.SUBMISSION_ISSUE_TYPE, jira.GITHUB_ISSUE_FIELD, issue_url,
        [jira.GITHUB_ISSUE_FIELD]))


def decide(commenter, author, association, issue_type_name, issue_url, client):
    """The template key explaining a refusal, or APPROVED to go ahead."""
    if commenter != author and association not in MAINTAINER_ASSOCIATIONS:
        print(f'{commenter} is not authorised to resubmit.')
        return NOT_AUTHORIZED

    if issue_type_name != 'Extension':
        print(f'Issue type "{issue_type_name}" is not a resubmittable extension submission.')
        return NOT_ELIGIBLE

    try:
        found = already_has_a_ticket(client, issue_url)
    except Exception as e:
        print(f'Jira lookup failed: {e}.')
        return LOOKUP_FAILED

    if found:
        print(f'A {jira.PROJECT} ticket already exists for this issue.')
        return ALREADY_PROCESSED

    print('Resubmission approved.')
    return APPROVED


def main():
    template_key = decide(
        commenter=os.environ.get('COMMENTER', ''),
        author=os.environ.get('ISSUE_AUTHOR', ''),
        association=os.environ.get('AUTHOR_ASSOCIATION', ''),
        issue_type_name=os.environ.get('ISSUE_TYPE_NAME', ''),
        issue_url=os.environ.get('ISSUE_URL', ''),
        client=jira.JiraClient.from_environment(),
    )

    set_output('proceed', output_flag(template_key == APPROVED))
    set_output('template_key', template_key)


if __name__ == '__main__':
    main()
