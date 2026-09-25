from __future__ import annotations

from typing import Any
from pathlib import Path
import great_expectations as gx
import pandas as pd

from core.config import Settings
from core.utils import write_json, ensure_parent


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Cài đặt Quality Gate theo chuẩn Great Expectations 1.x."""
    # 1. Khởi tạo Ephemeral context trên RAM (nhanh, chuẩn GX 1.x)
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name=f"papers_source_{report_name}")
    data_asset = data_source.add_dataframe_asset(name=f"papers_asset_{report_name}")
    batch_def = data_asset.add_batch_definition_whole_dataframe(f"papers_batch_{report_name}")
    batch = batch_def.get_batch(batch_parameters={"dataframe": df})

    # 2. Định nghĩa Suite và 4 Expectations thiết yếu
    suite_name = f"papers_{report_name}_suite"
    suite = gx.ExpectationSuite(name=suite_name)
    
    suite.add_expectation(gx.expectations.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column="paper_id"))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column="title"))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column="text_for_embedding"))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToBeUnique(column="paper_id"))
    suite.add_expectation(gx.expectations.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30))
    
    context.suites.add(suite)

    # 3. Chạy validation
    validation_result = batch.validate(suite)
    
    # 4. Gom kết quả và lưu ra JSON artifact
    result_dict = validation_result.to_json_dict()
    output_path = settings.paths.quality_dir / f"{report_name}_quality_report.json"
    write_json(output_path, result_dict)

    return {
        "success": bool(validation_result.success),
        "report_name": report_name,
        "evaluated_expectations": len(suite.expectations),
        "successful_expectations": sum(1 for res in validation_result.results if res.success),
        "output_path": str(output_path),
    }


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path: Path) -> dict[str, Any]:
    """Tổng hợp báo cáo Freshness SLA."""
    total_rows = len(df)
    if total_rows == 0:
        report = {
            "latest_published": None,
            "oldest_published": None,
            "stale_rows": 0,
            "total_rows": 0,
            "stale_ratio": 0.0,
            "is_fresh": False,
        }
        write_json(report_path, report)
        return report

    threshold_days = settings.freshness_threshold_days  # Mặc định: 180 ngày
    stale_mask = df["age_days"] > threshold_days
    stale_rows = int(stale_mask.sum())
    stale_ratio = stale_rows / total_rows

    # SLA: Nếu tỉ lệ stale > 25% thì cảnh báo is_fresh = False
    is_fresh = stale_ratio <= 0.25

    report = {
        "latest_published": str(df["published"].max()),
        "oldest_published": str(df["published"].min()),
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": round(stale_ratio, 4),
        "threshold_days": threshold_days,
        "is_fresh": is_fresh,
    }
    write_json(report_path, report)
    return report
