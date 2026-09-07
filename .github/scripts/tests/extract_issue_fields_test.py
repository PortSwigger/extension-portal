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

from extract_issue_fields import (
    SANITIZER_CONFIRMATION_KEYS,
    github_issue_type,
    checked_confirmations,
    extract_issue_fields,
    submission_type,
)

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

CONFIRMATION_BOXES = """
### I confirm that the following is true:

- [X] I have permission from all relevant persons to submit this extension to the BApp Store for public use, under the [terms and conditions of the EULA](https://portswigger.net/legal).
- [X] I have read and understood the [submission requirements for the BApp Store](https://portswigger.net/burp/documentation/desktop/extend-burp/extensions/creating/bapp-store-acceptance-criteria).
"""

BOTH_CONFIRMATIONS = ['acceptance-criteria', 'eula']


class SubmissionTypeTests(unittest.TestCase):
    def test_known_types(self):
        self.assertEqual(submission_type('Extension'), 'extension-submission')
        self.assertEqual(submission_type('Update'), 'extension-update')

    def test_unknown_type(self):
        self.assertEqual(submission_type('Bug'), '')
        self.assertEqual(submission_type(''), '')

    def test_type_wins_over_the_body(self):
        self.assertEqual(submission_type('Update', SUBMISSION_BODY), 'extension-update')

    def test_a_typed_issue_is_never_inferred_from_its_body(self):
        self.assertEqual(submission_type('Bug', SUBMISSION_BODY), '')

    def test_inferred_from_an_extension_url_heading(self):
        self.assertEqual(submission_type('', SUBMISSION_BODY), 'extension-submission')

    def test_inferred_from_a_pull_request_url_heading(self):
        self.assertEqual(submission_type('', UPDATE_BODY), 'extension-update')

    def test_submission_heading_wins_when_a_body_carries_both(self):
        self.assertEqual(
            submission_type('', SUBMISSION_BODY + UPDATE_BODY), 'extension-submission')

    def test_not_inferred_from_prose(self):
        self.assertEqual(submission_type('', 'please add my extension'), '')

    def test_not_inferred_from_a_heading_without_a_value(self):
        self.assertEqual(submission_type('', '### Extension URL\n\n'), '')

    def test_empty_body_is_tolerated(self):
        self.assertEqual(submission_type('', ''), '')
        self.assertEqual(submission_type('', None), '')


class GithubIssueTypeTests(unittest.TestCase):
    def test_round_trips_every_submission_type(self):
        for name in ('Extension', 'Update'):
            self.assertEqual(github_issue_type(submission_type(name)), name)

    def test_nothing_to_record_without_a_type(self):
        self.assertEqual(github_issue_type(''), '')


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
        fields = extract_issue_fields(body=None, title='T', issue_type_name='Extension')
        self.assertEqual(fields['url'], '')

    def test_unknown_issue_type_yields_no_url(self):
        fields = extract_issue_fields(body=SUBMISSION_BODY, title='T', issue_type_name='Bug')
        self.assertEqual(fields['type'], '')
        self.assertEqual(fields['url'], '')

    def test_an_untyped_issue_is_read_from_its_body(self):
        fields = extract_issue_fields(body=SUBMISSION_BODY, title='T', issue_type_name='')
        self.assertEqual(fields['type'], 'extension-submission')
        self.assertEqual(fields['url'], 'https://github.com/acme/widget')

    def test_an_untyped_update_is_read_from_its_body(self):
        fields = extract_issue_fields(body=UPDATE_BODY, title='T', issue_type_name='')
        self.assertEqual(fields['type'], 'extension-update')
        self.assertEqual(fields['url'], 'https://github.com/PortSwigger/widget/pull/9')

    def test_url_stops_at_whitespace(self):
        body = '### Extension URL\n\nhttps://github.com/acme/widget trailing words\n'
        fields = extract_issue_fields(body=body, title='T', issue_type_name='Extension')
        self.assertEqual(fields['url'], 'https://github.com/acme/widget')

    def test_title_defaults_to_empty(self):
        fields = extract_issue_fields(body='', title=None, issue_type_name='Extension')
        self.assertEqual(fields['title'], '')


class CheckedConfirmationsTests(unittest.TestCase):
    def test_both_boxes_ticked(self):
        self.assertEqual(checked_confirmations(CONFIRMATION_BOXES), BOTH_CONFIRMATIONS)

    def test_keys_match_the_ones_sanitize_inputs_declares(self):
        self.assertEqual(sorted(SANITIZER_CONFIRMATION_KEYS.values()), BOTH_CONFIRMATIONS)

    def test_result_is_sorted_so_the_output_is_stable(self):
        ticked = checked_confirmations(CONFIRMATION_BOXES)
        self.assertEqual(ticked, sorted(ticked))

    def test_lowercase_x_counts(self):
        self.assertEqual(
            checked_confirmations(CONFIRMATION_BOXES.replace('[X]', '[x]')),
            BOTH_CONFIRMATIONS)

    def test_unticked_boxes_do_not_count(self):
        self.assertEqual(checked_confirmations(CONFIRMATION_BOXES.replace('[X]', '[ ]')), [])

    def test_only_one_ticked(self):
        body = CONFIRMATION_BOXES.replace(
            '- [X] I have read and understood', '- [ ] I have read and understood')
        self.assertEqual(checked_confirmations(body), ['eula'])

    def test_reworded_label_does_not_count(self):
        reworded = CONFIRMATION_BOXES.replace(
            '- [X] I have permission', '- [X] Yes, I have permission')
        self.assertEqual(checked_confirmations(reworded), ['acceptance-criteria'])

    def test_compatibility_checkboxes_are_not_confirmations(self):
        self.assertEqual(checked_confirmations(SUBMISSION_BODY), [])

    def test_prose_body(self):
        self.assertEqual(checked_confirmations('please add my extension'), [])

    def test_empty_body(self):
        self.assertEqual(checked_confirmations(''), [])
        self.assertEqual(checked_confirmations(None), [])

    def test_no_duplicates_when_a_box_appears_twice(self):
        self.assertEqual(
            checked_confirmations(CONFIRMATION_BOXES + CONFIRMATION_BOXES),
            BOTH_CONFIRMATIONS)


if __name__ == '__main__':
    unittest.main(verbosity=2)
