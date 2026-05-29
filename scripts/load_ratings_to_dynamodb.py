"""
Batch load a ratings JSONL into the DynamoDB Ratings table (user_id + book_id).

Usage:
  python3 scripts/load_ratings_to_dynamodb.py \
      --file ratings.jsonl --table Ratings \
      --endpoint-url http://localhost:8001   # omit for real AWS
"""
import argparse
import json
from decimal import Decimal
from typing import Iterator

import boto3
from botocore.exceptions import ClientError


def iter_jsonl(path: str) -> Iterator[dict]:
    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line, parse_float=Decimal)
            except json.JSONDecodeError as e:
                print(f"[WARN] Line {line_num}: JSON decode error: {e}")


def load_ratings(file_path, table_name, region=None, endpoint_url=None):
    kwargs = {}
    if region:
        kwargs["region_name"] = region
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
        kwargs.setdefault("aws_access_key_id", "local")
        kwargs.setdefault("aws_secret_access_key", "local")
    table = boto3.resource("dynamodb", **kwargs).Table(table_name)

    total, skipped = 0, 0
    with table.batch_writer() as batch:
        for r in iter_jsonl(file_path):
            if not r.get("user_id") or not r.get("book_id"):
                skipped += 1
                continue
            try:
                batch.put_item(Item=r)
                total += 1
            except ClientError as e:
                print(f"[ERROR] {r.get('user_id')}/{r.get('book_id')}: {e}")
            if total % 1000 == 0 and total:
                print(f"  Written {total:,} ...")
    print(f"COMPLETE: {total:,} ratings written, {skipped:,} skipped (missing keys).")


def main():
    p = argparse.ArgumentParser(description="Batch load ratings JSONL into DynamoDB Ratings table")
    p.add_argument("--file", required=True)
    p.add_argument("--table", required=True)
    p.add_argument("--region", required=False)
    p.add_argument("--endpoint-url", required=False)
    a = p.parse_args()
    load_ratings(a.file, a.table, a.region, a.endpoint_url)


if __name__ == "__main__":
    main()
