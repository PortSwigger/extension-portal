#!/usr/bin/env python3

"""
Tests for notification.py
Run with: python notification_test.py

The contract every producer reports through: what a submission is called, how
a headline adapts to it, and that severity is something a producer states
rather than something read back out of the wording.
"""

import sys
import unittest
from pathlib import Path

# Make the script under test importable (it lives one directory up).
sys.path.insert(0, str(Path(__file__).parent.parent))

import notification as note


class SubjectTests(unittest.TestCase):
    def test_the_types_github_records(self):
        self.assertEqual(note.subject_of('Extension'), note.EXTENSION)
        self.assertEqual(note.subject_of('Update'), note.UPDATE)

    def test_a_submission_github_did_not_type_still_has_a_name(self):
        for missing in ('', '   ', None, 'Something else'):
            self.assertEqual(note.subject_of(missing), note.UNTYPED, repr(missing))

    def test_no_name_is_the_word_issue(self):
        for name in (note.EXTENSION, note.UPDATE, note.UNTYPED):
            self.assertNotIn('issue', name.lower())


class HeadlineTests(unittest.TestCase):
    def test_every_header_leads_with_its_event(self):
        for event, said in note.HEADLINES.items():
            for subject in (note.EXTENSION, note.UPDATE, note.UNTYPED):
                alert = note.Notification(event, subject).alert
                self.assertTrue(alert.startswith(said), alert)
                self.assertNotIn('issue', alert.lower())

    def test_a_typed_submission_is_named_after_the_colon(self):
        self.assertEqual(note.Notification(note.SUBMITTED, note.EXTENSION).alert,
                         'New submission: extension')
        self.assertEqual(note.Notification(note.SUBMITTED, note.UPDATE).alert,
                         'New submission: update')

    def test_an_untyped_submission_is_not_named_twice(self):
        self.assertEqual(note.Notification(note.SUBMITTED, note.UNTYPED).alert,
                         'New submission')

    def test_the_five_things_that_can_happen(self):
        self.assertEqual(set(note.HEADLINES),
                         {note.SUBMITTED, note.FAILED, note.REOPENED,
                          note.CHANGED, note.CLOSED})

    def test_one_wording_serves_every_subject(self):
        for subject, expected in ((note.EXTENSION, 'Submission reopened: extension'),
                                  (note.UPDATE, 'Submission reopened: update'),
                                  (note.UNTYPED, 'Submission reopened')):
            self.assertEqual(note.Notification(note.REOPENED, subject).alert, expected)


class DetailTests(unittest.TestCase):
    def test_a_reason_and_an_action_are_kept_apart(self):
        reported = note.Notification(note.FAILED).because(
            reason='Because.', action='Do this.')
        self.assertEqual(reported.reason, 'Because.')
        self.assertEqual(reported.action, 'Do this.')

    def test_nothing_to_say_is_not_said(self):
        reported = note.Notification(note.FAILED).because(reason='   ', action='')
        self.assertEqual((reported.reason, reported.action), ('', ''))

    def test_saying_more_leaves_the_original_untouched(self):
        original = note.Notification(note.FAILED)
        original.because(reason='Because.')
        self.assertEqual(original.reason, '')

    def test_what_moved_is_recorded_separately_from_why(self):
        reported = note.Notification(note.CHANGED).moving({'Name': 'a → b', 'Version': ''})
        self.assertEqual(reported.changes, {'Name': 'a → b'})

    def test_severity_is_not_something_a_reason_can_change(self):
        reported = note.Notification(note.CHANGED, severity=note.ROUTINE).because(
            reason='it broke badly')
        self.assertEqual(reported.severity, note.ROUTINE)


class TransportTests(unittest.TestCase):
    def test_a_notification_survives_the_trip_between_jobs(self):
        reported = note.Notification(
            note.REOPENED, note.UPDATE, note.ATTENTION,
            extension='Autorize', version='1.2.3', ticket='BAPP-1',
            issue_url='https://github.com/o/r/issues/1',
            actor='alice', actor_did='Reopened').because(reason='Because.')
        self.assertEqual(note.decode(note.encode(reported)), reported)

    def test_the_encoding_hides_nothing_from_itself(self):
        reported = note.Notification(note.CHANGED).because(reason='a · b → c ⚠️')
        self.assertEqual(note.decode(note.encode(reported)).reason, 'a · b → c ⚠️')


if __name__ == '__main__':
    unittest.main()
