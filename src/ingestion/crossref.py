from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from html import unescape
from pathlib import Path
import re

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def strip_markup(value: object) -> str:
    """Remove JATS/HTML tags and normalize whitespace and entities."""
    if not isinstance(value, str):
        return ""
    return normalize_whitespace(re.sub(r"<[^>]*>", " ", unescape(value)))


def _crossref_date(value: object) -> str:
    if not isinstance(value, dict):
        return ""
    parts = value.get("date-parts")
    if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0]:
        try:
            numbers = [int(part) for part in parts[0][:3]]
            return date(numbers[0], numbers[1] if len(numbers) > 1 else 1,
                        numbers[2] if len(numbers) > 2 else 1).isoformat()
        except (TypeError, ValueError):
            return ""
    stamp = value.get("date-time")
    if isinstance(stamp, str):
        try:
            return date.fromisoformat(stamp[:10]).isoformat()
        except ValueError:
            return ""
    return ""


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse Crossref work items, skipping entries without DOI or title."""
    message = payload.get("message") if isinstance(payload, dict) else None
    items = message.get("items") if isinstance(message, dict) else None
    if not isinstance(items, list):
        raise ValueError("Crossref payload must contain message.items as a list.")

    records: list[PaperRecord] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        paper_id = strip_markup(item.get("DOI")).lower()
        titles = item.get("title")
        title = strip_markup(titles[0] if isinstance(titles, list) and titles else titles)
        if not paper_id or not title:
            continue

        authors = []
        for author in item.get("author") or []:
            if isinstance(author, dict):
                name = strip_markup(" ".join(str(author.get(key) or "") for key in ("given", "family")))
                name = name or strip_markup(author.get("name"))
                if name:
                    authors.append(name)
        categories = [text for subject in (item.get("subject") or []) if (text := strip_markup(subject))]
        published = next((day for key in ("published", "published-online", "published-print", "issued", "created")
                          if (day := _crossref_date(item.get(key)))), "")
        updated = next((day for key in ("updated", "deposited", "created")
                        if (day := _crossref_date(item.get(key)))), published)
        abs_url = strip_markup(item.get("URL")) or f"https://doi.org/{paper_id}"
        pdf_url = next((strip_markup(link.get("URL")) for link in (item.get("link") or [])
                        if isinstance(link, dict) and "pdf" in str(link.get("content-type", "")).lower()
                        and strip_markup(link.get("URL"))), abs_url)
        records.append(PaperRecord(
            paper_id=paper_id,
            title=title,
            summary=strip_markup(item.get("abstract")),
            authors=authors,
            categories=categories,
            primary_category=categories[0] if categories else "",
            published=published,
            updated=updated,
            abs_url=abs_url,
            pdf_url=pdf_url,
            comment=f"Crossref record {paper_id}",
        ))
    return records


def _load_snapshot(settings: Settings) -> list[PaperRecord]:
    response_path = settings.paths.raw_api_response
    if response_path.exists():
        try:
            records = parse_crossref_payload(read_json(response_path))
            if records:
                write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
                return records
        except (ValueError, TypeError):
            pass
    if settings.paths.raw_records_json.exists():
        return load_raw_records(settings.paths.raw_records_json)
    raise FileNotFoundError("No usable Crossref snapshot exists in data/raw/.")


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Use the local snapshot by default; refresh from Crossref when requested."""
    if not settings.refresh_source and (settings.paths.raw_api_response.exists()
                                        or settings.paths.raw_records_json.exists()):
        return _load_snapshot(settings)

    retry = Retry(total=3, backoff_factor=0.5, status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=("GET",), respect_retry_after_header=True)
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    try:
        response = session.get(
            "https://api.crossref.org/works",
            params={"query": settings.source_query, "filter": settings.source_filter,
                    "rows": settings.max_results},
            timeout=20,
        )
        response.raise_for_status()
        records = parse_crossref_payload(response.json())
        if not records:
            raise ValueError("Crossref returned no usable records.")
        settings.paths.raw_api_response.parent.mkdir(parents=True, exist_ok=True)
        settings.paths.raw_api_response.write_bytes(response.content)
        write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
        return records
    except (requests.RequestException, ValueError, TypeError):
        try:
            return _load_snapshot(settings)
        except (FileNotFoundError, ValueError, TypeError) as snapshot_exc:
            raise RuntimeError("Crossref request failed and no usable local snapshot is available.") from snapshot_exc
    finally:
        session.close()


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Load the saved PaperRecord list without contacting Crossref."""
    payload = read_json(path)
    if not isinstance(payload, list):
        raise ValueError("Raw records snapshot must be a JSON list.")
    records = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"Raw record {index} must be an object.")
        try:
            records.append(PaperRecord(**item))
        except TypeError as exc:
            raise ValueError(f"Raw record {index} does not match PaperRecord schema.") from exc
    return records
