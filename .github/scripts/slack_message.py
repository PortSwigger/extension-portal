#!/usr/bin/env python3

"""Renders a Notification as the Slack message to post."""

import json
import os
import re
import sys

import notification as note
from github_actions_utils import set_output

ICONS = {note.SUBMITTED: '📥', note.FAILED: '⛔', note.REOPENED: '🔄',
         note.CHANGED: '✏️', note.CLOSED: '📁'}
DEFAULT_ICON = ICONS[note.SUBMITTED]

MARKERS = {note.ATTENTION: '⚠️', note.FAILURE: '🚨'}

HEADER_LIMIT = 150
TEXT_LIMIT = 3000
INLINE_WIDTH = 70

AVATAR = 'https://github.com/{login}.png?size=48'
PROFILE = 'https://github.com/{login}'
BROWSE = '{base}/browse/{key}'

NUMBERED = re.compile(r'^https://github\.com/[^/]+/[^/]+/(?:issues|pull)/(\d+)/?$')


def truncate(text, limit):
    return text if len(text) <= limit else text[:limit - 1] + '…'


def number(url):
    numbered = NUMBERED.match(url or '')
    return f'#{numbered.group(1)}' if numbered else ''


def ticket_url(base, key):
    base = (base or '').strip().rstrip('/')
    return BROWSE.format(base=base, key=key) if base.startswith('https://') and key else ''


def link(url, text):
    return f'<{url}|{text}>'


def header_block(text):
    return {'type': 'header',
            'text': {'type': 'plain_text', 'text': truncate(text, HEADER_LIMIT),
                     'emoji': True}}


def mrkdwn(text):
    return {'type': 'mrkdwn', 'text': truncate(text, TEXT_LIMIT)}


def context_block(elements):
    return {'type': 'context', 'elements': elements}


def text_block(text):
    return {'type': 'section', 'text': mrkdwn(text)}


def buttons_block(links):
    return {'type': 'actions',
            'elements': [{'type': 'button', 'url': url,
                          'text': {'type': 'plain_text', 'text': label, 'emoji': True}}
                         for label, url in links]}


def subtitle_of(notification):
    named = [notification.extension, notification.version,
             number(notification.issue_url), notification.ticket]
    return ' · '.join(part for part in named if part)


def body_of(notification):
    marker = MARKERS.get(notification.severity, '')
    action = f'{marker} {notification.action}'.strip() if notification.action else ''

    said = list(notification.changes.items())
    said.append(('Reason', notification.reason))
    said.append(('Action', action))
    return [(label, str(value).strip()) for label, value in said if str(value).strip()]


def detail_blocks(said):
    blocks, inline = [], []

    def flush():
        if inline:
            blocks.append(text_block('\n'.join(inline)))
            inline.clear()

    for label, value in said:
        if len(value) <= INLINE_WIDTH:
            inline.append(f'*{label}:* {value}')
            if sum(len(line) + 1 for line in inline) > TEXT_LIMIT:
                flush()
        else:
            flush()
            blocks.append(text_block(f'*{label}:*\n{value}'))

    flush()
    return blocks


def footer_block(notification):
    login = notification.actor
    if not login:
        return None

    did = notification.actor_did or 'Actioned'
    credited = [f'{did} by {link(PROFILE.format(login=login), login)}']
    if notification.actor_note:
        credited.append(notification.actor_note)

    return context_block([{'type': 'image', 'alt_text': login,
                           'image_url': AVATAR.format(login=login)},
                          mrkdwn(' · '.join(credited))])


def links_of(notification, jira_base_url):
    offered = [('View submission', notification.issue_url),
               ('View pull request', notification.pr_url),
               ('View original submission', notification.duplicate_url),
               ('View Jira', ticket_url(jira_base_url, notification.ticket))]
    return [(label, url) for label, url in offered if url]


def message_for(notification, jira_base_url=''):
    subtitle = subtitle_of(notification)
    body = detail_blocks(body_of(notification))
    footer = footer_block(notification)
    links = links_of(notification, jira_base_url)

    blocks = [header_block(f'{ICONS.get(notification.event, DEFAULT_ICON)} '
                           f'{notification.alert}')]
    if subtitle:
        blocks.append(context_block([mrkdwn(subtitle)]))
    if body:
        blocks.append({'type': 'divider'})
    blocks.extend(body)
    if footer:
        blocks.append(footer)
    if links:
        blocks.append(buttons_block(links))

    alert = notification.alert
    return {'text': f'{alert} · {subtitle}' if subtitle else alert, 'blocks': blocks}


if __name__ == '__main__':
    encoded = os.environ.get('PAYLOAD', '').strip()
    if not encoded:
        print('::warning::No notification to render - nothing was sent to Slack.')
        sys.exit(0)

    message = message_for(note.decode(encoded), os.environ.get('JIRA_BASE_URL', ''))
    set_output('message', json.dumps(message, separators=(',', ':')))

    sys.exit(0)
