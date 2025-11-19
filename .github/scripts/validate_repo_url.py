#!/usr/bin/env python3

"""
Validates GitHub repository URLs
"""

import sys
import re
from github_actions_utils import set_output

if __name__ == '__main__':
    url = sys.argv[1] if len(sys.argv) > 1 else None
    is_new = len(sys.argv) > 2 and sys.argv[2] == 'new-submission'

    url_regex = (
        r'^(?:https://)?(?:www\.)?github\.com/([a-zA-Z0-9](?:[a-zA-Z0-9-]{0,37}[a-zA-Z0-9])?)\/([a-zA-Z0-9_.-]{1,100})\/?$'
        if is_new else
        r'^(?:https://)?(?:www\.)?github\.com/[a-zA-Z0-9_.-]{1,100}/[a-zA-Z0-9_.-]{1,100}/pull/\d+\/?$'
    )

    if not url:
        error_msg = 'URL is required'
        print(f'::error::{error_msg}', file=sys.stderr)
        set_output('error_message', error_msg)
        sys.exit(1)

    if len(url) > 500:
        error_msg = 'URL exceeds maximum length of 500 characters'
        print(f'::error::{error_msg}', file=sys.stderr)
        set_output('error_message', error_msg)
        sys.exit(1)

    if not re.match(url_regex, url):
        error_msg = (
            f'Invalid GitHub URL: "{url}". Expected format: https://github.com/owner/repo'
            if is_new else
            f'Invalid GitHub PR URL format: "{url}". Expected: https://github.com/owner/repo/pull/123'
        )
        print(f'::error::{error_msg}', file=sys.stderr)
        set_output('error_message', error_msg)
        sys.exit(1)
