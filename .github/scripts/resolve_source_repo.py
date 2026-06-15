#!/usr/bin/env python3

"""
Resolves the source repository for an extension update.

Update pull requests are raised against a PortSwigger fork. The source
repository (the parent of that fork) is what the parent BAPP ticket records
as its "bapp url", so we resolve it here to identify the parent ticket later.
"""

import sys
import os
import re
import json
from urllib import request, error
from github_actions_utils import set_output

def extract_owner_repo(url):
    """Extract owner and repo from a GitHub URL (ignores any trailing path such as /pull/123)"""
    match = re.match(r'(?:https://)?(?:www\.)?github\.com/([^/]+)/([^/]+)', url)
    if not match:
        raise ValueError(f"Could not extract owner/repo from URL: {url}")

    owner = match.group(1)
    repo = match.group(2).rstrip('/')
    return owner, repo

def resolve_source_repo(owner, repo, github_token=None):
    """
    Resolve the source repository for the given PortSwigger repository.

    If the repository is a fork, the source is its parent (the author's original
    repository). Otherwise the repository is PortSwigger-owned and is itself the source.

    Returns:
        str: The normalized source GitHub URL (https://github.com/owner/repo)

    Raises:
        ValueError: If the repository doesn't exist or cannot be accessed
    """
    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    req = request.Request(api_url)
    if github_token:
        req.add_header('Authorization', f'token {github_token}')
    req.add_header('Accept', 'application/vnd.github.v3+json')

    try:
        with request.urlopen(req) as response:
            data = json.loads(response.read().decode())
    except error.HTTPError as e:
        if e.code == 404:
            raise ValueError(f"GitHub repository not found: {owner}/{repo}")
        raise ValueError(f"GitHub API error: {e.code} {e.reason}")

    parent = data.get('parent')
    if data.get('fork') and parent and parent.get('html_url'):
        # Fork of an author's repository: the source is the parent.
        return parent['html_url']

    # No parent: the repository is PortSwigger-owned and is itself the source.
    return data['html_url']

if __name__ == '__main__':
    url = os.environ.get('URL')
    github_token = os.environ.get('GITHUB_TOKEN')  # Optional

    if not url:
        error_msg = 'URL environment variable is required'
        print(f'::error::{error_msg}', file=sys.stderr)
        set_output('error_message', error_msg)
        sys.exit(1)

    try:
        owner, repo = extract_owner_repo(url)
        normalized_url = resolve_source_repo(owner, repo, github_token)
        set_output('normalized_url', normalized_url)
    except Exception as e:
        error_msg = str(e)
        print(f'::error::{error_msg}', file=sys.stderr)
        set_output('error_message', error_msg)
        sys.exit(1)
