#!/usr/bin/env python3

"""Jira access for the BApp Store submission pipelines."""

import base64
import json
import os
from urllib import error, request

from github_urls import normalize_url

HTTP_TIMEOUT_SECONDS = 60

PROJECT = 'BAPP'
SUBMISSION_ISSUE_TYPE = '10278'
UPDATE_SUBTASK_ISSUE_TYPE = '10279'
BAPP_URL_FIELD = 'customfield_10932'
GITHUB_ISSUE_FIELD = 'customfield_13486'

REJECTED_STATUS = '10103'
FEEDBACK_STATUS = '11030'
APPROVED_STATUS = '11006'
DECLINED_RESOLUTION = '10200'


class TransitionUnavailable(RuntimeError):
    pass


def jql_field(field):
    return f"cf[{field.removeprefix('customfield_')}]"


def escape_jql(value):
    return (value or '').replace('\\', '\\\\').replace('"', '\\"')


def allowed_fields(fields, transition):
    # Jira rejects a field that is not on the transition's own screen.
    offered = transition.get('fields') or {}
    return {name: value for name, value in (fields or {}).items()
            if name in offered}


class JiraClient:
    def __init__(self, base_url, email, token):
        self._base_url = (base_url or '').rstrip('/')
        credentials = base64.b64encode(f'{email}:{token}'.encode()).decode()
        self._headers = {
            'Authorization': f'Basic {credentials}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

    @classmethod
    def from_environment(cls, env=None):
        env = os.environ if env is None else env
        return cls(env.get('JIRA_BASE_URL'),
                   env.get('JIRA_USER_EMAIL'),
                   env.get('JIRA_API_TOKEN'))

    def _send(self, method, path, payload=None):
        req = request.Request(
            f'{self._base_url}{path}', method=method,
            data=None if payload is None else json.dumps(payload).encode())
        for name, value in self._headers.items():
            req.add_header(name, value)
        with request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as response:
            body = response.read().decode()
        return json.loads(body) if body else {}

    def search(self, jql, fields):
        return self._send('POST', '/rest/api/3/search/jql',
                          {'jql': jql, 'fields': fields, 'maxResults': 50})

    def find_by_url_field(self, issue_type, field, url, fields):
        """
        Tickets of this type whose `field` holds this URL.

        Jira matches URL fields loosely, so the search asks for "contains" -
        falling back to exact match if rejected - and re-checks the results.
        """
        def jql(operator):
            return (f'project = {PROJECT} AND issuetype = {issue_type} '
                    f'AND {jql_field(field)} {operator} "{escape_jql(url)}"')

        try:
            results = self.search(jql('~'), fields)
        except error.HTTPError as e:
            if e.code != 400:
                raise
            results = self.search(jql('='), fields)

        return [ticket for ticket in results.get('issues', [])
                if normalize_url(ticket.get('fields', {}).get(field)) == normalize_url(url)]

    def create_issue(self, fields):
        return self._send('POST', '/rest/api/3/issue', {'fields': fields})['key']

    def update_issue(self, key, fields):
        self._send('PUT', f'/rest/api/3/issue/{key}', {'fields': fields})

    def transitions(self, key):
        return self._send(
            'GET',
            f'/rest/api/3/issue/{key}/transitions?expand=transitions.fields',
        ).get('transitions') or []

    def transition_to_status(self, key, status_id, fields=None):
        for transition in self.transitions(key):
            if (transition.get('to') or {}).get('id') != status_id:
                continue
            payload = {'transition': {'id': transition['id']}}
            accepted = allowed_fields(fields, transition)
            if accepted:
                payload['fields'] = accepted
            self._send('POST', f'/rest/api/3/issue/{key}/transitions', payload)
            return

        raise TransitionUnavailable(
            f'{key} offers no transition to status {status_id}.')
