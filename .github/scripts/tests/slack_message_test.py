#!/usr/bin/env python3

"""
Tests for slack_message.py
Run with: python slack_message_test.py

The renderer is the one place that decides how a notification looks, so these
cover the shape every category comes out in: what heads it, what identifies the
submission, what reaches the body, and what becomes a button.
"""

import sys
import unittest
from pathlib import Path

# Make the script under test importable (it lives one directory up).
sys.path.insert(0, str(Path(__file__).parent.parent))

import notification as note
import slack_message as sm

ISSUE = 'https://github.com/PortSwigger/extension-portal/issues/412'
PR = 'https://github.com/PortSwigger/autorize/pull/7'
JIRA = 'https://example.atlassian.net'


def notified(event=note.REOPENED, severity=note.ROUTINE, **kw):
    return note.Notification(event, kw.pop('subject', note.EXTENSION), severity, **kw)


def blocks_of(notification, base=''):
    return sm.message_for(notification, base)['blocks']


def of_type(notification, kind, base=''):
    return [b for b in blocks_of(notification, base) if b['type'] == kind]


def lines(notification, base=''):
    return [line for block in of_type(notification, 'section', base)
            for line in block['text']['text'].split('\n')]


def buttons(notification, base=''):
    return [(e['text']['text'], e['url'])
            for block in of_type(notification, 'actions', base) for e in block['elements']]


def subtitle(notification, base=''):
    contexts = of_type(notification, 'context', base)
    return contexts[0]['elements'][-1]['text'] if contexts else ''


class HeaderTests(unittest.TestCase):
    def header(self, notification):
        return of_type(notification, 'header')[0]['text']['text']

    def test_the_headline_names_the_submission_and_the_event(self):
        self.assertIn('Submission reopened: extension', self.header(notified()))
        self.assertIn('New submission: extension', self.header(notified(note.SUBMITTED)))

    def test_one_wording_serves_every_subject(self):
        for subject, expected in ((note.EXTENSION, 'Submission reopened: extension'),
                                  (note.UPDATE, 'Submission reopened: update'),
                                  (note.UNTYPED, 'Submission reopened')):
            self.assertIn(expected, self.header(notified(subject=subject)))

    def test_a_lowercase_slot_reads_inside_a_sentence(self):
        self.assertIn('New submission: update',
                      self.header(notified(note.SUBMITTED, subject=note.UPDATE)))

    def test_the_event_decides_the_icon(self):
        icons = {self.header(notified(event)).split()[0] for event in note.HEADLINES}
        self.assertEqual(len(icons), len(note.HEADLINES), icons)

    def test_everything_of_a_kind_looks_alike(self):
        for event in note.HEADLINES:
            icons = {self.header(notified(event, severity)).split()[0]
                     for severity in (note.ROUTINE, note.ATTENTION, note.FAILURE)}
            self.assertEqual(len(icons), 1, f'{event}: {icons}')

    def test_the_wording_of_a_detail_cannot_change_the_icon(self):
        quiet = notified(severity=note.ROUTINE)
        self.assertEqual(self.header(quiet),
                         self.header(quiet.because(reason='it all went fine ✅')))

    def test_an_overlong_headline_is_cut_to_what_slack_accepts(self):
        self.assertLessEqual(
            len(self.header(notified(subject='x' * 400))), sm.HEADER_LIMIT)


class SubtitleTests(unittest.TestCase):
    def test_the_submission_is_named_the_way_you_would_say_it(self):
        self.assertEqual(
            subtitle(notified(extension='Autorize', version='1.0.0',
                              issue_url=ISSUE, ticket='BAPP-1')),
            'Autorize · 1.0.0 · #412 · BAPP-1')

    def test_each_part_is_optional(self):
        self.assertEqual(subtitle(notified(extension='Autorize')), 'Autorize')
        self.assertEqual(subtitle(notified(ticket='BAPP-1')), 'BAPP-1')

    def test_nothing_to_say_leaves_the_subtitle_out(self):
        self.assertEqual(of_type(notified(), 'context'), [])

    def test_a_url_that_names_no_number_contributes_nothing(self):
        self.assertEqual(
            subtitle(notified(extension='Autorize',
                              issue_url='https://github.com/PortSwigger/autorize')),
            'Autorize')

    def test_the_ticket_names_the_submission_with_or_without_a_jira_host(self):
        for base in (JIRA, ''):
            self.assertEqual(subtitle(notified(extension='Autorize', ticket='BAPP-1'), base),
                             'Autorize · BAPP-1', base)


class SeverityTests(unittest.TestCase):
    """Severity shows where the work is, not beside the headline."""

    def test_routine_work_is_marked_in_no_way_at_all(self):
        reported = notified(severity=note.ROUTINE).because(action='Do this.')
        self.assertEqual(lines(reported), ['*Action:* Do this.'])

    def test_something_needing_a_person_is_marked_on_the_action(self):
        reported = notified(severity=note.ATTENTION).because(action='Do this.')
        self.assertEqual(lines(reported), ['*Action:* ⚠️ Do this.'])

    def test_a_pipeline_failure_is_marked_more_loudly(self):
        reported = notified(severity=note.FAILURE).because(action='Do this.')
        self.assertEqual(lines(reported), ['*Action:* 🚨 Do this.'])

    def test_nothing_to_do_carries_no_marker_however_severe(self):
        reported = notified(severity=note.FAILURE).because(reason='It broke.')
        self.assertEqual(lines(reported), ['*Reason:* It broke.'])


class BodyTests(unittest.TestCase):
    def test_short_facts_sit_on_a_line_each_in_one_block(self):
        reported = notified().moving({'Board': 'off the board', 'Queue': 'Concept review'})
        self.assertEqual(len(of_type(reported, 'section')), 1)
        self.assertEqual(lines(reported),
                         ['*Board:* off the board', '*Queue:* Concept review'])

    def test_no_two_column_grid_is_used(self):
        for block in blocks_of(notified().moving({'Board': 'off', 'Queue': 'Concept review'})):
            self.assertNotIn('fields', block)

    def test_a_long_value_gets_a_block_with_its_label_above_it(self):
        reason = 'because ' * 20
        [section] = of_type(notified().because(reason=reason), 'section')
        self.assertEqual(section['text']['text'], f'*Reason:*\n{reason.strip()}')

    def test_the_body_reads_as_what_happened_then_why_then_what_to_do(self):
        reported = notified().moving({'Board': 'off'}).because(reason='Because.',
                                                               action='Do this.')
        self.assertEqual(lines(reported),
                         ['*Board:* off', '*Reason:* Because.', '*Action:* Do this.'])

    def test_that_order_holds_whatever_order_the_producer_used(self):
        one = notified().because(reason='Because.', action='Do this.')
        other = notified().because(action='Do this.', reason='Because.')
        self.assertEqual(lines(one), lines(other))

    def test_an_empty_value_is_left_out_entirely(self):
        self.assertEqual(lines(notified().moving({'Board': '', 'Queue': '   '}).because(reason='Because.')),
                         ['*Reason:* Because.'])

    def test_nothing_to_report_needs_no_divider(self):
        self.assertEqual(of_type(notified(issue_url=ISSUE), 'divider'), [])

    def test_a_body_is_divided_from_the_header(self):
        self.assertEqual(blocks_of(notified().because(reason='Because.'))[1]['type'], 'divider')

    def test_an_overlong_value_is_cut_to_what_slack_accepts(self):
        [section] = of_type(notified().because(reason='r' * 5000), 'section')
        self.assertLessEqual(len(section['text']['text']), sm.TEXT_LIMIT)


class AttributionTests(unittest.TestCase):
    def footer(self, notification):
        return of_type(notification, 'context')[-1]

    def test_the_actor_gets_their_github_avatar(self):
        [image] = [e for e in self.footer(notified(actor='alice', actor_did='Reopened'))['elements']
                   if e['type'] == 'image']
        self.assertEqual(image['image_url'], 'https://github.com/alice.png?size=48')
        self.assertEqual(image['alt_text'], 'alice')

    def test_the_actor_is_linked_to_their_profile(self):
        text = self.footer(notified(actor='alice', actor_did='Reopened'))['elements'][-1]['text']
        self.assertEqual(text, 'Reopened by <https://github.com/alice|alice>')

    def test_the_verb_is_the_producer_s(self):
        for did in ('Submitted', 'Reopened', 'Closed', 'Edited'):
            text = self.footer(notified(actor='alice', actor_did=did))['elements'][-1]['text']
            self.assertTrue(text.startswith(f'{did} by '), text)

    def test_a_note_qualifying_the_actor_is_kept(self):
        text = self.footer(notified(actor='mallory', actor_did='Edited',
                                    actor_note='none access'))['elements'][-1]['text']
        self.assertTrue(text.endswith('· none access'), text)

    def test_an_actor_the_pipeline_could_not_name_leaves_no_empty_row(self):
        self.assertEqual(of_type(notified(extension='Autorize'), 'context'),
                         of_type(notified(extension='Autorize', actor_did='Reopened'), 'context'))

    def test_the_attribution_sits_below_what_it_explains(self):
        reported = notified(actor='alice', actor_did='Reopened').because(reason='Because.')
        self.assertEqual([b['type'] for b in blocks_of(reported)],
                         ['header', 'divider', 'section', 'context'])

    def test_an_attribution_alone_needs_no_divider(self):
        self.assertEqual(of_type(notified(actor='alice', actor_did='Reopened'), 'divider'), [])


class ButtonTests(unittest.TestCase):
    def test_where_to_go_next_nearest_first(self):
        reported = notified(subject=note.UPDATE, issue_url=ISSUE, pr_url=PR,
                            ticket='BAPP-1')
        self.assertEqual([label for label, _ in buttons(reported, JIRA)],
                         ['View submission', 'View pull request', 'View Jira'])

    def test_a_duplicate_points_at_what_it_duplicates(self):
        reported = notified(issue_url=ISSUE, duplicate_url='https://x/1')
        self.assertEqual(buttons(reported),
                         [('View submission', ISSUE), ('View original submission', 'https://x/1')])

    def test_no_button_calls_the_submission_an_issue(self):
        reported = notified(issue_url=ISSUE, pr_url=PR, duplicate_url='https://x/1',
                            ticket='BAPP-1')
        for label, _ in buttons(reported, JIRA):
            self.assertNotIn('issue', label.lower(), label)

    def test_the_ticket_button_opens_the_ticket(self):
        self.assertEqual(buttons(notified(ticket='BAPP-1'), JIRA),
                         [('View Jira', f'{JIRA}/browse/BAPP-1')])

    def test_a_trailing_slash_on_the_host_does_not_double_up(self):
        self.assertEqual(buttons(notified(ticket='BAPP-1'), JIRA + '/'),
                         [('View Jira', f'{JIRA}/browse/BAPP-1')])

    def test_without_a_jira_host_there_is_no_ticket_button(self):
        self.assertEqual(buttons(notified(ticket='BAPP-1'), ''), [])

    def test_a_host_that_is_not_an_https_url_is_refused(self):
        for base in ('not-a-url', 'example.atlassian.net', 'http://example.atlassian.net', ' '):
            self.assertEqual(buttons(notified(ticket='BAPP-1'), base), [], base)

    def test_no_ticket_means_no_button_however_good_the_host(self):
        self.assertEqual(buttons(notified(), JIRA), [])


class FallbackTests(unittest.TestCase):
    def test_the_preview_names_the_alert_and_the_submission(self):
        message = sm.message_for(notified(extension='Autorize', version='1.0.0'))
        self.assertEqual(message['text'],
                         'Submission reopened: extension · Autorize · 1.0.0')

    def test_the_preview_falls_back_to_the_alert_alone(self):
        self.assertEqual(sm.message_for(notified())['text'], 'Submission reopened: extension')


class ShapeTests(unittest.TestCase):
    """Every category comes out in the same order, with the empty parts gone."""

    def test_a_routine_report_is_a_headline_a_subtitle_and_a_way_in(self):
        reported = notified(note.SUBMITTED, extension='Autorize',
                            version='1.0.0', issue_url=ISSUE, ticket='BAPP-1')
        self.assertEqual([b['type'] for b in blocks_of(reported, JIRA)],
                         ['header', 'context', 'actions'])

    def test_an_attributed_routine_report_adds_only_the_attribution(self):
        reported = notified(note.SUBMITTED, extension='Autorize',
                            issue_url=ISSUE, ticket='BAPP-1',
                            actor='carol', actor_did='Submitted')
        self.assertEqual([b['type'] for b in blocks_of(reported, JIRA)],
                         ['header', 'context', 'context', 'actions'])

    def test_a_full_notification_keeps_every_part_in_its_place(self):
        reported = notified(note.CHANGED, note.ATTENTION,
                            extension='Autorize', issue_url=ISSUE, ticket='BAPP-1',
                            actor='mallory', actor_did='Edited', actor_note='none access'
                            ).moving({'Extension URL': 'https://a/old → https://b/new'}
                                     ).because(action='Treat as a new submission - review '
                                                      'has not been re-run and the ticket '
                                                      'has NOT been updated.')
        self.assertEqual([b['type'] for b in blocks_of(reported, JIRA)],
                         ['header', 'context', 'divider', 'section', 'section',
                          'context', 'actions'])


if __name__ == '__main__':
    unittest.main()
