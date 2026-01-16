#!/usr/bin/env python3

"""
Detects the primary programming language of a GitHub repository.

Queries the GitHub API to get language statistics and identifies the primary
supported language (Java, Kotlin, Python, or Ruby) with the most bytes of code.
Kotlin is treated as Java for consistency.
"""

import json
import os
import re
import sys
from urllib import request, error

from github_actions_utils import set_output


SUPPORTED_LANGUAGES = {'java', 'kotlin', 'python', 'ruby'}

LANGUAGE_ALIASES = {'kotlin': 'Java'}


def extract_owner_repo(url):
    """Extract owner and repo from GitHub URL."""
    pattern = r'(?:https://)?(?:www\.)?github\.com/([^/]+)/([^/]+)'
    if match := re.match(pattern, url):
        return match.group(1), match.group(2).rstrip('/')
    raise ValueError(f"Could not extract owner/repo from URL: {url}")


def fetch_languages(owner, repo, github_token=None):
    """Fetch language statistics from GitHub API."""
    api_url = f"https://api.github.com/repos/{owner}/{repo}/languages"
    req = request.Request(api_url, headers={
        'Accept': 'application/vnd.github.v3+json',
        **({"Authorization": f"token {github_token}"} if github_token else {})
    })

    try:
        with request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except error.HTTPError as e:
        if e.code == 404:
            raise ValueError(f"GitHub repository not found: {owner}/{repo}")
        raise ValueError(f"GitHub API error: {e.code} {e.reason}")


def detect_language(url, github_token=None):
    """
    Detect the primary supported language in a GitHub repository.

    Args:
        url: GitHub repository URL
        github_token: Optional GitHub token for authentication

    Returns:
        str: The detected language (Java, Python, Ruby, or Unknown)
             Note: Kotlin is returned as "Java"

    Raises:
        ValueError: If the repository cannot be accessed or languages detected
    """
    owner, repo = extract_owner_repo(url)
    repo_name = f"{owner}/{repo}"

    print(f"Detecting language for repository: {repo_name}")

    languages_data = fetch_languages(owner, repo, github_token)
    print(f"Language data: {json.dumps(languages_data)}")

    # Filter and aggregate supported languages
    supported_langs = {
        lang: bytes_count
        for lang, bytes_count in languages_data.items()
        if lang.lower() in SUPPORTED_LANGUAGES
    }

    if not supported_langs:
        return "Unknown"

    # Find language with most bytes and apply aliases
    primary_language = max(supported_langs, key=supported_langs.get)
    primary_language = LANGUAGE_ALIASES.get(primary_language.lower(), primary_language)

    print(f"Detected primary language: {primary_language}")
    return primary_language


def main():
    """Main entry point for GitHub Actions workflow."""
    url = sys.argv[1] if len(sys.argv) > 1 else None

    if not url:
        error_msg = 'Repository URL is required'
        print(f'::error::{error_msg}', file=sys.stderr)
        set_output('error_message', error_msg)
        sys.exit(1)

    try:
        github_token = os.environ.get('GITHUB_TOKEN')
        language = detect_language(url, github_token)
        set_output('language', language)
    except Exception as e:
        error_msg = str(e)
        print(f'::error::{error_msg}', file=sys.stderr)
        set_output('error_message', error_msg)
        sys.exit(1)


if __name__ == '__main__':
    main()
