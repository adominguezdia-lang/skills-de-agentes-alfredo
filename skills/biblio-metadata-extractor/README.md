# biblio-metadata-extractor

A distributable Hermes Agent skill that converts bibliographic input (PDF metadata, web pages, institutional reports, books, journal articles) into a strict JSON record following a fixed 12-key schema.

## Install

Drop this folder into one of the two locations:

| Location                                  | Scope                          |
|-------------------------------------------|--------------------------------|
| `~/.hermes/skills/productivity/biblio-metadata-extractor/` | Personal, this user only      |
| `skills/productivity/biblio-metadata-extractor/` (in a Hermes Agent checkout) | Shipped with the repo          |

The skill must be reachable as `productivity/biblio-metadata-extractor/SKILL.md` so the loader can find it.

## Layout

```
biblio-metadata-extractor/
├── SKILL.md                       # the skill itself (frontmatter + body)
├── README.md                      # this file
├── references/
│   ├── schema.json                # JSON Schema (draft-07) — authoritative
│   └── decision-rules.md          # extended rules + edge cases
├── templates/
│   └── empty-record.json          # blank record ready to fill in
├── examples/
│   ├── book.json
│   ├── report.json
│   ├── journal-article.json
│   └── web-page.json
└── scripts/
    ├── validate_biblio.py         # schema + sanity validator (CLI)
    └── __init__.py
```

## Quick start

Once installed, invoke the skill from any Hermes Agent chat:

> "Extrae los metadatos bibliográficos de este PDF: [título, autor, año...]"

The agent emits a single JSON object with the 12 canonical keys:

```json
{
  "Tag": "Garcia2022PobDerechos",
  "SourceType": "Book",
  "AuthorType": "person",
  "Authors": [{ "Last": "García Pérez", "First": "Juan" }],
  "CorporateAuthor": { "Name": "" },
  "Title": "Pobreza y derechos sociales",
  "Year": "2022",
  "City": "México",
  "Publisher": "Editorial Tirant lo Blanch",
  "Institution": "",
  "URL": "",
  "Notes": ""
}
```

## Validate a record locally

```bash
python scripts/validate_biblio.py examples/report.json
# → OK — record conforms to the biblio-metadata-extractor schema.

cat examples/book.json | python scripts/validate_biblio.py -
```

Exit codes: `0` OK, `1` validation errors (or warnings with `--strict`), `2` I/O / usage.

## Schema

The 12 required keys (full spec in `references/schema.json`):

| Key               | Type     | Notes                                                            |
|-------------------|----------|------------------------------------------------------------------|
| `Tag`             | string   | ASCII, no spaces. Pattern: `<AuthorOrOrg><Year><Keyword>`.       |
| `SourceType`      | enum     | `Book` / `JournalArticle` / `Report` / `ElectronicSource` / `""`. |
| `AuthorType`      | enum     | `person` / `corporate` / `""`.                                   |
| `Authors`         | array    | `[{Last, First}, ...]`. Empty when `AuthorType="corporate"`.    |
| `CorporateAuthor` | object   | `{Name}`. Empty name when `AuthorType="person"`.                |
| `Title`           | string   | Full title as printed.                                           |
| `Year`            | string   | 4-digit year or empty.                                           |
| `City`            | string   | Place of publication.                                            |
| `Publisher`       | string   | Imprint / responsible unit.                                      |
| `Institution`     | string   | Sponsoring institution (reports) or publisher's parent (books).   |
| `URL`             | string   | Stable public URL.                                               |
| `Notes`           | string   | Inferences, ambiguities, missing data — one-liner.               |

## License

MIT. See SKILL.md header.