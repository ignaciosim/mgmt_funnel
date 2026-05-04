"""
Generate publication-ready visualizations for the article.

Usage:
    python visualize.py
"""

import json

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

import numpy as np
import pandas as pd
import seaborn as sns

from config import PROCESSED_DIR, FIGURES_DIR


def setup_style():
    """Set a clean, magazine-ready plot style."""
    plt.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "font.family": "sans-serif",
        "font.size": 12,
        "axes.titlesize": 14,
        "axes.labelsize": 12,
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
    })
    sns.set_palette("muted")


def plot_tier_heatmap(metrics):
    """Heatmap showing citation flow between tiers — base-rate adjusted."""
    pct = metrics["tier_citation_matrix_pct"]
    df_pct = pd.DataFrame(pct).astype(float)
    df_pct = df_pct.reindex(index=["1", "2", "3"], columns=["1", "2", "3"], fill_value=0)

    # Population shares (from author tier counts)
    authors_by_tier = metrics.get("authors_by_tier", {"1": 2926, "2": 3024, "3": 25972})
    total_authors = sum(int(v) for v in authors_by_tier.values())
    base_rates = {t: int(authors_by_tier[t]) / total_authors * 100 for t in ["1", "2", "3"]}

    # Compute multiplier: actual citation % / expected % (base rate)
    df_mult = df_pct.copy()
    for col in ["1", "2", "3"]:
        df_mult[col] = df_pct[col] / base_rates[col]

    # Two-panel figure: raw % and base-rate adjusted
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))

    # Left: raw percentages
    sns.heatmap(
        df_pct, annot=True, fmt=".1f", cmap="YlOrRd",
        cbar_kws={"label": "% of citing tier's references"},
        ax=ax1, vmin=0, vmax=100,
        xticklabels=["Tier 1\n(Elite)", "Tier 2\n(Strong)", "Tier 3\n(Other)"],
        yticklabels=["Tier 1\n(Elite)", "Tier 2\n(Strong)", "Tier 3\n(Other)"],
    )
    ax1.set_xlabel("Cited author's tier")
    ax1.set_ylabel("Citing author's tier")
    ax1.set_title("Raw citation flows (%)")

    # Add base rate annotation
    for i, col in enumerate(["1", "2", "3"]):
        ax1.text(i + 0.5, 3.35, f"base: {base_rates[col]:.0f}%",
                 ha="center", va="top", fontsize=9, alpha=0.6)

    # Right: base-rate adjusted multipliers
    # Custom annotation: show "2.8x" format
    annot_labels = df_mult.map(lambda x: f"{x:.1f}x")

    sns.heatmap(
        df_mult, annot=annot_labels, fmt="", cmap="RdYlGn_r",
        cbar_kws={"label": "multiplier vs expected (1.0x = random)"},
        ax=ax2, vmin=0.5, vmax=3.0, center=1.0,
        xticklabels=["Tier 1\n(Elite 7%)", "Tier 2\n(Strong 8%)", "Tier 3\n(Other 85%)"],
        yticklabels=["Tier 1\n(Elite)", "Tier 2\n(Strong)", "Tier 3\n(Other)"],
    )
    ax2.set_xlabel("Cited author's tier (with population share)")
    ax2.set_ylabel("Citing author's tier")
    ax2.set_title("Adjusted for base rates (1.0x = no bias)")

    fig.suptitle("Who cites whom? The prestige loop in management citations",
                 fontsize=14, fontweight="bold", y=1.02)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "tier_citation_heatmap.png")
    plt.close()
    print("  Saved tier_citation_heatmap.png")


def plot_lorenz_curve(metrics):
    """Lorenz curve showing citation inequality, built from gatekeepers + metrics."""
    # Use the full gatekeepers CSV (all authors with citations) if available,
    # otherwise reconstruct from the citation edges parquet
    edges = pd.read_parquet(PROCESSED_DIR / "citation_edges.parquet")
    articles = pd.read_parquet(PROCESSED_DIR / "articles.parquet")
    authorships = pd.read_parquet(PROCESSED_DIR / "authorships.parquet")

    # Only internal edges
    our_works = set(articles["work_id"])
    internal = edges[edges["citing_work"].isin(our_works) & edges["cited_work"].isin(our_works)]

    # Map cited_work -> authors, count incoming citations per author
    work_authors = authorships.groupby("work_id")["author_id"].apply(list).to_dict()
    from collections import Counter
    author_cites = Counter()
    for cited_work in internal["cited_work"]:
        for author in work_authors.get(cited_work, []):
            if author:
                author_cites[author] += 1

    in_deg = np.sort(np.array(list(author_cites.values())))
    cum_share = np.cumsum(in_deg) / in_deg.sum()
    pop_share = np.arange(1, len(in_deg) + 1) / len(in_deg)

    fig, ax = plt.subplots(figsize=(7, 6))
    ax.fill_between(pop_share, cum_share, pop_share, alpha=0.2, color="C3")
    ax.plot(pop_share, cum_share, "C3-", linewidth=2, label="Citation Lorenz curve")
    ax.plot([0, 1], [0, 1], "k--", linewidth=1, alpha=0.5, label="Perfect equality")

    # Mark key percentiles
    for pct_label, pct in [("Top 1%", 0.99), ("Top 5%", 0.95), ("Top 10%", 0.90)]:
        idx = int(pct * len(cum_share))
        share = 1 - cum_share[idx] if idx < len(cum_share) else 0
        ax.annotate(
            f"{pct_label}: {share*100:.0f}% of citations",
            xy=(1 - (1 - pct), cum_share[idx]),
            xytext=(0.15, cum_share[idx] + 0.05),
            fontsize=10,
            arrowprops=dict(arrowstyle="->", color="gray"),
        )

    ax.set_xlabel("Cumulative share of authors (ranked lowest to highest)")
    ax.set_ylabel("Cumulative share of citations received")
    ax.set_title("Citation inequality in management journals (2005-2025)")
    ax.legend(loc="upper left")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    fig.savefig(FIGURES_DIR / "lorenz_curve.png")
    plt.close()
    print("  Saved lorenz_curve.png")


def plot_gatekeeper_bar(top_n=25):
    """Bar chart of the most-cited authors in the network."""
    df = pd.read_csv(PROCESSED_DIR / "top_gatekeepers.csv").head(top_n)

    tier_colors = {1: "#d62728", 2: "#ff7f0e", 3: "#2ca02c"}
    colors = [tier_colors.get(t, "#999") for t in df["tier"]]

    fig, ax = plt.subplots(figsize=(10, 8))
    bars = ax.barh(
        range(len(df)), df["citations_in_network"],
        color=colors, edgecolor="white", linewidth=0.5,
    )
    ax.set_yticks(range(len(df)))
    ax.set_yticklabels(
        [f"{row['name']}  ({str(row['institution'] or '')[:30]})"
         for _, row in df.iterrows()],
        fontsize=9,
    )
    ax.invert_yaxis()
    ax.set_xlabel("Citations received within the network")
    ax.set_title(f"Top {top_n} most-cited management scholars (internal citations)")

    # Legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor="#d62728", label="Tier 1 (Elite)"),
        Patch(facecolor="#ff7f0e", label="Tier 2 (Strong)"),
        Patch(facecolor="#2ca02c", label="Tier 3 (Other)"),
    ]
    ax.legend(handles=legend_elements, loc="lower right")

    fig.savefig(FIGURES_DIR / "top_gatekeepers.png")
    plt.close()
    print("  Saved top_gatekeepers.png")


def plot_new_entrants_over_time():
    """Show how new entrant dynamics have changed over time."""
    articles = pd.read_parquet(PROCESSED_DIR / "articles.parquet")
    authorships = pd.read_parquet(PROCESSED_DIR / "authorships.parquet")

    # First pub year per author
    first_pub = (
        authorships.merge(articles[["work_id", "year"]], on="work_id")
        .groupby("author_id")["year"].min()
        .reset_index()
        .rename(columns={"year": "first_year"})
    )

    # Count unique authors per year vs new authors per year
    yearly = (
        authorships.merge(articles[["work_id", "year"]], on="work_id")
        .merge(first_pub, on="author_id")
    )
    yearly["is_new"] = yearly["year"] == yearly["first_year"]

    stats = yearly.groupby("year").agg(
        total_authors=("author_id", "nunique"),
        new_authors=("author_id", lambda x: yearly.loc[x.index, "is_new"].sum()),
    ).reset_index()
    stats["new_pct"] = stats["new_authors"] / stats["total_authors"] * 100

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    ax1.bar(stats["year"], stats["total_authors"], color="C0", alpha=0.7, label="Total")
    ax1.bar(stats["year"], stats["new_authors"], color="C3", alpha=0.7, label="New entrants")
    ax1.set_xlabel("Year")
    ax1.set_ylabel("Number of authors")
    ax1.set_title("Author counts by year")
    ax1.legend()

    ax2.plot(stats["year"], stats["new_pct"], "C3o-", linewidth=2)
    ax2.set_xlabel("Year")
    ax2.set_ylabel("% new authors")
    ax2.set_title("Share of first-time authors in top journals")
    ax2.yaxis.set_major_formatter(mtick.PercentFormatter())

    fig.suptitle("Breaking in: new entrants to top management journals", fontsize=14, y=1.02)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "new_entrants_trend.png")
    plt.close()
    print("  Saved new_entrants_trend.png")


def plot_institution_concentration():
    """Show how concentrated publications are by institution."""
    authorships = pd.read_parquet(PROCESSED_DIR / "authorships.parquet")

    # Count unique papers per institution (first listed), excluding unknown/empty
    authorships["primary_inst"] = authorships["institution_names"].apply(
        lambda x: (x or "").split("|")[0].strip() if x else ""
    )
    known = authorships[authorships["primary_inst"].str.len() > 0]
    inst_counts = known.groupby("primary_inst")["work_id"].nunique().sort_values(ascending=False)

    # Top 20
    top20 = inst_counts.head(20)

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(range(len(top20)), top20.values, color="C0", edgecolor="white")
    ax.set_yticks(range(len(top20)))
    ax.set_yticklabels(top20.index, fontsize=10)
    ax.invert_yaxis()
    ax.set_xlabel("Number of articles (unique)")
    ax.set_title("Top 20 institutions by article count in top management journals")

    # Annotate concentration
    total = inst_counts.sum()
    n_institutions = len(inst_counts)
    top20_share = top20.sum() / total * 100
    ax.text(
        0.95, 0.95,
        f"Top 20 of {n_institutions:,} institutions: {top20_share:.0f}% of all articles",
        transform=ax.transAxes, ha="right", va="top",
        fontsize=11, fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", alpha=0.8),
    )

    fig.savefig(FIGURES_DIR / "institution_concentration.png")
    plt.close()
    print("  Saved institution_concentration.png")


def plot_elite_pipeline():
    """
    Show how dramatically overrepresented elite institutions are
    among academics who cross over to practitioner outlets (HBR/MIT SMR).
    Uses 583 crossover authors — academics who publish in both top journals
    and HBR/MIT SMR — as the operationalized 'thought leader' definition.
    """
    from config import TIER_LOOKUP

    # --- Load data ---
    crossover = pd.read_parquet(PROCESSED_DIR / "crossover_authors.parquet")
    authorships = pd.read_parquet(PROCESSED_DIR / "authorships.parquet")

    def _get_tier(text):
        if not text:
            return 3
        t = text.lower()
        for key, tier in TIER_LOOKUP.items():
            if key in t or t in key:
                return tier
        return 3

    # Crossover author tiers (already computed, but recalc for safety)
    tl_counts = crossover["tier"].value_counts().to_dict()
    tl_total = len(crossover)

    # General population tiers
    uniq = authorships.drop_duplicates("author_id")
    uniq_tiers = uniq["institution_names"].apply(_get_tier)
    gen_counts = uniq_tiers.value_counts().to_dict()
    gen_total = len(uniq)

    # --- Figure: side-by-side + odds multiplier ---
    fig = plt.figure(figsize=(14, 6))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.2, 1], wspace=0.35)

    # Left panel: stacked comparison bars
    ax1 = fig.add_subplot(gs[0])
    tier_labels = ["Tier 1\n(Elite)", "Tier 2\n(Strong)", "Tier 3\n(Other)"]
    tier_colors = ["#d62728", "#ff7f0e", "#2ca02c"]

    tl_pcts = [tl_counts.get(t, 0) / tl_total * 100 for t in [1, 2, 3]]
    gen_pcts = [gen_counts.get(t, 0) / gen_total * 100 for t in [1, 2, 3]]

    x = np.arange(3)
    w = 0.35
    bars1 = ax1.bar(x - w/2, tl_pcts, w, color=tier_colors, edgecolor="white",
                    linewidth=1.5, label="Thought leaders")
    bars2 = ax1.bar(x + w/2, gen_pcts, w, color=tier_colors, edgecolor="white",
                    linewidth=1.5, alpha=0.35, label="All academics")

    # Add percentage labels on bars
    for bar, pct in zip(bars1, tl_pcts):
        if pct > 3:
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                     f"{pct:.0f}%", ha="center", va="bottom", fontweight="bold", fontsize=12)
    for bar, pct in zip(bars2, gen_pcts):
        if pct > 3:
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                     f"{pct:.0f}%", ha="center", va="bottom", fontsize=11, alpha=0.7)

    ax1.set_xticks(x)
    ax1.set_xticklabels(tier_labels, fontsize=12)
    ax1.set_ylabel("% of group", fontsize=12)
    ax1.set_title("Who crosses over to HBR / MIT SMR?\n(n=583 academics in both worlds)", fontsize=13, fontweight="bold")
    ax1.set_ylim(0, 100)

    # Custom legend
    from matplotlib.patches import Patch
    ax1.legend(handles=[
        Patch(facecolor="gray", alpha=1.0, label="HBR/MIT SMR crossover academics"),
        Patch(facecolor="gray", alpha=0.35, label="All management academics"),
    ], loc="upper right", fontsize=10)

    # Right panel: odds multiplier
    ax2 = fig.add_subplot(gs[1])

    multipliers = []
    for t in [1, 2, 3]:
        tl_rate = tl_counts.get(t, 0) / tl_total
        gen_rate = gen_counts.get(t, 0) / gen_total
        mult = tl_rate / gen_rate if gen_rate > 0 else 0
        multipliers.append(mult)

    bars = ax2.barh([2, 1, 0], multipliers, color=tier_colors, edgecolor="white", height=0.6)

    # Add multiplier labels
    for i, (bar, mult) in enumerate(zip(bars, multipliers)):
        label = f"{mult:.1f}x" if mult >= 0.1 else "<0.1x"
        ax2.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height()/2,
                 label, ha="left", va="center", fontweight="bold", fontsize=14)

    ax2.set_yticks([2, 1, 0])
    ax2.set_yticklabels(tier_labels, fontsize=12)
    ax2.set_xlabel("Likelihood multiplier vs base rate", fontsize=12)
    ax2.set_title("How much more likely to\ncross over to practitioner outlets?", fontsize=13, fontweight="bold")
    ax2.axvline(x=1, color="black", linestyle="--", alpha=0.3, linewidth=1)
    ax2.text(1, -0.55, "expected\nif random", ha="center", va="top", fontsize=9, alpha=0.5)
    ax2.set_xlim(0, max(multipliers) * 1.35)

    fig.savefig(FIGURES_DIR / "elite_pipeline.png")
    plt.close()
    print("  Saved elite_pipeline.png")


def plot_quality_controlled():
    """
    The cartelization chart: even at the SAME citation level,
    Tier 1 authors are ~4-5x more likely to cross over to HBR/MIT SMR.
    This controls for 'quality' and isolates the institutional advantage.
    """
    from config import TIER_LOOKUP

    articles = pd.read_parquet(PROCESSED_DIR / "articles.parquet")
    auth = pd.read_parquet(PROCESSED_DIR / "authorships.parquet")
    crossover = pd.read_parquet(PROCESSED_DIR / "crossover_authors.parquet")
    crossover_ids = set(crossover["author_id"])

    merged = auth.merge(articles[["work_id", "cited_by_count"]], on="work_id")
    author_stats = merged.groupby("author_id").agg(
        total_citations=("cited_by_count", "sum"),
    ).reset_index()

    name_inst = auth.drop_duplicates("author_id")[["author_id", "institution_names"]]
    author_stats = author_stats.merge(name_inst, on="author_id")

    def _get_tier(inst_str):
        if not inst_str or pd.isna(inst_str):
            return 3
        for name in inst_str.split("|"):
            nl = name.strip().lower()
            for key, tier in TIER_LOOKUP.items():
                if key in nl or nl in key:
                    return tier
        return 3

    author_stats["tier"] = author_stats["institution_names"].apply(_get_tier)
    author_stats["is_crossover"] = author_stats["author_id"].isin(crossover_ids)

    # Bin by citations
    bins = [0, 50, 200, 500, 1000, 2000, 100000]
    labels = ["0-50", "51-200", "201-500", "501-1K", "1K-2K", "2K+"]
    author_stats["citation_bin"] = pd.cut(
        author_stats["total_citations"], bins=bins, labels=labels
    )

    # Compute crossover rates
    tier_colors = {1: "#d62728", 2: "#ff7f0e", 3: "#2ca02c"}
    tier_labels_map = {1: "Tier 1 (Elite)", 2: "Tier 2 (Strong)", 3: "Tier 3 (Other)"}

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6), gridspec_kw={"width_ratios": [1.6, 1]})

    # Left: crossover rate by citation bin and tier
    x = np.arange(len(labels))
    width = 0.25

    for i, t in enumerate([1, 2, 3]):
        rates = []
        for bl in labels:
            sub = author_stats[(author_stats["citation_bin"] == bl) & (author_stats["tier"] == t)]
            rate = sub["is_crossover"].mean() * 100 if len(sub) > 10 else np.nan
            rates.append(rate)
        offset = (i - 1) * width
        bars = ax1.bar(x + offset, rates, width, color=tier_colors[t],
                       label=tier_labels_map[t], edgecolor="white", linewidth=0.8)
        # Add rate labels on the tallest bars
        for j, (bar, rate) in enumerate(zip(bars, rates)):
            if not np.isnan(rate) and rate > 3:
                ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                         f"{rate:.0f}%", ha="center", va="bottom", fontsize=8, fontweight="bold")

    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontsize=11)
    ax1.set_xlabel("Total citations in top journals (quality proxy)", fontsize=12)
    ax1.set_ylabel("% who also publish in HBR / MIT SMR", fontsize=12)
    ax1.set_title("Same quality, different access\nCrossover rate to practitioner outlets, by citation level",
                  fontsize=13, fontweight="bold")
    ax1.legend(fontsize=10)

    # Right: the T1/T3 ratio at each bin
    ratios = []
    for bl in labels:
        t1_sub = author_stats[(author_stats["citation_bin"] == bl) & (author_stats["tier"] == 1)]
        t3_sub = author_stats[(author_stats["citation_bin"] == bl) & (author_stats["tier"] == 3)]
        t1_rate = t1_sub["is_crossover"].mean() if len(t1_sub) > 10 else np.nan
        t3_rate = t3_sub["is_crossover"].mean() if len(t3_sub) > 10 else np.nan
        ratio = t1_rate / t3_rate if t3_rate and t3_rate > 0 else np.nan
        ratios.append(ratio)

    bars = ax2.bar(x, ratios, color="#d62728", alpha=0.8, edgecolor="white", width=0.5)
    for bar, ratio in zip(bars, ratios):
        if not np.isnan(ratio):
            ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                     f"{ratio:.1f}x", ha="center", va="bottom", fontsize=12, fontweight="bold")

    ax2.axhline(y=1, color="black", linestyle="--", alpha=0.3)
    ax2.text(len(labels) - 0.5, 1.15, "no advantage", ha="right", fontsize=9, alpha=0.5)
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, fontsize=11)
    ax2.set_xlabel("Total citations in top journals", fontsize=12)
    ax2.set_ylabel("Tier 1 / Tier 3 likelihood ratio", fontsize=12)
    ax2.set_title("The institutional advantage persists\nat every quality level",
                  fontsize=13, fontweight="bold")
    ax2.set_ylim(0, max(r for r in ratios if not np.isnan(r)) * 1.3)

    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "quality_controlled_crossover.png")
    plt.close()
    print("  Saved quality_controlled_crossover.png")


def plot_thought_leader_funnel():
    """
    The funnel chart: at each stage of the pipeline — academic publishing,
    practitioner crossover, bestselling book — the share from elite
    institutions increases, from 7% to 30% to 91%.
    """
    fig, ax = plt.subplots(figsize=(10, 7))

    # The data
    stages = [
        "All management\nacademics\n(n=35,194)",
        "Crossover to\nHBR / MIT SMR\n(n=583)",
        "Bestselling book\nauthor, academic\n(n=32)",
        "Full pipeline:\njournals + HBR + book\n(n=12)",
    ]
    elite_pcts = [7.2, 30, 91, 92]
    other_pcts = [100 - p for p in elite_pcts]
    n_stages = len(stages)
    y_positions = list(range(n_stages - 1, -1, -1))  # top to bottom

    # Draw funnel bars (full width = 100%, red portion = elite %)
    bar_height = 0.55
    # Widths narrow as we go down to create funnel effect
    max_width = 0.9
    widths = [max_width, max_width * 0.65, max_width * 0.35, max_width * 0.25]

    for i, (y, elite, other, w) in enumerate(zip(y_positions, elite_pcts, other_pcts, widths)):
        # Other (non-elite) portion
        left_start = 0.5 - w / 2
        other_w = w * (other / 100)
        elite_w = w * (elite / 100)

        ax.barh(y, other_w, height=bar_height, left=left_start,
                color="#cccccc", edgecolor="white", linewidth=1.5)
        ax.barh(y, elite_w, height=bar_height, left=left_start + other_w,
                color="#d62728", edgecolor="white", linewidth=1.5)

        # Label: percentage
        ax.text(0.5, y, f"{elite:.0f}%",
                ha="center", va="center", fontsize=18, fontweight="bold",
                color="white" if elite > 50 else "#d62728")

    # Stage labels on the left
    for i, (y, label) in enumerate(zip(y_positions, stages)):
        ax.text(0.5 - max_width / 2 - 0.02, y, label,
                ha="right", va="center", fontsize=11, linespacing=1.3)

    # Arrows between stages
    for i in range(n_stages - 1):
        ax.annotate("", xy=(0.5, y_positions[i + 1] + bar_height / 2 + 0.05),
                    xytext=(0.5, y_positions[i] - bar_height / 2 - 0.05),
                    arrowprops=dict(arrowstyle="->", color="gray", lw=1.5))

    # Legend
    from matplotlib.patches import Patch
    ax.legend(handles=[
        Patch(facecolor="#d62728", label="Tier 1 (Elite ~15 schools)"),
        Patch(facecolor="#cccccc", label="Everyone else"),
    ], loc="lower right", fontsize=11, framealpha=0.9)

    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.7, n_stages - 0.3)
    ax.set_title("The Making of a Thought Leader\nShare from elite institutions at each pipeline stage",
                 fontsize=15, fontweight="bold", pad=15)
    ax.axis("off")

    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "thought_leader_funnel.png")
    plt.close()
    print("  Saved thought_leader_funnel.png")


# Need RAW_DIR for the new function
from config import RAW_DIR


def main():
    setup_style()
    print("Generating figures...\n")

    # Load metrics
    with open(PROCESSED_DIR / "homophily_metrics.json") as f:
        metrics = json.load(f)

    plot_tier_heatmap(metrics)
    plot_lorenz_curve(metrics)
    plot_gatekeeper_bar()
    plot_new_entrants_over_time()
    plot_institution_concentration()
    plot_elite_pipeline()
    plot_quality_controlled()
    plot_thought_leader_funnel()

    print(f"\nAll figures saved to {FIGURES_DIR}/")


if __name__ == "__main__":
    main()
