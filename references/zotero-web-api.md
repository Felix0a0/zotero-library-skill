# Zotero Web API Notes

Use Zotero Web API v3 for direct library access.

Official references:

- Basics: https://www.zotero.org/support/dev/web_api/v3/basics
- Full-text content: https://www.zotero.org/support/dev/web_api/v3/fulltext_content
- File download/upload endpoints: https://www.zotero.org/support/dev/web_api/v3/file_upload

## Required Configuration

Use environment variables:

- `ZOTERO_API_KEY`: API key for private libraries.
- `ZOTERO_LIBRARY_TYPE`: `user` or `group`.
- `ZOTERO_LIBRARY_ID`: numeric user ID or group ID, not username/group name.

Public libraries can sometimes be read without a key. Private libraries need a key with read access. File download requires access to stored attachment files.

PowerShell example:

```powershell
$env:ZOTERO_API_KEY="..."
$env:ZOTERO_LIBRARY_TYPE="user"
$env:ZOTERO_LIBRARY_ID="1234567"
```

## Direct Reading Strategy

For a parent paper item:

1. Fetch parent metadata from `/users/<id>/items/<itemKey>` or `/groups/<id>/items/<itemKey>`.
2. Fetch child items from `/items/<itemKey>/children`.
3. For each attachment child, try `/items/<attachmentKey>/fulltext` first.
4. If full text is absent or incomplete and the user permits it, download `/items/<attachmentKey>/file`.
5. Summarize from full-text content first, then local PDF extraction if needed.

For batch work:

1. Select parent items by collection, search query, tag, or explicit item keys.
2. Limit the first batch unless the user explicitly asks for the whole collection.
3. Fetch metadata and attachment text for each item.
4. Produce per-paper summaries plus a cross-paper synthesis.

## Safety

- Do not print or write API keys.
- Prefer read-only requests.
- Do not use write, upload, delete, or patch endpoints unless the user explicitly asks.
- Treat missing full text as a normal condition; ask for local PDFs or allow attachment download.
- Respect rate limits and retry guidance if the API returns throttling headers.
