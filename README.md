# Zotero Library Skill

A Codex skill for connecting to a Zotero library, locating papers by item key or folder path, reading attachment full text, and producing in-chat literature summaries.

## Included Files

- `SKILL.md`: skill instructions and workflow
- `agents/openai.yaml`: UI metadata
- `scripts/zotero_api.py`: read-only Zotero Web API helper
- `references/zotero-web-api.md`: API notes and configuration hints

## Main Capabilities

- Connect to Zotero via Web API
- Resolve Zotero folder paths such as `功率预测 > 迁移学习`
- Fetch item metadata, attachments, and full-text indexes
- Support single-paper and batch-paper reading workflows
- Keep final summaries in chat by default instead of saving them to files
- Track generated temporary files and ask before deleting them

## Required Environment Variables

Set these before using direct Zotero access:

```powershell
$env:ZOTERO_API_KEY="your_api_key"
$env:ZOTERO_LIBRARY_TYPE="user"
$env:ZOTERO_LIBRARY_ID="your_numeric_user_id"
```

## Example Commands

```powershell
python scripts/zotero_api.py whoami
python scripts/zotero_api.py collections --tree
python scripts/zotero_api.py items --collection-path "功率预测 > 迁移学习" --max 5
python scripts/zotero_api.py pack --collection-path "功率预测 > 迁移学习" --max 3 --out-dir zotero_pack
```

## Installation

Copy this folder into your Codex skills directory, typically:

```text
C:\Users\<your-user>\.codex\skills\zotero-library
```
