#!/usr/bin/env python3

"""
Extracts the submitted values from an extension submission or update issue.

Shared by the created-issue and edited-issue pipelines so both read the issue
form the same way. detect_issue_changes.py imports extract_issue_fields() to
read two revisions of an issue and work out what an edit actually changed.

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


def submission_type(issue_type_name):
    """Map the GitHub issue type set by the form template to our submission type."""
    if issue_type_name == 'Extension':
        return 'extension-submission'
    if issue_type_name == 'Update':
        return 'extension-update'
    return ''


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

    type_ = submission_type(issue_type_name)

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


if __name__ == '__main__':
    try:
        fields = extract_issue_fields(
            body=os.environ.get('ISSUE_BODY', ''),
            title=os.environ.get('ISSUE_TITLE', ''),
            issue_type_name=os.environ.get('ISSUE_TYPE_NAME', ''),
        )
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
