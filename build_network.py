"""
Build the citation network and compute homophily metrics.

Reads the processed parquet files from Layer 1 and produces:
  - Author-level citation network (directed, weighted)
  - Institution tier assignments
  - Homophily / assortativity metrics
  - Summary tables for the article

Usage:
    python build_network.py
"""

import json
from collections import Counter, defaultdict

import networkx as nx
import numpy as np
import pandas as pd
from tqdm import tqdm

from config import PROCESSED_DIR, TIER_LOOKUP, FIGURES_DIR


def load_data():
    articles = pd.read_parquet(PROCESSED_DIR / "articles.parquet")
    authorships = pd.read_parquet(PROCESSED_DIR / "authorships.parquet")
    edges = pd.read_parquet(PROCESSED_DIR / "citation_edges.parquet")
    return articles, authorships, edges


def assign_institution_tiers(authorships):
    """Assign each author their 'best' institution tier (lowest number = highest tier)."""

    def _get_tier(inst_names_str):
        if not inst_names_str or pd.isna(inst_names_str):
            return 3
        for name in inst_names_str.split("|"):
            name_lower = name.strip().lower()
            for key, tier in TIER_LOOKUP.items():
                if key in name_lower or name_lower in key:
                    return tier
        return 3  # default: tier 3

    authorships["institution_tier"] = authorships["institution_names"].apply(_get_tier)

    # Author-level: take the best (lowest) tier across all their papers
    author_tiers = (
        authorships
        .groupby("author_id")["institution_tier"]
        .min()
        .reset_index()
        .rename(columns={"institution_tier": "best_tier"})
    )
    return author_tiers


def build_author_citation_network(articles, authorships, edges):
    """
    Build a directed graph where:
      - Nodes = authors
      - Edge (A -> B) = author A cited a paper by author B
      - Edge weight = number of times A cited B's papers
    """
    print("Building author citation network...")

    # Map work_id -> list of author_ids
    work_to_authors = (
        authorships
        .groupby("work_id")["author_id"]
        .apply(list)
        .to_dict()
    )

    # Only keep citation edges where both works are in our dataset
    our_works = set(articles["work_id"])
    internal_edges = edges[
        edges["citing_work"].isin(our_works) & edges["cited_work"].isin(our_works)
    ]
    print(f"  Internal citation edges: {len(internal_edges):,} / {len(edges):,} total")

    # Build author-to-author edges
    author_edges = Counter()
    for _, row in tqdm(internal_edges.iterrows(), total=len(internal_edges),
                       desc="  Building author edges"):
        citing_authors = work_to_authors.get(row["citing_work"], [])
        cited_authors = work_to_authors.get(row["cited_work"], [])
        for ca in citing_authors:
            for cb in cited_authors:
                if ca and cb and ca != cb:  # no self-citations
                    author_edges[(ca, cb)] += 1

    # Build NetworkX graph
    G = nx.DiGraph()
    for (a, b), weight in author_edges.items():
        G.add_edge(a, b, weight=weight)

    print(f"  Network: {G.number_of_nodes():,} authors, {G.number_of_edges():,} edges")
    return G


def compute_homophily_metrics(G, author_tiers):
    """Compute tier-based homophily metrics on the citation network."""
    print("\nComputing homophily metrics...")

    # Attach tier to nodes
    tier_map = dict(zip(author_tiers["author_id"], author_tiers["best_tier"]))
    nx.set_node_attributes(G, tier_map, "tier")

    # Fill missing tiers with 3
    for node in G.nodes():
        if "tier" not in G.nodes[node]:
            G.nodes[node]["tier"] = 3

    metrics = {}

    # 1. Assortativity coefficient by tier
    try:
        assort = nx.attribute_assortativity_coefficient(G, "tier")
        metrics["assortativity_by_tier"] = assort
        print(f"  Assortativity coefficient (tier): {assort:.4f}")
        print(f"    (>0 = homophily, 0 = random, <0 = heterophily)")
    except Exception as e:
        print(f"  Could not compute assortativity: {e}")

    # 2. Tier-to-tier citation matrix
    tier_matrix = defaultdict(lambda: defaultdict(int))
    for u, v, d in G.edges(data=True):
        t_from = G.nodes[u].get("tier", 3)
        t_to = G.nodes[v].get("tier", 3)
        tier_matrix[t_from][t_to] += d.get("weight", 1)

    tier_df = pd.DataFrame(tier_matrix).fillna(0).astype(int)
    tier_df = tier_df.reindex(index=[1, 2, 3], columns=[1, 2, 3], fill_value=0)
    tier_df.index.name = "citing_tier"
    tier_df.columns.name = "cited_tier"

    # Normalize rows to percentages
    tier_pct = tier_df.div(tier_df.sum(axis=1), axis=0) * 100
    metrics["tier_citation_matrix_raw"] = tier_df.to_dict()
    metrics["tier_citation_matrix_pct"] = tier_pct.round(1).to_dict()

    print(f"\n  Citation flow (% of tier's outgoing citations):")
    print(tier_pct.round(1).to_string())

    # 3. Gini coefficient of citation counts
    in_degrees = np.array([d for _, d in G.in_degree(weight="weight")])
    in_degrees = in_degrees[in_degrees > 0]
    if len(in_degrees) > 0:
        gini = _gini(in_degrees)
        metrics["citation_gini"] = gini
        print(f"\n  Gini coefficient of citations: {gini:.4f}")
        print(f"    (0 = perfect equality, 1 = one author gets all citations)")

    # 4. Concentration: what % of citations go to top 1%, 5%, 10% of authors?
    sorted_cites = np.sort(in_degrees)[::-1]
    total_cites = sorted_cites.sum()
    for pct in [1, 5, 10]:
        n = max(1, int(len(sorted_cites) * pct / 100))
        share = sorted_cites[:n].sum() / total_cites * 100
        metrics[f"top_{pct}pct_citation_share"] = share
        print(f"  Top {pct}% of authors receive {share:.1f}% of citations")

    # 5. Node count by tier
    tier_counts = Counter(nx.get_node_attributes(G, "tier").values())
    metrics["authors_by_tier"] = dict(tier_counts)
    print(f"\n  Authors by tier: {dict(sorted(tier_counts.items()))}")

    return metrics


def _gini(values):
    """Compute the Gini coefficient of a numpy array."""
    values = np.sort(values).astype(float)
    n = len(values)
    index = np.arange(1, n + 1)
    return (2 * np.sum(index * values) - (n + 1) * np.sum(values)) / (n * np.sum(values))


def find_gatekeepers(G, author_tiers, authorships, top_n=50):
    """Find the most influential authors (by weighted in-degree + betweenness)."""
    print(f"\nFinding top {top_n} gatekeepers...")

    # Weighted in-degree (= total citations received from within the network)
    in_deg = dict(G.in_degree(weight="weight"))

    # Author metadata lookup
    author_info = (
        authorships
        .drop_duplicates("author_id")
        .set_index("author_id")[["author_name", "institution_names"]]
        .to_dict("index")
    )

    tier_map = dict(zip(author_tiers["author_id"], author_tiers["best_tier"]))

    rows = []
    for author_id, citations in sorted(in_deg.items(), key=lambda x: -x[1])[:top_n]:
        info = author_info.get(author_id, {})
        rows.append({
            "author_id": author_id,
            "name": info.get("author_name", "Unknown"),
            "institution": (info.get("institution_names", "") or "").split("|")[0],
            "tier": tier_map.get(author_id, 3),
            "citations_in_network": citations,
            "out_citations": G.out_degree(author_id, weight="weight"),
        })

    df = pd.DataFrame(rows)
    print(df[["name", "institution", "tier", "citations_in_network"]].to_string(index=False))
    return df


def analyze_new_entrants(articles, authorships):
    """
    Analyze how often new authors break into top journals.
    A 'new entrant' = first-ever publication in our journal set.
    Key question: do they need a top-tier co-author to get in?
    """
    print("\nAnalyzing new entrants...")

    # For each author, find their first publication year in the dataset
    first_pub = (
        authorships
        .merge(articles[["work_id", "year"]], on="work_id")
        .groupby("author_id")["year"]
        .min()
        .reset_index()
        .rename(columns={"year": "first_year"})
    )

    # A paper is a "debut" if the author's first_year matches the paper's year
    debut_authorships = (
        authorships
        .merge(articles[["work_id", "year"]], on="work_id")
        .merge(first_pub, on="author_id")
    )
    debut_authorships["is_debut"] = debut_authorships["year"] == debut_authorships["first_year"]
    debuts = debut_authorships[debut_authorships["is_debut"]]

    # For each debut paper, check if there's a non-debut co-author from tier 1
    debut_works = set(debuts["work_id"])
    all_authorships_with_tier = authorships.copy()
    all_authorships_with_tier["inst_tier"] = all_authorships_with_tier["institution_names"].apply(
        lambda x: min(
            [TIER_LOOKUP.get(k, 3) for n in (x or "").split("|")
             for k in TIER_LOOKUP if k in n.lower()] or [3]
        )
    )

    debut_coauthor_stats = []
    for work_id in debut_works:
        paper_authors = all_authorships_with_tier[all_authorships_with_tier["work_id"] == work_id]
        debut_authors = debuts[debuts["work_id"] == work_id]
        non_debut = paper_authors[~paper_authors["author_id"].isin(debut_authors["author_id"])]

        has_senior_coauthor = len(non_debut) > 0
        has_tier1_coauthor = (non_debut["inst_tier"] == 1).any() if len(non_debut) > 0 else False
        debut_tier = debut_authors["institution_names"].apply(
            lambda x: min(
                [TIER_LOOKUP.get(k, 3) for n in (x or "").split("|")
                 for k in TIER_LOOKUP if k in n.lower()] or [3]
            )
        ).min()

        debut_coauthor_stats.append({
            "work_id": work_id,
            "has_senior_coauthor": has_senior_coauthor,
            "has_tier1_coauthor": has_tier1_coauthor,
            "debut_author_tier": debut_tier,
        })

    stats_df = pd.DataFrame(debut_coauthor_stats)
    total = len(stats_df)
    with_senior = stats_df["has_senior_coauthor"].sum()
    with_t1 = stats_df["has_tier1_coauthor"].sum()

    print(f"  Total debut papers: {total:,}")
    print(f"  With senior co-author: {with_senior:,} ({with_senior/total*100:.1f}%)")
    print(f"  With tier-1 co-author: {with_t1:,} ({with_t1/total*100:.1f}%)")

    # Solo debuts (no established co-author)
    solo = stats_df[~stats_df["has_senior_coauthor"]]
    print(f"  Solo debuts (no senior co-author): {len(solo):,} ({len(solo)/total*100:.1f}%)")

    return stats_df


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    from config import TIER_LOOKUP  # re-import for new_entrants closure

    articles, authorships, edges = load_data()
    print(f"Loaded: {len(articles):,} articles, {len(authorships):,} authorships, "
          f"{len(edges):,} citation edges\n")

    # Assign tiers
    author_tiers = assign_institution_tiers(authorships)
    print(f"Author tier distribution:")
    print(author_tiers["best_tier"].value_counts().sort_index().to_string())
    print()

    # Build network
    G = build_author_citation_network(articles, authorships, edges)

    # Homophily metrics
    metrics = compute_homophily_metrics(G, author_tiers)

    # Top gatekeepers
    gatekeepers = find_gatekeepers(G, author_tiers, authorships)
    gatekeepers.to_csv(PROCESSED_DIR / "top_gatekeepers.csv", index=False)

    # New entrant analysis
    entrant_stats = analyze_new_entrants(articles, authorships)
    entrant_stats.to_parquet(PROCESSED_DIR / "new_entrant_stats.parquet", index=False)

    # Save all metrics
    # Convert numpy types for JSON serialization
    clean_metrics = {}
    for k, v in metrics.items():
        if isinstance(v, (np.integer,)):
            clean_metrics[k] = int(v)
        elif isinstance(v, (np.floating,)):
            clean_metrics[k] = float(v)
        elif isinstance(v, dict):
            clean_metrics[k] = {
                str(k2): (float(v2) if isinstance(v2, (np.floating,)) else
                          int(v2) if isinstance(v2, (np.integer,)) else v2)
                for k2, v2 in v.items()
            }
        else:
            clean_metrics[k] = v

    with open(PROCESSED_DIR / "homophily_metrics.json", "w") as f:
        json.dump(clean_metrics, f, indent=2)

    # Save network
    nx.write_graphml(G, str(PROCESSED_DIR / "citation_network.graphml"))
    print(f"\nAll outputs saved to {PROCESSED_DIR}/")


if __name__ == "__main__":
    main()
