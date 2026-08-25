#!/usr/bin/env python3

"""
Tests for detect_issue_changes.py
Run with: python detect_issue_changes_test.py
"""

import sys
import unittest
from pathlib import Path

# Make the script under test importable (it lives one directory up).
sys.path.insert(0, str(Path(__file__).parent.parent))

import detect_issue_changes as dic
from extract_issue_fields import extract_issue_fields


def submission(url='https://github.com/acme/widget', version='1.0.0', overview='overview text'):
    return f"""### Extension URL

{url}

### Version number

{version}

### Author display name

Alice

### Extension overview

{overview}
"""


def update(url='https://github.com/PortSwigger/widget/pull/1', version='2.0.0'):
    return f"""### Pull request URL

{url}

### Version number

{version}

### Author display name

Alice
"""


def changes(current_body, previous_body, type_name='Extension',
            current_title='Widget', previous_title='Widget'):
    return dic.detect_changes(
        extract_issue_fields(body=current_body, title=current_title, issue_type_name=type_name),
        extract_issue_fields(body=previous_body, title=previous_title, issue_type_name=type_name),
    )


class IrrelevantEditTests(unittest.TestCase):
    """Edits that must stop the pipeline at the gate."""

    def test_overview_text_only(self):
        result = changes(submission(overview='new words'), submission(overview='old words'))
        self.assertFalse(result['any_changed'])

    def test_identical_bodies(self):
        result = changes(submission(), submission())
        self.assertFalse(result['any_changed'])

    def test_whitespace_only_title_change(self):
        result = changes(submission(), submission(),
                         current_title='  Widget ', previous_title='Widget')
        self.assertFalse(result['any_changed'])

    def test_url_differing_only_by_git_suffix_and_slash(self):
        result = changes(submission(url='https://github.com/acme/widget.git/'),
                         submission(url='https://github.com/acme/widget'))
        self.assertFalse(result['any_changed'])

    def test_update_title_is_not_recorded_on_the_ticket(self):
        result = changes(update(), update(), type_name='Update',
                         current_title='New name', previous_title='Old name')
        self.assertFalse(result['any_changed'])


class RelevantEditTests(unittest.TestCase):
    """Edits that must let the pipeline proceed."""

    def test_submission_title_changed(self):
        result = changes(submission(), submission(), current_title='New', previous_title='Old')
        self.assertTrue(result['any_changed'])
        self.assertTrue(result['summary_changed'])
        self.assertFalse(result['url_changed'])

    def test_submission_url_changed(self):
        result = changes(submission(url='https://github.com/acme/other'), submission())
        self.assertTrue(result['any_changed'])
        self.assertTrue(result['url_changed'])
        self.assertFalse(result['summary_changed'])

    def test_update_version_changed(self):
        result = changes(update(version='2.1.0'), update(), type_name='Update')
        self.assertTrue(result['any_changed'])
        self.assertTrue(result['summary_changed'])

    def test_update_pull_request_url_changed(self):
        result = changes(update(url='https://github.com/PortSwigger/widget/pull/2'),
                         update(), type_name='Update')
        self.assertTrue(result['any_changed'])
        self.assertTrue(result['url_changed'])

    def test_submission_version_alone_is_not_on_the_ticket(self):
        result = changes(submission(version='9.9.9'), submission())
        self.assertFalse(result['any_changed'])

    def test_both_changed(self):
        result = changes(submission(url='https://github.com/acme/other'), submission(),
                         current_title='New', previous_title='Old')
        self.assertTrue(result['summary_changed'])
        self.assertTrue(result['url_changed'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
