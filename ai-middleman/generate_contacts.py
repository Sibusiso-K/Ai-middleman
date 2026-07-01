#!/usr/bin/env python3
"""Generate a reproducible simulated Alex DB of 50,000 professional contacts."""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from faker import Faker

SEED = 42
NUM_CONTACTS = 50_000
SAMPLE_SIZE = 200

COLUMNS = [
    "contact_id",
    "full_name",
    "phone",
    "email",
    "company",
    "title",
    "sector",
    "specialty",
    "location",
    "seniority",
    "expertise_tags",
    "can_help_with",
    "looking_for",
    "relationship_strength",
    "how_alex_knows_them",
    "is_vip",
    "last_contacted",
    "intros_made",
    "deals_closed",
    "preferred_contact_channel",
    "do_not_intro_to",
    "last_verified",
    "comment",
]

SECTOR_WEIGHTS = [
    ("Finance", 35),
    ("Tech", 20),
    ("Legal/Professional Services", 12),
    ("Real Estate", 10),
    ("Energy", 8),
    ("Healthcare", 8),
    ("Recruiting/Other", 7),
]

LOCATIONS = [
    ("New York, USA", "+1"),
    ("London, UK", "+44"),
    ("San Francisco, USA", "+1"),
    ("Singapore", "+65"),
    ("Dubai, UAE", "+971"),
    ("Frankfurt, Germany", "+49"),
    ("Hong Kong", "+852"),
    ("Boston, USA", "+1"),
    ("Chicago, USA", "+1"),
    ("Paris, France", "+33"),
    ("Zurich, Switzerland", "+41"),
    ("Toronto, Canada", "+1"),
    ("Sydney, Australia", "+61"),
    ("Mumbai, India", "+91"),
    ("São Paulo, Brazil", "+55"),
    ("Los Angeles, USA", "+1"),
    ("Amsterdam, Netherlands", "+31"),
    ("Tel Aviv, Israel", "+972"),
    ("Shanghai, China", "+86"),
    ("Geneva, Switzerland", "+41"),
]

HOW_ALEX_KNOWS = [
    "Met at {event} in {year}.",
    "Introduced by {mutual} after a {context} conversation.",
    "Alex placed him with {company} years ago; stayed in touch.",
    "Mutual friend {mutual} connected them at a dinner.",
    "They co-invested on a {deal_type} deal in {year}.",
    "Alex intro'd them to {target}; reciprocated later.",
    "Conference hallway chat at {event}; exchanged cards.",
    "LinkedIn connection Alex nurtured into a real relationship.",
    "Warm referral from {mutual} when Alex needed {need}.",
    "Same ski trip / charity board; occasional deal flow.",
]

EVENTS = [
    "SuperReturn",
    "Money2020",
    "Slush",
    "WEF Davos side event",
    "City AM awards",
    "a family office roundtable",
    "a LP/GP dinner",
    "a fintech founders breakfast",
]

MUTUALS = [
    "Sarah Chen",
    "Marcus Webb",
    "Elena Kowalski",
    "David Okonkwo",
    "James Whitmore",
    "Anita Desai",
]

CONTEXTS = ["credit", "real estate", "growth equity", "legal", "recruiting"]
DEAL_TYPES = ["unitranche", "Series B", "real estate JV", "M&A", "growth credit"]
NEEDS = ["a CFO search", "debt financing", "legal counsel", "LP intros"]
TARGETS = ["a sovereign fund", "a growth fund", "a corporate buyer", "a co-GP"]

CHANNELS = ["WhatsApp", "Email", "Phone", "LinkedIn"]
CHANNEL_WEIGHTS = [55, 25, 10, 10]

REL_STRENGTH_WEIGHTS = [8, 28, 38, 18, 8]

SECTOR_BANKS: dict[str, dict] = {
    "Finance": {
        "companies": [
            "JP Morgan", "Goldman Sachs", "Blackstone Credit", "Apollo Global",
            "KKR Credit", "Ares Management", "Barclays", "Deutsche Bank",
            "Northbridge Ventures", "Summit Peak Capital", "Meridian Growth Partners",
            "Crescent Debt Partners", "Harrington Capital", "Oakline Private Credit",
            "BlueRiver Asset Management", "Sterling Bridge Finance",
        ],
        "roles": [
            ("VP Leveraged Finance", "Credit Finance", "VP", "leveraged finance origination for mid-cap sponsors"),
            ("Director Structured Credit", "Structured Credit", "Director", "structured credit and CLO equity"),
            ("Partner", "Series A VC", "Partner", "early-stage B2B venture investing"),
            ("Managing Director", "Private Equity", "MD", "lower-mid buyouts in business services"),
            ("Principal", "Growth Equity", "Principal", "minority growth rounds in software"),
            ("Associate", "Investment Banking", "Associate", "M&A advisory for financial sponsors"),
            ("Head of Credit", "Direct Lending", "Director", "direct lending to upper mid-market borrowers"),
            ("Analyst", "Leveraged Finance", "Analyst", "credit analysis on sponsor-backed deals"),
        ],
        "expertise": [
            "unitranche", "TLBs", "direct lending", "Sponsor finance", "CLO equity",
            "distressed debt", "revenue-based finance", "LP relations", "credit memos",
            "family office capital", "secondaries", "growth equity", "Series A",
        ],
        "can_help": [
            "debt financing", "credit memos", "sponsor intros", "LP allocations",
            "co-invest opportunities", "bank referrals", "term sheet feedback",
            "family office warm intros", "portfolio company CFO searches",
        ],
        "looking_for": [
            "family office capital", "quality deal flow", "co-GP relationships",
            "downstream portfolio intros", "warm LP referrals", "sponsor relationships",
            "credit opportunities $50-300M", "revenue-stage SaaS deals",
        ],
        "deal_sizes": ["$50-300M", "$20-100M", "$2-8M", "$100-500M", "£2-8M", "$5-25M"],
    },
    "Tech": {
        "companies": [
            "Stripe", "Revolut", "Palantir", "Databricks", "Notion",
            "Stealth (ex-Revolut)", "Stealth (ex-Stripe)", "Cloudline AI",
            "Nexus Payments", "Vector Security", "Horizon Robotics", "Lattice Data",
            "Forge Analytics", "Pulse Health Tech", "Arc Platform",
        ],
        "roles": [
            ("Founder", "Payments", "Founder", "building in payments and fintech infrastructure"),
            ("CEO", "B2B SaaS", "Founder", "scaling enterprise SaaS globally"),
            ("VP Engineering", "Infrastructure", "VP", "platform and infra at high-growth startups"),
            ("Head of Product", "AI/ML", "Director", "AI product strategy and GTM"),
            ("CTO", "Cybersecurity", "Founder", "security tooling for regulated industries"),
            ("Chief Revenue Officer", "Enterprise Software", "VP", "enterprise sales motion"),
            ("General Partner", "Deep Tech VC", "Partner", "deep tech and infrastructure investing"),
            ("Operating Partner", "Venture Studio", "Partner", "hands-on scaling for portfolio cos"),
        ],
        "expertise": [
            "payments", "B2B SaaS", "AI infrastructure", "PLG", "enterprise sales",
            "API platforms", "data pipelines", "security", "marketplace dynamics",
            "international expansion", "product-led growth", "DevOps",
        ],
        "can_help": [
            "technical diligence", "hiring engineers", "customer intros",
            "GTM advice", "vendor negotiations", "design partners",
            "regulatory navigation", "fundraising intros",
        ],
        "looking_for": [
            "design partners", "Series A lead", "enterprise pilots",
            "technical co-founders", "US expansion partners", "strategic acquirers",
            "talent for key hires", "channel partnerships",
        ],
        "deal_sizes": ["seed checks", "Series A", "Series B", "strategic partnerships"],
    },
    "Legal/Professional Services": {
        "companies": [
            "Clifford Chance", "Linklaters", "Kirkland & Ellis", "Latham & Watkins",
            "Freshfields", "Allen & Overy", "Slaughter and May", "White & Case",
            "McKinsey & Company", "Bain & Company", "BCG", "Deloitte",
            "PwC Deals", "EY Parthenon", "A&O Shearman",
        ],
        "roles": [
            ("Counsel", "M&A Law", "Counsel", "cross-border M&A and private equity transactions"),
            ("Partner", "Funds Law", "Partner", "fund formation and regulatory work for GPs"),
            ("Managing Partner", "Corporate Law", "Partner", "large-cap corporate and governance"),
            ("Principal", "Strategy Consulting", "Principal", "corporate strategy for PE portfolio cos"),
            ("Director", "Transaction Services", "Director", "financial due diligence on deals"),
            ("Associate", "Capital Markets", "Associate", "equity and debt capital markets"),
            ("Of Counsel", "Regulatory", "Counsel", "financial services regulatory advice"),
        ],
        "expertise": [
            "M&A", "fund formation", "regulatory", "due diligence", "tax structuring",
            "employment law", "IP licensing", "competition law", "restructuring",
            "ESG compliance", "cross-border deals",
        ],
        "can_help": [
            "legal diligence", "term sheet review", "regulatory guidance",
            "vendor contracts", "employment issues", "fund docs",
            "board governance", "dispute resolution",
        ],
        "looking_for": [
            "mandates on live deals", "referrals from bankers", "portfolio company work",
            "cross-border matters", "repeat sponsor relationships", "panel appointments",
        ],
        "deal_sizes": ["$100M+ M&A", "fund launches", "mid-cap transactions", "regulatory filings"],
    },
    "Real Estate": {
        "companies": [
            "Harrington Capital", "Brookfield Properties", "Blackstone Real Estate",
            "Greystar", "Hines", "Savills Investment", "CBRE Capital Advisors",
            "Patrizia", "LaSalle Investment", "Oxford Properties", "Grosvenor",
            "Crown Estate Partners", "Meridian RE Partners",
        ],
        "roles": [
            ("Chairman", "Real Estate", "Chairman", "UK and European property portfolios"),
            ("Managing Director", "Real Estate PE", "MD", "value-add real estate private equity"),
            ("Partner", "Development", "Partner", "ground-up development and JV structures"),
            ("Head of Acquisitions", "Commercial Real Estate", "Director", "office and logistics acquisitions"),
            ("VP Investments", "Multifamily", "VP", "multifamily and residential platforms"),
            ("Director", "Hospitality", "Director", "hotel and leisure asset management"),
        ],
        "expertise": [
            "value-add RE", "logistics", "multifamily", "hospitality", "development",
            "sale-leaseback", "REITs", "JV structures", "asset management", "UK property",
        ],
        "can_help": [
            "off-market deals", "capital stack advice", "operator intros",
            "planning navigation", "co-invest equity", "broker relationships",
        ],
        "looking_for": [
            "off-market assets", "operating partners", "debt for acquisitions",
            "institutional co-investors", "distressed sellers", "development sites",
        ],
        "deal_sizes": ["£50-200M", "~£800M portfolios", "$100-400M", "£20-80M"],
    },
    "Energy": {
        "companies": [
            "Vitol", "Trafigura", "Orsted", "NextEra Energy", "Shell Ventures",
            "BP Energy Partners", "EnCap Investments", "Riverstone Holdings",
            "Generate Capital", "Lightsource bp", "Copenhagen Infrastructure Partners",
            "Macquarie Green Investment", "TotalEnergies Ventures",
        ],
        "roles": [
            ("Partner", "Energy PE", "Partner", "infrastructure and energy transition investing"),
            ("Director", "Renewables", "Director", "utility-scale solar and wind development"),
            ("VP", "Oil & Gas", "VP", "upstream and midstream transactions"),
            ("Head of Investments", "Infrastructure", "Director", "energy infrastructure assets"),
            ("Principal", "Climate Tech", "Principal", "climate tech and cleantech venture"),
            ("Managing Director", "Power & Utilities", "MD", "power generation and grid assets"),
        ],
        "expertise": [
            "renewables", "power markets", "midstream", "energy transition",
            "carbon credits", "battery storage", "grid infrastructure", "LNG",
            "project finance", "ESG reporting",
        ],
        "can_help": [
            "project finance", "offtake agreements", "regulatory permits",
            "EPC contractor intros", "tax equity partners", "utility relationships",
        ],
        "looking_for": [
            "development pipelines", "tax equity", "of-takers", "co-development partners",
            "distressed assets", "battery storage projects",
        ],
        "deal_sizes": ["$100-500M projects", "$20-80M venture", "multi-GW pipelines"],
    },
    "Healthcare": {
        "companies": [
            "Johnson & Johnson Innovation", "Roche Venture Fund", "General Catalyst Health",
            "OrbiMed", "Deerfield Management", "F-Prime Capital", "GV (Google Ventures)",
            "Sofinnova Partners", "New Enterprise Associates Health", "Flagship Pioneering",
            "Mayo Clinic Ventures", "Catalio Capital", "RA Capital",
        ],
        "roles": [
            ("Partner", "Healthcare VC", "Partner", "biotech and medtech venture investing"),
            ("Managing Director", "Pharma BD", "MD", "pharma business development and licensing"),
            ("Director", "Healthtech", "Director", "digital health and care delivery"),
            ("VP", "Life Sciences", "VP", "life sciences growth equity"),
            ("Principal", "Biotech", "Principal", "early clinical-stage biotech"),
            ("Head of Corporate Dev", "Medtech", "Director", "medtech M&A and partnerships"),
        ],
        "expertise": [
            "biotech", "medtech", "digital health", "clinical trials", "FDA pathways",
            "pharma BD", "healthcare services", "diagnostics", "AI in healthcare",
        ],
        "can_help": [
            "clinical KOL intros", "regulatory strategy", "pharma partnerships",
            "hospital system pilots", "CRO relationships", "reimbursement advice",
        ],
        "looking_for": [
            "Series B biotech", "strategic pharma partners", "clinical data partners",
            "health system pilots", "FDA consultants", "co-development deals",
        ],
        "deal_sizes": ["$5-30M Series A/B", "licensing deals", "strategic partnerships"],
    },
    "Recruiting/Other": {
        "companies": [
            "Heidrick & Struggles", "Russell Reynolds", "Egon Zehnder", "Odgers Berndtson",
            "True Search", "Daversa Partners", "Graphite", "Caldwell Partners",
            "Boyden", "Spencer Stuart", "Korn Ferry", "AlphaSights",
        ],
        "roles": [
            ("Partner", "Executive Search", "Partner", "C-suite and board placements"),
            ("Managing Director", "Finance Search", "MD", "PE and credit hiring"),
            ("Principal", "Tech Recruiting", "Principal", "VP+ engineering and product leaders"),
            ("Director", "Board Services", "Director", "non-exec and advisory board searches"),
            ("VP", "Operations Search", "VP", "COO and ops leadership placements"),
        ],
        "expertise": [
            "C-suite search", "board placement", "PE operating talent", "credit hiring",
            "engineering leadership", "comp benchmarking", "retained search",
        ],
        "can_help": [
            "CFO searches", "board candidates", "operating partners",
            "comp data", "back-channel references", "talent mapping",
        ],
        "looking_for": [
            "mandates from sponsors", "portfolio company roles", "repeat clients",
            "exclusive searches", "referrals from operators",
        ],
        "deal_sizes": ["retained searches", "board mandates", "PE portfolio roles"],
    },
}

COMPETITOR_BLOCKS = [
    "Competitor: {company}",
    "Conflict: same cap table as C{conflict_id}",
    "Do not intro to rival fund {company}",
    "Sensitive: litigation with {company}",
]

SPARSE_COMMENT_TEMPLATES = [
    "{name}, {company}, {title}: Building something in {area}. {extra}",
    "{name}, {company}, {title}: {extra}",
    "{name}, {company}, {title}: Early-stage; limited history with Alex.",
]

VIP_COMMENT_SUFFIX = " Only takes curated intros. Never auto-message."


def weighted_sector() -> str:
    sectors, weights = zip(*SECTOR_WEIGHTS)
    return random.choices(sectors, weights=weights, k=1)[0]


def pick_list_items(pool: list[str], min_n: int = 2, max_n: int = 5) -> str:
    n = random.randint(min_n, max_n)
    return "; ".join(random.sample(pool, k=min(n, len(pool))))


def slugify_email(local: str) -> str:
    keep = []
    for ch in local.lower():
        if ch.isalnum() or ch in "._":
            keep.append(ch)
    return "".join(keep)


def company_domain(company: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "" for ch in company)
    cleaned = cleaned.replace("ex", "").replace("stealth", "stealthco")
    if not cleaned:
        cleaned = "example"
    return f"{cleaned[:18]}.com"


def make_phone(country_code: str) -> str:
    cc = country_code.lstrip("+")
    if cc == "1":
        return f"+1{random.randint(200, 999)}{random.randint(200, 999)}{random.randint(1000, 9999)}"
    length = random.choice([9, 10, 11])
    digits = "".join(str(random.randint(0, 9)) for _ in range(length))
    return f"+{cc}{digits}"


def random_recent_date(max_days_ago: int = 1095, min_days_ago: int = 14) -> date:
    days = random.randint(min_days_ago, max_days_ago)
    return date.today() - timedelta(days=days)


def make_email(full_name: str, company: str, blank: bool) -> str:
    if blank:
        return ""
    parts = full_name.lower().split()
    first = slugify_email(parts[0]) if parts else "contact"
    last = slugify_email(parts[-1]) if len(parts) > 1 else "user"
    pattern = random.choice(
        [
            f"{first}.{last}",
            f"{first}{last}",
            f"{first[0]}{last}",
            f"{first}_{last}",
        ]
    )
    return f"{pattern}@{company_domain(company)}"


def relationship_metrics(strength: int, is_vip: bool, sparse: bool) -> tuple[int, int]:
    if sparse:
        return 0, 0
    if is_vip:
        intros = random.randint(8, 40)
        deals = random.randint(max(3, intros // 3), intros)
        return intros, deals
    caps = {1: (0, 1), 2: (0, 3), 3: (1, 8), 4: (3, 15), 5: (5, 25)}
    lo, hi = caps[strength]
    intros = random.randint(lo, hi)
    deals = random.randint(0, intros) if intros else 0
    return intros, deals


def build_comment(
    *,
    full_name: str,
    company: str,
    title: str,
    specialty: str,
    sector: str,
    role_blurb: str,
    sparse: bool,
    is_vip: bool,
    bank: dict,
) -> str:
    if sparse:
        area = specialty.split()[0] if specialty else sector.lower()
        extra = random.choice(
            [
                f"ex-{random.choice(['Revolut', 'Goldman', 'McKinsey', 'Google'])}.",
                "Prefers WhatsApp.",
                "Met Alex once at an event.",
                "",
            ]
        )
        tpl = random.choice(SPARSE_COMMENT_TEMPLATES)
        return tpl.format(name=full_name, company=company, title=title, area=area, extra=extra).strip()

    deal_size = random.choice(bank["deal_sizes"])
    can = random.choice(bank["can_help"])
    need = random.choice(bank["looking_for"])

    if sector == "Finance":
        body = (
            f"{full_name}, {company}, {title}, {specialty}: "
            f"{role_blurb.capitalize()}. Strong on {random.choice(bank['expertise'])} "
            f"for {deal_size} deals. Needs warm intros to {need}; reciprocates on {can}."
        )
    elif sector == "Tech":
        body = (
            f"{full_name}, {company}, {title}, {specialty}: "
            f"{role_blurb.capitalize()}. Focus on {random.choice(bank['expertise'])}. "
            f"Looking for {need}; can help with {can}."
        )
    elif sector == "Real Estate" and is_vip:
        body = (
            f"{full_name}, {company}, {title}, {specialty}: "
            f"Controls {deal_size} UK property.{VIP_COMMENT_SUFFIX}"
        )
        return body
    elif sector == "Legal/Professional Services":
        body = (
            f"{full_name}, {company}, {title}, {specialty}: "
            f"{role_blurb.capitalize()}. Trusted on {random.choice(bank['expertise'])} "
            f"for {deal_size}. Open to {need} via warm referral only."
        )
    else:
        body = (
            f"{full_name}, {company}, {title}, {specialty}: "
            f"{role_blurb.capitalize()}. Can assist with {can}; seeking {need}."
        )

    if is_vip and VIP_COMMENT_SUFFIX.strip() not in body:
        body = body.rstrip(".") + "." + VIP_COMMENT_SUFFIX
    return body


def generate_contact(contact_num: int, fake: Faker) -> dict:
    sector = weighted_sector()
    bank = SECTOR_BANKS[sector]
    role = random.choice(bank["roles"])
    title, specialty, seniority, role_blurb = role

    location, country_code = random.choice(LOCATIONS)
    company = random.choice(bank["companies"])

    sparse = random.random() < 0.125
    blank_email = sparse or random.random() < 0.03

    if sparse:
        rel_strength = random.choices([1, 2, 3], weights=[40, 45, 15], k=1)[0]
    else:
        rel_strength = random.choices(range(1, 6), weights=REL_STRENGTH_WEIGHTS, k=1)[0]

    high_seniority = seniority in {"Partner", "MD", "Chairman", "Founder", "Counsel"}
    vip_roll = random.random()
    is_vip = (high_seniority and vip_roll < 0.08) or (not sparse and vip_roll < 0.015)
    if is_vip:
        rel_strength = max(rel_strength, random.choice([4, 5]))

    full_name = fake.name()
    phone = make_phone(country_code)
    email = make_email(full_name, company, blank_email)

    expertise_tags = pick_list_items(bank["expertise"])
    can_help_with = pick_list_items(bank["can_help"])
    looking_for = pick_list_items(bank["looking_for"])

    how = random.choice(HOW_ALEX_KNOWS).format(
        event=random.choice(EVENTS),
        year=random.randint(2016, 2025),
        mutual=random.choice(MUTUALS),
        context=random.choice(CONTEXTS),
        company=random.choice(bank["companies"]),
        deal_type=random.choice(DEAL_TYPES),
        target=random.choice(TARGETS),
        need=random.choice(NEEDS),
    )

    last_contacted = random_recent_date(
        max_days_ago=1095 if not sparse else 1400,
        min_days_ago=30 if rel_strength >= 3 else 90,
    )
    verify_lag = random.randint(0, 120)
    last_verified = last_contacted - timedelta(days=verify_lag)
    if last_verified > last_contacted:
        last_verified = last_contacted

    intros_made, deals_closed = relationship_metrics(rel_strength, is_vip, sparse)
    channel = random.choices(CHANNELS, weights=CHANNEL_WEIGHTS, k=1)[0]

    do_not_intro = ""
    if random.random() < 0.04:
        conflict_id = random.randint(1, NUM_CONTACTS)
        do_not_intro = random.choice(COMPETITOR_BLOCKS).format(
            company=random.choice(bank["companies"]),
            conflict_id=f"{conflict_id:05d}",
        )

    comment = build_comment(
        full_name=full_name,
        company=company,
        title=title,
        specialty=specialty,
        sector=sector,
        role_blurb=role_blurb,
        sparse=sparse,
        is_vip=is_vip,
        bank=bank,
    )

    return {
        "contact_id": f"C{contact_num:05d}",
        "full_name": full_name,
        "phone": phone,
        "email": email,
        "company": company,
        "title": title,
        "sector": sector,
        "specialty": specialty,
        "location": location,
        "seniority": seniority,
        "expertise_tags": expertise_tags,
        "can_help_with": can_help_with,
        "looking_for": looking_for,
        "relationship_strength": rel_strength,
        "how_alex_knows_them": how,
        "is_vip": "TRUE" if is_vip else "FALSE",
        "last_contacted": last_contacted.isoformat(),
        "intros_made": intros_made,
        "deals_closed": deals_closed,
        "preferred_contact_channel": channel,
        "do_not_intro_to": do_not_intro,
        "last_verified": last_verified.isoformat(),
        "comment": comment,
    }


def generate_all(num: int, fake: Faker) -> list[dict]:
    return [generate_contact(i, fake) for i in range(1, num + 1)]


def write_csv(rows: list[dict], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_sample_xlsx(rows: list[dict], path: Path, sample_size: int) -> None:
    df = pd.DataFrame(rows[:sample_size], columns=COLUMNS)
    df.to_excel(path, index=False, engine="openpyxl")


def verify(rows: list[dict], csv_path: Path) -> None:
    with csv_path.open(encoding="utf-8") as f:
        data_rows = sum(1 for _ in f) - 1

    print(f"CSV data rows: {data_rows}")
    print("Header:", ",".join(COLUMNS))
    for row in rows[:3]:
        print(",".join(str(row[c]) for c in COLUMNS))

    sectors = pd.Series([r["sector"] for r in rows])
    print("\nSector distribution:")
    print(sectors.value_counts(normalize=True).mul(100).round(1).astype(str) + "%")

    vip_count = sum(1 for r in rows if r["is_vip"] == "TRUE")
    blank_email = sum(1 for r in rows if not r["email"])
    print(f"\nVIP count: {vip_count} ({vip_count / len(rows) * 100:.1f}%)")
    print(f"Blank email count: {blank_email} ({blank_email / len(rows) * 100:.1f}%)")


def main() -> None:
    random.seed(SEED)
    fake = Faker()
    fake.seed_instance(SEED)

    data_dir = Path(__file__).resolve().parent
    csv_path = data_dir / "contacts.csv"
    xlsx_path = data_dir / "contacts_sample.xlsx"

    print(f"Generating {NUM_CONTACTS:,} contacts (seed={SEED})...")
    rows = generate_all(NUM_CONTACTS, fake)

    write_csv(rows, csv_path)
    write_sample_xlsx(rows, xlsx_path, SAMPLE_SIZE)
    print(f"Wrote {csv_path}")
    print(f"Wrote {xlsx_path} ({SAMPLE_SIZE} rows)")

    verify(rows, csv_path)


if __name__ == "__main__":
    main()
