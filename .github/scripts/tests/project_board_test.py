#!/usr/bin/env python3

"""
Tests for project_board.py
Run with: python project_board_test.py

Projects v2 answers every query with a 200 and buries refusals in an "errors"
key, and it returns nulls rather than omissions for things the token cannot
see, so most of what matters here is what the helpers do with a reply that is
shaped right but empty.
"""

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

# Make the script under test importable (it lives one directory up).
sys.path.insert(0, str(Path(__file__).parent.parent))

import project_board as pb

# Distinctive fragments of each document, so a fake can tell them apart.
ITEMS = 'projectItems(first:'
STATUS = 'field(name: "Status")'
ADD = 'addProjectV2ItemById'
UNARCHIVE = 'unarchiveProjectV2Item'
SET_STATUS = 'updateProjectV2ItemFieldValue'


class FakeClient:
    """A GraphQLClient stand-in that answers by document and records calls."""

    def __init__(self, responses=None, raises=None):
        self.responses = responses or {}
        self.raises = raises
        self.calls = []

    def query(self, document, variables):
        self.calls.append((document, variables))
        if self.raises:
            raise self.raises
        for fragment, response in self.responses.items():
            if fragment in document:
                return response
        return {}

    def documents(self):
        return [d for d, _ in self.calls]

    def variables_for(self, fragment):
        return next(v for d, v in self.calls if fragment in d)

    def sent(self, fragment):
        return any(fragment in d for d in self.documents())


def items_response(*nodes):
    return {'node': {'projectItems': {'nodes': list(nodes)}}}


def item(number=pb.PROJECT_NUMBER, archived=False, item_id='ITEM_1'):
    return {'id': item_id, 'isArchived': archived, 'project': {'number': number}}


def status_response(*option_names, project_id='PROJ', field_id='FIELD'):
    return {'organization': {'projectV2': {
        'id': project_id,
        'field': {'id': field_id,
                  'options': [{'id': f'OPT_{n}', 'name': n} for n in option_names]},
    }}}


class GraphQLClientTests(unittest.TestCase):
    def run_query(self, body, document='query {}', variables=None):
        """Run one query against a canned reply, entirely offline."""
        response = mock.MagicMock()
        response.read.return_value = json.dumps(body).encode()
        response.__enter__.return_value = response
        with mock.patch.object(pb.request, 'urlopen', return_value=response) as urlopen:
            result = pb.GraphQLClient('sekrit').query(document, variables or {})
        return result, urlopen

    def test_returns_the_data_block(self):
        result, _ = self.run_query({'data': {'node': {'id': 'X'}}})
        self.assertEqual(result, {'node': {'id': 'X'}})

    def test_errors_in_a_200_are_raised(self):
        with self.assertRaises(pb.GraphQLError) as raised:
            self.run_query({'errors': [{'message': 'Could not resolve to a node'}]})
        self.assertIn('Could not resolve to a node', str(raised.exception))

    def test_several_errors_are_all_reported(self):
        with self.assertRaises(pb.GraphQLError) as raised:
            self.run_query({'errors': [{'message': 'first'}, {'message': 'second'}]})
        self.assertIn('first', str(raised.exception))
        self.assertIn('second', str(raised.exception))

    def test_an_error_without_a_message_still_raises(self):
        with self.assertRaises(pb.GraphQLError):
            self.run_query({'errors': [{}]})

    def test_a_missing_data_block_is_not_a_crash(self):
        result, _ = self.run_query({})
        self.assertEqual(result, {})

    def test_the_request_carries_the_token_and_a_timeout(self):
        _, urlopen = self.run_query({'data': {}}, variables={'a': 1})
        sent = urlopen.call_args.args[0]
        self.assertEqual(sent.get_header('Authorization'), 'Bearer sekrit')
        self.assertEqual(urlopen.call_args.kwargs['timeout'], pb.HTTP_TIMEOUT_SECONDS)
        self.assertEqual(json.loads(sent.data)['variables'], {'a': 1})


class FindItemTests(unittest.TestCase):
    def test_finds_the_card_on_the_submission_board(self):
        client = FakeClient({ITEMS: items_response(item(item_id='WANTED'))})
        self.assertEqual(pb.find_item(client, 'ISSUE')['id'], 'WANTED')

    def test_ignores_cards_on_other_boards(self):
        client = FakeClient({ITEMS: items_response(item(number=7), item(number=9))})
        self.assertIsNone(pb.find_item(client, 'ISSUE'))

    def test_picks_the_submission_board_out_of_several(self):
        client = FakeClient({ITEMS: items_response(
            item(number=7, item_id='OTHER'), item(item_id='WANTED'))})
        self.assertEqual(pb.find_item(client, 'ISSUE')['id'], 'WANTED')

    def test_an_issue_on_no_board_is_not_found(self):
        client = FakeClient({ITEMS: items_response()})
        self.assertIsNone(pb.find_item(client, 'ISSUE'))

    def test_a_null_node_is_not_found(self):
        # What the API returns when the token cannot see the issue.
        client = FakeClient({ITEMS: {'node': None}})
        self.assertIsNone(pb.find_item(client, 'ISSUE'))

    def test_a_null_project_on_an_item_is_skipped(self):
        client = FakeClient({ITEMS: items_response({'id': 'X', 'project': None})})
        self.assertIsNone(pb.find_item(client, 'ISSUE'))


class IsArchivedTests(unittest.TestCase):
    def test_a_missing_item_counts_as_archived(self):
        self.assertTrue(pb.is_archived(None))

    def test_an_archived_item_is_archived(self):
        self.assertTrue(pb.is_archived(item(archived=True)))

    def test_a_live_item_is_not(self):
        self.assertFalse(pb.is_archived(item(archived=False)))

    def test_an_absent_flag_is_not_archived(self):
        self.assertFalse(pb.is_archived({'id': 'X'}))


class ResolveProjectTests(unittest.TestCase):
    def resolve(self, response):
        return pb.resolve_project(FakeClient({STATUS: response}), 'PortSwigger')

    def test_reads_the_board_id_and_its_columns(self):
        project = self.resolve(status_response('Concept review', 'Done'))
        self.assertEqual(project.id, 'PROJ')
        self.assertEqual(project.status_field_id, 'FIELD')
        self.assertEqual(set(project.status_options), {'concept review', 'done'})

    def test_an_invisible_project_resolves_to_nothing(self):
        # A non-organisation owner, or a token without project access.
        self.assertIsNone(self.resolve({'organization': None}))

    def test_a_board_without_a_status_field_still_resolves(self):
        # The id is what restoring a card needs; the columns are optional.
        project = self.resolve({'organization': {'projectV2': {
            'id': 'PROJ', 'field': None}}})
        self.assertEqual(project.id, 'PROJ')
        self.assertIsNone(project.status_field_id)
        self.assertEqual(project.status_options, {})


class StatusTargetTests(unittest.TestCase):
    def target_for(self, column, response=None):
        project = pb.resolve_project(
            FakeClient({STATUS: response or status_response('Concept review')}),
            'PortSwigger')
        return project.status_target(column)

    def test_resolves_the_column_to_its_ids(self):
        target = self.target_for('Concept review')
        self.assertEqual(
            (target.project_id, target.field_id, target.option_id),
            ('PROJ', 'FIELD', 'OPT_Concept review'))

    def test_matches_a_column_regardless_of_case_or_padding(self):
        self.assertIsNotNone(self.target_for('  concept review '))

    def test_a_renamed_column_resolves_to_nothing(self):
        self.assertIsNone(
            self.target_for('Concept review', status_response('Triage', 'Done')))

    def test_a_board_without_a_status_field_has_no_target(self):
        self.assertIsNone(self.target_for('Concept review', {'organization': {
            'projectV2': {'id': 'PROJ', 'field': None}}}))

    def test_an_empty_column_name_has_no_target(self):
        self.assertIsNone(self.target_for(''))
        self.assertIsNone(self.target_for(None))


class MutationTests(unittest.TestCase):
    def test_add_item_returns_the_new_item_id(self):
        client = FakeClient({ADD: {'addProjectV2ItemById': {'item': {'id': 'NEW'}}}})
        self.assertEqual(pb.add_item(client, 'PROJ', 'ISSUE'), 'NEW')
        self.assertEqual(client.variables_for(ADD),
                         {'projectId': 'PROJ', 'contentId': 'ISSUE'})

    def test_add_item_survives_a_reply_without_an_item(self):
        client = FakeClient({ADD: {'addProjectV2ItemById': None}})
        self.assertIsNone(pb.add_item(client, 'PROJ', 'ISSUE'))

    def test_unarchive_targets_the_item(self):
        client = FakeClient()
        pb.unarchive_item(client, 'PROJ', 'ITEM')
        self.assertEqual(client.variables_for(UNARCHIVE),
                         {'projectId': 'PROJ', 'itemId': 'ITEM'})

    def test_set_status_sends_every_id_the_mutation_needs(self):
        client = FakeClient()
        target = pb.StatusTarget(project_id='PROJ', field_id='FIELD', option_id='OPT')
        pb.set_status(client, target, 'ITEM')
        self.assertEqual(client.variables_for(SET_STATUS), {
            'projectId': 'PROJ', 'itemId': 'ITEM',
            'fieldId': 'FIELD', 'optionId': 'OPT'})


if __name__ == '__main__':
    unittest.main(verbosity=2)
