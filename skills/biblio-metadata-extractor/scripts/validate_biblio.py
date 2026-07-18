#!/usr/bin/env python3
"""
validate_biblio.py — schema + sanity validator for the biblio-metadata-extractor skill.

Usage:
    python validate_biblio.py file.json
    cat file.json | python validate_biblio.py -
    python validate_biblio.py --strict file.json   # treat warnings as errors

Exit codes:
    0  OK
    1  Validation errors
    2  Usage / I/O error

Checks performed:
  - 12 required keys present, no extras.
  - SourceType ∈ allowed enum.
  - AuthorType ∈ allowed enum.
  - Authors entries have exactly Last + First.
  - CorporateAuthor has exactly { "Name": ... }.
  - AuthorType / Authors / CorporateAuthor consistency (cross-field rules).
  - Year is 4-digit string or empty.
  - Tag is ASCII, no spaces.
  - JSON parses (round-trip).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


REQUIRED_KEYS = [
    "Tag",
    "SourceType",
    "AuthorType",
    "Authors",
    "CorporateAuthor",
    "Title",
    "Year",
    "City",
    "Publisher",
    "Institution",
    "URL",
    "Notes",
]

SOURCETYPE_ENUM = {"Book", "JournalArticle", "Report", "ElectronicSource", ""}
AUTHORTYPE_ENUM = {"person", "corporate", ""}
TAG_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
YEAR_PATTERN = re.compile(r"^(\d{4})?$")


class ValidationError:
    def __init__(self, level: str, message: str):
        self.level = level  # "error" or "warning"
        self.message = message

    def __str__(self) -> str:
        return f"[{self.level.upper()}] {self.message}"


def validate(record: Any) -> list[ValidationError]:
    errors: list[ValidationError] = []

    if not isinstance(record, dict):
        errors.append(ValidationError("error", "Top-level value must be a JSON object."))
        return errors

    # 1. Required keys (and no extras).
    present = set(record.keys())
    expected = set(REQUIRED_KEYS)
    missing = expected - present
    extra = present - expected
    for k in sorted(missing):
        errors.append(ValidationError("error", f"Missing required key: '{k}'"))
    for k in sorted(extra):
        errors.append(ValidationError("error", f"Unexpected extra key: '{k}'"))

    # If keys are missing, skip deeper validation (it would just produce noise).
    if missing:
        return errors

    # 2. SourceType.
    st = record["SourceType"]
    if st not in SOURCETYPE_ENUM:
        errors.append(
            ValidationError(
                "error",
                f"SourceType '{st}' not in allowed set {sorted(SOURCETYPE_ENUM)}",
            )
        )

    # 3. AuthorType.
    at = record["AuthorType"]
    if at not in AUTHORTYPE_ENUM:
        errors.append(
            ValidationError(
                "error",
                f"AuthorType '{at}' not in allowed set {sorted(AUTHORTYPE_ENUM)}",
            )
        )

    # 4. Authors.
    authors = record["Authors"]
    if not isinstance(authors, list):
        errors.append(ValidationError("error", "Authors must be an array."))
    else:
        for i, a in enumerate(authors):
            if not isinstance(a, dict):
                errors.append(ValidationError("error", f"Authors[{i}] must be an object."))
                continue
            akeys = set(a.keys())
            if akeys != {"Last", "First"}:
                wrong = akeys - {"Last", "First"}
                missing_a = {"Last", "First"} - akeys
                if wrong:
                    errors.append(
                        ValidationError(
                            "error",
                            f"Authors[{i}] has unexpected keys: {sorted(wrong)}",
                        )
                    )
                if missing_a:
                    errors.append(
                        ValidationError(
                            "error",
                            f"Authors[{i}] missing keys: {sorted(missing_a)}",
                        )
                    )

    # 5. CorporateAuthor.
    ca = record["CorporateAuthor"]
    if not isinstance(ca, dict):
        errors.append(ValidationError("error", "CorporateAuthor must be an object."))
    elif set(ca.keys()) != {"Name"}:
        errors.append(
            ValidationError(
                "error",
                f"CorporateAuthor must have exactly one key 'Name', got {sorted(ca.keys())}",
            )
        )

    # 6. Cross-field rules.
    if at == "person":
        if isinstance(authors, list) and len(authors) == 0:
            errors.append(
                ValidationError(
                    "error",
                    "AuthorType='person' requires Authors to have at least one entry.",
                )
            )
        if isinstance(ca, dict) and ca.get("Name", "") != "":
            errors.append(
                ValidationError(
                    "error",
                    "AuthorType='person' requires CorporateAuthor.Name to be empty.",
                )
            )
    elif at == "corporate":
        if isinstance(authors, list) and len(authors) != 0:
            errors.append(
                ValidationError(
                    "error",
                    "AuthorType='corporate' requires Authors to be empty.",
                )
            )
        if isinstance(ca, dict) and ca.get("Name", "") == "":
            errors.append(
                ValidationError(
                    "error",
                    "AuthorType='corporate' requires CorporateAuthor.Name to be non-empty.",
                )
            )

    # 7. Year.
    year = record["Year"]
    if not isinstance(year, str) or not YEAR_PATTERN.match(year):
        errors.append(
            ValidationError(
                "error",
                f"Year must be a 4-digit string or empty, got {year!r}.",
            )
        )

    # 8. Tag.
    tag = record["Tag"]
    if not isinstance(tag, str) or not TAG_PATTERN.match(tag):
        errors.append(
            ValidationError(
                "error",
                f"Tag must be ASCII without spaces, got {tag!r}.",
            )
        )

    # 9. Optional sanity warnings.
    if isinstance(tag, str) and tag and not re.search(r"\d{4}", tag):
        errors.append(
            ValidationError(
                "warning",
                "Tag does not contain a 4-digit year — consider ApellidoYYYYKeyword format.",
            )
        )
    if isinstance(authors, list) and len(authors) > 10:
        errors.append(
            ValidationError(
                "warning",
                f"Authors list is long ({len(authors)}); confirm this is intentional.",
            )
        )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", help="Path to JSON file (use '-' for stdin)")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    args = parser.parse_args()

    if args.path == "-":
        raw = sys.stdin.read()
    else:
        try:
            raw = Path(args.path).read_text(encoding="utf-8")
        except OSError as e:
            print(f"I/O error: {e}", file=sys.stderr)
            return 2

    try:
        record = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}", file=sys.stderr)
        return 1

    errors = validate(record)

    if not errors:
        print("OK — record conforms to the biblio-metadata-extractor schema.")
        return 0

    has_error = any(e.level == "error" for e in errors)
    has_warning = any(e.level == "warning" for e in errors)

    for e in errors:
        print(str(e))

    if has_error:
        return 1
    if has_warning and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())