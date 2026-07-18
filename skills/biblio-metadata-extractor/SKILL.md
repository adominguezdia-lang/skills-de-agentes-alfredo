---
name: biblio-metadata-extractor
description: "Extract bibliographic metadata from a document (PDF, web page, institutional report, book, journal article) into a strict JSON schema with Tag, SourceType, AuthorType, Authors, CorporateAuthor, Title, Year, City, Publisher, Institution, URL, Notes. Triggers: 'extraer metadatos bibliográficos', 'referencia bibliográfica JSON', 'catalogar fuente', 'metadata schema', 'biblio ref', 'dame la referencia en JSON'. Distinct from academic-revision (revises manuscripts) and document-processing (only extracts text)."
version: 1.0.0
author: Luna
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [bibliography, metadata, json, references, citation, cataloging]
    related_skills: [document-processing, academic-revision, research-paper-writing]
---

# Bibliographic Metadata Extractor

Produce a strict JSON object describing a source's bibliographic metadata, following a fixed schema. The agent never invents fields, never changes key names, and never wraps output in prose — the response IS the JSON.

## When to load

- User says "dame la referencia en JSON", "extrae los metadatos", "catalogar esta fuente", "referencia bibliográfica".
- User pastes a title, a PDF excerpt, institutional report, web page URL, or DOI and wants a structured reference.
- A downstream pipeline (Zotero import, RIS converter, citation manager) needs the canonical JSON shape defined here.

Do NOT use for:
- Extracting raw text from a PDF → `document-processing`.
- Editing or revising an existing manuscript → `academic-revision`.
- Writing a new academic paper → `research-paper-writing`.
- Producing a human-readable citation (APA, Chicago, MLA prose) — this skill outputs structured JSON, not formatted prose.

## Output contract (HARD)

The response MUST be **a single valid JSON object** matching the schema in `references/schema.json`. No markdown, no commentary, no code fences, no preamble, no trailing prose. Just JSON.

Required keys (all 12, in this order):

```json
{
  "Tag": "",
  "SourceType": "",
  "AuthorType": "",
  "Authors": [],
  "CorporateAuthor": { "Name": "" },
  "Title": "",
  "Year": "",
  "City": "",
  "Publisher": "",
  "Institution": "",
  "URL": "",
  "Notes": ""
}
```

AuthorType controls whether `Authors` is populated (person) and whether `CorporateAuthor.Name` is populated (corporate). When one of the two is empty, it stays in the schema with its empty default — keys are NEVER omitted.

## Decision rules

### Tag

Short identifier, no spaces. Format: `ApellidoPrincipalAñoPalabraClave`.

Examples: `Garcia2022InfPobreza`, `CONEVAL2021ProgSocial`, `WorldBank2023IneqReport`.

When no personal author exists, use the institution name as the leading token (`CONEVAL2022InfPobreza`, `UN2023SDGs`). Strip accents and use ASCII (`Perez`, not `Pérez`) to keep tags portable across systems.

### SourceType

Exactly one of:

| Value           | When                                                                       |
|-----------------|----------------------------------------------------------------------------|
| `Book`          | Monograph with ISBN, publisher, place of publication.                      |
| `JournalArticle`| Scholarly journal article (DOI, volume/issue/pages).                       |
| `Report`        | Institutional / governmental / corporate report.                           |
| `ElectronicSource` | Web page without a downloadable PDF, blog post, online database entry. |
| (other)         | If unsure, pick the closest and explain the doubt in `Notes`.              |

### AuthorType

- `person` — individuals are clearly identified as authors of the text.
- `corporate` — only an organization is named as author.

When BOTH are present: if individuals are clearly the authors of the text content, use `person` and put the institution in `Institution` or `Publisher`. Reserve `corporate` for when the organization is the sole visible author.

### Authors (only when AuthorType = "person")

Array, order preserved from the document. Each entry:

```json
{ "Last": "Pérez", "First": "Juan" }
```

`Last` = surname(s). `First` = given name, optionally with middle initial(s) (e.g. `"María A."`).

When `AuthorType = "corporate"`, leave `Authors` as an empty array `[]` (do NOT delete the key).

### CorporateAuthor (only when AuthorType = "corporate")

```json
{ "Name": "Consejo Nacional de Evaluación de la Política de Desarrollo Social" }
```

Use the full official name as it appears in the document. When `AuthorType = "person"`, keep `{ "Name": "" }`.

### Title

Full title as printed on the cover, header, or metadata. Do NOT add subtitle in brackets — include the subtitle only if it is part of the official title.

### Year

Year of publication as printed. If only a full date is visible, extract the year. If unclear, leave empty and explain in `Notes`.

### City, Publisher, Institution

Books → `City` (place of publication) + `Publisher` (imprint). `Institution` empty unless a sponsor is named.

Institutional reports → `Institution` is the responsible org (CONEVAL, SEP, World Bank). `Publisher` mirrors it (or names the responsible unit). `City` if printed.

Missing data → empty string `""`, NOT omitted. Note the absence in `Notes` only when the gap is notable.

### URL

Stable public URL when the document was retrieved online. Leave empty if internal / no public URL.

### Notes

Free-text clarifications. Use sparingly:
- Inferences ("año inferido por contexto del programa").
- Ambiguity ("tipo de documento dudoso, se clasifica como Report").
- Missing critical data ("no se indica ciudad de publicación").

## Workflow (5 steps)

### 1. Inspect the input

The user supplies one or more of: title, metadata block, cover/intro text fragments, URL, DOI, filename.

If multiple sources are supplied, **process one at a time** and emit one JSON per source (the user runs the skill once per source; do not batch unless explicitly asked).

If the input is so sparse that ≥5 of the 12 keys would be empty, say so before emitting — the user may have pasted the wrong artifact.

### 2. Apply the schema

Walk each field in the order shown in `references/schema.json`. Make every decision before emitting, so the response is produced once at the end (no half-formed JSON in chat).

For each decision, consult `references/decision-rules.md` (the full rule book with worked examples). The summary above is the short version; that file is authoritative when in doubt.

### 3. Emit pure JSON

```
{ "Tag": "...", "SourceType": "...", ... }
```

No markdown, no code fence, no "Here is the JSON:", no trailing "Let me know if...". The first byte of the response is `{` and the last byte is `}`.

### 4. Self-validate

Run `scripts/validate_biblio.py < file.json` on the output mentally (or via terminal if the user wants a file). Required checks:

- Top-level object with exactly the 12 expected keys, in any order.
- `SourceType` ∈ {`Book`, `JournalArticle`, `Report`, `ElectronicSource`, `""`}.
- `AuthorType` ∈ {`person`, `corporate`, `""`}.
- `Authors` is an array; entries have only `Last` and `First`.
- `CorporateAuthor` is an object with only `Name`.
- `Year` is 4-digit string or empty.
- No invented data — if uncertain, leave empty and explain in `Notes`.

### 5. Deliver

If the user wants the JSON written to disk, save with a deterministic name:

```
references/<Tag>_<SourceType>.json
```

Then deliver via `MEDIA:/absolute/path/to/file.json`. Otherwise, inline JSON is the response.

## Provenance-aware input handling

Different sources expose the same article through different surfaces. Use the right one:

| Input shape                           | Where the metadata lives                                  | Reliability |
|---------------------------------------|-----------------------------------------------------------|-------------|
| Local PDF with text layer             | `pymupdf` first 2 pages + `doc.metadata`                  | High if text is selectable |
| Local scanned PDF (no text layer)     | `marker-pdf` OCR (`marker-pdf file.pdf --output_dir ./`)  | High for typed scans |
| Web URL returning `application/pdf`   | Download then treat as local PDF                          | Same as above |
| OJS article page (HTML, no PDF link)  | `RIS` via `/citationstylelanguage/download/ris?...`      | **Highest — canonical** |
| OJS article page (RIS not exposed)    | `<meta name="citation_*">` tags + `<meta name="DC.*">`    | High |
| OJS article page (no metadata at all) | Visible rendered text near title block                    | Last resort |

### OJS recipe (most common academic publisher in Mexico)

OJS = Open Journal Systems, used by INACIPE, UNAM, SciELO, many Mexican journals.

1. Try `https://<host>/index.php/<journal>/article/download/<id>/<galley>?inline=1` — if it returns `application/pdf`, save and extract with pymupdf.
2. If it returns HTML (the common case), the page is still useful:
   - Parse `<meta name="citation_title|author|publication_date|doi|volume|issue|firstpage|lastpage|journal_title">`.
   - Also look for `<meta name="DC.*">` (Dublin Core fallback).
3. For canonical metadata, hit the CSL endpoint:
   ```
   https://<host>/index.php/<journal>/citationstylelanguage/download/ris?submissionId=<id>&publicationId=<id>
   ```
   RIS is the cleanest structured source. Use it whenever present.
4. BibTeX is an acceptable fallback at the same endpoint with `download/bibtex`.
5. **Do not** attempt the OJS API (`/api/v1/submissions/<id>`) — it requires a token and returns 403 to anonymous clients.
6. If the PDF link is not exposed at all, say so in `Notes` and proceed with the metadata. Do not invent a PDF URL.

### DOI handling when present

A `<meta name="citation_doi">` value like `10.57042/rmcp.v9i28.994` is metadata, not a URL. Per the rules in this skill:
- Keep the DOI in `Notes` (e.g. `DOI: 10.xxxx/...`).
- Do NOT paste it into `URL`.
- Optional: if the user wants a clickable link, convert to `https://doi.org/<DOI>` and put it in `URL`, but only when the user confirms.

## Common pitfalls

1. **Wrapping the response in markdown fences.** The contract is "raw JSON only". Code fences (` ```json ... ``` `) break parsers downstream. First byte `{`, last byte `}`.
2. **Omitting empty keys.** The schema has 12 fixed keys. `Authors: []` and `CorporateAuthor: { "Name": "" }` are valid even when empty — they communicate which AuthorType was selected.
3. **Inventing data instead of leaving empty.** "Probably published in Mexico City" is NOT a valid `City`. Leave empty and explain in `Notes` if relevant.
4. **Using `corporate` when personal authors are listed.** If Pérez and López are on the cover, `AuthorType = "person"` even if CONEVAL also appears.
5. **Reversing Last/First.** `"First": "García", "Last": "Juan"` is the classic mistake. Double-check the names.
6. **Adding subtitles in brackets.** `Title: "Informe [versión preliminar]"` is wrong. Either include the subtitle as it appears or omit it.
7. **Non-ASCII characters in Tag.** Tags travel through databases, URLs, filenames. Strip accents (`Pérez → Perez`) and collapse whitespace to keep them portable.
8. **Year as integer.** Schema says string (`"2022"` not `2022`). Type-check before emitting.
9. **Year as full date.** `"15 de marzo de 2022"` → `"2022"`. Do not pass through `"15/03/2022"`.
10. **Wrong SourceType for institutional reports.** A CONEVAL "Informe de evaluación" is `Report`, not `Book`. ISBN alone does not make it a book.
11. **DOI/URL confusion.** A DOI (`10.1234/abc`) is NOT a URL by itself; convert to `https://doi.org/10.1234/abc` only if the user wants a clickable link. Otherwise leave `URL` empty and put the DOI in `Notes`.
12. **Mixing languages mid-field.** If the document is in Spanish, the title stays in Spanish. Do not translate. Only translate metadata about the document (Notes, clarifications) if the user requests.
13. **Forgetting Notes when ambiguous.** When you guessed or left a critical field empty, Notes is the only signal the user has to evaluate your work. Write a one-liner.

## Verification checklist

```
[ ] Response starts with { and ends with }
[ ] Exactly 12 keys, all named per schema
[ ] SourceType ∈ {Book, JournalArticle, Report, ElectronicSource, ""}
[ ] AuthorType ∈ {person, corporate, ""}
[ ] Authors is an array; entries have only Last + First
[ ] CorporateAuthor is an object with only Name
[ ] Year is 4-digit string or ""
[ ] Tag has no spaces; ASCII; pattern <AuthorOrOrg><Year><Keyword>
[ ] No invented data; gaps explained in Notes
[ ] No markdown, no prose, no code fence
```

## One-shot recipes

### Book

Input: `978-607-30-1234-5, "Pobreza y derechos sociales", García Pérez Juan, 2022, Editorial Tirant lo Blanch, México.`

Output:
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

### Institutional report

Input: `Informe de Evaluación de la Política de Desarrollo Social 2021, CONEVAL, Ciudad de México, 2022. https://www.coneval.org.mx/...`

Output:
```json
{
  "Tag": "CONEVAL2022EvalPDS",
  "SourceType": "Report",
  "AuthorType": "corporate",
  "Authors": [],
  "CorporateAuthor": { "Name": "Consejo Nacional de Evaluación de la Política de Desarrollo Social" },
  "Title": "Informe de Evaluación de la Política de Desarrollo Social 2021",
  "Year": "2022",
  "City": "Ciudad de México",
  "Publisher": "CONEVAL",
  "Institution": "CONEVAL",
  "URL": "https://www.coneval.org.mx/...",
  "Notes": ""
}
```

### Web page (no PDF)

Input: `https://www.gob.mx/sep/articulos/programa-de-becas-2023, SEP, sin fecha visible.`

Output:
```json
{
  "Tag": "SEP2023BecasWeb",
  "SourceType": "ElectronicSource",
  "AuthorType": "corporate",
  "Authors": [],
  "CorporateAuthor": { "Name": "Secretaría de Educación Pública" },
  "Title": "Programa de Becas 2023",
  "Year": "",
  "City": "",
  "Publisher": "Secretaría de Educación Pública",
  "Institution": "Secretaría de Educación Pública",
  "URL": "https://www.gob.mx/sep/articulos/programa-de-becas-2023",
  "Notes": "No se indica año de publicación explícito; se usa el año del título del programa (2023) como referencia temporal."
}
```

### Journal article

Input: `Pérez, J. & López, M. (2021). "Desigualdad y cohesión social". Revista Mexicana de Sociología, 83(2), 245-270. DOI: 10.22201/...`

Output:
```json
{
  "Tag": "Perez2021DesigCoh",
  "SourceType": "JournalArticle",
  "AuthorType": "person",
  "Authors": [
    { "Last": "Pérez", "First": "Juan" },
    { "Last": "López", "First": "María" }
  ],
  "CorporateAuthor": { "Name": "" },
  "Title": "Desigualdad y cohesión social",
  "Year": "2021",
  "City": "",
  "Publisher": "Universidad Nacional Autónoma de México",
  "Institution": "Instituto de Investigaciones Sociales, UNAM",
  "URL": "",
  "Notes": "DOI: 10.22201/..."
}
```

## Support files

- `references/schema.json` — canonical JSON schema for the output. Authoritative when in doubt.
- `references/decision-rules.md` — extended rule book with edge cases (multiple institutions, mixed authorship, no clear publisher, etc.).
- `templates/empty-record.json` — blank record matching the schema, ready to fill in.
- `examples/book.json`, `examples/report.json`, `examples/journal-article.json`, `examples/web-page.json` — one worked example per SourceType.
- `scripts/validate_biblio.py` — schema + sanity-check validator. Pipe JSON through it before delivery if the user wants a file.

## License

MIT. Distribute freely. Attribution appreciated but not required.