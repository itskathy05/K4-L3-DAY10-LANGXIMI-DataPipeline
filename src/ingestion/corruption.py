from __future__ import annotations

from datetime import date, timedelta
from math import ceil

import pandas as pd

from core.utils import write_json
from ingestion.cleaning import build_embedding_text

_NOISE = " #@!$~~??garbled_bytes_0x00"


def _refresh_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    df["summary_chars"] = df["summary"].str.len()
    df["text_for_embedding"] = df.apply(lambda row: build_embedding_text(row), axis=1)
    return df


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Inject 6 realistic data-corruption scenarios into a clean dataframe.

    Assumes `df` is sorted by `published` descending (most recent first), as produced by
    `build_clean_dataframe`.
    """
    df = df.reset_index(drop=True).copy()
    n = len(df)
    log: list[dict] = []
    cursor = 0

    # 1. Drop the most recent 20% of records (simulates lost fresh ingestion).
    drop_n = max(1, ceil(0.2 * n))
    dropped_idx = list(range(cursor, min(cursor + drop_n, n)))
    dropped_ids = df.loc[dropped_idx, "paper_id"].tolist()
    log.append(
        {
            "corruption_type": "drop_latest_records",
            "description": "Removed the most recently published records to simulate a failed ingestion run.",
            "affected_paper_ids": dropped_ids,
            "count": len(dropped_ids),
        }
    )
    cursor += drop_n

    # 2. Blank out the summary field on a few rows.
    blank_idx = list(range(cursor, min(cursor + 3, n)))
    df.loc[blank_idx, "summary"] = ""
    log.append(
        {
            "corruption_type": "blank_summary",
            "description": "Cleared the summary text to simulate an empty scrape.",
            "affected_paper_ids": df.loc[blank_idx, "paper_id"].tolist(),
            "count": len(blank_idx),
        }
    )
    cursor += 3

    # 3. Inject garbage characters into the summary.
    noise_idx = list(range(cursor, min(cursor + 3, n)))
    df.loc[noise_idx, "summary"] = df.loc[noise_idx, "summary"] + _NOISE
    log.append(
        {
            "corruption_type": "inject_noise",
            "description": "Appended garbage characters into the summary to simulate scraping noise.",
            "affected_paper_ids": df.loc[noise_idx, "paper_id"].tolist(),
            "count": len(noise_idx),
        }
    )
    cursor += 3

    # 4. Truncate titles below a readable length.
    truncate_idx = list(range(cursor, min(cursor + 3, n)))
    df.loc[truncate_idx, "title"] = df.loc[truncate_idx, "title"].str[:7]
    log.append(
        {
            "corruption_type": "truncate_title",
            "description": "Truncated the title to fewer than 8 characters.",
            "affected_paper_ids": df.loc[truncate_idx, "paper_id"].tolist(),
            "count": len(truncate_idx),
        }
    )
    cursor += 3

    # 5. Push published dates back a year, staling the freshness SLA.
    remaining = n - drop_n
    stale_n = max(1, ceil(0.3 * remaining))
    stale_idx = list(range(cursor, min(cursor + stale_n, n)))

    def _stale_date(value: str) -> str:
        return (date.fromisoformat(value) - timedelta(days=365)).isoformat()

    df.loc[stale_idx, "published"] = df.loc[stale_idx, "published"].apply(_stale_date)
    log.append(
        {
            "corruption_type": "stale_date",
            "description": "Pushed the published date back 365 days to simulate stale metadata.",
            "affected_paper_ids": df.loc[stale_idx, "paper_id"].tolist(),
            "count": len(stale_idx),
        }
    )
    cursor += stale_n

    # 6. Duplicate a couple of rows.
    dup_idx = list(range(cursor, min(cursor + 2, n)))
    duplicated_rows = df.loc[dup_idx].copy()
    log.append(
        {
            "corruption_type": "duplicate_rows",
            "description": "Duplicated rows to simulate a duplicate ingestion write.",
            "affected_paper_ids": df.loc[dup_idx, "paper_id"].tolist(),
            "count": len(dup_idx),
        }
    )

    df = df.drop(index=dropped_idx).reset_index(drop=True)
    df = pd.concat([df, duplicated_rows], ignore_index=True)

    run_day = date.today()
    df["age_days"] = df["published"].apply(lambda value: (run_day - date.fromisoformat(value)).days)
    df = _refresh_derived_columns(df)

    write_json(output_log_path, log)
    return df
