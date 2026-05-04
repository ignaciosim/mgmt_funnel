"""
Layer 2: Collect practitioner-facing thought leadership data.

Sources:
  - HBR: scrape article metadata (author, title, date, topic)
  - MIT Sloan Management Review: scrape article metadata
  - Google Scholar: top management author profiles (h-index, citations)

This layer enriches the academic data with "public intellectual" visibility.

Usage:
    python collect_practitioner.py --hbr          # scrape HBR
    python collect_practitioner.py --mitsmr        # scrape MIT SMR
    python collect_practitioner.py --scholars      # pull Google Scholar profiles
    python collect_practitioner.py --all           # everything
"""

import argparse
import csv
import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from config import RAW_DIR, PROCESSED_DIR

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (research project; academic citation study)"
})

# ── HBR ──────────────────────────────────────────────────────────────────────

def scrape_hbr(max_pages=100):
    """
    Scrape HBR article listing pages for metadata.
    HBR's /the-latest has paginated listings.
    """
    articles = []
    base = "https://hbr.org/the-latest"

    print("Scraping HBR...")
    for page in tqdm(range(1, max_pages + 1), desc="HBR pages"):
        url = f"{base}?page={page}" if page > 1 else base
        try:
            r = SESSION.get(url, timeout=15)
            if r.status_code != 200:
                print(f"  Stopped at page {page} (status {r.status_code})")
                break
            soup = BeautifulSoup(r.text, "lxml")

            # HBR uses <stream-item> custom elements with data attributes
            cards = soup.select("stream-item.stream-item")
            if not cards:
                # Fallback to broader selectors
                cards = soup.select("div.stream-item, article.hed-card")
            if not cards:
                cards = soup.find_all("a", href=re.compile(r"^/\d{4}/\d{2}/"))

            if not cards:
                print(f"  No articles found on page {page}, stopping.")
                break

            for card in cards:
                article = _parse_hbr_card(card)
                if article:
                    articles.append(article)

            time.sleep(1.5)  # polite crawling
        except Exception as e:
            print(f"  Error on page {page}: {e}")
            continue

    return articles


def _parse_hbr_card(card):
    """Extract metadata from an HBR article card element."""
    try:
        # Prefer data attributes on <stream-item> elements
        title = card.get("data-title")
        href = card.get("data-url", "")
        authors = card.get("data-authors", "")
        topic = card.get("data-topic", "")
        content_type = card.get("data-content-type", "")

        # Date from nested <time> element
        date_el = card.select_one("div.pubdate time") or card.find("time")
        date = date_el.get_text(strip=True) if date_el else ""

        # Fallback if no data attributes (non-stream-item card)
        if not title:
            link = card.find("a", href=True) if card.name != "a" else card
            if not link:
                return None
            href = link.get("href", "")
            title = link.get_text(strip=True)
            author_el = card.find(class_=re.compile(r"author|byline", re.I))
            authors = author_el.get_text(strip=True) if author_el else ""

        if not title or len(title) < 5:
            return None

        return {
            "source": "HBR",
            "title": title,
            "author": authors,
            "date": date,
            "topic": topic,
            "content_type": content_type,
            "url": f"https://hbr.org{href}" if href.startswith("/") else href,
        }
    except Exception:
        return None


# ── MIT Sloan Management Review ──────────────────────────────────────────────

def scrape_mitsmr(max_pages=50):
    """Scrape MIT Sloan Management Review article listings."""
    articles = []
    base = "https://sloanreview.mit.edu/article"

    print("Scraping MIT SMR...")
    for page in tqdm(range(1, max_pages + 1), desc="MIT SMR pages"):
        url = f"{base}/page/{page}/" if page > 1 else f"{base}/"
        try:
            r = SESSION.get(url, timeout=15)
            if r.status_code != 200:
                print(f"  Stopped at page {page} (status {r.status_code})")
                break
            soup = BeautifulSoup(r.text, "lxml")

            cards = soup.select("article, div.post-item, div.article-item")
            if not cards:
                cards = soup.find_all("h2")

            if not cards:
                print(f"  No articles found on page {page}, stopping.")
                break

            for card in cards:
                article = _parse_mitsmr_card(card)
                if article:
                    articles.append(article)

            time.sleep(1.5)
        except Exception as e:
            print(f"  Error on page {page}: {e}")
            continue

    return articles


def _parse_mitsmr_card(card):
    """Extract metadata from a MIT SMR article card."""
    try:
        link = card.find("a", href=True)
        if not link:
            return None

        title = link.get_text(strip=True)
        href = link.get("href", "")

        author_el = card.find(class_=re.compile(r"author|byline", re.I))
        author = author_el.get_text(strip=True) if author_el else ""

        date_el = card.find("time") or card.find(class_=re.compile(r"date", re.I))
        date = date_el.get_text(strip=True) if date_el else ""

        if not title or len(title) < 5:
            return None

        return {
            "source": "MIT_SMR",
            "title": title,
            "author": author,
            "date": date,
            "url": href,
        }
    except Exception:
        return None


# ── "Management Gods" curated list ──────────────────────────────────────────

# Top management thinkers who cross over to practitioner audiences.
# This list is used to anchor Layer 2 — we look up their academic profiles
# and their practitioner output to bridge the two worlds.
MANAGEMENT_THOUGHT_LEADERS = [
    # Name, known affiliation, OpenAlex author ID (if known, else None)
    ("Adam Grant", "Wharton", None),
    ("Amy Edmondson", "Harvard Business School", None),
    ("Clayton Christensen", "Harvard Business School", None),
    ("Michael Porter", "Harvard Business School", None),
    ("Henry Mintzberg", "McGill University", None),
    ("Gary Hamel", "London Business School", None),
    ("Roger Martin", "Rotman School of Management", None),
    ("Herminia Ibarra", "London Business School", None),
    ("Linda Hill", "Harvard Business School", None),
    ("Rosabeth Moss Kanter", "Harvard Business School", None),
    ("Rita McGrath", "Columbia Business School", None),
    ("Kathleen Eisenhardt", "Stanford University", None),
    ("Jeffrey Pfeffer", "Stanford University", None),
    ("Robert Kaplan", "Harvard Business School", None),
    ("David Teece", "UC Berkeley", None),
    ("C.K. Prahalad", "University of Michigan", None),
    ("Nitin Nohria", "Harvard Business School", None),
    ("Lynda Gratton", "London Business School", None),
    ("Tsedal Neeley", "Harvard Business School", None),
    ("Francesca Gino", "Harvard Business School", None),
    ("Ranjay Gulati", "Harvard Business School", None),
    ("Anita Elberse", "Harvard Business School", None),
    ("Andrew McAfee", "MIT Sloan", None),
    ("Erik Brynjolfsson", "Stanford University", None),
    ("Ethan Mollick", "Wharton", None),
    ("Zeynep Ton", "MIT Sloan", None),
    ("Amy Bernstein", "Harvard Business Review", None),
    ("Scott Galloway", "NYU Stern", None),
    ("Whitney Johnson", "Dartmouth", None),
    ("Marshall Goldsmith", "Independent", None),
]


def resolve_thought_leader_ids():
    """Look up OpenAlex author IDs for the curated thought leaders."""
    print("Resolving thought leader OpenAlex IDs...")
    resolved = []

    for name, affiliation, existing_id in tqdm(MANAGEMENT_THOUGHT_LEADERS):
        if existing_id:
            resolved.append({"name": name, "affiliation": affiliation, "openalex_id": existing_id})
            continue

        # Search OpenAlex for the author
        try:
            params = {"search": name, "per_page": 5}
            data = SESSION.get("https://api.openalex.org/authors", params=params, timeout=15).json()
            results = data.get("results", [])

            # Try to match by affiliation
            best = None
            for r in results:
                inst = r.get("last_known_institution") or {}
                inst_name = (inst.get("display_name") or "").lower()
                if affiliation.lower() in inst_name or inst_name in affiliation.lower():
                    best = r
                    break
            if not best and results:
                best = results[0]  # fallback: top result

            if best:
                resolved.append({
                    "name": name,
                    "affiliation": affiliation,
                    "openalex_id": best["id"],
                    "openalex_name": best.get("display_name"),
                    "works_count": best.get("works_count"),
                    "cited_by_count": best.get("cited_by_count"),
                    "h_index": best.get("summary_stats", {}).get("h_index"),
                    "last_institution": (best.get("last_known_institution") or {}).get("display_name"),
                })
                print(f"  {name} -> {best['display_name']} (h={best.get('summary_stats', {}).get('h_index')})")
            else:
                print(f"  WARNING: Could not find {name}")
                resolved.append({"name": name, "affiliation": affiliation, "openalex_id": None})

            time.sleep(0.3)
        except Exception as e:
            print(f"  Error looking up {name}: {e}")
            resolved.append({"name": name, "affiliation": affiliation, "openalex_id": None})

    return resolved


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hbr", action="store_true")
    parser.add_argument("--mitsmr", action="store_true")
    parser.add_argument("--scholars", action="store_true")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    if args.all:
        args.hbr = args.mitsmr = args.scholars = True

    if not any([args.hbr, args.mitsmr, args.scholars]):
        print("Specify --hbr, --mitsmr, --scholars, or --all")
        return

    if args.scholars:
        leaders = resolve_thought_leader_ids()
        out = RAW_DIR / "thought_leaders.json"
        with open(out, "w") as f:
            json.dump(leaders, f, indent=2)
        print(f"\nSaved {len(leaders)} thought leader profiles to {out}")

    if args.hbr:
        hbr_articles = scrape_hbr(max_pages=150)
        out = RAW_DIR / "hbr_articles.json"
        with open(out, "w") as f:
            json.dump(hbr_articles, f, indent=2)
        print(f"\nSaved {len(hbr_articles)} HBR articles to {out}")

    if args.mitsmr:
        mitsmr_articles = scrape_mitsmr(max_pages=80)
        out = RAW_DIR / "mitsmr_articles.json"
        with open(out, "w") as f:
            json.dump(mitsmr_articles, f, indent=2)
        print(f"\nSaved {len(mitsmr_articles)} MIT SMR articles to {out}")


if __name__ == "__main__":
    main()
