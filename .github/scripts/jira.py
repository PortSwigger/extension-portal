#!/usr/bin/env python3

"""
Jira access for the BApp Store submission pipelines.

Every ticket the pipelines touch lives in the BAPP project and carries two
custom fields: the "bapp url" of the artifact under review, and the URL of the
GitHub issue it came from. Tickets are found by one of those URLs, which Jira
matches loosely, so find_by_url_field re-checks the results properly.
"""

import base64
import json
import os
from urllib import error, request

from github_urls import normalize_url

PROJECT = 'BAPP'
SUBMISSION_ISSUE_TYPE = '10278'
UPDATE_SUBTASK_ISSUE_TYPE = '10279'
BAPP_URL_FIELD = 'customfield_10932'
GITHUB_ISSUE_FIELD = 'customfield_13486'


def jql_field(field):
    return f"cf[{field.removeprefix('customfield_')}]"


def escape_jql(value):
    return (value or '').replace('\\', '\\\\').replace('"', '\\"')


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

    def _send(self, method, path, payload):
        req = request.Request(f'{self._base_url}{path}', method=method,
                              data=json.dumps(payload).encode())
        for name, value in self._headers.items():
            req.add_header(name, value)
        with request.urlopen(req) as response:
            body = response.read().decode()
        return json.loads(body) if body else {}

    def search(self, jql, fields):
        return self._send('POST', '/rest/api/3/search/jql',
                          {'jql': jql, 'fields': fields, 'maxResults': 50})

    def find_by_url_field(self, issue_type, field, url, fields):
        """
        Tickets of this type whose `field` holds this URL.

        Jira matches URL fields loosely, so the search asks for "contains" - falling
        back to exact match if the field rejects that - and the results are then
        compared properly.
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
