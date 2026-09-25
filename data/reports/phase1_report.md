# Phase 1 — Baseline Pipeline Report

## Source
- Documents indexed: 24
- Collection: `papers-baseline`

## Evaluation metrics
| Metric | Value |
| --- | --- |
| Samples | 10 |
| Retrieval hit rate | 1.000 |
| Mean token F1 | 1.000 |
| Judge accuracy | 1.000 |
| Mean judge score | 5.000 |

## Data quality gate (Great Expectations 1.x)
- Overall success: **True**
| Expectation | Column | Success |
| --- | --- | --- |
| expect_table_row_count_to_be_between | - | True |
| expect_column_values_to_not_be_null | paper_id | True |
| expect_column_values_to_be_unique | paper_id | True |
| expect_column_values_to_not_be_null | title | True |
| expect_column_values_to_not_be_null | text_for_embedding | True |
| expect_column_value_lengths_to_be_between | summary | True |

## Freshness SLA
- Latest published: 2026-07-22
- Oldest published: 2026-03-28
- Stale rows: 1 / 24 (4.2%)
- Is fresh: **True**
