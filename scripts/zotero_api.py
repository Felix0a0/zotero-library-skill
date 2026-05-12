#!/usr/bin/env python3
"""Small read-only Zotero Web API helper for Codex skills."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "https://api.zotero.org"


class ZoteroError(RuntimeError):
    pass


def eprint(*parts: object) -> None:
    print(*parts, file=sys.stderr)


def sanitize_filename(value: str, fallback: str = "zotero-file") -> str:
    value = value.strip() or fallback
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    return value[:180] or fallback


def parse_key_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in re.split(r"[,;\s]+", value) if part.strip()]


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def dump_json(data: Any, path: str | None = None) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if path:
        output = Path(path)
        ensure_parent(output)
        output.write_text(text + "\n", encoding="utf-8")
        print(str(output))
    else:
        print(text)


def creators_text(data: dict[str, Any]) -> str:
    creators = []
    for creator in data.get("creators") or []:
        if creator.get("name"):
            creators.append(creator["name"])
            continue
        name = " ".join(
            part for part in [creator.get("firstName"), creator.get("lastName")] if part
        ).strip()
        if name:
            creators.append(name)
    return "; ".join(creators)


def simplify_item(item: dict[str, Any]) -> dict[str, Any]:
    data = item.get("data") or item
    tags = data.get("tags") or []
    return {
        "key": data.get("key") or item.get("key"),
        "version": data.get("version") or item.get("version"),
        "itemType": data.get("itemType"),
        "title": data.get("title"),
        "creators": creators_text(data),
        "date": data.get("date"),
        "publicationTitle": data.get("publicationTitle")
        or data.get("conferenceName")
        or data.get("bookTitle")
        or data.get("publisher"),
        "DOI": data.get("DOI") or data.get("doi"),
        "url": data.get("url"),
        "abstractNote": data.get("abstractNote"),
        "tags": [tag.get("tag") for tag in tags if isinstance(tag, dict) and tag.get("tag")],
        "collections": data.get("collections") or [],
        "parentItem": data.get("parentItem"),
        "linkMode": data.get("linkMode"),
        "contentType": data.get("contentType"),
        "filename": data.get("filename"),
        "note": data.get("note"),
    }


def collection_data(item: dict[str, Any]) -> dict[str, Any]:
    data = item.get("data") or item
    return {
        "key": data.get("key") or item.get("key"),
        "name": data.get("name"),
        "parentCollection": data.get("parentCollection") or False,
        "version": data.get("version") or item.get("version"),
    }


def normalize_path_part(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def split_collection_path(path: str) -> list[str]:
    raw_parts = re.split(r"\s*(?:>|/|\\)\s*", path.strip())
    parts = [part.strip() for part in raw_parts if part.strip()]
    if parts and parts[0].casefold() in {"my library", "mylibrary", "library"}:
        parts = parts[1:]
    return parts


class ZoteroClient:
    def __init__(
        self,
        library_type: str,
        library_id: str,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        sleep_seconds: float = 0.0,
    ) -> None:
        if library_type not in {"user", "group"}:
            raise ZoteroError("library type must be 'user' or 'group'")
        self.library_type = library_type
        self.library_id = library_id
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.sleep_seconds = sleep_seconds

    @property
    def prefix(self) -> str:
        if not self.library_id:
            raise ZoteroError("library id is required. Run 'whoami' to find a user library ID.")
        root = "users" if self.library_type == "user" else "groups"
        return f"/{root}/{self.library_id}"

    def url(self, path: str, params: dict[str, Any] | None = None) -> str:
        if not path.startswith("/"):
            path = "/" + path
        query = urllib.parse.urlencode(
            {key: value for key, value in (params or {}).items() if value not in (None, "")},
            doseq=True,
        )
        return f"{self.base_url}{path}" + (f"?{query}" if query else "")

    def request(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        raw: bool = False,
    ) -> tuple[Any, dict[str, str]]:
        if self.sleep_seconds:
            time.sleep(self.sleep_seconds)

        headers = {
            "Zotero-API-Version": "3",
            "User-Agent": "codex-zotero-library-skill/1.0",
        }
        if self.api_key:
            headers["Zotero-API-Key"] = self.api_key

        request = urllib.request.Request(self.url(path, params), headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                header_map = dict(response.headers.items())
                payload = response.read()
                if raw:
                    return payload, header_map
                if not payload:
                    return None, header_map
                charset = response.headers.get_content_charset() or "utf-8"
                text = payload.decode(charset)
                content_type = response.headers.get("Content-Type", "")
                if "json" in content_type or text[:1] in "[{":
                    return json.loads(text), header_map
                return text, header_map
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ZoteroError(f"HTTP {exc.code} for {path}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise ZoteroError(f"Network error for {path}: {exc.reason}") from exc

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        data, _headers = self.request(path, params)
        return data

    def get_raw(self, path: str, params: dict[str, Any] | None = None) -> tuple[bytes, dict[str, str]]:
        data, headers = self.request(path, params, raw=True)
        return data, headers

    def current_key(self) -> dict[str, Any]:
        if not self.api_key:
            raise ZoteroError("ZOTERO_API_KEY is required to inspect the current key")
        data = self.get_json("/keys/current")
        if not isinstance(data, dict):
            raise ZoteroError("Expected key metadata from /keys/current")
        return data

    def fetch_page_items(
        self,
        path: str,
        params: dict[str, Any],
        max_items: int | None,
        fetch_all: bool,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        start = int(params.get("start") or 0)
        page_size = min(int(params.get("limit") or 25), 100)

        while True:
            if max_items is not None:
                remaining = max_items - len(items)
                if remaining <= 0:
                    break
                page_size = min(page_size, remaining)

            page_params = dict(params)
            page_params["start"] = start
            page_params["limit"] = page_size
            page = self.get_json(path, page_params)
            if not isinstance(page, list):
                raise ZoteroError(f"Expected a JSON list from {path}")
            items.extend(page)
            if not fetch_all and (max_items is None or len(items) >= max_items):
                break
            if len(page) < page_size:
                break
            start += page_size
        return items

    def item(self, key: str) -> dict[str, Any]:
        data = self.get_json(f"{self.prefix}/items/{key}")
        if not isinstance(data, dict):
            raise ZoteroError(f"Expected one item for key {key}")
        return data

    def children(self, key: str) -> list[dict[str, Any]]:
        data = self.get_json(f"{self.prefix}/items/{key}/children", {"limit": 100})
        if not isinstance(data, list):
            raise ZoteroError(f"Expected child item list for key {key}")
        return data

    def all_collections(self) -> list[dict[str, Any]]:
        return self.fetch_page_items(
            f"{self.prefix}/collections",
            {"sort": "title", "direction": "asc", "limit": 100},
            max_items=None,
            fetch_all=True,
        )

    def collection_records(self) -> list[dict[str, Any]]:
        return [collection_data(item) for item in self.all_collections()]

    def collection_paths(self) -> list[dict[str, Any]]:
        records = self.collection_records()
        by_key = {record["key"]: record for record in records if record.get("key")}
        path_records = []
        for record in records:
            key = record.get("key")
            names = []
            current = record
            seen = set()
            while current and current.get("key") not in seen:
                seen.add(current.get("key"))
                name = current.get("name")
                if name:
                    names.append(name)
                parent_key = current.get("parentCollection")
                current = by_key.get(parent_key) if parent_key else None
            names.reverse()
            path_records.append(
                {
                    "key": key,
                    "name": record.get("name"),
                    "path": " > ".join(names),
                    "parentCollection": record.get("parentCollection"),
                    "version": record.get("version"),
                }
            )
        return sorted(path_records, key=lambda value: normalize_path_part(value.get("path") or ""))

    def resolve_collection_path(self, path: str) -> str:
        parts = split_collection_path(path)
        if not parts:
            raise ZoteroError("collection path is empty")
        wanted = [normalize_path_part(part) for part in parts]
        matches = []
        for record in self.collection_paths():
            record_parts = [normalize_path_part(part) for part in split_collection_path(record.get("path") or "")]
            if record_parts == wanted:
                matches.append(record)
        if not matches:
            raise ZoteroError(f"No collection found for path: {path}")
        if len(matches) > 1:
            options = "; ".join(f"{record['path']} [{record['key']}]" for record in matches[:10])
            raise ZoteroError(f"Collection path is ambiguous: {path}. Matches: {options}")
        return str(matches[0]["key"])

    def fulltext(self, attachment_key: str) -> dict[str, Any] | None:
        try:
            data = self.get_json(f"{self.prefix}/items/{attachment_key}/fulltext")
            return data if isinstance(data, dict) else None
        except ZoteroError as exc:
            if "HTTP 404" in str(exc):
                return None
            raise

    def download_file(self, attachment: dict[str, Any], out_dir: Path) -> dict[str, Any]:
        data = attachment.get("data") or attachment
        key = data.get("key") or attachment.get("key")
        filename = data.get("filename") or data.get("title") or key or "attachment"
        target = out_dir / sanitize_filename(filename)
        try:
            payload, headers = self.get_raw(f"{self.prefix}/items/{key}/file")
        except ZoteroError as exc:
            return {"key": key, "error": str(exc)}
        out_dir.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        return {
            "key": key,
            "path": str(target),
            "bytes": len(payload),
            "etag": headers.get("ETag"),
            "contentType": headers.get("Content-Type"),
        }


def client_from_args(args: argparse.Namespace) -> ZoteroClient:
    library_type = args.library_type or os.getenv("ZOTERO_LIBRARY_TYPE", "user")
    library_id = args.library_id or os.getenv("ZOTERO_LIBRARY_ID", "")
    client = ZoteroClient(
        library_type=library_type,
        library_id=library_id,
        api_key=args.api_key or os.getenv("ZOTERO_API_KEY"),
        base_url=args.base_url or os.getenv("ZOTERO_API_BASE", DEFAULT_BASE_URL),
        sleep_seconds=args.sleep,
    )
    if not library_id and library_type == "user" and client.api_key:
        current = client.current_key()
        user_id = current.get("userID")
        if user_id:
            client.library_id = str(user_id)
            eprint(f"Resolved user library ID from API key: {client.library_id}")
    return client


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--api-key", help="Zotero API key. Prefer ZOTERO_API_KEY.")
    parser.add_argument("--library-type", choices=["user", "group"], help="Library type.")
    parser.add_argument("--library-id", help="Numeric user ID or group ID.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="API base URL.")
    parser.add_argument("--sleep", type=float, default=0.0, help="Seconds to pause between requests.")


def cmd_config(args: argparse.Namespace) -> None:
    data = {
        "library_type": args.library_type or os.getenv("ZOTERO_LIBRARY_TYPE", "user"),
        "library_id": args.library_id or os.getenv("ZOTERO_LIBRARY_ID", ""),
        "api_key_set": bool(args.api_key or os.getenv("ZOTERO_API_KEY")),
        "base_url": args.base_url or os.getenv("ZOTERO_API_BASE", DEFAULT_BASE_URL),
    }
    dump_json(data)


def cmd_whoami(args: argparse.Namespace) -> None:
    client = ZoteroClient(
        library_type=args.library_type or os.getenv("ZOTERO_LIBRARY_TYPE", "user"),
        library_id=args.library_id or os.getenv("ZOTERO_LIBRARY_ID", ""),
        api_key=args.api_key or os.getenv("ZOTERO_API_KEY"),
        base_url=args.base_url or os.getenv("ZOTERO_API_BASE", DEFAULT_BASE_URL),
        sleep_seconds=args.sleep,
    )
    data = client.current_key()
    dump_json(
        {
            "userID": data.get("userID"),
            "username": data.get("username"),
            "access": data.get("access"),
        },
        args.out,
    )


def cmd_collections(args: argparse.Namespace) -> None:
    client = client_from_args(args)
    if args.tree:
        dump_json(client.collection_paths(), args.out)
        return
    endpoint = f"{client.prefix}/collections/top" if args.top else f"{client.prefix}/collections"
    items = client.fetch_page_items(
        endpoint,
        {"sort": "title", "direction": "asc", "limit": min(args.page_size, 100)},
        max_items=None if args.all else args.max,
        fetch_all=args.all,
    )
    output = [simplify_item(item) | {"name": (item.get("data") or {}).get("name")} for item in items]
    dump_json(output, args.out)


def resolve_collection_arg(client: ZoteroClient, args: argparse.Namespace) -> str | None:
    collection = args.collection
    if getattr(args, "collection_path", None):
        collection = client.resolve_collection_path(args.collection_path)
        eprint(f"Resolved collection path to key: {collection}")
    return collection


def item_list_endpoint(client: ZoteroClient, args: argparse.Namespace) -> str:
    collection = resolve_collection_arg(client, args)
    if collection:
        suffix = "/items/top" if args.top else "/items"
        return f"{client.prefix}/collections/{collection}{suffix}"
    return f"{client.prefix}/items/top" if args.top else f"{client.prefix}/items"


def item_list_params(args: argparse.Namespace) -> dict[str, Any]:
    params: dict[str, Any] = {
        "sort": args.sort,
        "direction": args.direction,
        "limit": min(args.page_size, 100),
    }
    if args.q:
        params["q"] = args.q
    if args.qmode:
        params["qmode"] = args.qmode
    if args.tag:
        params["tag"] = args.tag
    if args.item_type:
        params["itemType"] = args.item_type
    return params


def cmd_items(args: argparse.Namespace) -> None:
    client = client_from_args(args)
    items = client.fetch_page_items(
        item_list_endpoint(client, args),
        item_list_params(args),
        max_items=None if args.all else args.max,
        fetch_all=args.all,
    )
    dump_json([simplify_item(item) for item in items], args.out)


def write_attachment_fulltext(out_dir: Path, parent_key: str, attachment_key: str, fulltext: dict[str, Any]) -> str:
    text_dir = out_dir / "fulltext"
    text_dir.mkdir(parents=True, exist_ok=True)
    target = text_dir / f"{sanitize_filename(parent_key)}__{sanitize_filename(attachment_key)}.txt"
    target.write_text(fulltext.get("content") or "", encoding="utf-8")
    return str(target)


def pack_one_item(
    client: ZoteroClient,
    key: str,
    out_dir: Path,
    include_fulltext: bool,
    download_files: bool,
) -> dict[str, Any]:
    item = client.item(key)
    children = client.children(key)
    packed = {
        "item": simplify_item(item),
        "children": [simplify_item(child) for child in children],
        "attachments": [],
    }

    for child in children:
        child_data = child.get("data") or child
        if child_data.get("itemType") != "attachment":
            continue
        attachment_key = child_data.get("key") or child.get("key")
        attachment = {"metadata": simplify_item(child)}
        if include_fulltext:
            fulltext = client.fulltext(attachment_key)
            if fulltext:
                attachment["fulltext"] = {
                    "path": write_attachment_fulltext(out_dir, key, attachment_key, fulltext),
                    "indexedPages": fulltext.get("indexedPages"),
                    "totalPages": fulltext.get("totalPages"),
                    "indexedChars": fulltext.get("indexedChars"),
                    "totalChars": fulltext.get("totalChars"),
                    "chars": len(fulltext.get("content") or ""),
                }
            else:
                attachment["fulltext"] = {"error": "No full-text content found"}
        if download_files:
            attachment["download"] = client.download_file(child, out_dir / "files")
        packed["attachments"].append(attachment)
    return packed


def selected_keys_for_pack(client: ZoteroClient, args: argparse.Namespace) -> list[str]:
    keys = parse_key_list(args.keys)
    if keys:
        return keys

    items = client.fetch_page_items(
        item_list_endpoint(client, args),
        item_list_params(args),
        max_items=None if args.all else args.max,
        fetch_all=args.all,
    )
    return [item.get("key") or (item.get("data") or {}).get("key") for item in items if item.get("key") or (item.get("data") or {}).get("key")]


def cmd_pack(args: argparse.Namespace) -> None:
    client = client_from_args(args)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    keys = selected_keys_for_pack(client, args)
    bundle = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "library": {"type": client.library_type, "id": client.library_id},
        "selection": {
            "keys": keys,
            "collection": resolve_collection_arg(client, args),
            "collection_path": args.collection_path,
            "q": args.q,
            "tag": args.tag,
            "max": None if args.all else args.max,
        },
        "items": [],
    }
    for key in keys:
        eprint(f"Fetching {key}...")
        try:
            bundle["items"].append(
                pack_one_item(
                    client,
                    key,
                    out_dir,
                    include_fulltext=not args.skip_fulltext,
                    download_files=args.download_files,
                )
            )
        except ZoteroError as exc:
            bundle["items"].append({"item": {"key": key}, "error": str(exc)})
    target = out_dir / "zotero_pack.json"
    dump_json(bundle, str(target))


def cmd_fulltext(args: argparse.Namespace) -> None:
    client = client_from_args(args)
    fulltext = client.fulltext(args.attachment_key)
    if not fulltext:
        raise ZoteroError("No full-text content found for attachment")
    if args.out:
        target = Path(args.out)
        ensure_parent(target)
        target.write_text(fulltext.get("content") or "", encoding="utf-8")
        print(str(target))
    else:
        dump_json(fulltext)


def cmd_download(args: argparse.Namespace) -> None:
    client = client_from_args(args)
    attachment = client.item(args.attachment_key)
    result = client.download_file(attachment, Path(args.out_dir))
    dump_json(result, args.out)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only Zotero Web API helper.")
    add_common(parser)
    sub = parser.add_subparsers(dest="command", required=True)

    config = sub.add_parser("config", help="Show resolved config without exposing the API key.")
    config.set_defaults(func=cmd_config)

    whoami = sub.add_parser("whoami", help="Show userID and access for the current API key.")
    whoami.add_argument("--out")
    whoami.set_defaults(func=cmd_whoami)

    collections = sub.add_parser("collections", help="List collections.")
    collections.add_argument("--top", action="store_true", help="Only top-level collections.")
    collections.add_argument("--tree", action="store_true", help="List collections with full paths.")
    collections.add_argument("--all", action="store_true", help="Fetch all pages.")
    collections.add_argument("--max", type=int, default=100, help="Maximum records unless --all.")
    collections.add_argument("--page-size", type=int, default=100)
    collections.add_argument("--out")
    collections.set_defaults(func=cmd_collections)

    items = sub.add_parser("items", help="List or search items.")
    add_item_selection_args(items)
    items.add_argument("--out")
    items.set_defaults(func=cmd_items)

    pack = sub.add_parser("pack", help="Fetch metadata, child attachments, and full text for summarization.")
    add_item_selection_args(pack)
    pack.add_argument("--keys", help="Comma/space separated parent item keys.")
    pack.add_argument("--out-dir", default="zotero_pack", help="Directory for JSON and full text files.")
    pack.add_argument("--skip-fulltext", action="store_true", help="Do not fetch Zotero full-text index.")
    pack.add_argument("--download-files", action="store_true", help="Download attachment files when possible.")
    pack.set_defaults(func=cmd_pack)

    fulltext = sub.add_parser("fulltext", help="Fetch full text for an attachment item key.")
    fulltext.add_argument("attachment_key")
    fulltext.add_argument("--out", help="Write content text to this file.")
    fulltext.set_defaults(func=cmd_fulltext)

    download = sub.add_parser("download", help="Download an attachment file by attachment item key.")
    download.add_argument("attachment_key")
    download.add_argument("--out-dir", default="zotero_files")
    download.add_argument("--out", help="Write result JSON to this file.")
    download.set_defaults(func=cmd_download)

    return parser


def add_item_selection_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--collection", help="Collection key.")
    parser.add_argument("--collection-path", help="Collection path, e.g. 'Research > Topic > Subtopic'.")
    parser.add_argument("--top", action="store_true", default=True, help="Use top-level parent items.")
    parser.add_argument("--include-children", dest="top", action="store_false", help="Include child items in item listing.")
    parser.add_argument("--q", help="Quick search string.")
    parser.add_argument("--qmode", help="Zotero search mode, e.g. titleCreatorYear or everything.")
    parser.add_argument("--tag", help="Tag filter.")
    parser.add_argument("--item-type", help="Zotero item type filter, e.g. journalArticle.")
    parser.add_argument("--sort", default="dateModified")
    parser.add_argument("--direction", default="desc", choices=["asc", "desc"])
    parser.add_argument("--all", action="store_true", help="Fetch all pages.")
    parser.add_argument("--max", type=int, default=25, help="Maximum records unless --all.")
    parser.add_argument("--page-size", type=int, default=25)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
        return 0
    except ZoteroError as exc:
        eprint(f"zotero_api.py: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
