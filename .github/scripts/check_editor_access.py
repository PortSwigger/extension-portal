#!/usr/bin/env python3

"""
Decides whether an issue was edited by a maintainer or by its submitter.

A maintainer's edit is applied to the associated ticket in full; a submitter's
change of bapp url is not, because that is the artifact that was reviewed.

The submitter and bots are ruled out from the webhook payload alone. Write
access is then confirmed against the GitHub API, which is what separates a
maintainer from a triage-only account; asking needs push access, which the
default GITHUB_TOKEN may not hold, so an unanswerable lookup leaves the payload
checks standing.
"""

import json
import os
from dataclasses import dataclass
from http.client import HTTPException
from urllib import error, request
from urllib.parse import quote

from github_actions_utils import output_flag, set_output

WRITE_ROLES = frozenset({'admin', 'maintain', 'write'})

UNVERIFIED_ACCESS_WARNING = (
    'Reading collaborator permissions needs push access, which the default GITHUB_TOKEN '
    'may not hold. Treating this as a maintainer edit because it came from a non-bot '
    'account other than the submitter. Triage-only accounts are not told apart from '
    'maintainers while this warning appears.'
)


@dataclass(frozen=True)
class Access:
    """What GitHub reports an account may do with a repository."""

    role: str = 'unknown'
    permission: str = 'unknown'
    known: bool = True

    @property
    def grants_write(self):
        return self.known and (self.role in WRITE_ROLES or self.permission in WRITE_ROLES)

    def __str__(self):
        if self.role == self.permission:
            return self.role
        return f'{self.role} (permission: {self.permission})'


UNKNOWN_ACCESS = Access(known=False)
NO_ACCESS = Access(role='none', permission='none')


@dataclass(frozen=True)
class Editor:
    """Who made the edit, and the access they were found to hold."""

    login: str
    is_maintainer: bool
    access: str


def github_api_get(api_url, github_token=None):
    """Fetch and decode a GitHub API resource."""
    req = request.Request(api_url)
    if github_token:
        req.add_header('Authorization', f'token {github_token}')
    req.add_header('Accept', 'application/vnd.github.v3+json')
    with request.urlopen(req) as response:
        return json.loads(response.read().decode())


def collaborator_permission_url(repository, login):
    return (f'https://api.github.com/repos/{repository}'
            f'/collaborators/{quote(login, safe="")}/permission')


def look_up_access(repository, login, github_token=None):
    """Ask GitHub what access an account holds, or UNKNOWN_ACCESS if it will not say."""
    if not repository:
        return UNKNOWN_ACCESS
    try:
        data = github_api_get(collaborator_permission_url(repository, login), github_token)
    except error.HTTPError as e:
        return NO_ACCESS if e.code == 404 else UNKNOWN_ACCESS
    except (OSError, HTTPException, ValueError):
        return UNKNOWN_ACCESS

    return Access(
        role=(data.get('role_name') or 'unknown').strip().lower(),
        permission=(data.get('permission') or 'unknown').strip().lower(),
    )


def is_bot(login, account_type):
    return (account_type or '').strip().lower() == 'bot' or login.endswith('[bot]')


def classify_editor(editor_login, author_login, editor_type='', repository='', github_token=None):
    """Whether this edit came from a maintainer acting on someone else's submission."""
    editor = (editor_login or '').strip()
    author = (author_login or '').strip()

    if not editor or not author:
        print('::warning::Could not identify the editor or the submitter.')
        return Editor(login=editor or '(unknown)', is_maintainer=False, access='unidentified')

    if editor == author:
        return Editor(login=editor, is_maintainer=False, access='submitter')

    if is_bot(editor, editor_type):
        return Editor(login=editor, is_maintainer=False, access='bot')

    access = look_up_access(repository, editor, github_token)
    if not access.known:
        print(f'::warning::Could not determine what access {editor} holds on '
              f'{repository or "this repository"}. {UNVERIFIED_ACCESS_WARNING}')
        return Editor(login=editor, is_maintainer=True, access=str(access))

    return Editor(login=editor, is_maintainer=access.grants_write, access=str(access))


def main():
    editor = classify_editor(
        os.environ.get('EDITOR_LOGIN'),
        os.environ.get('AUTHOR_LOGIN'),
        editor_type=os.environ.get('EDITOR_TYPE', ''),
        repository=os.environ.get('GITHUB_REPOSITORY', ''),
        github_token=os.environ.get('GITHUB_TOKEN'),
    )

    print(f'Edited by {editor.login} [access: {editor.access}] - treated as '
          f'{"a maintainer" if editor.is_maintainer else "the submitter"}.')

    set_output('is_maintainer', output_flag(editor.is_maintainer))
    set_output('access', editor.access)


if __name__ == '__main__':
    main()
