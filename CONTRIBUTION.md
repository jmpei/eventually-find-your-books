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
Designed cross-validation methodology to derive sharding serial 
fraction `f` via two independent methods:
- (1) Least-squares fit over measured speedups at N = 1/16/26 ECS shards
- (2) Per-request phase profiling via `X-Phase-Parse` / `Aggregate` / 
      `Total` response headers

This isolates fan-out overhead and load imbalance from inherent 
serial sections.

## Files I Authored
```

data-processing/ ├── extract_works_clean.py ← strict ETL filter ├── extract_works_loose.py ← relaxed ETL filter (final pipeline) ├── update_book_ratings.py ← rating join + popularity ranking ├── validate_jsonl.py ← schema validation └── analyze_data.py ← dataset statistics

scripts/ ├── load_books_to_dynamodb.py ← Books table batch loader └── load_ratings_to_dynamodb.py ← Ratings table batch loader

infra/ ├── dynamodb.tf ← 3 tables + 3 GSIs + PITR + SSE └── main.tf ← AWS provider config

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
