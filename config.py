"""
Configuration for the management citation homophily study.
"""

from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
FIGURES_DIR = PROJECT_ROOT / "figures"

for d in [RAW_DIR, PROCESSED_DIR, FIGURES_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── Time window ──────────────────────────────────────────────────────────────
YEAR_START = 2005
YEAR_END = 2025

# ── OpenAlex settings ────────────────────────────────────────────────────────
OPENALEX_EMAIL = "ignacio.chechile@gmail.com"
OPENALEX_PER_PAGE = 200
OPENALEX_MAX_RESULTS = None  # None = all results

# ── Top management journals (FT50 management subset + ABS 4* management) ────
# Format: (short_name, full_name, ISSN(s))
# ISSNs used for OpenAlex source lookup
JOURNALS = [
    # --- FT50 / ABS 4* core management ---
    ("AMJ",   "Academy of Management Journal",        ["0001-4273", "1948-0989"]),
    ("AMR",   "Academy of Management Review",         ["0363-7425", "1930-3807"]),
    ("ASQ",   "Administrative Science Quarterly",     ["0001-8392", "1930-3815"]),
    ("SMJ",   "Strategic Management Journal",         ["0143-2095", "1097-0266"]),
    ("OrgSci","Organization Science",                 ["1047-7039", "1526-5455"]),
    ("JOM",   "Journal of Management",                ["0149-2063", "1557-1211"]),
    ("JMS",   "Journal of Management Studies",        ["0022-2380", "1467-6486"]),
    ("MgmtSci","Management Science",                  ["0025-1909", "1526-5501"]),
    ("JIBS",  "Journal of International Business Studies", ["0047-2506", "1478-6990"]),
    ("JOB",   "Journal of Organizational Behavior",   ["0894-3796", "1099-1379"]),
    ("LQ",    "The Leadership Quarterly",             ["1048-9843"]),
    ("OrgStud","Organization Studies",                ["0170-8406", "1741-3044"]),
    ("JBV",   "Journal of Business Venturing",        ["0883-9026"]),
    ("ETP",   "Entrepreneurship Theory and Practice", ["1042-2587", "1540-6520"]),
    ("HRM",   "Human Resource Management",            ["0090-4848", "1099-050X"]),
    ("JOpsM", "Journal of Operations Management",     ["0272-6963", "1873-1317"]),
    ("ResPol","Research Policy",                      ["0048-7333"]),
    ("AMLE",  "Academy of Management Learning & Education", ["1537-260X"]),
    ("AMP",   "Academy of Management Perspectives",   ["1558-9080"]),
]

# ── Practitioner outlets (Layer 2) ───────────────────────────────────────────
PRACTITIONER_OUTLETS = [
    ("HBR",   "Harvard Business Review",       "https://hbr.org"),
    ("MITSMR","MIT Sloan Management Review",    "https://sloanreview.mit.edu"),
]

# ── Elite institution tiers (for homophily analysis) ────────────────────────
# Based on FT Global MBA ranking + research output reputation
# Tier 1 = top ~15 schools historically dominating management research
INSTITUTION_TIERS = {
    1: [
        "Harvard Business School", "Harvard University",
        "Wharton", "University of Pennsylvania",
        "Stanford Graduate School of Business", "Stanford University",
        "MIT Sloan", "Massachusetts Institute of Technology",
        "London Business School",
        "Columbia Business School", "Columbia University",
        "Kellogg", "Northwestern University",
        "Booth", "University of Chicago",
        "INSEAD",
        "NYU Stern", "New York University",
        "Ross", "University of Michigan",
        "Tuck", "Dartmouth College",
        "Yale School of Management", "Yale University",
        "Haas", "University of California, Berkeley",
        "Duke", "Fuqua", "Duke University",
    ],
    2: [
        "University of Toronto", "Rotman",
        "University of Virginia", "Darden",
        "Cornell University", "Johnson",
        "University of Cambridge", "Judge",
        "University of Oxford", "Said",
        "UCLA", "Anderson", "University of California, Los Angeles",
        "University of Minnesota",
        "University of Texas at Austin", "McCombs",
        "Georgia Institute of Technology",
        "University of Maryland",
        "University of Washington",
        "Erasmus University Rotterdam",
        "IE Business School",
        "IMD",
        "University of British Columbia",
        "Penn State", "Pennsylvania State University",
        "University of Illinois",
        "University of North Carolina",
        "Boston University",
        "Texas A&M University",
    ],
    # Tier 3 = everything else (assigned dynamically)
}

# Flatten for lookup
TIER_LOOKUP = {}
for tier, names in INSTITUTION_TIERS.items():
    for name in names:
        TIER_LOOKUP[name.lower()] = tier
