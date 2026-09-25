from __future__ import annotations

from dataclasses import asdict, dataclass
from html import unescape
from pathlib import Path
import re
import time

import requests

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


def _clean_summary(raw: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", raw or "")
    return normalize_whitespace(unescape(without_tags))


def _format_date(date_parts: list[list[int]] | None, fallback: str | None = None) -> str:
    parts = (date_parts or [[]])[0]
    if not parts:
        return (fallback or "")[:10]
    year = parts[0]
    month = parts[1] if len(parts) > 1 else 1
    day = parts[2] if len(parts) > 2 else 1
    return f"{year:04d}-{month:02d}-{day:02d}"


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse a Crossref `/works` response into `PaperRecord`s, dropping invalid items."""
    items = payload.get("message", {}).get("items", [])
    records: list[PaperRecord] = []
    for item in items:
        doi = item.get("DOI")
        titles = item.get("title") or []
        summary = _clean_summary(item.get("abstract", ""))
        if not doi or not titles or not summary:
            continue
        title = normalize_whitespace(titles[0])
        authors = [
            normalize_whitespace(f"{a.get('given', '')} {a.get('family', '')}")
            for a in item.get("author", [])
            if a.get("given") or a.get("family")
        ]
        categories = [normalize_whitespace(c) for c in item.get("subject", []) if c]
        published = _format_date(item.get("published", {}).get("date-parts"))
        updated = item.get("created", {}).get("date-time", "")[:10] or published
        url = item.get("URL", "")
        records.append(
            PaperRecord(
                paper_id=doi,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=categories[0] if categories else "",
                published=published,
                updated=updated,
                abs_url=url,
                pdf_url=url,
                comment=f"Crossref record {doi}",
            )
        )
    return records


def _fetch_live(settings: Settings) -> dict | None:
    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
    }
    for attempt in range(3):
        try:
            response = requests.get("https://api.crossref.org/works", params=params, timeout=15)
            if response.status_code in {429, 503}:
                time.sleep(2**attempt)
                continue
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            time.sleep(2**attempt)
    return None


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Fetch source records (live API when requested, else the offline snapshot fallback)."""
    payload = None
    if settings.refresh_source:
        payload = _fetch_live(settings)
        if payload is not None:
            write_json(settings.paths.raw_api_response, payload)

    if payload is None:
        if settings.paths.raw_api_response.exists():
            payload = read_json(settings.paths.raw_api_response)
        else:
            raise RuntimeError(
                "No live Crossref response and no offline snapshot found at "
                f"{settings.paths.raw_api_response}."
            )

    records = parse_crossref_payload(payload)
    write_json(settings.paths.raw_records_json, [asdict(r) for r in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    return [PaperRecord(**item) for item in read_json(path)]
