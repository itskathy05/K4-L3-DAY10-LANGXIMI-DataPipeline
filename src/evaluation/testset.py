from __future__ import annotations

from typing import Any

import pandas as pd

from core.utils import first_sentence, write_json

_QUESTION_TYPES = ["summary", "authors", "date", "categories"]


def _build_question(question_type: str, row: pd.Series) -> tuple[str, str]:
    title = row["title"]
    if question_type == "summary":
        return f"What is the summary of the paper '{title}'?", first_sentence(row["summary"])
    if question_type == "authors":
        return f"Who authored the paper '{title}'?", row["authors_joined"]
    if question_type == "date":
        return f"When was the paper '{title}' published?", row["published"]
    return f"What categories does the paper '{title}' belong to?", row["categories_joined"]


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Build a 10-question benchmark set cycling through summary/authors/date/categories."""
    min_rows = 10
    if len(df) < min_rows:
        raise ValueError(f"Need at least {min_rows} clean documents to build the test set, got {len(df)}.")

    sample = df.iloc[:min_rows].reset_index(drop=True)
    test_set: list[dict[str, Any]] = []
    for idx, row in sample.iterrows():
        question_type = _QUESTION_TYPES[idx % len(_QUESTION_TYPES)]
        question, ground_truth = _build_question(question_type, row)
        test_set.append(
            {
                "id": f"eval_{idx + 1:03d}",
                "question_type": question_type,
                "question": question,
                "ground_truth": ground_truth,
                "ground_truth_doc_ids": [row["paper_id"]],
            }
        )

    write_json(output_path, test_set)
    return test_set
