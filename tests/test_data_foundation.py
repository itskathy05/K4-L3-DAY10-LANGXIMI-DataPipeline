from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path

import pandas as pd
import requests

from core.config import load_settings
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records, parse_crossref_payload


ROOT = Path(__file__).resolve().parents[1]
RUN_DATE = datetime(2026, 9, 25, tzinfo=timezone.utc)


def test_snapshot_parses_and_cleaning_matches_retrieval_contract() -> None:
    payload = json.loads((ROOT / "data/raw/crossref_response.json").read_text(encoding="utf-8"))
    records = parse_crossref_payload(payload)
    cleaned = build_clean_dataframe(records, RUN_DATE)

    assert len(records) == len(cleaned) == 24
    assert cleaned.paper_id.is_unique
    assert cleaned.summary_chars.ge(30).all()
    assert {"paper_id", "title", "summary", "published", "authors_joined",
            "categories_joined", "text_for_embedding", "abs_url", "pdf_url"} <= set(cleaned.columns)
    assert cleaned.text_for_embedding.str.split("\n").map(len).eq(5).all()
    assert not cleaned.text_for_embedding.str.contains("<jats:", regex=False).any()


def test_parser_skips_missing_identity_and_normalizes_dates_and_markup() -> None:
    base = {
        "DOI": "10.1234/ABC",
        "title": [" A  <i>paper</i> "],
        "abstract": "<jats:p>A sufficiently long summary with &amp; an escaped character.</jats:p>",
        "author": [{"given": "Ada", "family": "Lovelace"}],
        "subject": ["Computer Science"],
        "published": {"date-parts": [[2025]]},
    }
    records = parse_crossref_payload({"message": {"items": [base, {**base, "DOI": ""},
                                                     {**base, "title": []},
                                                     {**base, "DOI": "10.1234/month", "published": {"date-parts": [[2025, 7]]}}]}})

    assert [record.paper_id for record in records] == ["10.1234/abc", "10.1234/month"]
    assert [record.published for record in records] == ["2025-01-01", "2025-07-01"]
    assert records[0].title == "A paper"
    assert "&" in records[0].summary and "<jats:" not in records[0].summary


def test_cleaning_deduplicates_and_repair_is_repeatable() -> None:
    records = load_raw_records(ROOT / "data/raw/crossref_records.json")
    first = build_clean_dataframe(records + [records[0], replace(records[0], paper_id="10.1234/no-summary",
                                                        summary="")], RUN_DATE)
    repaired = build_clean_dataframe(load_raw_records(ROOT / "data/raw/crossref_records.json"), RUN_DATE)

    assert len(first) == 24
    pd.testing.assert_frame_equal(first, repaired)
    assert repaired.loc[0, "age_days"] == (RUN_DATE.date() - datetime.fromisoformat(
        repaired.loc[0, "published"]).date()).days


def test_default_mode_uses_snapshot_without_network(tmp_path, monkeypatch) -> None:
    snapshot = (ROOT / "data/raw/crossref_response.json").read_bytes()
    response_path = tmp_path / "crossref_response.json"
    response_path.write_bytes(snapshot)
    settings = load_settings(ROOT)
    settings = replace(settings, refresh_source=False, paths=replace(
        settings.paths,
        raw_api_response=response_path,
        raw_records_json=tmp_path / "crossref_records.json",
    ))

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Offline mode must not call Crossref")

    monkeypatch.setattr(requests.Session, "get", fail_if_called)
    records = fetch_source_records(settings)

    assert len(records) == 24
    assert response_path.read_bytes() == snapshot
    assert load_raw_records(settings.paths.raw_records_json) == records


def test_live_api_failure_falls_back_without_changing_response(tmp_path, monkeypatch) -> None:
    snapshot = (ROOT / "data/raw/crossref_response.json").read_bytes()
    response_path = tmp_path / "crossref_response.json"
    response_path.write_bytes(snapshot)
    settings = load_settings(ROOT)
    settings = replace(settings, refresh_source=True, paths=replace(
        settings.paths,
        raw_api_response=response_path,
        raw_records_json=tmp_path / "crossref_records.json",
    ))

    def fail_request(*args, **kwargs):
        raise requests.ConnectionError("simulated network failure")

    monkeypatch.setattr(requests.Session, "get", fail_request)
    records = fetch_source_records(settings)

    assert len(records) == 24
    assert response_path.read_bytes() == snapshot
    assert load_raw_records(settings.paths.raw_records_json) == records
