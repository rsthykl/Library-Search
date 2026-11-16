"""Terminal book search using the Open Library Search API."""

import re
from typing import Any

import requests

API_URL = "https://openlibrary.org/search.json"
RESULT_LIMIT = 100
FIELDS = "title,author_name,first_publish_year"
SEARCH_TYPES = {"1": "author", "2": "title", "3": "subject"}


class SearchError(Exception):
    """A recoverable API failure with a user-facing explanation."""


def validate_query(raw: str) -> str:
    query = raw.strip()
    if not query:
        raise ValueError("Enter a nonblank search term.")
    return query


def validate_search_type(raw: str) -> str:
    choice = raw.strip().lower()
    if choice in SEARCH_TYPES:
        return SEARCH_TYPES[choice]
    if choice in SEARCH_TYPES.values():
        return choice
    raise ValueError("Choose 1 (author), 2 (title), or 3 (subject).")


def validate_decade(raw: str) -> int | None:
    value = raw.strip()
    if not value:
        return None
    if not re.fullmatch(r"[0-9]{4}", value) or int(value) < 1000 or int(value) % 10:
        raise ValueError("Enter a four-digit decade ending in 0, such as 1990, or leave blank.")
    return int(value)


def fetch_books(search_type: str, query: str) -> list[dict[str, Any]]:
    """Retrieve a single page; reject malformed envelopes and document entries."""
    search_type = validate_search_type(search_type)
    query = validate_query(query)
    try:
        response = requests.get(
            API_URL,
            params={search_type: query, "limit": RESULT_LIMIT, "fields": FIELDS},
            timeout=10,
        )
        response.raise_for_status()
    except requests.Timeout as exc:
        raise SearchError("Open Library timed out after 10 seconds. Please try again.") from exc
    except requests.ConnectionError as exc:
        raise SearchError("Cannot connect to Open Library. Check your internet connection and try again.") from exc
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        raise SearchError(f"Open Library returned HTTP {status}. Please try again later.") from exc
    except requests.RequestException as exc:
        raise SearchError("The Open Library request failed. Please try again.") from exc
    try:
        data = response.json()
    except ValueError as exc:
        raise SearchError("Open Library returned invalid JSON. Please try again later.") from exc
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("docs"), list)
        or any(not isinstance(doc, dict) for doc in data["docs"])
    ):
        raise SearchError("Open Library returned an unexpected response structure. Please try again later.")
    return data["docs"][:RESULT_LIMIT]


def publication_year(book: dict[str, Any]) -> int | None:
    year = book.get("first_publish_year")
    return year if type(year) is int else None


def filter_by_decade(books: list[dict[str, Any]], decade: int | None) -> list[dict[str, Any]]:
    if decade is None:
        return list(books)
    return [book for book in books if (year := publication_year(book)) is not None and decade <= year <= decade + 9]


def metadata_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else "Unknown"


def format_book(number: int, book: dict[str, Any]) -> str:
    authors = book.get("author_name")
    if isinstance(authors, list) and authors:
        author_text = ", ".join(metadata_text(author) for author in authors)
    else:
        author_text = "Unknown"
    year = publication_year(book)
    return (
        f"{number}. {metadata_text(book.get('title'))}\n"
        f"   Authors: {author_text}\n"
        f"   First publication year: {year if year is not None else 'Unknown'}"
    )


def display_results(books: list[dict[str, Any]], decade: int | None) -> None:
    print(f"\nRetrieved {len(books)} work(s); limit: up to {RESULT_LIMIT} works per search.")
    if decade is not None:
        print(
            f"Decade: {decade}–{decade + 9} (inclusive). Filtering covers only retrieved works; "
            "unknown publication years are excluded."
        )
    if not books:
        print("Open Library returned no works for this search. Try a different term or search type.")
        return
    filtered = filter_by_decade(books, decade)
    if not filtered:
        print("No retrieved works match this decade. Try another decade or leave the filter blank.")
        return
    print(f"Showing {len(filtered)} work(s):\n")
    for number, book in enumerate(filtered, 1):
        print(format_book(number, book))


def prompt_validated(prompt: str, validator):
    while True:
        try:
            return validator(input(prompt))
        except ValueError as exc:
            print(exc)


def prompt_search_again() -> bool:
    while True:
        answer = input("\nSearch again? [y/n]: ").strip().lower()
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no", "q", "quit"}:
            return False
        print("Enter y to search again or n to quit.")


def main() -> None:
    print("Library Search — Open Library")
    print(f"Each search retrieves up to {RESULT_LIMIT} works. Decade filtering covers only retrieved works.")
    print("Press Ctrl+C or send EOF at any prompt to quit.")
    try:
        while True:
            print("\nSearch by: 1. Author  2. Title  3. Subject")
            search_type = prompt_validated("Choose a search type: ", validate_search_type)
            query = prompt_validated("Search term: ", validate_query)
            decade = prompt_validated("Decade (e.g. 1990; blank for all years): ", validate_decade)
            try:
                books = fetch_books(search_type, query)
                display_results(books, decade)
            except SearchError as exc:
                print(f"Search failed: {exc}")
            if not prompt_search_again():
                break
    except (EOFError, KeyboardInterrupt):
        print()
    print("Goodbye!")


if __name__ == "__main__":
    main()
