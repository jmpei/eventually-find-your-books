# Book Recommendation System - Database Schema Design

**Version:** 1.0  
**Last Updated:** 2025-11-05  
**Author:** Jiaming(Theodore) Pei  

---

## Table of Contents
1. [Overview](#overview)
2. [Tables](#tables)
3. [Access Patterns](#access-patterns)
4. [Indexing Strategy](#indexing-strategy)
5. [Data Models](#data-models)
6. [Capacity Planning](#capacity-planning)
7. [Design Decisions](#design-decisions)
8. [Migration Plan](#migration-plan)

---


## 1. Overview

### Purpose
This document defines the DynamoDB schema for a book recommendation system 
supporting 50,000+ books with A-Z sharding capability.

### Technology
- **Database**: Amazon DynamoDB
- **Backend**: Python 3.11
- **Data Source**: Open Library API

---

## 2. Tables

### 2.1 Books Table

#### Table Configuration
```json
{
  "TableName": "Books",
  "BillingMode": "PAY_PER_REQUEST"
}
```

#### Primary Key
- **Partition Key**: `book_id` (String) - Format: `OL45883W`

#### Attributes

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| book_id | String | Yes | Unique book identifier (PK) |
| title | String | Yes | Book title |
| title_prefix | String | Yes | First letter (A-Z, 0) for sharding |
| title_lower | String | Yes | Lowercase title for search |
| authors | List<Map> | Yes | `[{author_id, author_name}]` |
| isbn_13 | List<String> | Yes | ISBN-13 identifiers |
| first_publish_year | Number | Optional | Publication year (nullable) |
| subjects | List<String> | Optional | Genre/topic tags |
| language | String | Yes | language: "en" |
| avg_rating | Number | Yes | Average rating (0.0-5.0), default: 0.0 |
| rating_count | Number | Yes | Total ratings, default: 0 |
| created_at | String | Yes | ISO 8601 timestamp |
| updated_at | String | Yes | ISO 8601 timestamp |



#### Sample Item (DynamoDB Format)
```json
{
  "book_id": {"S": "OL17713267W"},
  "title": {"S": "Deep Work"},
  "title_prefix": {"S": "D"},
  "title_lower": {"S": "deep work"},
  "authors": {"L": [{"M": {"author_id": {"S": "OL2853212A"}, "author_name": {"S": "Cal Newport"}}}]},
  "subjects": {"L": [{"S": "Productivity"}, {"S": "Cognition"}]},
  "language": {"S": "en"},
  "avg_rating": {"N": "3.79"},
  "rating_count": {"N": "166"},
  "created_at": {"S": "2025-11-07T00:00:00Z"},
  "updated_at": {"S": "2025-11-07T00:00:00Z"}
}
```

### 2.2 Ratings Table

#### Table Configuration
```json
{
  "TableName": "Ratings",
  "BillingMode": "PAY_PER_REQUEST"
}
```

#### Primary Key
- **Partition Key**: `user_id` (String, HASH)
- **Sort Key**: `book_id` (String, RANGE)

#### Attributes

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| user_id | String | Yes | User identifier (PK HASH) |
| book_id | String | Yes | Book identifier (PK RANGE) |
| rating | Number | Yes | Rating value |
| created_at | String | Yes | ISO 8601 timestamp |

#### Global Secondary Index

**BookRatingsIndex**
```json
{
  "IndexName": "BookRatingsIndex",
  "KeySchema": [
    {"AttributeName": "book_id", "KeyType": "HASH"}
  ],
  "Projection": {"ProjectionType": "ALL"}
}
```
**Purpose**: Query all ratings for a given book.

#### Additional Configuration
- PITR enabled; SSE enabled

---

### 2.3 UserProfiles Table

#### Table Configuration
```json
{
  "TableName": "UserProfiles",
  "BillingMode": "PAY_PER_REQUEST"
}
```

#### Primary Key
- **Partition Key**: `user_id` (String, HASH)

#### Attributes

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| user_id | String | Yes | User identifier (PK) |

#### Additional Configuration
- No GSI. Username/email indexes could be added later if needed.
- PITR enabled; SSE enabled

---

## 3. Indexing

### TitleLowerIndex (Global Secondary Index — Books table)

**Purpose**: Case-insensitive title search.
```json
{
  "IndexName": "TitleLowerIndex",
  "KeySchema": [
    {"AttributeName": "title_lower", "KeyType": "HASH"}
  ],
  "Projection": {"ProjectionType": "ALL"}
}
```

---

### TitlePrefixIndex (Global Secondary Index — Books table)

**Purpose**: Enable A-Z sharding for parallel processing.
```json
{
  "IndexName": "TitlePrefixIndex",
  "KeySchema": [
    {"AttributeName": "title_prefix", "KeyType": "HASH"}
  ],
  "Projection": {"ProjectionType": "ALL"}
}
```

**Usage**: 
```
Task 1: Query(title_prefix="A") → Books starting with A
Task 2: Query(title_prefix="B") → Books starting with B
...
Task 26: Query(title_prefix="Z") → Books starting with Z
```

---

### BookRatingsIndex (Global Secondary Index — Ratings table)

**Purpose**: Per-book rating lookups; query all ratings for a given book.
```json
{
  "IndexName": "BookRatingsIndex",
  "KeySchema": [
    {"AttributeName": "book_id", "KeyType": "HASH"}
  ],
  "Projection": {"ProjectionType": "ALL"}
}
```

---

## 4. Data Type Mappings

### JSON to DynamoDB

| JSON Type | DynamoDB Type | Example |
|-----------|---------------|---------|
| string | S (String) | `"title"` → `{"S": "The Great Gatsby"}` |
| number | N (Number) | `1925` → `{"N": "1925"}` |
| string[] | L (List) of S | `["Fiction"]` → `{"L": [{"S": "Fiction"}]}` |
| object[] | L (List) of M | `[{name:"..."}]` → `{"L": [{"M": {...}}]}` |
| null | omit or NULL | `null` → field not stored |

### Key Transformation
```
JSON key: "/works/OL45883W"
    ↓
DynamoDB book_id: "OL45883W"
```

---

## 5. Basic Access Patterns

| Operation | Description | Use Case |
|-----------|-------------|----------|
| GetItem | Get book by book_id | Display book details |
| Query (GSI) | Query by title_prefix | A-Z sharding (26 workers) |
| UpdateItem | Update avg_rating, rating_count | ratings ingestion |

---

## 6. Storage Estimate

### 6.1 Source Data
- **JSONL file**: ~18.5 MB (50,000 books)
- **Average per book**: ~370 bytes

### 6.2 DynamoDB Storage
- Base table: **32 MB**
- GSI: **32 MB**
- **Total: ~65 MB**

### 6.3 Cost Estimate
- Storage: $0.016/month (~1.6 cents)
- Read/Write: $2-5/month
- **Total: ~$5/month**

---

## 7. Key Design Decisions

### Why `title_prefix` field?
- Enables 26-way A-Z parallel processing (one ECS task per letter partition)
- Each task queries one letter partition
- Enables ~26× speedup for parallel searches

### Why both `title` and `title_lower`?
- Pre-compute lowercase for faster case-insensitive search
- Trade-off: +100MB storage vs. -50ms query latency

### Why `book_id` instead of full key?
- Storage: 17 bytes → 8 bytes (saves 450KB)
- Cleaner API responses

---

## References

- Open Library API: https://openlibrary.org/developers/api
- DynamoDB Best Practices: https://docs.aws.amazon.com/dynamodb/