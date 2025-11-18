#!/usr/bin/env python3

"""
Tests for validate_repo.py
Run with: python validate_repo_test.py
"""

import subprocess
import sys
import os
from pathlib import Path

# Get the script path
SCRIPT_PATH = Path(__file__).parent.parent / 'validate_repo.py'

# Test cases
tests = [
    {
        'name': 'Valid non-fork repository (turbo-intruder)',
        'env': {
            'URL': 'https://github.com/PortSwigger/turbo-intruder'
        },
        'expect_success': True,
        'expected_output': 'normalized_url=https://github.com/PortSwigger/turbo-intruder'
    },
    {
        'name': 'Valid URL without protocol',
        'env': {
            'URL': 'github.com/PortSwigger/turbo-intruder'
        },
        'expect_success': True,
        'expected_output': 'normalized_url=https://github.com/PortSwigger/turbo-intruder'
    },
    {
        'name': 'Valid URL with trailing slash',
        'env': {
            'URL': 'https://github.com/PortSwigger/turbo-intruder/'
        },
        'expect_success': True,
        'expected_output': 'normalized_url=https://github.com/PortSwigger/turbo-intruder'
    },
    {
        'name': 'Valid URL with www',
        'env': {
            'URL': 'https://www.github.com/PortSwigger/turbo-intruder'
        },
        'expect_success': True,
        'expected_output': 'normalized_url=https://github.com/PortSwigger/turbo-intruder'
    },
    {
        'name': 'Repository is a fork (hackvertor)',
        'env': {
            'URL': 'https://github.com/PortSwigger/hackvertor'
        },
        'expect_success': False,
        'expected_error': 'is a fork'
    },
    {
        'name': 'Repository not found (404)',
        'env': {
            'URL': 'https://github.com/PortSwigger/this-repo-definitely-does-not-exist-123456789'
        },
        'expect_success': False,
        'expected_error': 'not found'
    },
    {
        'name': 'Invalid URL format',
        'env': {
            'URL': 'not-a-github-url'
        },
        'expect_success': False,
        'expected_error': 'Could not extract owner/repo'
    },
    {
        'name': 'Missing URL environment variable',
        'env': {},
        'expect_success': False,
        'expected_error': 'URL environment variable is required'
    }
]


def run_test(test):
    """Run a single test case."""
    env = os.environ.copy()
    env.update(test.get('env', {}))

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        capture_output=True,
        text=True,
        env=env
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
        elif test['expect_success'] and 'expected_output' in test:
            # Check if expected output is present
            if test['expected_output'] in output:
                test_passed = True
            else:
                reason = f"Expected output \"{test['expected_output']}\" not found"
        else:
            test_passed = True
    else:
        reason = f"Expected {'success' if test['expect_success'] else 'failure'}, got {'success' if success else 'failure'}"

    return test_passed, reason, output


def main():
    """Run all tests."""
    print('Running repository validation tests...\n')

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
