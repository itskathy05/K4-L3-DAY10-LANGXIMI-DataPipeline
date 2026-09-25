from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime

import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord


def build_embedding_text(row: dict) -> str:
    return (
        f"Title: {row['title']}\n"
        f"Authors: {row['authors_joined']}\n"
        f"Published: {row['published']}\n"
        f"Categories: {row['categories_joined']}\n"
        f"Summary: {row['summary']}"
    )


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw `PaperRecord`s into an embed-ready dataframe."""
    rows = []
    for record in records:
        row = asdict(record)
        row["title"] = normalize_whitespace(row["title"])
        row["summary"] = normalize_whitespace(row["summary"])
        row["authors"] = [normalize_whitespace(a) for a in row["authors"] if a]
        row["categories"] = [normalize_whitespace(c) for c in row["categories"] if c]
        rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df = df[df["paper_id"].astype(bool) & df["title"].astype(bool) & df["summary"].astype(bool)]
    df = df.drop_duplicates(subset="paper_id", keep="first").reset_index(drop=True)

    df["authors_joined"] = df["authors"].apply(compact_join)
    df["categories_joined"] = df["categories"].apply(compact_join)
    df["summary_chars"] = df["summary"].str.len()

    run_day = run_date.date() if isinstance(run_date, datetime) else run_date
    df["age_days"] = df["published"].apply(
        lambda value: (run_day - date.fromisoformat(value)).days if value else None
    )

    df["text_for_embedding"] = df.apply(lambda row: build_embedding_text(row), axis=1)

    df = df.sort_values(by=["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)
    return df
