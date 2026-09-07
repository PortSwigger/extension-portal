#!/usr/bin/env python3

"""
Extracts the submitted values from an extension submission or update issue.

Shared by the created-issue and edited-issue pipelines so both read the issue
form the same way. detect_issue_changes.py imports extract_issue_fields() to
read two revisions of an issue and work out what an edit actually changed.

The submitted values are checked by the sanitize-inputs action, which never sees
the issue body: checkboxes are read here, and which of them a submission must
record is declared there.

A submitter without push access cannot set an issue type - GitHub drops it
silently rather than failing - so an issue raised through the API arrives with
none and the form's field headings are what identify it. The created-issue
pipeline records the type it infers, so /resubmit and edit syncing work
afterwards.

Reads ISSUE_BODY, ISSUE_TITLE and ISSUE_TYPE_NAME from the environment and
writes the extracted values as GitHub Actions outputs.
"""

import json
import os
import re
import sys

from github_actions_utils import set_output

# An unanswered optional field in a GitHub issue form comes through as this.
EMPTY_RESPONSE = '_No response_'

COMPATIBILITY_OPTIONS = ['Community', 'DAST', 'Burp AI']

AUTHOR_PATTERN = re.compile(r'### Author display name\s+([^\n]+)')
VERSION_PATTERN = re.compile(r'### Version number\s+([^\n]+)')
EXTENSION_URL_PATTERN = re.compile(r'### Extension URL\s+(\S+)')
PULL_REQUEST_URL_PATTERN = re.compile(r'### Pull request URL\s+(\S+)')

SUBMISSION_TYPES = {
    'Extension': 'extension-submission',
    'Update': 'extension-update',
}

CHECKED_BOX = '- [x]'

SANITIZER_CONFIRMATION_KEYS = {
    'I have permission from all relevant persons': 'eula',
    'I have read and understood': 'acceptance-criteria',
}


def submission_type(issue_type_name, body=''):
    """Our submission type, from the issue's type or else the headings in its body."""
    if issue_type_name:
        return SUBMISSION_TYPES.get(issue_type_name, '')
    if EXTENSION_URL_PATTERN.search(body or ''):
        return SUBMISSION_TYPES['Extension']
    if PULL_REQUEST_URL_PATTERN.search(body or ''):
        return SUBMISSION_TYPES['Update']
    return ''


def github_issue_type(submission_type_):
    """The GitHub issue type name for one of our submission types."""
    return next(
        (name for name, type_ in SUBMISSION_TYPES.items() if type_ == submission_type_),
        '')


def extract_issue_fields(body='', title='', issue_type_name=''):
    """
    Pull the submitted values out of an issue.

    Args:
        body: Issue body to read the form fields from.
        title: Issue title.
        issue_type_name: GitHub issue type name ("Extension" or "Update").

    Returns:
        dict with keys: type, title, author, url, version_number,
        product_compatibility (a list).
    """
    body = body or ''

    def field(pattern):
        match = pattern.search(body)
        value = match.group(1).strip() if match else ''
        return '' if value == EMPTY_RESPONSE else value

    type_ = submission_type(issue_type_name, body)

    if type_ == 'extension-submission':
        url = field(EXTENSION_URL_PATTERN)
    elif type_ == 'extension-update':
        url = field(PULL_REQUEST_URL_PATTERN)
    else:
        url = ''

    return {
        'type': type_,
        'title': title or '',
        'author': field(AUTHOR_PATTERN),
        'url': url,
        'version_number': field(VERSION_PATTERN),
        'product_compatibility': [
            label for label in COMPATIBILITY_OPTIONS
            if f'- [x] {label}' in body or f'- [X] {label}' in body
        ],
    }


def checked_confirmations(body):
    """The keys of the confirmations the body ticks, sorted."""
    ticked = set()
    for line in (body or '').splitlines():
        stripped = line.strip()
        if not stripped[:len(CHECKED_BOX)].lower() == CHECKED_BOX:
            continue
        label = stripped[len(CHECKED_BOX):].strip()
        ticked.update(
            key for text, key in SANITIZER_CONFIRMATION_KEYS.items()
            if label.startswith(text))
    return sorted(ticked)


if __name__ == '__main__':
    try:
        body = os.environ.get('ISSUE_BODY', '')
        fields = extract_issue_fields(
            body=body,
            title=os.environ.get('ISSUE_TITLE', ''),
            issue_type_name=os.environ.get('ISSUE_TYPE_NAME', ''),
        )
        confirmations = checked_confirmations(body)
    except Exception as e:  # pragma: no cover - defensive
        error_msg = str(e)
        print(f'::error::{error_msg}', file=sys.stderr)
        set_output('error_message', error_msg)
        sys.exit(1)

    set_output('type', fields['type'])
    set_output('title', fields['title'])
    set_output('author', fields['author'])
    set_output('url', fields['url'])
    set_output('version_number', fields['version_number'])
    set_output('product_compatibility', json.dumps(fields['product_compatibility']))
    set_output('confirmations', json.dumps(confirmations))
    set_output('github_issue_type', github_issue_type(fields['type']))
