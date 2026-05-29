"""
Create the Books table (with TitlePrefixIndex / TitleLowerIndex) in DynamoDB Local
and load the 50K books JSONL into it, so the Amdahl harness can run with no real AWS.

Usage:
    docker compose up -d dynamodb
    python scripts/setup_local.py \
        --endpoint-url http://localhost:8001 \
        --file data-processing/books_english_top50k_with_ratings.jsonl
"""
import argparse
import boto3
from botocore.exceptions import ClientError

from load_books_to_dynamodb import load_books  # same scripts/ dir


def create_books_table(endpoint_url: str, region: str = "us-west-2"):
    ddb = boto3.client("dynamodb", endpoint_url=endpoint_url, region_name=region,
                       aws_access_key_id="local", aws_secret_access_key="local")
    try:
        ddb.create_table(
            TableName="Books",
            BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[
                {"AttributeName": "book_id", "AttributeType": "S"},
                {"AttributeName": "title_prefix", "AttributeType": "S"},
                {"AttributeName": "title_lower", "AttributeType": "S"},
            ],
            KeySchema=[{"AttributeName": "book_id", "KeyType": "HASH"}],
            GlobalSecondaryIndexes=[
                {"IndexName": "TitlePrefixIndex",
                 "KeySchema": [{"AttributeName": "title_prefix", "KeyType": "HASH"}],
                 "Projection": {"ProjectionType": "ALL"}},
                {"IndexName": "TitleLowerIndex",
                 "KeySchema": [{"AttributeName": "title_lower", "KeyType": "HASH"}],
                 "Projection": {"ProjectionType": "ALL"}},
            ],
        )
        ddb.get_waiter("table_exists").wait(TableName="Books")
        print("Created Books table in DynamoDB Local.")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceInUseException":
            print("Books table already exists, reusing.")
        else:
            raise


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--endpoint-url", default="http://localhost:8001")
    p.add_argument("--file", default="data-processing/books_english_top50k_with_ratings.jsonl")
    p.add_argument("--region", default="us-west-2")
    args = p.parse_args()
    create_books_table(args.endpoint_url, args.region)
    load_books(args.file, "Books", args.region, args.endpoint_url)


if __name__ == "__main__":
    main()
