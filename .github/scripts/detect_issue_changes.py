#!/usr/bin/env python3

"""
Decides whether an edit changed anything the Jira ticket holds: its summary
(the issue title, or the version number for updates) or its bapp url.

An edit touching neither stops the pipeline here. Both revisions are in the
webhook payload, so this needs no network access.
"""

import os

from extract_issue_fields import extract_issue_fields
from github_actions_utils import output_flag, set_output
from github_urls import normalize_url


def summary_of(fields):
    """The value the ticket summary is built from for this submission type."""
    if fields['type'] == 'extension-update':
        return (fields['version_number'] or '').strip()
    return (fields['title'] or '').strip()


def detect_changes(current, previous):
    """Which of the ticket's fields two revisions of an issue disagree on."""
    summary_changed = summary_of(current) != summary_of(previous)
    url_changed = normalize_url(current['url']) != normalize_url(previous['url'])
    return {
        'summary_changed': summary_changed,
        'url_changed': url_changed,
        'any_changed': summary_changed or url_changed,
    }


def log_changes(changes, current, previous):
    if not changes['any_changed']:
        print('Nothing the ticket holds was edited - stopping here.')
        return

    print(f'Summary: {summary_of(previous)!r} -> {summary_of(current)!r}')
    print(f'URL: {previous["url"]!r} -> {current["url"]!r}')


def main():
    issue_type_name = os.environ.get('ISSUE_TYPE_NAME', '')
    body = os.environ.get('ISSUE_BODY', '')
    title = os.environ.get('ISSUE_TITLE', '')

    current = extract_issue_fields(body=body, title=title, issue_type_name=issue_type_name)
    previous = extract_issue_fields(
        body=os.environ.get('PREVIOUS_BODY', '') or body,
        title=os.environ.get('PREVIOUS_TITLE', '') or title,
        issue_type_name=issue_type_name,
    )

    changes = detect_changes(current, previous)
    log_changes(changes, current, previous)

    set_output('summary_changed', output_flag(changes['summary_changed']))
    set_output('url_changed', output_flag(changes['url_changed']))
    set_output('any_changed', output_flag(changes['any_changed']))


if __name__ == '__main__':
    main()
