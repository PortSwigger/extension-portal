#!/usr/bin/env python3

"""
Tests for extract_issue_fields.py
Run with: python extract_issue_fields_test.py
"""

import sys
import unittest
from pathlib import Path

# Make the script under test importable (it lives one directory up).
sys.path.insert(0, str(Path(__file__).parent.parent))

from extract_issue_fields import extract_issue_fields, submission_type

SUBMISSION_BODY = """### Extension URL

https://github.com/acme/widget

### Version number

1.2.3

### Select additional compatible products and features

- [x] Community
- [ ] DAST
- [X] Burp AI

### Author display name

Alice Smith
"""

UPDATE_BODY = """### Pull request URL

https://github.com/PortSwigger/widget/pull/9

### Version number

2.0.0

### Author display name

_No response_
"""


class SubmissionTypeTests(unittest.TestCase):
    def test_known_types(self):
        self.assertEqual(submission_type('Extension'), 'extension-submission')
        self.assertEqual(submission_type('Update'), 'extension-update')

    def test_unknown_type(self):
        self.assertEqual(submission_type('Bug'), '')
        self.assertEqual(submission_type(''), '')


class ExtractSubmissionTests(unittest.TestCase):
    def fields(self, **kwargs):
        defaults = {'body': SUBMISSION_BODY, 'title': 'Widget', 'issue_type_name': 'Extension'}
        defaults.update(kwargs)
        return extract_issue_fields(**defaults)

    def test_extracts_every_field(self):
        self.assertEqual(self.fields(), {
            'type': 'extension-submission',
            'title': 'Widget',
            'author': 'Alice Smith',
            'url': 'https://github.com/acme/widget',
            'version_number': '1.2.3',
            'product_compatibility': ['Community', 'Burp AI'],
        })

    def test_checkbox_is_case_insensitive_but_only_for_x(self):
        self.assertEqual(self.fields()['product_compatibility'], ['Community', 'Burp AI'])

    def test_pull_request_url_is_ignored_for_a_submission(self):
        self.assertEqual(self.fields(body=UPDATE_BODY)['url'], '')


class ExtractUpdateTests(unittest.TestCase):
    def fields(self, **kwargs):
        defaults = {'body': UPDATE_BODY, 'title': 'Widget', 'issue_type_name': 'Update'}
        defaults.update(kwargs)
        return extract_issue_fields(**defaults)

    def test_extracts_pull_request_url(self):
        self.assertEqual(self.fields()['url'], 'https://github.com/PortSwigger/widget/pull/9')

    def test_unanswered_optional_field_becomes_empty(self):
        self.assertEqual(self.fields()['author'], '')

    def test_no_compatibility_checkboxes_on_the_update_form(self):
        self.assertEqual(self.fields()['product_compatibility'], [])


class EdgeCaseTests(unittest.TestCase):
    def test_empty_body(self):
        fields = extract_issue_fields(body='', title='T', issue_type_name='Extension')
        self.assertEqual(fields['url'], '')
        self.assertEqual(fields['version_number'], '')
        self.assertEqual(fields['author'], '')
        self.assertEqual(fields['product_compatibility'], [])

    def test_body_without_any_headings(self):
        fields = extract_issue_fields(body='just prose', title='T', issue_type_name='Extension')
        self.assertEqual(fields['url'], '')

    def test_none_body_is_tolerated(self):
        self.assertEqual(extract_issue_fields(body=None, title='T', issue_type_name='Extension')['url'], '')

    def test_unknown_issue_type_yields_no_url(self):
        fields = extract_issue_fields(body=SUBMISSION_BODY, title='T', issue_type_name='Bug')
        self.assertEqual(fields['type'], '')
        self.assertEqual(fields['url'], '')

    def test_url_stops_at_whitespace(self):
        body = '### Extension URL\n\nhttps://github.com/acme/widget trailing words\n'
        fields = extract_issue_fields(body=body, title='T', issue_type_name='Extension')
        self.assertEqual(fields['url'], 'https://github.com/acme/widget')

    def test_title_defaults_to_empty(self):
        self.assertEqual(extract_issue_fields(body='', title=None, issue_type_name='Extension')['title'], '')


if __name__ == '__main__':
    unittest.main(verbosity=2)
