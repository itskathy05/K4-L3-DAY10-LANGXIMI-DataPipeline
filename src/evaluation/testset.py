from __future__ import annotations

from pathlib import Path
from typing import Any
import pandas as pd

from core.utils import first_sentence, write_json


def build_test_set(df: pd.DataFrame, output_path: Path) -> list[dict[str, Any]]:
    """Tạo bộ evaluation benchmark gồm 10 câu hỏi chuẩn qua 4 dạng nghiệp vụ."""
    if len(df) < 10:
        raise ValueError(f"Dataframe cần tối thiểu 10 bản ghi để sinh test set, hiện có {len(df)}")

    # Lấy 10 bài báo đại diện
    sample_df = df.iloc[:10].reset_index(drop=True)
    test_set: list[dict[str, Any]] = []

    # Phân bổ: 3 summary, 3 authors, 2 date, 2 categories
    question_plan = (
        [("summary", 3)] +
        [("authors", 3)] +
        [("date", 2)] +
        [("categories", 2)]
    )

    row_idx = 0
    q_id = 1
    for q_type, count in question_plan:
        for _ in range(count):
            row = sample_df.iloc[row_idx]
            title = row["title"]
            paper_id = str(row["paper_id"])

            if q_type == "summary":
                question = f"What is the summary of the paper '{title}'?"
                ground_truth = first_sentence(str(row["summary"]))
            elif q_type == "authors":
                question = f"Who authored the paper '{title}'?"
                ground_truth = str(row["authors_joined"])
            elif q_type == "date":
                question = f"When was the paper '{title}' published?"
                ground_truth = str(row["published"])
            else:  # categories
                question = f"What categories does the paper '{title}' belong to?"
                ground_truth = str(row["categories_joined"])

            test_set.append(
                {
                    "id": f"eval_{q_id:03d}",
                    "question_type": q_type,
                    "question": question,
                    "ground_truth": ground_truth,
                    "ground_truth_doc_ids": [paper_id],
                }
            )
            row_idx += 1
            q_id += 1

    write_json(Path(output_path), test_set)
    return test_set
