# Extended Decision Rules

Authoritative supplement to `SKILL.md`. When the short rules in SKILL.md and these extended rules disagree, the extended rules win.

## 1. Tag

### Construction

`ApellidoPrincipal + Año + PalabraClave`

- Strip accents (`Pérez → Perez`, `López → Lopez`).
- Strip non-alphanumeric characters except `_` and `-`.
- Concatenate without separators (PascalCase) or with single underscores.
- Year must be 4 digits.
- Keyword: 1–3 words from the title, PascalCase.

### When no personal author

Use the corporate token instead of `ApellidoPrincipal`. Examples:

- `CONEVAL2022EvalPDS`
- `WorldBank2023Ineq`
- `UN2023SDGs`
- `SEP2023Becas`

Use the organization's most-recognized short name, not the full legal name. The full legal name goes in `CorporateAuthor.Name`; the tag stays short.

### Collisions

Two sources with the same tag? Append a letter (`Garcia2022InfPobrezaA`, `Garcia2022InfPobrezaB`) or extend the keyword (`Garcia2022InfPobrezaRural`, `Garcia2022InfPobrezaUrbana`). Never change the year to disambiguate.

## 2. SourceType edge cases

### "Working paper" / "Discussion paper"

If it is clearly a scholarly working paper (NBER, SSRN, university series) → `Report` (institutional output, not yet a journal article).

### "White paper" / "Policy brief"

`Report` unless it is genuinely a journal article.

### "Book chapter" / "Contribution to an edited volume"

Use the chapter's author, title (chapter title), and `SourceType: Book`. Put the book's editors and book title in `Notes` if relevant for the user's pipeline.

### "Conference proceedings"

`Report` (institutional output) unless the proceedings are formally published as a journal special issue.

### "Thesis / dissertation"

Use a custom tag pattern but map to `Report`. Note "Tesis de maestría / doctorado" in `Notes`.

### "Press release" / "Blog post"

`ElectronicSource` with the URL.

### "Newspaper article"

`ElectronicSource` (online) or use a different SourceType if the user has a custom schema. Note in `Notes` the publication name and date.

## 3. AuthorType edge cases

### Mixed authorship: editor + chapter author

For a book chapter, the chapter author is the AuthorType=`person`. The book editor goes in `Notes`.

### Mixed authorship: corporate body + named contributors

If the cover says "World Bank" and then a list of contributors, but no one is named as author:

- If contributors are clearly authors of the text → `AuthorType: person`.
- If they are listed as "with contributions from" or in acknowledgments → `AuthorType: corporate`, list contributors in `Notes` only.

### Anonymous author

`AuthorType: ""` (neither person nor corporate). Use `Notes` to flag it. Tag uses the title's first keyword.

### Pseudonym / institutional author inside an article

If an article's "author" line says "Equipo de Investigación X" rather than a person, treat as `corporate` even if the journal is academic.

## 4. Authors array edge cases

### Compound surnames

Spanish "García Pérez" — keep both as the surname. `Last: "García Pérez"`, `First: "Juan"`. Do not split into two authors.

### "et al."

NEVER include "et al." as an author. If the document shows "García, J. et al." and no other names, list only García in `Authors` and write "et al." in `Notes`.

### Many authors (10+)

List all of them. The downstream pipeline may want to filter; that's not this skill's call.

### Authors in a non-Latin script

Transliterate to ASCII for `Last` / `First` (per the tag rule). Keep the original script in `Notes` if it matters.

### No diacritics in the name

`Last: "Garcia"` not `Last: "García"` — same portability argument as the Tag.

## 5. CorporateAuthor edge cases

### Subsidiary / department

If the document credits "Banco Mundial — Oficina para México y Colombia", put the office in `Notes` and use the parent org (`World Bank`) in `CorporateAuthor.Name`.

### Acronym vs full name

Use the FULL name as it appears in the document. If both appear, prefer the spelled-out form for `CorporateAuthor.Name` and the acronym for the Tag.

### Multiple institutions

Pick the one that appears first on the cover. Mention the others in `Notes`.

## 6. Title edge cases

### Title in a foreign language

Use the title AS PRINTED, in its original language. Do not translate. If the document has both an English and Spanish title, use whichever appears first on the cover.

### Subtitle on the cover

Include the subtitle only if it is part of the official title (typically separated by `:` or `—`). Do NOT add explanatory subtitles in brackets.

### Translation provided by the document

If the document is bilingual and provides an official translation (e.g. UN reports), use the title in the language the user is working in. Note the other-language title in `Notes`.

## 7. Year edge cases

### Forthcoming / in press

Leave `Year` empty and note "En prensa" in `Notes`. Do not guess the year from the URL slug.

### Reprint / new edition

Use the year of the edition you are cataloging. Note earlier editions in `Notes` only if relevant.

### Multivolume work

If citing a specific volume, use that volume's year.

### No date at all

Empty `Year`, `Notes: "No se indica año de publicación"`. Do NOT infer from the URL or filename.

## 8. URL edge cases

### DOI

Do NOT put a bare DOI in `URL`. Either:
- Convert to `https://doi.org/<DOI>` if you want a clickable link, OR
- Leave `URL` empty and put `DOI: 10.xxxx/...` in `Notes`.

### Wayback Machine / archive URLs

Use the original URL in `URL`, the archive URL in `Notes`. (Or vice versa, depending on the user's pipeline convention — ask once if unclear.)

### Internal / intranet URLs

Empty `URL` unless the user explicitly wants the internal path. Internal URLs leak infrastructure details.

### URL with auth tokens / query strings

Strip the query string. The skill does not transmit credentials, ever.

## 9. Notes style

- Spanish or English (match the document's working language).
- One short line per note. Multiple notes separated by ` | `.
- No pleasantries ("Cabe mencionar que…", "Es importante señalar que…").
- Examples of GOOD notes:
  - `"DOI: 10.22201/iis.01882503p.2021.83.2" | "pp. 245-270"`
  - `"Informe de evaluación MIR, programa federal X"`
  - `"Año inferido por contexto del programa"`
- Examples of BAD notes:
  - `"Esta es una referencia muy interesante que habla sobre..."` (analysis, not metadata)
  - `"Verificar con el autor"` (action item, not metadata)
  - `"!!!"` (no signal)