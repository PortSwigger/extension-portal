#!/usr/bin/env python3

"""
Tests for validate_repo_url.py
Run with: python validate_repo_url_test.py
"""

import subprocess
import sys
from pathlib import Path

# Get the script path
SCRIPT_PATH = Path(__file__).parent.parent / 'validate_repo_url.py'

# Test cases
tests = [
    # New submission tests
    {
        'name': 'Valid HTTPS URL with www',
        'args': ['https://www.github.com/owner/repo', 'new-submission'],
        'expect_success': True
    },
    {
        'name': 'Valid HTTPS URL without www',
        'args': ['https://github.com/owner/repo', 'new-submission'],
        'expect_success': True
    },
    {
        'name': 'Valid URL without protocol',
        'args': ['github.com/owner/repo', 'new-submission'],
        'expect_success': True
    },
    {
        'name': 'Valid owner with hyphens',
        'args': ['https://github.com/my-org-name/repo', 'new-submission'],
        'expect_success': True
    },
    {
        'name': 'Valid repo with dots and underscores',
        'args': ['https://github.com/owner/my.repo_name', 'new-submission'],
        'expect_success': True
    },
    {
        'name': 'Valid URL with trailing slash',
        'args': ['https://github.com/owner/repo/', 'new-submission'],
        'expect_success': True
    },
    {
        'name': 'Invalid - missing repo name',
        'args': ['https://github.com/owner', 'new-submission'],
        'expect_success': False,
        'expected_error': 'Invalid GitHub URL'
    },
    {
        'name': 'Invalid - owner starts with hyphen',
        'args': ['https://github.com/-owner/repo', 'new-submission'],
        'expect_success': False,
        'expected_error': 'Invalid GitHub URL'
    },
    {
        'name': 'Invalid - owner ends with hyphen',
        'args': ['https://github.com/owner-/repo', 'new-submission'],
        'expect_success': False,
        'expected_error': 'Invalid GitHub URL'
    },
    {
        'name': 'Invalid - contains spaces',
        'args': ['https://github.com/my owner/repo', 'new-submission'],
        'expect_success': False,
        'expected_error': 'Invalid GitHub URL'
    },
    {
        'name': 'Invalid - wrong domain',
        'args': ['https://gitlab.com/owner/repo', 'new-submission'],
        'expect_success': False,
        'expected_error': 'Invalid GitHub URL'
    },
    {
        'name': 'Invalid - includes pull request path',
        'args': ['https://github.com/owner/repo/pull/123', 'new-submission'],
        'expect_success': False,
        'expected_error': 'Invalid GitHub URL'
    },
    {
        'name': 'Invalid - URL too long',
        'args': ['https://github.com/owner/' + 'a' * 500, 'new-submission'],
        'expect_success': False,
        'expected_error': 'URL exceeds maximum length'
    },
    {
        'name': 'Invalid - empty URL',
        'args': ['', 'new-submission'],
        'expect_success': False,
        'expected_error': 'URL is required'
    },
    # PR URL tests
    {
        'name': 'Valid PR URL',
        'args': ['https://github.com/owner/repo/pull/123'],
        'expect_success': True
    },
    {
        'name': 'Valid PR URL with large number',
        'args': ['https://github.com/owner/repo/pull/999999'],
        'expect_success': True
    },
    {
        'name': 'Valid PR URL with trailing slash',
        'args': ['https://github.com/owner/repo/pull/123/'],
        'expect_success': True
    },
    {
        'name': 'Invalid PR - missing protocol',
        'args': ['github.com/owner/repo/pull/123'],
        'expect_success': False,
        'expected_error': 'Invalid GitHub PR URL'
    },
    {
        'name': 'Invalid PR - wrong path',
        'args': ['https://github.com/owner/repo/issues/123'],
        'expect_success': False,
        'expected_error': 'Invalid GitHub PR URL'
    },
    {
        'name': 'Invalid PR - missing PR number',
        'args': ['https://github.com/owner/repo/pull/'],
        'expect_success': False,
        'expected_error': 'Invalid GitHub PR URL'
    }
]


def run_test(test):
    """Run a single test case."""
    args = test['args']

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)] + args,
        capture_output=True,
        text=True
    )

    success = result.returncode == 0
    output = result.stdout + result.stderr

    test_passed = False
    reason = ''

    if success == test['expect_success']:
        if not test['expect_success'] and 'expected_error' in test:
            # Check if expected error message is present
            if test['expected_error'] in output:
                test_passed = True
            else:
                reason = f"Expected error \"{test['expected_error']}\" not found in output"
        else:
            test_passed = True
    else:
        reason = f"Expected {'success' if test['expect_success'] else 'failure'}, got {'success' if success else 'failure'}"

    return test_passed, reason, output


def main():
    """Run all tests."""
    print('Running repository URL validation tests...\n')

    passed = 0
    failed = 0

    for test in tests:
        test_passed, reason, output = run_test(test)

        if test_passed:
            print(f"✅ {test['name']}")
            passed += 1
        else:
            print(f"❌ {test['name']}")
            print(f"   Reason: {reason}")
            if output:
                print(f"   Output: {output[:200]}")
            failed += 1

    print(f"\n{passed + failed} tests run: {passed} passed, {failed} failed")

    if failed > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
