"""
Batch load books JSONL into DynamoDB Books table.

Usage example:

  python3 load_books_to_dynamodb.py \
    --file ../Data_process/books_english_top50k_with_ratings.jsonl \
    --table Books \
    --region us-east-1

Make sure your AWS credentials & region are configured (env vars or ~/.aws).
"""

import argparse
import json
from decimal import Decimal
from typing import Iterator

import boto3
from botocore.exceptions import ClientError


def iter_jsonl(path: str) -> Iterator[dict]:
    """
    Stream JSON objects from a JSONL file, one line at a time.
    Use parse_float=Decimal so DynamoDB accepts numeric types.
    """
    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line, parse_float=Decimal)
                yield obj
            except json.JSONDecodeError as e:
                print(f"[WARN] Line {line_num}: JSON decode error: {e}")
                continue


def load_books(file_path: str, table_name: str, region: str | None = None,
               endpoint_url: str | None = None):
    """
    Load books from JSONL file into DynamoDB using BatchWrite (25 items per request).
    """
    print("=" * 70)
    print("LOADING BOOKS INTO DYNAMODB")
    print("=" * 70)
    print(f"Source file : {file_path}")
    print(f"DynamoDB    : {table_name}")
    if region:
        print(f"Region      : {region}")
    print()

    # Create DynamoDB resource
    kwargs = {}
    if region:
        kwargs["region_name"] = region
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
        kwargs.setdefault("aws_access_key_id", "local")
        kwargs.setdefault("aws_secret_access_key", "local")
    dynamodb = boto3.resource("dynamodb", **kwargs)
    table = dynamodb.Table(table_name)

    total = 0
    with table.batch_writer(overwrite_by_pkeys=["book_id"]) as batch:
        for book in iter_jsonl(file_path):
            # Basic sanity check
            book_id = book.get("book_id")
            if not book_id:
                # fallback for legacy "key"
                book_id = book.get("key")
                if not book_id:
                    print("[WARN] Skip item without book_id/key")
                    continue
                book["book_id"] = book_id

            # You can optionally enforce fields here, e.g. default rating fields:
            book.setdefault("rating_count", 0)
            book.setdefault("avg_rating", Decimal("0"))

            try:
                batch.put_item(Item=book)
                total += 1
            except ClientError as e:
                print(f"[ERROR] Failed to write book_id={book_id}: {e}")
                continue

            if total % 1000 == 0:
                print(f"  Written {total:,} items ...")

    print()
    print(f"COMPLETE: {total:,} items written to DynamoDB table '{table_name}'")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Batch load books JSONL into DynamoDB Books table"
    )
    parser.add_argument(
        "--file",
        required=True,
        help="Input JSONL file, e.g. books_english_top50k_with_ratings.jsonl",
    )
    parser.add_argument(
        "--table",
        required=True,
        help="DynamoDB table name, e.g. Books",
    )
    parser.add_argument(
        "--region",
        required=False,
        help="AWS region, e.g. us-east-1 (optional if already configured)",
    )
    parser.add_argument("--endpoint-url", required=False,
                        help="DynamoDB endpoint, e.g. http://localhost:8001 for DynamoDB Local")

    args = parser.parse_args()
    load_books(args.file, args.table, args.region, args.endpoint_url)


if __name__ == "__main__":
    main()