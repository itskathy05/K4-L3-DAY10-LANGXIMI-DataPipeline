from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from ingestion.crossref import PaperRecord, strip_markup


CLEAN_COLUMNS = [
    "paper_id", "title", "summary", "authors", "categories", "primary_category",
    "published", "updated", "abs_url", "pdf_url", "comment", "authors_joined",
    "categories_joined", "summary_chars", "age_days", "text_for_embedding",
]


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value[:10])
    except (TypeError, ValueError):
        return None


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Create a deterministic, retrieval-ready table from preserved raw records."""
    rows = []
    seen_ids = set()
    for record in records:
        paper_id = strip_markup(record.paper_id).lower()
        title = strip_markup(record.title)
        summary = strip_markup(record.summary)
        published = _parse_date(record.published)
        if not paper_id or paper_id in seen_ids or not title or len(summary) < 30 or published is None:
            continue
        seen_ids.add(paper_id)

        authors = [text for author in (record.authors or []) if (text := strip_markup(author))]
        categories = [text for category in (record.categories or []) if (text := strip_markup(category))]
        authors_joined = ", ".join(authors)
        categories_joined = ", ".join(categories)
        updated = _parse_date(record.updated)
        published_text = published.isoformat()
        text_for_embedding = "\n".join((
            f"Title: {title}",
            f"Authors: {authors_joined}",
            f"Published: {published_text}",
            f"Categories: {categories_joined}",
            f"Summary: {summary}",
        ))
        rows.append({
            "paper_id": paper_id,
            "title": title,
            "summary": summary,
            "authors": authors,
            "categories": categories,
            "primary_category": strip_markup(record.primary_category) or (categories[0] if categories else ""),
            "published": published_text,
            "updated": updated.isoformat() if updated else published_text,
            "abs_url": strip_markup(record.abs_url),
            "pdf_url": strip_markup(record.pdf_url),
            "comment": strip_markup(record.comment),
            "authors_joined": authors_joined,
            "categories_joined": categories_joined,
            "summary_chars": len(summary),
            "age_days": (run_date.date() - published).days,
            "text_for_embedding": text_for_embedding,
        })
    return pd.DataFrame(rows, columns=CLEAN_COLUMNS).sort_values("paper_id", kind="stable").reset_index(drop=True)
