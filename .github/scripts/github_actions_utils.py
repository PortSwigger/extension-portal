#!/usr/bin/env python3

"""
Utilities for GitHub Actions integration.

Provides helpers for setting outputs in a way that works both within
GitHub Actions and for local testing/development.
"""

import sys
import os


def set_output(key, value, output_file=None):
    """
    Set a GitHub Actions output variable.

    This function writes to GITHUB_OUTPUT if running in GitHub Actions,
    or prints to stdout for local testing. This ensures scripts remain
    testable and portable outside GitHub Actions.

    Uses the heredoc delimiter format so that values containing newlines
    or '=' characters cannot inject additional output entries.

    Args:
        key: Output variable name
        value: Output variable value
        output_file: Path to write to. Defaults to the GITHUB_OUTPUT
            environment variable. Pass an explicit path to exercise the
            file-writing path in tests without setting GITHUB_OUTPUT.

    Example:
        # Set an output
        set_output('normalized_url', 'https://github.com/owner/repo')

        # Set an error output with accompanying annotation
        print('::error::Repository not found', file=sys.stderr)
        set_output('error_message', 'Repository not found')

        # Write to a known path, for tests
        set_output('normalized_url', 'https://github.com/owner/repo', tmp_file)
    """
    if output_file is None:
        output_file = os.environ.get('GITHUB_OUTPUT')
    if output_file:
        try:
            with open(output_file, 'a') as f:
                delimiter = f'ghadelimiter_{os.urandom(8).hex()}'
                f.write(f'{key}<<{delimiter}\n{value}\n{delimiter}\n')
        except Exception as e:
            print(f'::warning::Could not write {key} to {output_file}: {e}', file=sys.stderr)
    else:
        # Fallback for local testing
        print(f'{key}={value}')
