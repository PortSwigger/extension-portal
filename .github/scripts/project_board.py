#!/usr/bin/env python3

"""
GitHub Projects (v2) access for the submission board.

Submissions are tracked on a single organisation project board, and both of the
issue-comment commands have to put an issue back onto it. Reopening a closed
submission only returns it to the issue list; if its card was archived or
removed the issue comes back invisible to the reviewers, so /reopen and
/resubmit both restore the card as well. Projects v2 has no REST interface, so
everything here goes through GraphQL.

The board is a convenience rather than the source of truth, so nothing here
decides what a failure means - the helpers raise and the callers choose. Both
callers choose to warn and carry on.
"""

import json
from dataclasses import dataclass
from http.client import HTTPException
from urllib import request

GITHUB_GRAPHQL_URL = 'https://api.github.com/graphql'
HTTP_TIMEOUT_SECONDS = 60

# The submission board. Both commands act on this one project.
PROJECT_NUMBER = 1

# Projects v2 caps a query page; an issue on more boards than this would need
# paging, but a submission only ever belongs to the one.
MAX_PROJECT_ITEMS = 10


class GraphQLError(RuntimeError):
    """The API answered, but with errors instead of data."""


# Failures that mean the board would not answer, as opposed to a bug in this
# code. Callers swallow these and carry on; anything else is a real error and
# is left to surface.
BOARD_UNAVAILABLE = (OSError, HTTPException, ValueError, GraphQLError)


ISSUE_PROJECT_ITEMS_QUERY = """
query($issueId: ID!, $first: Int!) {
  node(id: $issueId) {
    ... on Issue {
      projectItems(first: $first) {
        nodes {
          id
          isArchived
          project { ... on ProjectV2 { number } }
        }
      }
    }
  }
}
"""

PROJECT_STATUS_FIELD_QUERY = """
query($org: String!, $number: Int!) {
  organization(login: $org) {
    projectV2(number: $number) {
      id
      field(name: "Status") {
        ... on ProjectV2SingleSelectField {
          id
          options { id name }
        }
      }
    }
  }
}
"""

ADD_ITEM_MUTATION = """
mutation($projectId: ID!, $contentId: ID!) {
  addProjectV2ItemById(input: { projectId: $projectId, contentId: $contentId }) {
    item { id }
  }
}
"""

UNARCHIVE_ITEM_MUTATION = """
mutation($projectId: ID!, $itemId: ID!) {
  unarchiveProjectV2Item(input: { projectId: $projectId, itemId: $itemId }) {
    item { id }
  }
}
"""

SET_STATUS_MUTATION = """
mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
  updateProjectV2ItemFieldValue(input: {
    projectId: $projectId,
    itemId: $itemId,
    fieldId: $fieldId,
    value: { singleSelectOptionId: $optionId }
  }) {
    projectV2Item { id }
  }
}
"""


@dataclass(frozen=True)
class StatusTarget:
    """Everything needed to set one item's Status to a particular column."""

    project_id: str
    field_id: str
    option_id: str


@dataclass(frozen=True)
class Project:
    """The board, and the Status column names it offers."""

    id: str
    status_field_id: str
    # Column name, lowercased and stripped, to its option id.
    status_options: dict

    def status_target(self, column_name):
        """The ids needed to move an item into `column_name`, or None if the
        board has no such column."""
        option_id = self.status_options.get((column_name or '').strip().lower())
        if not option_id or not self.status_field_id:
            return None
        return StatusTarget(project_id=self.id,
                            field_id=self.status_field_id,
                            option_id=option_id)


class GraphQLClient:
    def __init__(self, token, endpoint=None):
        self._endpoint = endpoint or GITHUB_GRAPHQL_URL
        self._headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'Accept': 'application/vnd.github+json',
        }

    def query(self, document, variables):
        """Run a document and return its data, raising GraphQLError on refusal."""
        req = request.Request(
            self._endpoint, method='POST',
            data=json.dumps({'query': document, 'variables': variables}).encode())
        for name, value in self._headers.items():
            req.add_header(name, value)

        with request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as response:
            body = json.loads(response.read().decode())

        # GraphQL reports failure in the body with a 200, so status is not enough.
        if body.get('errors'):
            messages = '; '.join(
                e.get('message', 'unknown error') for e in body['errors'])
            raise GraphQLError(messages)
        return body.get('data') or {}


def find_item(client, issue_node_id, project_number=PROJECT_NUMBER):
    """This issue's card on the board, or None if it is not on it."""
    data = client.query(ISSUE_PROJECT_ITEMS_QUERY,
                        {'issueId': issue_node_id, 'first': MAX_PROJECT_ITEMS})
    node = data.get('node') or {}
    for item in (node.get('projectItems') or {}).get('nodes') or []:
        if ((item.get('project') or {}).get('number')) == project_number:
            return item
    return None


def is_archived(item):
    """Whether an item found by find_item is off the board's views.

    A missing item counts as archived: from the board's point of view an issue
    that was removed and one that was archived are equally out of sight.
    """
    return item is None or bool(item.get('isArchived'))


def resolve_project(client, org, project_number=PROJECT_NUMBER):
    """The board and its Status columns, or None if the token cannot see it.

    Restoring a card needs the board's id whether or not the caller intends to
    set a column, so this is one query serving both.
    """
    data = client.query(PROJECT_STATUS_FIELD_QUERY,
                        {'org': org, 'number': project_number})
    project = ((data.get('organization') or {}).get('projectV2')) or {}
    if not project.get('id'):
        return None

    field = project.get('field') or {}
    options = {(option.get('name') or '').strip().lower(): option.get('id')
               for option in field.get('options') or []}
    return Project(id=project['id'],
                   status_field_id=field.get('id'),
                   status_options=options)


def add_item(client, project_id, content_id):
    """Put an issue back on the board, returning the new item's id."""
    data = client.query(ADD_ITEM_MUTATION,
                        {'projectId': project_id, 'contentId': content_id})
    return ((data.get('addProjectV2ItemById') or {}).get('item') or {}).get('id')


def unarchive_item(client, project_id, item_id):
    """Bring an archived item back into the board's views."""
    client.query(UNARCHIVE_ITEM_MUTATION,
                 {'projectId': project_id, 'itemId': item_id})


def set_status(client, target, item_id):
    """Move an item into the column `target` was resolved for."""
    client.query(SET_STATUS_MUTATION, {
        'projectId': target.project_id,
        'itemId': item_id,
        'fieldId': target.field_id,
        'optionId': target.option_id,
    })
