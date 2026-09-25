# Corruption & Repair Comparison Report

## Three-state metric comparison
| Metric | Baseline | Corrupted | Repaired |
| --- | --- | --- | --- |
| Retrieval hit rate | 1.000 | 0.500 | 1.000 |
| Mean token F1 | 1.000 | 0.679 | 1.000 |
| Judge accuracy | 1.000 | 0.600 | 1.000 |
| Mean judge score | 5.000 | 3.900 | 5.000 |

## Analysis
- Corruption dropped retrieval hit rate by 0.500 versus baseline.
- Data quality gate on corrupted data: success = **False**.
- Freshness on corrupted data: is_fresh = **False** (stale_ratio=33.3%).
- After idempotent repair from raw records, data quality gate success = **True**, freshness is_fresh = **True**.
- Retrieval hit rate recovered to baseline level: **True**.
