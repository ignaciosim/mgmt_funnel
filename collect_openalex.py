"""
Layer 1: Collect academic publication + citation data from OpenAlex.

Pulls all articles from the configured management journals (2005-2025),
extracts authors, institutions, and citation edges.

Usage:
    python collect_openalex.py              # full collection
    python collect_openalex.py --test       # small sample for testing
"""

import argparse
import json
import time
from pathlib import Path

import pandas as pd
import requests
from tqdm import tqdm

from config import (
    JOURNALS, YEAR_START, YEAR_END,
    OPENALEX_EMAIL, OPENALEX_PER_PAGE,
    RAW_DIR, PROCESSED_DIR,
)

BASE_URL = "https://api.openalex.org"
SESSION = requests.Session()
if OPENALEX_EMAIL:
    SESSION.params = {"mailto": OPENALEX_EMAIL}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get(url, params=None, retries=3):
    """GET with retries and rate-limit backoff."""
    for attempt in range(retries):
        try:
            r = SESSION.get(url, params=params, timeout=30)
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", 5))
                print(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            if attempt == retries - 1:
                raise
            print(f"  Retry {attempt+1}/{retries} after error: {e}")
            time.sleep(2 ** attempt)


def resolve_journal_source_ids():
    """Map each journal's ISSNs to an OpenAlex source ID."""
    print("Resolving journal source IDs...")
    source_map = {}
    for short, full, issns in JOURNALS:
        for issn in issns:
            data = _get(f"{BASE_URL}/sources", params={"filter": f"issn:{issn}"})
            results = data.get("results", [])
            if results:
                src = results[0]
                source_map[short] = {
                    "id": src["id"],
                    "display_name": src["display_name"],
                    "issn": issn,
                }
                print(f"  {short}: {src['display_name']} ({src['id']})")
                break
        else:
            print(f"  WARNING: Could not resolve {short} ({full})")
    return source_map


def fetch_works_for_source(source_id, short_name, test_mode=False):
    """Fetch all works for a source within the time window via cursor pagination."""
    works = []
    params = {
        "filter": f"primary_location.source.id:{source_id},"
                  f"publication_year:{YEAR_START}-{YEAR_END},"
                  f"type:article",
        "select": "id,doi,title,publication_year,authorships,referenced_works,"
                  "cited_by_count,concepts,primary_location",
        "per_page": OPENALEX_PER_PAGE,
        "cursor": "*",
    }

    page = 0
    with tqdm(desc=f"  {short_name}", unit=" works") as pbar:
        while True:
            data = _get(f"{BASE_URL}/works", params=params)
            batch = data.get("results", [])
            if not batch:
                break
            works.extend(batch)
            pbar.update(len(batch))

            if test_mode and len(works) >= 50:
                works = works[:50]
                break

            next_cursor = data["meta"].get("next_cursor")
            if not next_cursor:
                break
            params["cursor"] = next_cursor
            page += 1

    return works


# ── Extraction ───────────────────────────────────────────────────────────────

def extract_records(all_works, source_map):
    """
    From raw OpenAlex works, produce three DataFrames:
      - articles: one row per article
      - authorships: one row per (article, author) pair
      - citation_edges: one row per (citing_work, cited_work) pair
    """
    # Reverse lookup: source_id -> short_name
    sid_to_short = {v["id"]: k for k, v in source_map.items()}

    articles = []
    authorships = []
    citation_edges = []

    for w in tqdm(all_works, desc="Extracting records"):
        work_id = w["id"]
        # Determine journal
        loc = w.get("primary_location") or {}
        src = loc.get("source") or {}
        journal_short = sid_to_short.get(src.get("id"), "UNKNOWN")

        articles.append({
            "work_id": work_id,
            "doi": w.get("doi"),
            "title": w.get("title"),
            "year": w.get("publication_year"),
            "journal": journal_short,
            "cited_by_count": w.get("cited_by_count", 0),
        })

        # Authorships
        for auth in (w.get("authorships") or []):
            author = auth.get("author") or {}
            # Get institution(s)
            institutions = auth.get("institutions") or []
            inst_names = [i.get("display_name", "") for i in institutions]
            inst_ids = [i.get("id", "") for i in institutions]
            inst_rors = [i.get("ror", "") for i in institutions]

            authorships.append({
                "work_id": work_id,
                "author_id": author.get("id"),
                "author_name": author.get("display_name"),
                "author_position": auth.get("author_position"),
                "institution_names": "|".join(inst_names),
                "institution_ids": "|".join(inst_ids),
                "institution_rors": "|".join(str(r) for r in inst_rors if r),
            })

        # Citation edges
        for ref_id in (w.get("referenced_works") or []):
            citation_edges.append({
                "citing_work": work_id,
                "cited_work": ref_id,
            })

    df_articles = pd.DataFrame(articles)
    df_authorships = pd.DataFrame(authorships)
    df_edges = pd.DataFrame(citation_edges)

    return df_articles, df_authorships, df_edges


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="Fetch small sample only")
    args = parser.parse_args()

    # Step 1: Resolve journals
    source_map = resolve_journal_source_ids()
    with open(RAW_DIR / "source_map.json", "w") as f:
        json.dump(source_map, f, indent=2)
    print(f"\nResolved {len(source_map)}/{len(JOURNALS)} journals\n")

    # Step 2: Fetch works
    all_works = []
    for short, info in source_map.items():
        print(f"Fetching {short}...")
        works = fetch_works_for_source(info["id"], short, test_mode=args.test)
        all_works.extend(works)
        print(f"  -> {len(works)} works\n")

    # Save raw
    with open(RAW_DIR / "works_raw.json", "w") as f:
        json.dump(all_works, f)
    print(f"Total raw works: {len(all_works)}")

    # Step 3: Extract structured data
    df_articles, df_authorships, df_edges = extract_records(all_works, source_map)

    df_articles.to_parquet(PROCESSED_DIR / "articles.parquet", index=False)
    df_authorships.to_parquet(PROCESSED_DIR / "authorships.parquet", index=False)
    df_edges.to_parquet(PROCESSED_DIR / "citation_edges.parquet", index=False)

    print(f"\nSaved to {PROCESSED_DIR}/:")
    print(f"  articles:       {len(df_articles):,} rows")
    print(f"  authorships:    {len(df_authorships):,} rows")
    print(f"  citation_edges: {len(df_edges):,} rows")

    # Quick stats
    print(f"\nArticles by journal:")
    print(df_articles.groupby("journal").size().sort_values(ascending=False).to_string())


if __name__ == "__main__":
    main()
