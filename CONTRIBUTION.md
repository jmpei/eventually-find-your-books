# My Contribution — Theodore (Jiaming) Pei

This project is a 4-person team effort for the CS6650 Distributed 
Systems final project at Northeastern University. I owned the 
**Data Pipeline + AWS Infrastructure track** end-to-end.

## What I Built

### 1. ETL Pipeline (Python)
Streaming hash-join over an in-memory author lookup map, processing 
30 GB+ Open Library raw dumps (works / authors / ratings) and 
normalizing 50,000 English books into DynamoDB-ready JSONL with 
composite popularity scoring.

- Strict-quality rules initially yielded only 3,574 valid records 
  out of 150K candidates → iteratively relaxed thresholds (made 
  description optional) to reach the 50K target.
- Pre-computed `title_prefix` and `title_lower` fields during ETL 
  to enable A-Z sharding via DynamoDB GSI downstream.

### 2. DynamoDB Schema + Terraform IaC
Designed and provisioned 3-table schema (Books / Ratings / 
UserProfiles) with 3 GSIs:
- `TitleLowerIndex` for case-insensitive title search
- `TitlePrefixIndex` for A-Z sharding access
- `BookRatingsIndex` for per-book rating lookups

Configured PITR (point-in-time recovery), server-side encryption, 
and on-demand billing for cost-efficiency under unpredictable 
workloads.

### 3. Batch Loader with Retry
Implemented `load_books_to_dynamodb.py` and `load_ratings_to_dynamodb.py` 
using boto3 BatchWriteItem with exponential backoff (0.5s → 10s capped) 
for unprocessed-item retries, achieving 100% schema-validation pass 
rate across 50K records (verified by automated jsonschema checks).

### 4. Data Validation + Analysis
Wrote `validate_jsonl.py` (schema integrity + A-Z prefix coverage 
checks) and `analyze_data.py` (statistical analysis: language 
distribution, year buckets, top subjects, rating coverage).

### 5. Amdahl's Law Analysis Pipeline
Built a reproducible scatter-gather harness (`analysis/amdahl/harness.py`)
that drives N concurrent worker threads querying all 27 `TitlePrefixIndex`
partitions (A–Z + "0") and records per-phase timings: fan-out wall time
(`parse_s`), serial merge + ranking (`aggregate_s`), and total (`total_s`).
The harness sweeps N ∈ {1, 2, 4, 8, 16, 26}, takes the median over 5 repeats
per N, and writes `analysis/amdahl/results/speedup.csv`.

`analysis/amdahl/fit.py` estimates the serial fraction `f` via two
independent cross-validated methods:
- (1) Closed-form linearized least-squares fit of the measured speedup curve
      to Amdahl's Law — no external solver required.
- (2) Phase-profiling: `f ≈ aggregate_s / total_s` at N = 1, where the
      merge step is the only component that does not shrink with more workers.

Both estimates and their cross-validation gap are printed to stdout;
`fit.py` also renders the measured points overlaid with the fitted Amdahl
curve (`results/speedup.png`).

**Honest framing:** the original production study ran on AWS ECS at
N = 1 / 16 / 26 tasks, but those raw run logs were not retained. This harness
reproduces the methodology at local scale (DynamoDB Local) and regenerates
the speedup curve and `f` estimate — absolute numbers differ from the ECS
run; the analysis method is identical.

## Files I Authored
```
data-processing/
├── extract_works_clean.py      ← strict ETL filter
├── extract_works_loose.py      ← relaxed ETL filter (final pipeline)
├── update_book_ratings.py      ← rating join + popularity ranking
├── validate_jsonl.py           ← schema validation
└── analyze_data.py             ← dataset statistics

scripts/
├── load_books_to_dynamodb.py   ← Books table batch loader
└── load_ratings_to_dynamodb.py ← Ratings table batch loader

infrastructure/
├── dynamodb.tf                 ← 3 tables + 3 GSIs + PITR + SSE
└── main.tf                     ← AWS provider config

analysis/amdahl/
├── harness.py                  ← scatter-gather sweep; writes results/speedup.csv
├── fit.py                      ← Amdahl fit, phase profiling, speedup plot
└── README.md                   ← methodology and run instructions

tests/
├── test_amdahl_fit.py          ← unit tests for fit.py estimators
└── test_etl_transforms.py      ← unit tests for ETL transform logic
```

See commit `a4f3e2...` (or click my profile in Insights → Contributors) 
for the full code change.

## Team & Other Contributors

| Track | Owner |
|---|---|
| Rating API + Infrastructure setup | [@modimansi](https://github.com/modimansi) (Mansi) |
| Search service + Book detail service | [@MartinJHan](https://github.com/MartinJHan) (Martin) |
| ML / Recommendation + Performance testing | [@dsnahil](https://github.com/dsnahil) (Snahil) |
| **Data Pipeline + AWS Infrastructure** | **[@TomatoesSuck](https://github.com/TomatoesSuck) (Theodore — me)** |
