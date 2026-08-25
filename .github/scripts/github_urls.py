#!/usr/bin/env python3

"""
Splits GitHub URLs into the parts the API needs, and reduces them to a single
spelling so two references to the same thing compare equal.

Which URLs are acceptable is decided by sanitize-inputs, not here.
"""

import re

REPOSITORY_PATTERN = re.compile(
    r'github\.com/(?P<owner>[^/\s?#]+)/(?P<repository>[^/\s?#]+?)(?:\.git)?(?:[/?#]|$)',
    re.IGNORECASE)

PULL_REQUEST_PATTERN = re.compile(
    r'github\.com/(?P<owner>[^/\s?#]+)/(?P<repository>[^/\s?#]+?)(?:\.git)?'
    r'/pull/(?P<number>\d+)',
    re.IGNORECASE)

GIT_SUFFIX_PATTERN = re.compile(r'\.git$', re.IGNORECASE)


def normalize_url(url):
    """Reduce a URL to a form safe to compare: no trailing slash, no .git, lowercase."""
    value = (url or '').strip().rstrip('/')
    return GIT_SUFFIX_PATTERN.sub('', value).rstrip('/').lower()


def repository_parts(url):
    """(owner, repository) from a GitHub repository URL, or None."""
    match = REPOSITORY_PATTERN.search((url or '').strip())
    return match.group('owner', 'repository') if match else None


def pull_request_parts(url):
    """(owner, repository, number) from a GitHub pull request URL, or None."""
    match = PULL_REQUEST_PATTERN.search((url or '').strip())
    return match.group('owner', 'repository', 'number') if match else None


def repository_url(url):
    """The canonical https://github.com/owner/repository spelling of a repository URL."""
    parts = repository_parts(url)
    return f'https://github.com/{parts[0]}/{parts[1]}' if parts else ''
