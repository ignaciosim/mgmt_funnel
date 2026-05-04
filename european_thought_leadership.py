"""
European Management Thought Leadership Landscape.

Maps the European equivalent of the US-dominated thought leadership
pipeline we identified: who are Europe's management thinkers, where
do they publish, and is there a distinct European pipeline or just
a branch of the American one?

Key questions:
  1. Who are Europe's management thought leaders?
  2. What are the European practitioner publications?
  3. Do European schools produce thought leaders independently
     or only through US-tier journals and HBR?
  4. How does the European consulting ecosystem relate?
"""

import json
import requests
import time
from pathlib import Path
from collections import Counter

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

SESSION = requests.Session()
SESSION.params = {"mailto": "ignacio.chechile@gmail.com"}


# ═══════════════════════════════════════════════════════════════════
# EUROPEAN MANAGEMENT PUBLICATIONS
# ═══════════════════════════════════════════════════════════════════

EUROPEAN_ACADEMIC_JOURNALS = [
    # (Short name, Full name, ISSN, HQ country, ABS ranking)
    ("OrgStud", "Organization Studies", "0170-8406", "GB/EU", "4*"),
    ("JMS", "Journal of Management Studies", "0022-2380", "GB", "4*"),
    ("BJM", "British Journal of Management", "1045-3172", "GB", "4"),
    ("LRP", "Long Range Planning", "0024-6301", "GB", "3"),
    ("EMJ", "European Management Journal", "0263-2373", "GB/EU", "2"),
    ("EMR", "European Management Review", "1740-4754", "EU", "3"),
    ("SJM", "Scandinavian Journal of Management", "0956-5221", "Nordic", "2"),
    ("MIR", "Management International Review", "0938-8249", "DE", "3"),
    ("HumRel", "Human Relations", "0018-7267", "GB", "4*"),
    ("OS", "Organization", "1350-5084", "GB", "3"),
    ("EJIS", "European Journal of Information Systems", "0960-085X", "GB", "3"),
]

EUROPEAN_PRACTITIONER_OUTLETS = [
    # (Name, Type, HQ, URL, Reach, Notes)
    ("INSEAD Knowledge", "School publication", "FR", "knowledge.insead.edu",
     "Medium", "INSEAD's own thought leadership platform; articles by faculty"),
    ("LBS Review", "School publication", "GB", "lbsr.london.edu",
     "Medium", "London Business School's practitioner publication"),
    ("IMD Research & Knowledge", "School publication", "CH", "imd.org/research-knowledge",
     "Medium", "IMD's thought leadership; strong in executive education"),
    ("EFMD Global Focus", "Association magazine", "EU", "efmd.org",
     "Low-Medium", "EFMD's magazine for business school leaders"),
    ("The European Business Review", "Magazine", "GB", "europeanbusinessreview.com",
     "Low", "Independent European management magazine"),
    ("McKinsey Quarterly", "Consulting publication", "US/Global", "mckinsey.com/quarterly",
     "Very High", "Global — not European, but heavily read in Europe"),
    ("BCG Henderson Institute", "Consulting think tank", "US/Global", "bcg.com/henderson-institute",
     "High", "BCG's thought leadership arm"),
    ("Roland Berger Insights", "Consulting publication", "DE", "rolandberger.com",
     "Medium", "Largest European-origin strategy firm's publications"),
    ("Strategy+Business (PwC)", "Consulting magazine", "US/Global", "strategy-business.com",
     "High", "PwC/Strategy& publication"),
    ("Drucker Forum / Drucker Society", "Conference/Community", "AT", "druckerforum.org",
     "Medium", "Annual Vienna forum; European hub for management thinking"),
    ("Thinkers50", "Ranking/Community", "GB", "thinkers50.com",
     "High", "Biennial ranking of management thinkers; UK-based"),
]


# ═══════════════════════════════════════════════════════════════════
# EUROPEAN MANAGEMENT THOUGHT LEADERS
# ═══════════════════════════════════════════════════════════════════

EUROPEAN_THINKERS = [
    # (Name, Institution, Country, Domain, Key contribution,
    #  Books, HBR articles (est), Practitioner reach, Notes)

    # ── The established European pantheon ──
    ("Henry Mintzberg", "McGill University", "CA (European influence)",
     "Strategy/Organization", "Critique of strategic planning; managerial roles",
     ["The Rise and Fall of Strategic Planning", "Managers Not MBAs", "Strategy Safari"],
     5, "Very High", "Canadian but deeply influential in European management thinking"),

    ("Hermann Simon", "Simon-Kucher & Partners", "DE",
     "Pricing/Hidden Champions", "Hidden Champions concept; pricing strategy",
     ["Hidden Champions", "Confessions of the Pricing Man", "True Profit"],
     3, "High in Europe, moderate globally",
     "Founded Simon-Kucher (now $500M+ revenue); most cited German management author"),

    ("Yves Pigneur", "University of Lausanne", "CH",
     "Business Models", "Business Model Canvas (with Osterwalder)",
     ["Business Model Generation", "Value Proposition Design", "The Invincible Company"],
     2, "Very High", "Swiss academic; BMC is the most widely used business framework globally"),

    ("Alex Osterwalder", "Strategyzer", "CH",
     "Business Models", "Business Model Canvas; Strategyzer platform",
     ["Business Model Generation", "Value Proposition Design", "Testing Business Ideas"],
     3, "Very High", "Swiss; built a product company (Strategyzer) from academic framework"),

    ("Erin Meyer", "INSEAD", "FR",
     "Cross-cultural management", "The Culture Map framework",
     ["The Culture Map", "No Rules Rules (with Reed Hastings)"],
     5, "Very High", "American at INSEAD; The Culture Map became a standard reference"),

    ("Gary Hamel", "London Business School", "GB",
     "Strategy/Innovation", "Core competence (with Prahalad); management innovation",
     ["Competing for the Future", "The Future of Management", "Humanocracy"],
     20, "Very High", "American at LBS; one of the most published HBR authors ever"),

    ("Lynda Gratton", "London Business School", "GB",
     "Future of Work", "Hot Spots; The Shift; redesigning work",
     ["The Shift", "The 100-Year Life", "Redesigning Work"],
     8, "High", "British; World Economic Forum advisor"),

    ("Herminia Ibarra", "London Business School", "GB",
     "Leadership/Career", "Identity transition; acting into new roles",
     ["Act Like a Leader Think Like a Leader", "Working Identity"],
     12, "High", "Cuban-American at LBS; bridges US-European thinking"),

    ("Costas Markides", "London Business School", "GB",
     "Strategy/Innovation", "Strategic innovation; game-changing strategies",
     ["Game-Changing Strategies", "Fast Second", "All the Right Moves"],
     5, "Medium", "Cypriot-British; influential in European strategy teaching"),

    ("Fredmund Malik", "Malik Management", "CH",
     "Management systems", "Systems-oriented management; anti-MBA",
     ["Managing Performing Living", "Strategy for Managing Complex Systems"],
     0, "High in DACH region", "Austrian-Swiss; huge influence in German-speaking world; minimal in Anglo world"),

    ("Kjell Nordström", "Stockholm School of Economics", "SE",
     "Business/Society", "Funky business; provocative futurism",
     ["Funky Business", "Karaoke Capitalism"],
     0, "Medium", "Swedish provocateur; popular speaker but limited academic output"),

    ("Jonas Ridderstråle", "Stockholm School of Economics", "SE",
     "Business/Society", "Funky Business (with Nordström)",
     ["Funky Business", "Karaoke Capitalism", "Fast/Forward"],
     0, "Medium", "Swedish; speaking circuit; lighter academic footprint"),

    ("Sumantra Ghoshal", "London Business School", "GB (deceased)",
     "Strategy/Organization", "Transnational organization; purpose-driven firms",
     ["Managing Across Borders", "The Individualized Corporation", "A Bias for Action"],
     10, "High (historical)", "Indian-British at LBS; died 2004; hugely influential"),

    ("Charles Handy", "London Business School", "GB",
     "Organization/Philosophy", "Shamrock organization; portfolio careers",
     ["The Age of Unreason", "The Empty Raincoat", "The Second Curve"],
     3, "High (historical)", "Irish-British philosopher of management; BBC radio presenter"),

    ("Manfred Kets de Vries", "INSEAD", "FR",
     "Leadership/Psychology", "Psychodynamic approach to leadership",
     ["The Leadership Mystique", "Leaders on the Couch", "Riding the Leadership Rollercoaster"],
     5, "High in exec ed", "Dutch at INSEAD; founder of INSEAD leadership centre"),

    ("W. Chan Kim", "INSEAD", "FR",
     "Strategy", "Blue Ocean Strategy",
     ["Blue Ocean Strategy", "Blue Ocean Shift"],
     8, "Very High", "Korean at INSEAD; Blue Ocean is one of the top-selling strategy books ever"),

    ("Renée Mauborgne", "INSEAD", "FR",
     "Strategy", "Blue Ocean Strategy (with Kim)",
     ["Blue Ocean Strategy", "Blue Ocean Shift"],
     8, "Very High", "American at INSEAD; co-creator of Blue Ocean"),

    ("Julian Birkinshaw", "London Business School", "GB",
     "Innovation/Management", "Management innovation; ambidexterity",
     ["Reinventing Management", "Fast/Forward", "Becoming a Better Boss"],
     10, "Medium-High", "British-Canadian; prolific at LBS"),

    # ── The newer generation ──
    ("Nicolai Foss", "Copenhagen Business School", "DK",
     "Organization/Strategy", "Knowledge-based view; microfoundations",
     ["Strategy, Economic Organization and the Knowledge Economy"],
     2, "Low-Medium", "Danish; strong academic but limited practitioner crossover"),

    ("Freek Vermeulen", "London Business School", "GB",
     "Strategy", "Breaking Bad Habits; strategy practice critique",
     ["Breaking Bad Habits", "Business Exposed"],
     5, "Medium", "Dutch at LBS; contrarian/provocative style"),

    ("Phanish Puranam", "INSEAD", "FR",
     "Organization Design", "Microstructure of organizations",
     ["Corporate Strategy", "The Microstructure of Organizations"],
     2, "Low-Medium", "Indian at INSEAD; more academic than practitioner"),

    ("Gianpiero Petriglieri", "INSEAD", "FR",
     "Leadership/Identity", "Leadership development; identity workspaces",
     [],
     5, "Medium", "Italian at INSEAD; popular on LinkedIn/social media"),

    ("Amy Edmondson", "Harvard (but European influence)", "US→EU bridge",
     "Psychological Safety", "Psychological safety; teaming",
     ["The Fearless Organization", "Teaming", "The Right Kind of Wrong"],
     15, "Very High", "American but deeply connected to European executive education"),

    ("Ethan Mollick", "Wharton (but European influence)", "US→EU bridge",
     "AI/Innovation", "AI adoption in organizations; entrepreneurship",
     ["Co-Intelligence"],
     5, "Very High (recent)", "American but widely read in European tech/business circles"),
]


def resolve_openalex_ids():
    """Look up European thinkers in OpenAlex."""
    print("Resolving European thinkers in OpenAlex...")
    resolved = []

    for entry in EUROPEAN_THINKERS:
        name = entry[0]
        institution = entry[1]
        try:
            r = SESSION.get("https://api.openalex.org/authors",
                           params={"search": name, "per_page": 3}, timeout=15).json()
            results = r.get("results", [])

            best = results[0] if results else None
            for res in results:
                inst = (res.get("last_known_institution") or {}).get("display_name", "")
                if institution.lower()[:10] in inst.lower():
                    best = res
                    break

            if best:
                resolved.append({
                    "name": name,
                    "institution": institution,
                    "country": entry[2],
                    "domain": entry[3],
                    "openalex_name": best.get("display_name"),
                    "works_count": best.get("works_count", 0),
                    "cited_by_count": best.get("cited_by_count", 0),
                    "h_index": best.get("summary_stats", {}).get("h_index", 0),
                    "last_institution": (best.get("last_known_institution") or {}).get("display_name"),
                    "books": entry[5],
                    "hbr_articles_est": entry[6],
                    "practitioner_reach": entry[7],
                    "notes": entry[8],
                })
                print(f"  {name}: h={best.get('summary_stats', {}).get('h_index', '?')}, "
                      f"works={best.get('works_count', '?')}")

            time.sleep(0.3)
        except Exception as e:
            print(f"  {name}: error - {e}")

    return resolved


def analyze(thinkers):
    print(f"\n{'='*70}")
    print("EUROPEAN MANAGEMENT THOUGHT LEADERSHIP LANDSCAPE")
    print(f"{'='*70}")

    df = pd.DataFrame(thinkers)

    # By institution
    print(f"\nBy institution:")
    inst_counts = df["institution"].value_counts()
    for inst, n in inst_counts.items():
        avg_h = df[df["institution"] == inst]["h_index"].mean()
        print(f"  {inst:<35s} {n:>2d} thinkers  avg h={avg_h:.0f}")

    # By practitioner reach
    print(f"\nBy practitioner reach:")
    for reach in ["Very High", "High", "High in Europe, moderate globally",
                   "High in DACH region", "High (historical)", "Medium-High",
                   "Medium", "Low-Medium"]:
        sub = df[df["practitioner_reach"].str.contains(reach, na=False)]
        if len(sub) > 0:
            names = ", ".join(sub["name"].tolist())
            print(f"  {reach:<35s} {len(sub):>2d}  ({names})")

    # HBR presence — the US crossover
    print(f"\nHBR article count (estimated):")
    for _, r in df.sort_values("hbr_articles_est", ascending=False).head(10).iterrows():
        hbr = r["hbr_articles_est"]
        bar = "#" * hbr
        print(f"  {hbr:>3d} articles  {r['name']:<30s}  ({r['institution']}) {bar}")

    hbr_active = df[df["hbr_articles_est"] >= 5]
    hbr_none = df[df["hbr_articles_est"] == 0]
    print(f"\n  With 5+ HBR articles: {len(hbr_active)}/{len(df)} ({len(hbr_active)/len(df)*100:.0f}%)")
    print(f"  With 0 HBR articles:  {len(hbr_none)}/{len(df)} ({len(hbr_none)/len(df)*100:.0f}%)")

    # Academic impact vs practitioner reach
    print(f"\nAcademic impact (h-index) vs practitioner reach:")
    print(f"  {'Name':<30s} {'h-index':>8s} {'Works':>6s} {'HBR':>4s} {'Reach':<25s}")
    print("  " + "-" * 78)
    for _, r in df.sort_values("h_index", ascending=False).iterrows():
        print(f"  {r['name']:<30s} {r['h_index']:>8d} {r['works_count']:>6d} "
              f"{r['hbr_articles_est']:>4d} {r['practitioner_reach']:<25s}")

    # The key question: do Europeans reach practitioners through their own
    # channels or through US channels?
    print(f"\n{'='*70}")
    print("THE PIPELINE QUESTION: European channels vs US channels?")
    print(f"{'='*70}")

    print(f"""
  European thinkers who reach practitioners primarily through US channels:
    - Gary Hamel (LBS → HBR, 20+ articles)
    - Herminia Ibarra (LBS → HBR, 12+ articles)
    - W. Chan Kim/Mauborgne (INSEAD → HBR, 8+ articles each)
    - Julian Birkinshaw (LBS → HBR, 10+ articles)
    - Erin Meyer (INSEAD → HBR, 5+ articles)

  European thinkers with distinct European channels:
    - Hermann Simon (→ German-speaking market; own consulting firm)
    - Fredmund Malik (→ DACH region; own management system)
    - Kjell Nordström/Ridderstråle (→ Nordic speaking circuit)
    - Osterwalder/Pigneur (→ built Strategyzer platform; bypassed HBR)

  European thinkers who bridged both:
    - Henry Mintzberg (→ both HBR and independent European influence)
    - Manfred Kets de Vries (→ INSEAD exec ed + some HBR)
    - Charles Handy (→ BBC + books; distinctly British channel)

  THE FINDING:
    Most European management thought leaders who achieve global reach
    do so through the AMERICAN pipeline (HBR + US bestseller lists).
    LBS and INSEAD are the primary European launch pads, but the
    amplification mechanism is American.

    European-only channels (school publications, Roland Berger Insights,
    EFMD Global Focus, Drucker Forum) have limited reach compared to
    HBR. There is no European HBR equivalent.

    The exceptions — Simon, Malik, Osterwalder — succeeded by creating
    their OWN channels (consulting firms, platforms) rather than using
    either the US or European institutional pipeline.
    """)

    # The European practitioner outlet gap
    print(f"{'='*70}")
    print("THE EUROPEAN PRACTITIONER OUTLET GAP")
    print(f"{'='*70}")

    print(f"""
  US Practitioner Outlets:
    HBR:                    ~100 years old, global reach, 300K+ subscribers
    MIT Sloan Mgmt Review:  70+ years, strong in tech/operations
    McKinsey Quarterly:     60+ years (US firm, global reach)
    Strategy+Business:      25+ years (PwC/Strategy&)

  European Practitioner Outlets:
    INSEAD Knowledge:       School-specific, limited external reach
    LBS Review:             School-specific
    IMD Knowledge:          School-specific
    European Business Rev:  Niche, low circulation
    EFMD Global Focus:      Association magazine, inward-looking
    Roland Berger Insights: Consulting firm publication
    Drucker Forum:          Annual event, not continuous publication

  The gap is structural:
    - No European publication has HBR's combination of academic
      credibility AND mass practitioner readership
    - European school publications are marketing vehicles, not
      independent editorial outlets
    - The best European thinkers publish in HBR because there
      is no European alternative with comparable reach
    - This creates a dependency: European management ideas must
      pass through American editorial gatekeeping to reach
      global practitioners

  Possible explanations:
    1. Language fragmentation — no single European language market
       large enough to sustain an HBR equivalent
    2. Cultural difference — European business culture is less
       "thought leadership"-oriented than American
    3. Institutional structure — European business schools are
       younger and less resourced than HBS/Wharton/Stanford
    4. First-mover advantage — HBR (founded 1922) is a century old;
       European competitors would need to overcome network effects
    """)

    return df


def main():
    thinkers = resolve_openalex_ids()

    with open(DATA_DIR / "raw" / "european_thinkers.json", "w") as f:
        json.dump(thinkers, f, indent=2, default=str)

    df = analyze(thinkers)

    df.to_csv(DATA_DIR / "processed" / "european_thinkers.csv", index=False)
    print(f"\nSaved to {DATA_DIR}/")


if __name__ == "__main__":
    main()
