#!/usr/bin/env python3

"""GitHub URL handling shared by the submission pipeline scripts."""

import re

REPOSITORY_PATTERN = re.compile(
    r'^(?:https?://)?(?:www\.)?github\.com/([^/\s]+)/([^/\s]+)', re.IGNORECASE)

GIT_SUFFIX_PATTERN = re.compile(r'\.git$', re.IGNORECASE)


def normalize_url(url):
    """Reduce a URL to a form safe to compare: no trailing slash, no .git, lowercase."""
    value = (url or '').strip().rstrip('/')
    return GIT_SUFFIX_PATTERN.sub('', value).rstrip('/').lower()


def canonical_repository_url(url):
    """The https://github.com/owner/repo form, or '' if this is not a GitHub repository."""
    match = REPOSITORY_PATTERN.match((url or '').strip())
    if not match:
        return ''
    owner, repository = match.groups()
    return f'https://github.com/{owner}/{GIT_SUFFIX_PATTERN.sub("", repository)}'
