# Library Search

A Python terminal tool for finding books by author, title, or subject using live
Open Library data. Optionally filter works by their first publication decade.
No accounts, persistence, cover downloads, or web interface are included.

## Setup and run

Requires Python 3.10 or later and an internet connection.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

On Windows, activate with `.venv\Scripts\activate` instead.
Choose 1/author, 2/title, or 3/subject; enter a nonblank term; then enter a
four-digit decade ending in zero (1000–9990), or leave it blank for all years.
For example, search by author for `Ursula K. Le Guin`, with decade `1990`.
Results show numbered titles, author names, and first publication years.
Enter `y` to search again or `n`/`q` to quit. Ctrl+C and EOF also exit cleanly.
Invalid input is re-prompted. Failed requests show an explanation and let you
start another search.

## API and result limit

The tool sends a GET request to `https://openlibrary.org/search.json` using
`requests` parameters: exactly one of `author`, `title`, or `subject`, plus
`limit=100` and `fields=title,author_name,first_publish_year`. Requests uses a
10-second timeout (connect/read inactivity timeout, not a total wall-clock
deadline). Query encoding is handled by Requests.

Only the first page of up to **100 works** is retrieved, in the API's default
relevance order. There is no pagination. A work can group multiple editions;
the year is the work's first publication year, not every edition's year.
Decade filtering is local: `1990` includes **1990 through 1999**, inclusive.
It covers only retrieved works, so matching works beyond the first 100 can be
missed. Unknown years are excluded only when a decade is selected. The terminal
distinguishes an empty API `docs` list from a nonempty list entirely removed by
the filter.

See the [official Search API documentation](https://openlibrary.org/dev/docs/api/search).

## Response inspection before implementation

On November 15, 2026, a live request with `title=the hobbit`, `limit=100`, and
the three fields above returned a JSON object with keys `numFound`, `start`,
`numFoundExact`, `num_found`, `documentation_url`, `q`, `offset`, and `docs`.
`docs` was a list of 100 work objects. The first two were:

```json
[
  {"author_name": ["J.R.R. Tolkien"], "first_publish_year": 1937, "title": "The Hobbit"},
  {"author_name": ["Charles Dixon", "Sean Deming", "J.R.R. Tolkien"], "first_publish_year": 1990, "title": "The Hobbit"}
]
```

`title` is a string, `first_publish_year` is an integer, and `author_name` is
a nested list of strings, potentially with multiple authors. Of those 100
objects, 9 omitted `author_name` and 2 omitted `first_publish_year`; none omitted
`title`. One returned object was just `{"title": "The Hobbit"}`. Missing fields
are therefore normal. Counts and ordering can change with catalog updates.

Absent, null, blank, or wrongly typed metadata displays as `Unknown`. Empty
author lists display as `Unknown`; invalid individual entries in an author
list also display as `Unknown`. Noninteger years (including booleans) count as
unknown. A missing/non-list `docs`, a non-object response, or a non-object
document produces an actionable API error instead. Connection failures,
timeouts, HTTP errors, and invalid JSON are handled without tracebacks.

## Tests

After installing requirements, run:

```sh
python -m unittest discover -s tests -v
```

Tests use standard-library `unittest` and mocked HTTP responses, with no live
network calls. They cover all search modes, parameters and timeout, decade
boundaries, validation, missing metadata, malformed responses, API failures,
and repeated searches and clean exits.
