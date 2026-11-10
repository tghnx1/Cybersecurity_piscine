import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

import arachnida


class TestArachnidaImport(unittest.TestCase):
    """The module must be importable without starting the command-line program."""

    def test_validate_is_available(self):
        self.assertTrue(callable(arachnida.validate))
        self.assertTrue(callable(arachnida.fetch_page))


class TestFetchPage(unittest.TestCase):
    @patch("arachnida.urlopen")
    def test_fetches_page_contents(self, mock_urlopen):
        response = MagicMock()
        response.read.return_value = b"<html>page</html>"
        mock_urlopen.return_value.__enter__.return_value = response

        contents = arachnida.fetch_page("https://example.com")

        self.assertEqual(contents, b"<html>page</html>")
        request = mock_urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://example.com")
        self.assertIn("Arachnida spider", request.get_header("User-agent"))

    @patch("arachnida.urlopen", side_effect=arachnida.URLError("offline"))
    def test_returns_none_when_download_fails(self, mock_urlopen):
        self.assertIsNone(arachnida.fetch_page("https://example.com"))
        mock_urlopen.assert_called_once()


class TestHTMLParsing(unittest.TestCase):
    def test_decode_page(self):
        self.assertEqual(arachnida.decode_page(b"<p>caf\xc3\xa9</p>"),
                         "<p>café</p>")

    def test_extracts_absolute_and_relative_image_urls(self):
        html = """
            <img src="images/one.jpg">
            <IMG src="/two.png">
            <img src="https://cdn.example.org/three.gif">
        """
        self.assertEqual(
            arachnida.extract_image_urls(html, "https://example.org/page/index.html"),
            [
                "https://example.org/page/images/one.jpg",
                "https://example.org/two.png",
                "https://cdn.example.org/three.gif",
            ],
        )

    def test_removes_duplicates_and_ignores_non_http_images(self):
        html = """
            <img src="photo.jpg">
            <img src="photo.jpg">
            <img src="data:image/png;base64,abc">
            <img alt="missing source">
        """
        self.assertEqual(
            arachnida.extract_image_urls(html, "http://example.org/"),
            ["http://example.org/photo.jpg"],
        )


class TestArguments(unittest.TestCase):
    def run_validate(self, *arguments):
        output = io.StringIO()
        with redirect_stdout(output):
            status = arachnida.validate(["arachnida.py", *arguments])
        return status, output.getvalue()

    def assert_valid(self, *arguments):
        settings, output = self.run_validate(*arguments)
        self.assertIsNotNone(settings, arguments)
        self.assertEqual(output, "", arguments)

    def assert_invalid(self, *arguments):
        settings, output = self.run_validate(*arguments)
        self.assertIsNone(settings, arguments)
        self.assertEqual(output, "Error!\n", arguments)

    def test_default_settings(self):
        settings, output = self.run_validate("instagram.com")
        self.assertEqual(settings, {
            "url": "https://instagram.com",
            "recursive": False,
            "depth": 5,
            "path": "./data/",
        })
        self.assertEqual(output, "")

    def test_custom_settings(self):
        settings, output = self.run_validate(
            "-p", "images", "-r", "-l", "3", "instagram.com"
        )
        self.assertEqual(settings, {
            "url": "https://instagram.com",
            "recursive": True,
            "depth": 3,
            "path": "images",
        })
        self.assertEqual(output, "")

    # URL forms, with and without an explicit protocol.
    def test_url_forms(self):
        self.assert_valid("instagram.com")
        self.assert_valid("cdn.intra.42.fr/pdf/file.pdf")
        self.assert_valid("http://instagram.com")
        self.assert_valid("https://instagram.com/path")

    # Every supported option combination.
    def test_option_combinations(self):
        url = "instagram.com"
        self.assert_valid(url)
        self.assert_valid("-r", url)
        self.assert_valid("-p", "data", url)
        self.assert_valid("-r", "-p", "data", url)
        self.assert_valid("-r", "-l", "1", url)
        self.assert_valid("-r", "-l", "5", "-p", "data", url)
        self.assert_valid("-r", "-p", "data", "-l", "5", url)
        self.assert_valid("-p", "data", "-r", url)
        self.assert_valid("-p", "data", "-r", "-l", "5", url)

    def test_depth_values(self):
        self.assert_valid("-r", "-l", "1", "site.test")
        self.assert_valid("-r", "-l", "999", "site.test")
        self.assert_invalid("-l", "1", "site.test")
        self.assert_invalid("-r", "-l", "0", "site.test")
        self.assert_invalid("-r", "-l", "-p", "data", "site.test")
        self.assert_invalid("-r", "-l", "depth", "site.test")
        self.assert_invalid("-r", "-l")

    def test_path_values(self):
        self.assert_valid("-p", "data", "site.test")
        self.assert_invalid("-p")
        self.assert_invalid("-p", "-r", "site.test")

    # Every invalid option/argument shape should have the same simple output.
    def test_invalid_arguments(self):
        self.assert_invalid()
        self.assert_invalid("-x", "site.test")
        self.assert_invalid("-r", "-r", "site.test")
        self.assert_invalid("-r", "-l", "1", "-l", "2", "site.test")
        self.assert_invalid("-p", "data", "-p", "other", "site.test")
        self.assert_invalid("site.test", "another.test")
        self.assert_invalid("ftp://site.test")


if __name__ == "__main__":
    unittest.main()
