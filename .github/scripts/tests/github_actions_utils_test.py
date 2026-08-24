#!/usr/bin/env python3

"""
Tests for github_actions_utils.py
Run with: python github_actions_utils_test.py
"""

import os
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

# Add parent directory to path to import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

from github_actions_utils import set_output


def parse_output(text):
    """
    Parse heredoc-formatted GitHub Actions output into (key, value) pairs.

    Mirrors how the runner reads $GITHUB_OUTPUT: a 'key<<delimiter' line,
    the value, then the delimiter alone on its own line.
    """
    pairs = []
    lines = text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        if '<<' in line:
            key, delimiter = line.split('<<', 1)
            i += 1
            value = []
            while i < len(lines) and lines[i] != delimiter:
                value.append(lines[i])
                i += 1
            pairs.append((key, '\n'.join(value)))
        i += 1
    return pairs


class TestSetOutputToFile(unittest.TestCase):
    """Tests for the file-writing path, driven by an explicit output_file."""

    def setUp(self):
        handle, self.output_file = tempfile.mkstemp()
        os.close(handle)

    def tearDown(self):
        os.unlink(self.output_file)

    def read_output(self):
        with open(self.output_file) as f:
            return f.read()

    def test_writes_heredoc_entry(self):
        set_output('normalized_url', 'https://github.com/owner/repo', self.output_file)
        self.assertEqual(
            parse_output(self.read_output()),
            [('normalized_url', 'https://github.com/owner/repo')]
        )

    def test_appends_rather_than_truncates(self):
        set_output('owner', 'PortSwigger', self.output_file)
        set_output('repo', 'turbo-intruder', self.output_file)
        self.assertEqual(
            parse_output(self.read_output()),
            [('owner', 'PortSwigger'), ('repo', 'turbo-intruder')]
        )

    def test_value_containing_newlines_is_preserved(self):
        set_output('error_message', 'line one\nline two', self.output_file)
        self.assertEqual(
            parse_output(self.read_output()),
            [('error_message', 'line one\nline two')]
        )

    def test_value_containing_equals_is_preserved(self):
        set_output('error_message', 'a=b', self.output_file)
        self.assertEqual(parse_output(self.read_output()), [('error_message', 'a=b')])

    def test_value_cannot_inject_additional_entries(self):
        # A value that mimics an output entry must stay a single value
        set_output('error_message', 'x\ninjected=true', self.output_file)
        parsed = parse_output(self.read_output())
        self.assertEqual(parsed, [('error_message', 'x\ninjected=true')])
        self.assertNotIn('injected', dict(parsed))

    def test_value_cannot_close_the_delimiter(self):
        # The delimiter is random per call, so a guessed one is just text
        set_output('error_message', 'x\nghadelimiter_0000\ninjected=true', self.output_file)
        parsed = parse_output(self.read_output())
        self.assertEqual(len(parsed), 1)
        self.assertNotIn('injected', dict(parsed))

    def test_delimiter_differs_between_calls(self):
        set_output('first', 'a', self.output_file)
        set_output('second', 'b', self.output_file)
        delimiters = [
            line.split('<<', 1)[1]
            for line in self.read_output().split('\n') if '<<' in line
        ]
        self.assertEqual(len(delimiters), 2)
        self.assertNotEqual(delimiters[0], delimiters[1])

    def test_non_string_value_is_written(self):
        set_output('count', 3, self.output_file)
        self.assertEqual(parse_output(self.read_output()), [('count', '3')])

    def test_unwritable_file_warns_without_raising(self):
        unwritable = os.path.join(self.output_file, 'not-a-directory')
        with patch('sys.stderr', new=StringIO()) as stderr:
            set_output('key', 'value', unwritable)
        self.assertIn('::warning::', stderr.getvalue())
        self.assertIn('Could not write key', stderr.getvalue())


class TestSetOutputDestination(unittest.TestCase):
    """Tests for how the destination is resolved."""

    def setUp(self):
        handle, self.output_file = tempfile.mkstemp()
        os.close(handle)

    def tearDown(self):
        os.unlink(self.output_file)

    @patch.dict('os.environ', {}, clear=True)
    def test_falls_back_to_stdout_when_no_destination(self):
        with patch('sys.stdout', new=StringIO()) as stdout:
            set_output('language', 'Java')
        self.assertEqual(stdout.getvalue(), 'language=Java\n')

    @patch.dict('os.environ', {}, clear=True)
    def test_defaults_to_github_output_env_var(self):
        os.environ['GITHUB_OUTPUT'] = self.output_file
        set_output('language', 'Java')
        with open(self.output_file) as f:
            self.assertEqual(parse_output(f.read()), [('language', 'Java')])

    def test_explicit_output_file_overrides_env_var(self):
        with patch.dict('os.environ', {'GITHUB_OUTPUT': '/dev/full'}):
            set_output('language', 'Java', self.output_file)
        with open(self.output_file) as f:
            self.assertEqual(parse_output(f.read()), [('language', 'Java')])


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestSetOutputToFile))
    suite.addTests(loader.loadTestsFromTestCase(TestSetOutputDestination))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())
