from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import pandas as pd

from core.utils import write_json


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path: Path | str) -> pd.DataFrame:
    """Simulate 6 realistic data corruption scenarios on a clean DataFrame.

    Scenarios:
    1. Drop latest records (~20% of newest records).
    2. Blank summary on selected rows.
    3. Inject noisy tokens into summaries.
    4. Truncate title to < 8 characters.
    5. Stale date (shift dates back by 365 days, making age_days > 180).
    6. Duplicate rows to introduce unique constraint violation.
    7. Rebuild text_for_embedding.
    8. Write corruption log to output_log_path.
    """
    corrupted = df.copy(deep=True)
    baseline_count = len(corrupted)

    # 1. Drop ~20% of latest records (sort by published descending, drop top 20%)
    drop_count = max(1, int(baseline_count * 0.20))
    corrupted = corrupted.sort_values("published", ascending=False).reset_index(drop=True)
    dropped_ids = list(corrupted.iloc[:drop_count]["paper_id"])
    corrupted = corrupted.iloc[drop_count:].reset_index(drop=True)

    # 2. Blank summary on a couple of remaining rows (triggers GX ExpectColumnValueLengthsToBeBetween fail)
    blank_indices = [0, 1] if len(corrupted) > 2 else [0]
    blanked_ids = []
    for idx in blank_indices:
        corrupted.loc[idx, "summary"] = ""
        blanked_ids.append(str(corrupted.loc[idx, "paper_id"]))

    # 3. Inject noise into summaries
    noise_indices = [2, 3] if len(corrupted) > 4 else [1]
    noised_ids = []
    for idx in noise_indices:
        original = str(corrupted.loc[idx, "summary"])
        corrupted.loc[idx, "summary"] = f"### CORRUPTED_GARBAGE_NOISE_!@#$%^&* {original}"
        noised_ids.append(str(corrupted.loc[idx, "paper_id"]))

    # 4. Truncate title to < 8 characters
    trunc_indices = [4, 5] if len(corrupted) > 6 else [2]
    truncated_ids = []
    for idx in trunc_indices:
        title = str(corrupted.loc[idx, "title"])
        corrupted.loc[idx, "title"] = title[:6].strip()
        truncated_ids.append(str(corrupted.loc[idx, "paper_id"]))

    # 5. Stale dates (shift published back by 365 days, make age_days > 180)
    stale_count = 0
    for idx in range(len(corrupted)):
        pub_str = str(corrupted.loc[idx, "published"])[:10]
        try:
            pub_date = date.fromisoformat(pub_str)
            stale_date = pub_date - timedelta(days=365)
            corrupted.loc[idx, "published"] = stale_date.isoformat()
        except (ValueError, TypeError):
            corrupted.loc[idx, "published"] = "2024-01-01"
        corrupted.loc[idx, "age_days"] = int(corrupted.loc[idx, "age_days"]) + 365
        stale_count += 1

    # 6. Duplicate rows (take 2 rows and append them again to create duplicate paper_ids)
    dup_indices = [0, 1] if len(corrupted) > 2 else [0]
    dup_rows = corrupted.iloc[dup_indices].copy(deep=True)
    duplicated_ids = list(dup_rows["paper_id"])
    corrupted = pd.concat([corrupted, dup_rows], ignore_index=True)

    # 7. Rebuild text_for_embedding and summary_chars
    def _rebuild_text(row):
        return "\n".join((
            f"Title: {row.get('title', '')}",
            f"Authors: {row.get('authors_joined', '')}",
            f"Published: {row.get('published', '')}",
            f"Categories: {row.get('categories_joined', '')}",
            f"Summary: {row.get('summary', '')}",
        ))

    corrupted["text_for_embedding"] = corrupted.apply(_rebuild_text, axis=1)
    if "summary_chars" in corrupted.columns:
        corrupted["summary_chars"] = corrupted["summary"].astype(str).str.len()

    # 8. Write detailed corruption log
    log = {
        "scenarios": [
            {
                "name": "drop_latest_records",
                "description": "Dropped ~20% of latest records to simulate stale ingestion & missing documents.",
                "affected_count": drop_count,
                "affected_ids": dropped_ids,
            },
            {
                "name": "blank_summary",
                "description": "Erased summaries on records to trigger schema length validation failure.",
                "affected_count": len(blank_indices),
                "affected_ids": blanked_ids,
            },
            {
                "name": "inject_noise",
                "description": "Injected random corruption tokens to degrade retrieval precision and Token F1.",
                "affected_count": len(noise_indices),
                "affected_ids": noised_ids,
            },
            {
                "name": "truncate_title",
                "description": "Truncated paper titles to fewer than 8 characters.",
                "affected_count": len(trunc_indices),
                "affected_ids": truncated_ids,
            },
            {
                "name": "stale_date",
                "description": "Shifted publication dates back by 365 days (age_days > 180) to violate Freshness SLA.",
                "affected_count": stale_count,
            },
            {
                "name": "duplicate_rows",
                "description": "Appended duplicate rows to cause ghost vectors and unique ID constraint violations.",
                "affected_count": len(dup_indices),
                "affected_ids": duplicated_ids,
            },
        ],
        "baseline_rows": baseline_count,
        "corrupted_rows": len(corrupted),
    }

    write_json(Path(output_log_path), log)
    return corrupted
