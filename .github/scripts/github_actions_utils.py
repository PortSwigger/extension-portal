#!/usr/bin/env python3

"""
Utilities for GitHub Actions integration.

Provides helpers for setting outputs in a way that works both within
GitHub Actions and for local testing/development.
"""

import sys
import os


def set_output(key, value):
    """
    Set a GitHub Actions output variable.

    This function writes to GITHUB_OUTPUT if running in GitHub Actions,
    or prints to stdout for local testing. This ensures scripts remain
    testable and portable outside GitHub Actions.

    Args:
        key: Output variable name
        value: Output variable value

    Example:
        # Set an output
        set_output('normalized_url', 'https://github.com/owner/repo')

        # Set an error output with accompanying annotation
        print('::error::Repository not found', file=sys.stderr)
        set_output('error_message', 'Repository not found')
    """
    github_output = os.environ.get('GITHUB_OUTPUT')
    if github_output:
        try:
            with open(github_output, 'a') as f:
                # Escape special characters per GitHub Actions spec
                safe_value = (str(value)
                    .replace('%', '%25')
                    .replace('\r', '%0D')
                    .replace('\n', '%0A'))
                f.write(f'{key}={safe_value}\n')
        except Exception as e:
            print(f'::warning::Could not write {key} to GITHUB_OUTPUT: {e}', file=sys.stderr)
    else:
        # Fallback for local testing
        print(f'{key}={value}')
