"""
Generate realistic sample data for the Supplier Evaluation Dashboard.

Produces one CSV per table:
    data/categories.csv   - product/service categories
    data/suppliers.csv    - supplier master data
    data/orders.csv       - purchase orders placed with suppliers
    data/ratings.csv       - per-order ratings on 4 criteria (1-5 scale)

Run once to (re)generate the data:  python generate_data.py
"""

import random
import csv
from pathlib import Path
from datetime import date, timedelta

random.seed(42)  # reproducible data

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# --------------------------------------------------------------------------- #
# 1. Categories
# --------------------------------------------------------------------------- #
categories = [
    (1, "Electronics", "Electronic components and assemblies"),
    (2, "Raw Materials", "Metals, plastics and base chemicals"),
    (3, "Packaging", "Boxes, films and protective packaging"),
    (4, "Logistics", "Freight, warehousing and distribution"),
    (5, "Office Supplies", "Stationery and consumables"),
    (6, "Machinery", "Industrial equipment and spare parts"),
]

# --------------------------------------------------------------------------- #
# 2. Suppliers
# --------------------------------------------------------------------------- #
# (name, country, category_id, quality_bias)  quality_bias shifts the rating
# distribution so some suppliers are consistently strong or weak.
supplier_defs = [
    ("Nordwind Elektronik GmbH", "Germany", 1, +0.8),
    ("Baltic Components AB", "Sweden", 1, +0.3),
    ("Shenzhen MicroParts Ltd", "China", 1, -0.6),
    ("Alpine Metals AG", "Switzerland", 2, +0.9),
    ("IberoPlast S.L.", "Spain", 2, -0.2),
    ("Rustbelt Steelworks Inc", "USA", 2, -1.1),
    ("GreenBox Packaging BV", "Netherlands", 3, +0.5),
    ("Toscana Imballaggi Srl", "Italy", 3, +0.1),
    ("QuickWrap Ltd", "United Kingdom", 3, -0.7),
    ("EuroFreight Logistics GmbH", "Germany", 4, +0.6),
    ("TransAsia Cargo Co", "Singapore", 4, -0.3),
    ("Polar Express Oy", "Finland", 4, -0.9),
    ("PaperPlus Bureau SARL", "France", 5, +0.2),
    ("OfficeMax Central", "Poland", 5, -0.4),
    ("Precision Machinery KK", "Japan", 6, +1.0),
    ("HeavyDuty Werke GmbH", "Germany", 6, +0.4),
    ("Bharat Tooling Pvt Ltd", "India", 6, -0.8),
]

# --------------------------------------------------------------------------- #
# 2b. Procedurally generate more suppliers until we reach TARGET_SUPPLIERS.
# The 17 curated suppliers above are kept as-is; the rest are synthesized by
# combining name fragments with a country and a random quality bias.
# --------------------------------------------------------------------------- #
TARGET_SUPPLIERS = 100

# Category-appropriate name parts: prefix words + suffix/entity words.
name_parts = {
    1: (["Nova", "Micro", "Volt", "Circuit", "Photon", "Quantum", "Ampere", "Silicon",
         "Byte", "Fusion", "Pulse", "Ion", "Lumen", "Vector"],
        ["Electronics", "Components", "Systems", "Semiconductors", "Devices", "Technik"]),
    2: (["Titan", "Iron", "Terra", "Copper", "Basalt", "Granite", "Alloy", "Forge",
         "Element", "Core", "Mineral", "Cobalt", "Zinc", "Carbon"],
        ["Metals", "Materials", "Chemicals", "Alloys", "Resources", "Industries"]),
    3: (["Eco", "Flex", "Secure", "Fresh", "Wrap", "Box", "Shield", "Pallet",
         "Cushion", "Seal", "Fold", "Crate", "Layer", "Guard"],
        ["Packaging", "Pack", "Wrapping", "Containers", "Solutions", "Supplies"]),
    4: (["Swift", "Global", "Rapid", "Prime", "Trans", "Cargo", "Route", "Freight",
         "Express", "Continental", "Ocean", "Sky", "Fleet", "Link"],
        ["Logistics", "Cargo", "Freight", "Shipping", "Transport", "Distribution"]),
    5: (["Paper", "Office", "Bureau", "Ink", "Clip", "Desk", "Note", "Print",
         "Stationery", "Supply", "Clerk", "Folio", "Quill", "Pen"],
        ["Supplies", "Office", "Stationery", "Bureau", "Products", "Trading"]),
    6: (["Precision", "Heavy", "Turbo", "Gear", "Axis", "Torque", "Hydra", "Machine",
         "Bolt", "Drive", "Mecha", "Industria", "Motion", "Power"],
        ["Machinery", "Werke", "Engineering", "Tooling", "Equipment", "Industries"]),
}

# entity/legal-form suffixes keyed by country flavour
country_pool = [
    ("Germany", "GmbH"), ("Sweden", "AB"), ("China", "Ltd"), ("Switzerland", "AG"),
    ("Spain", "S.L."), ("USA", "Inc"), ("Netherlands", "BV"), ("Italy", "Srl"),
    ("United Kingdom", "Ltd"), ("Singapore", "Co"), ("Finland", "Oy"), ("France", "SARL"),
    ("Poland", "Sp. z o.o."), ("Japan", "KK"), ("India", "Pvt Ltd"), ("Austria", "GmbH"),
    ("Belgium", "NV"), ("Denmark", "A/S"), ("Norway", "AS"), ("Portugal", "Lda"),
    ("Czechia", "s.r.o."), ("Ireland", "Ltd"), ("South Korea", "Co"), ("Mexico", "S.A."),
    ("Brazil", "Ltda"), ("Turkey", "A.S."), ("Canada", "Inc"), ("Australia", "Pty Ltd"),
]

suppliers = []
used_names = set()
for i, (name, country, cat, bias) in enumerate(supplier_defs, start=1):
    contact = "contact@" + "".join(c for c in name.lower().split()[0] if c.isalnum()) + ".example"
    suppliers.append((i, name, country, cat, contact, bias))
    used_names.add(name)

next_id = len(supplier_defs) + 1
while next_id <= TARGET_SUPPLIERS:
    cat = random.randint(1, len(categories))
    prefixes, suffixes = name_parts[cat]
    country, entity = random.choice(country_pool)
    name = f"{random.choice(prefixes)}{random.choice(suffixes)} {entity}"
    if name in used_names:
        continue
    used_names.add(name)
    bias = round(random.uniform(-1.2, 1.1), 2)
    slug = "".join(c for c in name.lower().split()[0] if c.isalnum())
    contact = f"contact@{slug}.example"
    suppliers.append((next_id, name, country, cat, contact, bias))
    next_id += 1

# --------------------------------------------------------------------------- #
# 3. Orders  (each supplier has a handful of orders)
# --------------------------------------------------------------------------- #
statuses = ["Delivered", "Delivered", "Delivered", "Delivered", "In Transit", "Cancelled"]
start_day = date(2025, 1, 1)

orders = []       # (order_id, supplier_id, order_date, amount_eur, status)
order_id = 1
supplier_orders = {}  # supplier_id -> list of order_ids
for sup_id, *_ in suppliers:
    n_orders = random.randint(2, 5)
    ids = []
    for _ in range(n_orders):
        d = start_day + timedelta(days=random.randint(0, 300))
        amount = round(random.uniform(1_500, 85_000), 2)
        status = random.choice(statuses)
        orders.append((order_id, sup_id, d.isoformat(), amount, status))
        ids.append(order_id)
        order_id += 1
    supplier_orders[sup_id] = ids

# --------------------------------------------------------------------------- #
# 4. Ratings  (one rating record per order, 4 criteria on a 1-5 scale)
# --------------------------------------------------------------------------- #
def biased_score(bias):
    """Return an integer 1-5, nudged by the supplier's quality bias."""
    base = random.gauss(3.3 + bias, 0.8)
    return max(1, min(5, round(base)))

rating_id = 1
ratings = []  # (rating_id, order_id, supplier_id, delivery_time, quality, price, communication)
bias_by_supplier = {s[0]: s[5] for s in suppliers}
for sup_id, ids in supplier_orders.items():
    bias = bias_by_supplier[sup_id]
    for oid in ids:
        delivery = biased_score(bias)
        quality = biased_score(bias)
        price = biased_score(bias * 0.5)          # price less correlated with quality
        communication = biased_score(bias * 0.7)
        ratings.append((rating_id, oid, sup_id, delivery, quality, price, communication))
        rating_id += 1

# --------------------------------------------------------------------------- #
# Write CSVs
# --------------------------------------------------------------------------- #
def write_csv(name, header, rows):
    path = DATA_DIR / name
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"  wrote {path.name:20s} ({len(rows)} rows)")

print("Generating CSV data ...")
write_csv("categories.csv", ["category_id", "category_name", "description"], categories)
write_csv(
    "suppliers.csv",
    ["supplier_id", "supplier_name", "country", "category_id", "contact_email"],
    [(s[0], s[1], s[2], s[3], s[4]) for s in suppliers],  # drop the bias helper column
)
write_csv(
    "orders.csv",
    ["order_id", "supplier_id", "order_date", "amount_eur", "status"],
    orders,
)
write_csv(
    "ratings.csv",
    ["rating_id", "order_id", "supplier_id", "delivery_time", "quality", "price", "communication"],
    ratings,
)
print("Done.")
