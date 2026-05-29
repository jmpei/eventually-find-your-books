"""
Scatter-gather measurement harness for the A-Z sharded search.

Model: a search over all 27 title-prefix partitions (A-Z + '0') is the fixed
work. The 27 partition queries fan out across N workers (parallel section);
merging + ranking all results is done once at the end (serial section). We
sweep N and record speedup S(N) = T(1)/T(N), plus per-phase timings emulating
the production X-Phase-Parse / X-Phase-Aggregate / X-Phase-Total headers.

Run (after `docker compose up -d dynamodb` and `python scripts/setup_local.py`):
    python -m analysis.amdahl.harness --endpoint-url http://localhost:8001
"""
import argparse
import csv
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import boto3
from boto3.dynamodb.conditions import Key

PREFIXES = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + ["0"]
RESULTS_DIR = Path(__file__).resolve().parent / "results"


def _table(endpoint_url, region):
    ddb = boto3.resource("dynamodb", endpoint_url=endpoint_url, region_name=region,
                         aws_access_key_id="local", aws_secret_access_key="local")
    return ddb.Table("Books")


def query_prefix(table, prefix):
    """Query one partition via TitlePrefixIndex; return its items."""
    items, resp = [], table.query(
        IndexName="TitlePrefixIndex",
        KeyConditionExpression=Key("title_prefix").eq(prefix),
    )
    items.extend(resp.get("Items", []))
    while "LastEvaluatedKey" in resp:
        resp = table.query(
            IndexName="TitlePrefixIndex",
            KeyConditionExpression=Key("title_prefix").eq(prefix),
            ExclusiveStartKey=resp["LastEvaluatedKey"],
        )
        items.extend(resp.get("Items", []))
    return items


def run_once(table, n_workers):
    """One scatter-gather pass at N workers. Returns (parse_s, aggregate_s, total_s)."""
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=n_workers) as ex:
        shards = list(ex.map(lambda p: query_prefix(table, p), PREFIXES))
    parse_s = time.perf_counter() - t0  # parallel fan-out wall time

    t1 = time.perf_counter()
    merged = [item for shard in shards for item in shard]
    merged.sort(key=lambda b: (int(b.get("rating_count", 0)),
                               float(b.get("avg_rating", 0))), reverse=True)
    aggregate_s = time.perf_counter() - t1  # serial merge + rank
    total_s = parse_s + aggregate_s
    return parse_s, aggregate_s, total_s


def sweep(table, worker_counts, repeats):
    """Median total time per N, normalized to speedup against the first N."""
    medians = {}
    for n in worker_counts:
        samples = [run_once(table, n) for _ in range(repeats)]
        samples.sort(key=lambda s: s[2])
        medians[n] = samples[len(samples) // 2]  # median by total_s
    base_total = medians[worker_counts[0]][2]
    rows = []
    for n in worker_counts:
        parse_s, aggregate_s, total_s = medians[n]
        rows.append({"n_workers": n, "parse_s": round(parse_s, 6),
                     "aggregate_s": round(aggregate_s, 6), "total_s": round(total_s, 6),
                     "speedup": round(base_total / total_s, 4)})
    return rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--endpoint-url", default="http://localhost:8001")
    p.add_argument("--region", default="us-west-2")
    p.add_argument("--workers", default="1,2,4,8,16,26")
    p.add_argument("--repeats", type=int, default=5)
    args = p.parse_args()

    table = _table(args.endpoint_url, args.region)
    worker_counts = [int(x) for x in args.workers.split(",")]
    rows = sweep(table, worker_counts, args.repeats)

    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / "speedup.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["n_workers", "parse_s", "aggregate_s", "total_s", "speedup"])
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {out}")
    for r in rows:
        print(f"  N={r['n_workers']:>2}  total={r['total_s']:.4f}s  speedup={r['speedup']}")


if __name__ == "__main__":
    main()
