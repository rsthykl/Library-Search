import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import requests

import main


class ValidationTests(unittest.TestCase):
    def test_query(self):
        self.assertEqual(main.validate_query("  Octavia Butler  "), "Octavia Butler")
        for value in ("", " ", "\t\n"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                main.validate_query(value)

    def test_menu(self):
        for value, expected in (("1", "author"), ("2", "title"), ("3", "subject"), (" AUTHOR ", "author")):
            self.assertEqual(main.validate_search_type(value), expected)
        for value in ("", "4", "name"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                main.validate_search_type(value)

    def test_decade(self):
        self.assertIsNone(main.validate_decade("  "))
        for value in ("1000", " 1990 ", "2000", "9990"):
            self.assertEqual(main.validate_decade(value), int(value))
        for value in ("1991", "199", "19900", "1990s", "-1990", "0000", "0990", "1990.0", "１９９０", "+1990"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                main.validate_decade(value)


class FilteringAndDisplayTests(unittest.TestCase):
    def test_inclusive_boundaries(self):
        books = [{"first_publish_year": year} for year in (1989, 1990, 1999, 2000)]
        self.assertEqual(main.filter_by_decade(books, 1990), books[1:3])
        self.assertEqual(len(books), 4)

    def test_unknown_years(self):
        books = [{}, {"first_publish_year": None}, {"first_publish_year": "1990"}, {"first_publish_year": True}]
        self.assertEqual(main.filter_by_decade(books, 1990), [])
        self.assertEqual(main.filter_by_decade(books, None), books)

    def test_missing_or_malformed_metadata(self):
        for book in ({}, {"title": None, "author_name": [], "first_publish_year": None},
                     {"title": 123, "author_name": "Author", "first_publish_year": "1990"}):
            with self.subTest(book=book):
                self.assertEqual(main.format_book(1, book).count("Unknown"), 3)

    def test_multiple_authors_and_partial_missing(self):
        text = main.format_book(2, {"title": " Book ", "author_name": ["Alice", "Bob", None], "first_publish_year": 1999})
        self.assertIn("2. Book", text)
        self.assertIn("Alice, Bob, Unknown", text)
        self.assertIn("1999", text)

    def test_distinct_empty_messages(self):
        output = io.StringIO()
        with redirect_stdout(output):
            main.display_results([], 1990)
        self.assertIn("returned no works", output.getvalue())
        self.assertNotIn("No retrieved works match", output.getvalue())
        output = io.StringIO()
        with redirect_stdout(output):
            main.display_results([{"first_publish_year": 2000}], 1990)
        self.assertIn("No retrieved works match this decade", output.getvalue())
        self.assertIn("only retrieved works", output.getvalue())
        self.assertIn("100", output.getvalue())

    def test_numbered_display(self):
        output = io.StringIO()
        with redirect_stdout(output):
            main.display_results([{"title": "A"}, {"title": "B"}], None)
        self.assertIn("1. A", output.getvalue())
        self.assertIn("2. B", output.getvalue())


class FetchTests(unittest.TestCase):
    @patch("main.requests.get")
    def test_all_search_modes_and_request_options(self, get):
        get.return_value.json.return_value = {"docs": [{"title": "Book"}]}
        for mode in ("author", "title", "subject"):
            self.assertEqual(main.fetch_books(mode, "  A & B  "), [{"title": "Book"}])
            get.assert_called_with(main.API_URL, params={mode: "A & B", "limit": 100,
                                                       "fields": "title,author_name,first_publish_year"}, timeout=10)
            get.return_value.raise_for_status.assert_called()

    @patch("main.requests.get")
    def test_empty_and_capped_responses(self, get):
        for docs in ([], [{}] * 101):
            get.return_value.json.return_value = {"docs": docs}
            self.assertEqual(len(main.fetch_books("title", "test")), min(len(docs), 100))

    @patch("main.requests.get")
    def test_unexpected_structures(self, get):
        for payload in (None, [], {}, {"docs": None}, {"docs": {}}, {"docs": [None]}, {"docs": ["book"]}):
            get.return_value.json.return_value = payload
            with self.subTest(payload=payload), self.assertRaisesRegex(main.SearchError, "unexpected response structure"):
                main.fetch_books("title", "test")

    @patch("main.requests.get")
    def test_invalid_json(self, get):
        get.return_value.json.side_effect = ValueError("bad JSON")
        with self.assertRaisesRegex(main.SearchError, "invalid JSON"):
            main.fetch_books("title", "test")

    @patch("main.requests.get")
    def test_network_failures(self, get):
        for error, message in ((requests.Timeout(), "timed out"),
                               (requests.ConnectionError(), "Check your internet"),
                               (requests.RequestException(), "Please try again")):
            get.side_effect = error
            with self.subTest(error=error), self.assertRaisesRegex(main.SearchError, message):
                main.fetch_books("title", "test")

    @patch("main.requests.get")
    def test_http_error(self, get):
        response = requests.Response()
        response.status_code = 503
        get.return_value.raise_for_status.side_effect = requests.HTTPError(response=response)
        with self.assertRaisesRegex(main.SearchError, "HTTP 503"):
            main.fetch_books("title", "test")

    @patch("main.requests.get")
    def test_invalid_input_does_not_fetch(self, get):
        for mode, query in (("invalid", "book"), ("title", " ")):
            with self.assertRaises(ValueError):
                main.fetch_books(mode, query)
        get.assert_not_called()


class FlowTests(unittest.TestCase):
    def run_cli(self, answers, fetch_effect):
        output = io.StringIO()
        with patch("builtins.input", side_effect=answers), patch("main.fetch_books", side_effect=fetch_effect) as fetch, redirect_stdout(output):
            main.main()
        return output.getvalue(), fetch

    def test_retry_invalid_input_and_search_again(self):
        output, fetch = self.run_cli(
            ["4", "1", " ", "Tolkien", "1991", "1990", "maybe", "y", "3", "fantasy", "", "n"],
            [[{"title": "The Hobbit", "first_publish_year": 1990}], []],
        )
        self.assertEqual(fetch.call_args_list[0].args, ("author", "Tolkien"))
        self.assertEqual(fetch.call_args_list[1].args, ("subject", "fantasy"))
        self.assertIn("Choose 1", output)
        self.assertIn("nonblank", output)
        self.assertIn("four-digit decade", output)
        self.assertIn("1. The Hobbit", output)
        self.assertTrue(output.rstrip().endswith("Goodbye!"))

    def test_recover_from_api_failure(self):
        output, fetch = self.run_cli(["2", "book", "", "y", "2", "book", "", "q"],
                                     [main.SearchError("Please try again."), [{}]])
        self.assertEqual(fetch.call_count, 2)
        self.assertIn("Search failed: Please try again.", output)
        self.assertIn("1. Unknown", output)

    def test_eof_and_interrupt_exit_cleanly(self):
        for error in (EOFError(), KeyboardInterrupt()):
            for prefix in ([], ["1", "book", ""]):
                output, _ = self.run_cli(prefix + [error], [[]])
                self.assertIn("Goodbye!", output)


if __name__ == "__main__":
    unittest.main()
