#!/usr/bin/env python3

"""
Resolves and validates the source repository for an extension update.

Update pull requests are raised against a PortSwigger fork. The source
repository (the parent of that fork) is what the parent BAPP ticket records
as its "bapp url", so we resolve it here to identify the parent ticket later.

We also verify that the pull request genuinely originates from that source
repository: the PR's head (source) repository must match the parent of the
PortSwigger fork. Updates raised from anywhere else are rejected so they can
be discussed on the GitHub issue.
"""

import sys
import os
import re
import json
from urllib import request, error
from github_actions_utils import set_output

def extract_pr_ref(url):
    """Extract owner, repo and pull request number from a GitHub pull request URL."""
    match = re.match(
        r'(?:https://)?(?:www\.)?github\.com/([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+)/pull/(\d+)',
        url,
    )
    if not match:
        raise ValueError(
            f"Could not extract a pull request reference from URL: {url}. "
            "Expected a link of the form https://github.com/PortSwigger/<repo>/pull/<number>."
        )

    owner = match.group(1)
    repo = match.group(2)
    pull_number = match.group(3)
    return owner, repo, pull_number

def github_api_get(api_url, github_token=None):
    """Fetch and decode a GitHub API resource, raising ValueError on failure."""
    req = request.Request(api_url)
    if github_token:
        req.add_header('Authorization', f'token {github_token}')
    req.add_header('Accept', 'application/vnd.github.v3+json')

    try:
        with request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except error.HTTPError as e:
        if e.code == 404:
            raise ValueError(f"GitHub resource not found: {api_url}")
        raise ValueError(f"GitHub API error: {e.code} {e.reason}")

def normalize_url(url):
    """Normalize a GitHub URL for comparison (drop trailing .git/slash, lowercase)."""
    value = (url or '').strip().rstrip('/')
    if value.endswith('.git'):
        value = value[:-len('.git')]
    return value.rstrip('/').lower()

def resolve_source_repo(owner, repo, pull_number, github_token=None):
    """
    Resolve the source repository for an update pull request and verify the
    pull request actually originates from it.

    The base repository (taken from the PR URL) is the PortSwigger fork. Its
    source is the fork's parent (the author's original repository), or the
    repository itself when it is a PortSwigger-owned original rather than a fork.

    Returns:
        str: The normalized source GitHub URL (https://github.com/owner/repo)

    Raises:
        ValueError: If the pull request or repository cannot be accessed, or
            the pull request's source repository does not match the resolved source.
    """
    pull = github_api_get(
        f"https://api.github.com/repos/{owner}/{repo}/pulls/{pull_number}",
        github_token,
    )

    head_repo = (pull.get('head') or {}).get('repo')
    if not head_repo or not head_repo.get('html_url'):
        raise ValueError(
            "Could not determine the source repository of the pull request. "
            "The repository the pull request was raised from may have been deleted."
        )
    head_url = head_repo['html_url']

    base = github_api_get(f"https://api.github.com/repos/{owner}/{repo}", github_token)
    parent = base.get('parent')
    if base.get('fork') and parent and parent.get('html_url'):
        # Fork of an author's repository: the source is the parent.
        source_url = parent['html_url']
    else:
        # No parent: the repository is PortSwigger-owned and is itself the source.
        source_url = base['html_url']

    # The update must originate from the source repository, not an arbitrary fork.
    if normalize_url(head_url) != normalize_url(source_url):
        raise ValueError(
            f"This update was raised from {head_url}, but updates must come from the "
            f"source repository {source_url} (the parent of the PortSwigger fork)."
        )

    return source_url

if __name__ == '__main__':
    url = os.environ.get('URL')
    github_token = os.environ.get('GITHUB_TOKEN')  # Optional

    if not url:
        error_msg = 'URL environment variable is required'
        print(f'::error::{error_msg}', file=sys.stderr)
        set_output('error_message', error_msg)
        sys.exit(1)

    try:
        owner, repo, pull_number = extract_pr_ref(url)
        normalized_url = resolve_source_repo(owner, repo, pull_number, github_token)
        set_output('normalized_url', normalized_url)
    except Exception as e:
        error_msg = str(e)
        print(f'::error::{error_msg}', file=sys.stderr)
        set_output('error_message', error_msg)
        sys.exit(1)
