---
name: zotero-library
description: Directly connect to Zotero libraries and work with collections, item keys, tags, exported bibliographies, Better BibTeX files, CSL JSON, BibTeX, RIS, DOI metadata, attachments, full-text indexes, PDF files, batch paper reading, per-paper summaries, cross-paper synthesis, duplicate detection, and bibliography cleanup. Use when Codex needs to inspect, fetch, read, summarize, clean, export, compare, or generate outputs from a user's Zotero library or Zotero-derived files.
---

# Zotero Library

Use this skill for Zotero-centered literature work. Prefer direct Zotero Web API access when the user wants the live library, folder/collection paths, item keys, batch reading, or summaries from stored attachments. Prefer exported files for offline bibliography cleanup.

Read [references/zotero-web-api.md](references/zotero-web-api.md) when configuring direct access, fetching attachments, or troubleshooting API responses.

## Source Preference

Prefer sources in this order:

1. Zotero Web API for live library access, folder/collection path lookup, collection search, item-key lookup, attachment full text, and batch summarization.
2. User-provided Zotero export file: Better BibTeX JSON, CSL JSON, BibTeX, RIS, RDF, or CSV.
3. A copied `zotero.sqlite` database only when export/API access is unavailable.

Never edit the live `zotero.sqlite` database directly. If database inspection is necessary, ask for or create a copy first.

## Direct API Configuration

Use environment variables for direct access:

- `ZOTERO_API_KEY`: Zotero API key for private libraries.
- `ZOTERO_LIBRARY_TYPE`: `user` or `group`.
- `ZOTERO_LIBRARY_ID`: numeric user ID or group ID.

PowerShell setup:

```powershell
$env:ZOTERO_API_KEY="..."
$env:ZOTERO_LIBRARY_TYPE="user"
$env:ZOTERO_LIBRARY_ID="1234567"
```

Use [scripts/zotero_api.py](scripts/zotero_api.py) for read-only API tasks. It must not print or persist the API key.

Check configuration:

```bash
python <skill>/scripts/zotero_api.py config
```

Find the numeric personal library ID from the current API key:

```bash
python <skill>/scripts/zotero_api.py whoami
```

For a personal library, `zotero_api.py` can auto-resolve `ZOTERO_LIBRARY_ID` from `ZOTERO_API_KEY` when the ID is not configured. For a group library, still provide the numeric group ID.

List collections:

```bash
python <skill>/scripts/zotero_api.py collections --top --out collections.json
```

List Zotero folders with full paths:

```bash
python <skill>/scripts/zotero_api.py collections --tree
```

Search parent items:

```bash
python <skill>/scripts/zotero_api.py items --q "transfer learning photovoltaic" --max 10 --out items.json
```

Search parent items inside a Zotero folder path:

```bash
python <skill>/scripts/zotero_api.py items --collection-path "My Library > Topic > Subtopic" --max 10
```

Pack one or more parent items for summarization:

```bash
python <skill>/scripts/zotero_api.py pack --keys ITEMKEY1,ITEMKEY2 --out-dir zotero_pack
```

Pack a Zotero folder path:

```bash
python <skill>/scripts/zotero_api.py pack --collection-path "My Library > Topic > Subtopic" --max 20 --out-dir zotero_pack
```

Pack a collection key:

```bash
python <skill>/scripts/zotero_api.py pack --collection COLLECTIONKEY --max 20 --out-dir zotero_pack
```

Add `--download-files` only when Zotero full-text content is missing, incomplete, or the user asks to inspect the PDFs directly.

## Intake Checklist

Identify:

- Live Zotero source, export file path, or copied database path.
- Target item key, Zotero folder path, collection key, tag, search query, saved search, or whole library scope.
- Whether the task is single-paper reading, batch paper summaries, cross-paper synthesis, bibliography cleanup, or duplicate detection.
- Desired output: concise summary, structured note, literature matrix, Markdown table, BibTeX, CSV, JSON, or review draft.
- Whether attachment download is allowed if Zotero full-text content is missing.
- Citation style or format constraints if bibliography output is requested.

Make reasonable assumptions for harmless read-only inspection. Ask a concise question only when the missing detail affects which library, collection, item set, or output should be used.

## Workflow Decision Tree

- If the user asks to read or summarize Zotero papers directly, use Web API first.
- If the user gives item keys, pack those exact parent items and summarize from their full text or attachments.
- If the user gives a Zotero folder path, use `--collection-path` and let the script resolve it to a collection key.
- If the user gives a collection key, tag, or query, list/select parent items first, then pack a bounded batch unless the user asks for all.
- If the user provides an export file, parse that file first and preserve its original metadata.
- If the user asks to clean, deduplicate, or transform records, write a new output file instead of replacing the source.
- If the user asks for current metadata, verify against authoritative web sources before changing DOI, venue, year, or publication status.

## Reading And Summarization Workflow

For a single paper:

1. Fetch parent metadata.
2. Fetch child attachments and notes.
3. Try Zotero full-text content for attachment items.
4. If full text is unavailable or too incomplete, download the attachment file when allowed.
5. If a local PDF is downloaded or provided, use the PDF skill or reliable PDF text extraction before summarizing.
6. Produce a summary that separates bibliographic metadata, research question, method, data, key findings, limitations, and relevance to the user's topic.

For batch papers:

1. Select the batch by explicit keys, collection, tag, or query.
2. Start with a bounded batch (`--max 10` to `--max 20`) unless the user requests a full collection.
3. Pack metadata and full text with `zotero_api.py pack`.
4. Produce one concise per-paper summary each.
5. Add a cross-paper synthesis: themes, methods, datasets, agreements, disagreements, gaps, and a recommended reading order.
6. Note items that lacked full text, had only abstracts, or need manual PDF access.

For long batches, summarize in passes and keep intermediate notes in the workspace so final synthesis can cite the item keys and titles.

## Temporary Files And Cleanup

When a task uses `--out`, `pack`, full-text extraction, PDF download, batch summaries, or generated export files:

- Track every generated path.
- At the end of the task, tell the user which files or directories were created.
- Ask whether to delete temporary/intermediate files.
- Recommend deleting raw API dumps, packed full-text `.txt` files, and downloaded PDFs when they were created only for one-time summarization.
- Recommend keeping final summaries, curated tables, cleaned bibliographies, or user-requested exports.
- Never delete generated files without the user's explicit confirmation.
- Do not save final summary prose to a file unless the user explicitly requests a saved deliverable.

## Local Export Workflow

For exported files:

- Inspect the file extension and structure before parsing.
- Use structured parsers where available instead of ad hoc string processing.
- Preserve item keys, DOI, URL, title, authors, year, venue, abstract, tags, collections, notes, and attachments when present.
- Keep Zotero-stored metadata separate from web-enriched metadata.
- Report uncertain or conflicting metadata instead of silently choosing one.
- Do not overwrite the original export; write cleaned or transformed outputs to a new file unless the user explicitly asks to replace it.

For BibTeX and Better BibTeX:

- Preserve citation keys unless the user asks to regenerate them.
- Normalize fields consistently, but avoid deleting unknown fields.
- Treat `doi`, `url`, `eprint`, `archivePrefix`, `primaryClass`, and `note` as meaningful provenance.

## Database Workflow

Use direct database inspection only as a fallback:

- Work from a copied `zotero.sqlite`, never the live database.
- Open SQLite in read-only mode when possible.
- Inspect schema tables before assuming field names.
- Treat item attachments and full-text cache paths as local references, not portable bibliography metadata.
- Do not write SQL migrations, updates, or deletes against Zotero data unless the user explicitly asks and a backup exists.

## Metadata Cleanup Rules

When cleaning records:

- Normalize DOI casing and remove `https://doi.org/` prefixes when producing DOI fields.
- Preserve original titles unless the user asks for title-case or sentence-case normalization.
- Prefer canonical metadata from DOI, Crossref, publisher pages, PubMed, arXiv, DBLP, or official conference pages when web verification is requested.
- Mark records as `needs review` when title, year, DOI, venue, or item type disagree across sources.
- Avoid deleting fields unless the user explicitly asks for a minimal export.

## Duplicate Detection

Detect likely duplicates by comparing:

- DOI exact match.
- Normalized title plus year.
- Title similarity plus first author.
- arXiv ID, PMID, ISBN, or URL when available.

Group duplicates and explain the merge recommendation. Do not perform destructive merges unless the user explicitly asks.

## Output Defaults

Use Markdown tables for inspection tasks.

Default columns:

- Title
- Authors
- Year
- Venue
- DOI
- Tags
- Notes

For single-paper summaries, include:

- Citation
- Purpose
- Method
- Data/materials
- Main findings
- Limitations
- Useful quotes or concepts when available
- How it relates to the user's project

For batch summaries, include:

- Per-paper summary table
- Thematic synthesis
- Method/data comparison
- Gaps and follow-up reading order

Present literature summaries directly in the chat by default. Do not create a final `.md`, `.docx`, `.pdf`, or other summary file unless the user explicitly asks for a file, export, or saved report.

For bibliography exports, produce a new `.bib`, `.json`, `.csv`, or `.md` file and state the output path.
