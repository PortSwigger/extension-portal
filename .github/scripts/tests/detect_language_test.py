#!/usr/bin/env python3

"""
Tests for detect_language.py
Run with: python detect_language_test.py
"""

import json
import sys
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
from urllib.error import HTTPError

# Add parent directory to path to import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

import detect_language


class TestExtractOwnerRepo(unittest.TestCase):
    """Tests for extract_owner_repo function."""

    def test_https_url(self):
        owner, repo = detect_language.extract_owner_repo('https://github.com/owner/repo')
        self.assertEqual(owner, 'owner')
        self.assertEqual(repo, 'repo')

    def test_https_url_with_www(self):
        owner, repo = detect_language.extract_owner_repo('https://www.github.com/owner/repo')
        self.assertEqual(owner, 'owner')
        self.assertEqual(repo, 'repo')

    def test_url_without_protocol(self):
        owner, repo = detect_language.extract_owner_repo('github.com/owner/repo')
        self.assertEqual(owner, 'owner')
        self.assertEqual(repo, 'repo')

    def test_url_with_trailing_slash(self):
        owner, repo = detect_language.extract_owner_repo('https://github.com/owner/repo/')
        self.assertEqual(owner, 'owner')
        self.assertEqual(repo, 'repo')

    def test_owner_with_hyphens(self):
        owner, repo = detect_language.extract_owner_repo('https://github.com/my-org-name/repo')
        self.assertEqual(owner, 'my-org-name')
        self.assertEqual(repo, 'repo')

    def test_repo_with_dots_and_underscores(self):
        owner, repo = detect_language.extract_owner_repo('https://github.com/owner/my.repo_name')
        self.assertEqual(owner, 'owner')
        self.assertEqual(repo, 'my.repo_name')

    def test_invalid_url(self):
        with self.assertRaises(ValueError) as cm:
            detect_language.extract_owner_repo('https://gitlab.com/owner/repo')
        self.assertIn('Could not extract owner/repo from URL', str(cm.exception))

    def test_missing_repo(self):
        with self.assertRaises(ValueError) as cm:
            detect_language.extract_owner_repo('https://github.com/owner')
        self.assertIn('Could not extract owner/repo from URL', str(cm.exception))


class TestFetchLanguages(unittest.TestCase):
    """Tests for fetch_languages function."""

    @patch('detect_language.request.urlopen')
    def test_successful_fetch_without_token(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            'Java': 50000,
            'Python': 30000,
            'JavaScript': 20000
        }).encode()
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        result = detect_language.fetch_languages('owner', 'repo')

        self.assertEqual(result, {
            'Java': 50000,
            'Python': 30000,
            'JavaScript': 20000
        })

    @patch('detect_language.request.urlopen')
    def test_successful_fetch_with_token(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({'Java': 50000}).encode()
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        result = detect_language.fetch_languages('owner', 'repo', 'test_token')

        self.assertEqual(result, {'Java': 50000})

    @patch('detect_language.request.urlopen')
    def test_404_error(self, mock_urlopen):
        mock_error = HTTPError('url', 404, 'Not Found', {}, None)
        mock_urlopen.side_effect = mock_error

        with self.assertRaises(ValueError) as cm:
            detect_language.fetch_languages('owner', 'repo')
        self.assertIn('GitHub repository not found', str(cm.exception))
        self.assertIn('owner/repo', str(cm.exception))

    @patch('detect_language.request.urlopen')
    def test_other_http_error(self, mock_urlopen):
        mock_error = HTTPError('url', 403, 'Forbidden', {}, None)
        mock_urlopen.side_effect = mock_error

        with self.assertRaises(ValueError) as cm:
            detect_language.fetch_languages('owner', 'repo')
        self.assertIn('GitHub API error', str(cm.exception))
        self.assertIn('403', str(cm.exception))


class TestDetectLanguage(unittest.TestCase):
    """Tests for detect_language function."""

    @patch('detect_language.fetch_languages')
    def test_java_repository(self, mock_fetch):
        mock_fetch.return_value = {
            'Java': 100000,
            'JavaScript': 5000,
            'HTML': 2000
        }

        result = detect_language.detect_language('https://github.com/owner/repo')
        self.assertEqual(result, 'Java')

    @patch('detect_language.fetch_languages')
    def test_python_repository(self, mock_fetch):
        mock_fetch.return_value = {
            'Python': 80000,
            'Shell': 1000
        }

        result = detect_language.detect_language('https://github.com/owner/repo')
        self.assertEqual(result, 'Python')

    @patch('detect_language.fetch_languages')
    def test_ruby_repository(self, mock_fetch):
        mock_fetch.return_value = {
            'Ruby': 60000,
            'HTML': 10000
        }

        result = detect_language.detect_language('https://github.com/owner/repo')
        self.assertEqual(result, 'Ruby')

    @patch('detect_language.fetch_languages')
    def test_kotlin_repository_returns_java(self, mock_fetch):
        mock_fetch.return_value = {
            'Kotlin': 90000,
            'Java': 10000
        }

        result = detect_language.detect_language('https://github.com/owner/repo')
        self.assertEqual(result, 'Java')

    @patch('detect_language.fetch_languages')
    def test_kotlin_alias_case_insensitive(self, mock_fetch):
        mock_fetch.return_value = {
            'Kotlin': 50000,
            'Python': 30000
        }

        result = detect_language.detect_language('https://github.com/owner/repo')
        self.assertEqual(result, 'Java')

    @patch('detect_language.fetch_languages')
    def test_unsupported_languages_only(self, mock_fetch):
        mock_fetch.return_value = {
            'JavaScript': 100000,
            'TypeScript': 50000,
            'HTML': 20000
        }

        result = detect_language.detect_language('https://github.com/owner/repo')
        self.assertEqual(result, 'Unknown')

    @patch('detect_language.fetch_languages')
    def test_no_languages(self, mock_fetch):
        mock_fetch.return_value = {}

        result = detect_language.detect_language('https://github.com/owner/repo')
        self.assertEqual(result, 'Unknown')

    @patch('detect_language.fetch_languages')
    def test_mixed_case_language_names(self, mock_fetch):
        mock_fetch.return_value = {
            'JAVA': 50000,
            'python': 30000
        }

        result = detect_language.detect_language('https://github.com/owner/repo')
        self.assertIn(result, ['JAVA', 'python'])

    @patch('detect_language.fetch_languages')
    def test_multiple_supported_languages(self, mock_fetch):
        mock_fetch.return_value = {
            'Java': 40000,
            'Python': 60000,
            'Ruby': 20000
        }

        result = detect_language.detect_language('https://github.com/owner/repo')
        self.assertEqual(result, 'Python')

    @patch('detect_language.fetch_languages')
    def test_with_github_token(self, mock_fetch):
        mock_fetch.return_value = {'Java': 50000}

        result = detect_language.detect_language('https://github.com/owner/repo', 'test_token')
        self.assertEqual(result, 'Java')
        mock_fetch.assert_called_once_with('owner', 'repo', 'test_token')


class TestMain(unittest.TestCase):
    """Tests for main function."""

    @patch('detect_language.detect_language')
    @patch('detect_language.set_output')
    @patch('sys.argv', ['detect_language.py', 'https://github.com/owner/repo'])
    @patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'})
    def test_main_success(self, mock_set_output, mock_detect):
        mock_detect.return_value = 'Java'

        # Main doesn't exit on success, just returns
        detect_language.main()

        mock_detect.assert_called_once_with('https://github.com/owner/repo', 'test_token')
        mock_set_output.assert_called_once_with('language', 'Java')

    @patch('detect_language.detect_language')
    @patch('detect_language.set_output')
    @patch('sys.argv', ['detect_language.py', 'https://github.com/owner/repo'])
    @patch.dict('os.environ', {}, clear=True)
    def test_main_without_token(self, mock_set_output, mock_detect):
        mock_detect.return_value = 'Python'

        # Main doesn't exit on success, just returns
        detect_language.main()

        mock_detect.assert_called_once_with('https://github.com/owner/repo', None)

    @patch('detect_language.set_output')
    @patch('sys.argv', ['detect_language.py'])
    def test_main_missing_url(self, mock_set_output):
        with self.assertRaises(SystemExit) as cm:
            with patch('sys.stderr', new=StringIO()):
                detect_language.main()

        self.assertEqual(cm.exception.code, 1)
        mock_set_output.assert_called_once_with('error_message', 'Repository URL is required')

    @patch('detect_language.detect_language')
    @patch('detect_language.set_output')
    @patch('sys.argv', ['detect_language.py', 'https://github.com/owner/repo'])
    def test_main_detect_language_error(self, mock_set_output, mock_detect):
        mock_detect.side_effect = ValueError('GitHub repository not found: owner/repo')

        with self.assertRaises(SystemExit) as cm:
            with patch('sys.stderr', new=StringIO()):
                detect_language.main()

        self.assertEqual(cm.exception.code, 1)
        mock_set_output.assert_called_once_with('error_message', 'GitHub repository not found: owner/repo')


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestExtractOwnerRepo))
    suite.addTests(loader.loadTestsFromTestCase(TestFetchLanguages))
    suite.addTests(loader.loadTestsFromTestCase(TestDetectLanguage))
    suite.addTests(loader.loadTestsFromTestCase(TestMain))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())
