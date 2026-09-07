#!/usr/bin/env python3

"""
Decides whether a close as "Completed" should be corrected to "Not planned".

Closed does not mean finished here: submissions are closed to park them while
their author works on feedback, and every close the pipeline makes is
"Not planned". "Completed" therefore reads as "a maintainer handled this", and
a reporter closing their own submission that way drops it out of the review
queue looking finished.

Maintainers and bots close as they see fit; everyone else may only close as
"Not planned". A maintainer is an account GitHub confirms holds triage access
or better, or one the payload already associates with the repository when it
closed its own issue. Where neither settles it the reporter is corrected and
anyone else is left to the team, since closing someone else's issue already
needs triage access at least.
"""

import os
from dataclasses import dataclass

from check_editor_access import WRITE_ROLES, is_bot, look_up_access
from check_resubmit_eligibility import MAINTAINER_ASSOCIATIONS
from github_actions_utils import output_flag, set_output

# Triage is granted deliberately and carries the run of the queue, so it speaks
# for a review outcome even though it cannot touch the code. Deliberately wider
# than WRITE_ROLES, which withholds from triage the power to repoint a
# submission at different code.
CLOSE_ROLES = WRITE_ROLES | {'triage'}


def grants_close_authority(access):
    """Whether this access level covers closing a submission as Completed."""
    return access.known and (access.role in CLOSE_ROLES or access.permission in CLOSE_ROLES)


@dataclass(frozen=True)
class Close:
    """Who closed the issue as Completed, and whether that reason may stand."""

    closer: str
    needs_correction: bool
    basis: str


def classify_close(closer_login, author_login, author_association='', closer_type='',
                   repository='', github_token=None):
    """Whether this close as Completed misrepresents the submission as handled."""
    closer = (closer_login or '').strip()
    author = (author_login or '').strip()
    author_association = (author_association or '').strip().upper()

    if not closer or not author:
        print('::warning::Could not identify who closed the issue, or its reporter.')
        return Close(closer or '(unknown)', needs_correction=False, basis='unidentified')

    if is_bot(closer, closer_type):
        return Close(closer, needs_correction=False, basis='bot')

    if closer == author and author_association in MAINTAINER_ASSOCIATIONS:
        return Close(closer, needs_correction=False,
                     basis=f'association: {author_association}')

    access = look_up_access(repository, closer, github_token)
    if grants_close_authority(access):
        return Close(closer, needs_correction=False, basis=f'access: {access}')

    if not access.known and closer != author:
        # An account GitHub will not place is left to the team, because closing
        # someone else's issue already needs triage access at least. The
        # reporter is placed by their association and needs no such latitude.
        return Close(closer, needs_correction=False, basis='access unconfirmed')

    return Close(closer, needs_correction=True,
                 basis=f'not a maintainer (association: {author_association or "NONE"}, '
                       f'access: {access})')


def main():
    close = classify_close(
        os.environ.get('CLOSER_LOGIN'),
        os.environ.get('AUTHOR_LOGIN'),
        author_association=os.environ.get('AUTHOR_ASSOCIATION', ''),
        closer_type=os.environ.get('CLOSER_TYPE', ''),
        repository=os.environ.get('GITHUB_REPOSITORY', ''),
        github_token=os.environ.get('GITHUB_TOKEN'),
    )

    print(f'Closed as Completed by {close.closer} [{close.basis}] - '
          f'{"correcting to Not planned" if close.needs_correction else "left as it is"}.')

    set_output('needs_correction', output_flag(close.needs_correction))
    set_output('basis', close.basis)


if __name__ == '__main__':
    main()
