from __future__ import annotations

from typing import Any

import great_expectations as gx
import pandas as pd

from core.config import Settings
from core.utils import write_json

_NOT_NULL_COLUMNS = ["paper_id", "title", "text_for_embedding"]


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Run the Great Expectations 1.x quality gate and persist a report to `data/quality/`."""
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name=f"{report_name}_source")
    data_asset = data_source.add_dataframe_asset(name=f"{report_name}_asset")
    batch_def = data_asset.add_batch_definition_whole_dataframe(f"{report_name}_batch")
    batch = batch_def.get_batch(batch_parameters={"dataframe": df})

    suite = context.suites.add(gx.ExpectationSuite(name=f"{report_name}_suite"))
    suite.add_expectation(gx.expectations.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000))
    for column in _NOT_NULL_COLUMNS:
        suite.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column=column))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToBeUnique(column="paper_id"))
    suite.add_expectation(
        gx.expectations.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30)
    )

    result = batch.validate(suite)
    expectations = [
        {
            "expectation_type": item["expectation_config"]["type"],
            "column": item["expectation_config"]["kwargs"].get("column"),
            "success": item["success"],
            "unexpected_count": item.get("result", {}).get("unexpected_count", 0),
        }
        for item in result["results"]
    ]

    report = {
        "report_name": report_name,
        "success": bool(result["success"]),
        "row_count": len(df),
        "expectations": expectations,
    }
    write_json(settings.paths.quality_dir / f"{report_name}_quality_report.json", report)
    return report


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Summarize freshness SLA: share of rows older than `freshness_threshold_days`."""
    total_rows = len(df)
    if total_rows == 0:
        payload = {
            "latest_published": None,
            "oldest_published": None,
            "stale_rows": 0,
            "total_rows": 0,
            "stale_ratio": 0.0,
            "is_fresh": False,
        }
        write_json(report_path, payload)
        return payload

    stale_rows = int((df["age_days"] > settings.freshness_threshold_days).sum())
    stale_ratio = stale_rows / total_rows
    payload = {
        "latest_published": df["published"].max(),
        "oldest_published": df["published"].min(),
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": stale_ratio,
        "is_fresh": stale_ratio <= 0.25,
    }
    write_json(report_path, payload)
    return payload
