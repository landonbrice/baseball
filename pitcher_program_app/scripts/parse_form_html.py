#!/usr/bin/env python3
"""Parse Google Form HTML table export → JSON array.

Usage:
    python scripts/parse_form_html.py /tmp/Form\ Responses\ 1.html
"""

import json
import sys
from html.parser import HTMLParser


class FormTableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.headers = []
        self.rows = []
        self._current_row = []
        self._current_cell = ""
        self._in_thead = False
        self._in_tbody = False
        self._in_td = False
        self._in_th_row = False  # first row of tbody (header row)
        self._row_count = 0

    def handle_starttag(self, tag, attrs):
        if tag == "thead":
            self._in_thead = True
        elif tag == "tbody":
            self._in_tbody = True
        elif tag in ("td", "th") and self._in_tbody:
            self._in_td = True
            self._current_cell = ""
        elif tag == "tr" and self._in_tbody:
            self._current_row = []
            self._row_count += 1
        elif tag == "br" and self._in_td:
            self._current_cell += "\n"

    def handle_endtag(self, tag):
        if tag == "thead":
            self._in_thead = False
        elif tag == "tbody":
            self._in_tbody = False
        elif tag in ("td", "th") and self._in_td:
            self._in_td = False
            self._current_row.append(self._current_cell.strip())
        elif tag == "tr" and self._in_tbody and self._current_row:
            if self._row_count == 1:
                # First row in tbody is the header row
                self.headers = self._current_row
            elif not all(c == "" for c in self._current_row):
                # Skip the freezebar row (all empty)
                self.rows.append(self._current_row)

    def handle_data(self, data):
        if self._in_td:
            self._current_cell += data

    def handle_entityref(self, name):
        if self._in_td:
            entities = {"amp": "&", "lt": "<", "gt": ">", "quot": '"', "apos": "'"}
            self._current_cell += entities.get(name, f"&{name};")


def parse_html_to_json(html_path: str) -> list[dict]:
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    parser = FormTableParser()
    parser.feed(html)

    # Build dicts from headers + rows
    results = []
    for row in parser.rows:
        entry = {}
        for i, header in enumerate(parser.headers):
            if i < len(row):
                entry[header] = row[i]
            else:
                entry[header] = ""
        results.append(entry)

    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/parse_form_html.py <path-to-html>")
        sys.exit(1)

    html_path = sys.argv[1]
    results = parse_html_to_json(html_path)

    out_path = "data/intake_responses.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"Parsed {len(results)} responses → {out_path}")
    for r in results:
        print(f"  - {r.get('Name', 'Unknown')}")


if __name__ == "__main__":
    main()
