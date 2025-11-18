#!/usr/bin/env python3

"""
Validates GitHub repository - checks if it exists and is not a fork
"""

import sys
import os
import re
import json
from urllib import request, error

def extract_owner_repo(url):
    """Extract owner and repo from GitHub URL"""
    match = re.match(r'(?:https://)?(?:www\.)?github\.com/([^/]+)/([^/]+)', url)
    if not match:
        raise ValueError(f"Could not extract owner/repo from URL: {url}")

    owner = match.group(1)
    repo = match.group(2).rstrip('/')
    return owner, repo

def validate_repo(url, github_token=None):
    """Validate that the repository exists and is not a fork"""
    try:
        owner, repo = extract_owner_repo(url)
        normalized_url = f"https://github.com/{owner}/{repo}"

        # Make GitHub API request
        api_url = f"https://api.github.com/repos/{owner}/{repo}"
        req = request.Request(api_url)
        if github_token:
            req.add_header('Authorization', f'token {github_token}')
        req.add_header('Accept', 'application/vnd.github.v3+json')

        with request.urlopen(req) as response:
            data = json.loads(response.read().decode())

            if data.get('fork'):
                raise ValueError(
                    f"Repository {owner}/{repo} is a fork. "
                    f"Extensions must be original work, not derivatives of other repositories. "
                    f"Please submit the original repository instead."
                )

        # Output normalized URL for GitHub Actions
        print(f"normalized_url={normalized_url}")

    except error.HTTPError as e:
        if e.code == 404:
            owner, repo = extract_owner_repo(url)
            repo_name = f"{owner}/{repo}"
            raise ValueError(f"GitHub repository not found: {repo_name}")
        raise ValueError(f"GitHub API error: {e.code} {e.reason}")

if __name__ == '__main__':
    url = os.environ.get('URL')
    github_token = os.environ.get('GITHUB_TOKEN')  # Optional

    if not url:
        print('::error::URL environment variable is required', file=sys.stderr)
        sys.exit(1)

    try:
        validate_repo(url, github_token)
    except Exception as e:
        print(f'::error::{str(e)}', file=sys.stderr)
        sys.exit(1)
