import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = ROOT_DIR / "data" / "sales.csv"

random.seed(42)

PRODUCTS = [
    ("SKU001", "Laptop Pro", "Informatique", 899.99),
    ("SKU002", "Wireless Mouse", "Informatique", 29.99),
    ("SKU003", "USB-C Hub", "Informatique", 49.90),
    ("SKU004", "Mechanical Keyboard", "Informatique", 89.99),
    ("SKU005", "Office Chair", "Mobilier", 249.00),
    ("SKU006", "Standing Desk", "Mobilier", 399.00),
    ("SKU007", "Desk Lamp", "Mobilier", 39.90),
    ("SKU008", "Notebook Pack", "Papeterie", 12.50),
    ("SKU009", "Ballpoint Pens", "Papeterie", 5.99),
    ("SKU010", "Monitor 27", "Informatique", 279.99),
    ("SKU011", "Water Bottle", "Accessoires", 19.90),
    ("SKU012", "Laptop Bag", "Accessoires", 44.90),
]

def generate_sales(number_of_sales=500):
    today = date.today()
    start_date = today - timedelta(days=364)

    rows = []

    for i in range(1, number_of_sales + 1):
        sku, name, category, base_price = random.choice(PRODUCTS)

        sale_date = start_date + timedelta(
            days=random.randint(0, 364)
        )

        quantity = random.randint(1, 8)

        # Variation de prix limitée autour du prix de référence.
        unit_price = round(
            base_price * random.uniform(0.95, 1.05), 2
        )

        rows.append({
            "sale_ref": f"SALE-{i:05d}",
            "sale_date": sale_date.isoformat(),
            "sku": sku,
            "product_name": name,
            "category": category,
            "quantity": quantity,
            "unit_price": unit_price,
        })

    return pd.DataFrame(rows)


if __name__ == "__main__":
    OUTPUT_FILE.parent.mkdir(
        parents=True, exist_ok=True
    )

    df = generate_sales()
    df.to_csv(OUTPUT_FILE, index=False)

    print(f"{len(df)} ventes générées.")
    print(f"Fichier créé : {OUTPUT_FILE}")
    print(df.head().to_string(index=False))