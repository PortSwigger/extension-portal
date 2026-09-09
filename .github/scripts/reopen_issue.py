#!/usr/bin/env python3

"""
Bring a closed submission back to life, on the board as well as in the issue list.

Reopening an issue only returns it to the issue list. If its card had been
archived or removed from the project board the issue would come back invisible
to the reviewers, so the card is restored first - before the reopen, because
the board's own "item reopened" automation needs a card to act on.

TARGET_COLUMN then decides where the card ends up:

  unset  the board's automation places it. This is what /reopen wants: the
         issue carries on from the stage it had reached.
  set    the card is moved there, after the reopen and so late enough to win
         over that automation. This is what /resubmit wants: a resubmission
         starts again from the top whatever stage it had reached.

Reopening is the part that matters, so it is not wrapped in a safety net - if
it fails the step should fail. The board is a convenience by comparison, and a
board that will not cooperate only warns.
"""

import json
import os
import sys
from urllib import request

import project_board
from github_actions_utils import set_output

HTTP_TIMEOUT_SECONDS = 60


def warn(message):
    """Record a board problem, and hand it back so the caller can report it."""
    print(f'::warning::{message}', file=sys.stderr)
    return message


def restore_card(client, org, issue_node_id):
    """Put the issue's card back on the board.

    Returns the board, the card's id, and a warning describing what could not
    be done - the reopen still has to happen either way, so a board that will
    not cooperate is reported rather than raised.
    """
    try:
        project = project_board.resolve_project(client, org)
        if project is None:
            return None, None, warn(
                f'Project #{project_board.PROJECT_NUMBER} is not visible to '
                f'this token.')

        item = project_board.find_item(client, issue_node_id)
        if item is None:
            # Removed from the board - re-add it (a new card, fields reset).
            item_id = project_board.add_item(client, project.id, issue_node_id)
            print('Re-added issue to the project board.')
        else:
            item_id = item.get('id')
            if project_board.is_archived(item):
                project_board.unarchive_item(client, project.id, item_id)
                print('Unarchived issue on the project board.')
            else:
                print('Issue is already on the project board.')

        if not item_id:
            return project, None, warn('The board did not say which card the '
                                       'issue ended up on.')
        return project, item_id, None
    except project_board.BOARD_UNAVAILABLE as e:
        return None, None, warn(
            f'Unable to restore the issue on the project board: {e}')


def reopen(repository, issue_number, token):
    """Reopen the issue itself. Any failure here is left to fail the step."""
    req = request.Request(
        f'https://api.github.com/repos/{repository}/issues/{issue_number}',
        method='PATCH', data=json.dumps({'state': 'open'}).encode())
    req.add_header('Authorization', f'token {token}')
    req.add_header('Accept', 'application/vnd.github+json')
    with request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as response:
        response.read()
    print('Issue reopened successfully.')


def move_card(client, project, item_id, column):
    """Move the card into `column`, once the reopen has already happened.

    Returns a warning describing what went wrong, or None.
    """
    try:
        target = project.status_target(column)
        if target is None:
            return warn(f'Column "{column}" not found on project '
                        f'#{project_board.PROJECT_NUMBER}.')
        project_board.set_status(client, target, item_id)
        print(f'Moved issue to "{column}".')
        return None
    except project_board.BOARD_UNAVAILABLE as e:
        return warn(f'Unable to move issue to "{column}": {e}')


def main():
    column = (os.environ.get('TARGET_COLUMN') or '').strip()

    client = project_board.GraphQLClient(os.environ.get('PROJECT_TOKEN'))
    project, item_id, warning = restore_card(client,
                                             os.environ.get('PROJECT_OWNER'),
                                             os.environ.get('ISSUE_NODE_ID'))

    reopen(os.environ.get('REPOSITORY'),
           os.environ.get('ISSUE_NUMBER'),
           os.environ.get('GITHUB_TOKEN'))

    if column and project and item_id:
        warning = move_card(client, project, item_id, column)

    # The issue is reopened either way, so the submitter is told it worked.
    # Anything left wrong on the board is the team's to pick up, and only
    # reaches them if it is reported here.
    set_output('board_warning', warning or '')


if __name__ == '__main__':
    main()
