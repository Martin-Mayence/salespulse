from pathlib import Path

import pandas as pd
import psycopg

from app.db import get_connection


ROOT_DIR = Path(__file__).resolve().parent.parent
CSV_FILE = ROOT_DIR / "data" / "sales.csv"

REQUIRED_COLUMNS = {
    "sale_ref",
    "sale_date",
    "sku",
    "product_name",
    "category",
    "quantity",
    "unit_price",
}


def load_and_validate_csv(path: Path):
    """Charge le CSV et sépare les lignes valides des rejets."""
    df = pd.read_csv(path)

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"Colonnes manquantes dans le CSV : {sorted(missing)}"
        )

    df = df[list(REQUIRED_COLUMNS)].copy()

    # Normaliser les champs textuels.
    for column in ["sale_ref", "sku", "product_name", "category"]:
        df[column] = df[column].astype("string").str.strip()

    # Convertir les types.
    df["sale_date"] = pd.to_datetime(
        df["sale_date"], errors="coerce"
    ).dt.date

    df["quantity"] = pd.to_numeric(
        df["quantity"], errors="coerce"
    )

    df["unit_price"] = pd.to_numeric(
        df["unit_price"], errors="coerce"
    )

    # Une quantité doit être un entier strictement positif.
    quantity_is_integer = (
        df["quantity"].notna()
        & (df["quantity"] % 1 == 0)
    )

    valid = (
        df["sale_ref"].notna()
        & df["sale_ref"].ne("")
        & df["sku"].notna()
        & df["sku"].ne("")
        & df["product_name"].notna()
        & df["product_name"].ne("")
        & df["category"].notna()
        & df["category"].ne("")
        & df["sale_date"].notna()
        & quantity_is_integer
        & df["quantity"].gt(0)
        & df["unit_price"].notna()
        & df["unit_price"].ge(0)
    )

    rejected_count = int((~valid).sum())
    valid_df = df.loc[valid].copy()

    # Éviter les doublons de référence au sein du même fichier.
    duplicate_mask = valid_df["sale_ref"].duplicated()
    duplicate_count = int(duplicate_mask.sum())

    valid_df = valid_df.loc[~duplicate_mask].copy()

    # Convertir vers les types Python attendus par PostgreSQL.
    valid_df["quantity"] = valid_df["quantity"].astype(int)
    valid_df["unit_price"] = valid_df["unit_price"].round(2)

    return valid_df, rejected_count, duplicate_count, len(df)


def import_sales(path: Path = CSV_FILE):
    """Importe les ventes dans PostgreSQL de façon transactionnelle."""
    if not path.is_file():
        raise FileNotFoundError(
            f"Fichier CSV introuvable : {path}"
        )

    df, rejected, file_duplicates, rows_read = (
        load_and_validate_csv(path)
    )

    inserted = 0
    db_duplicates = 0

    # La transaction englobe toutes les écritures SQL.
    with get_connection() as conn:
        with conn.cursor() as cur:

            # Enregistrer le lot, y compris si des lignes sont rejetées.
            cur.execute(
                """
                INSERT INTO import_batches (
                    filename, rows_processed, rows_rejected
                )
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (path.name, len(df), rejected),
            )
            batch_id = cur.fetchone()[0]

            if not df.empty:
                # 1. Créer les catégories manquantes.
                categories = sorted(df["category"].unique())

                cur.executemany(
                    """
                    INSERT INTO categories (name)
                    VALUES (%s)
                    ON CONFLICT (name) DO NOTHING
                    """,
                    [(name,) for name in categories],
                )

                # 2. Créer ou actualiser les produits par SKU.
                products = df[
                    ["sku", "product_name", "category"]
                ].drop_duplicates("sku")

                # Refuser un SKU associé à plusieurs descriptions
                # différentes dans un même fichier.
                if df.groupby("sku")["product_name"].nunique().gt(1).any():
                    raise ValueError(
                        "Un même SKU possède plusieurs noms dans le CSV."
                    )

                category_rows = cur.execute(
                    """
                    SELECT id, name
                    FROM categories
                    WHERE name = ANY(%s)
                    """,
                    (categories,),
                ).fetchall()

                category_ids = {
                    name: category_id
                    for category_id, name in category_rows
                }

                for row in products.itertuples(index=False):
                    cur.execute(
                        """
                        INSERT INTO products (
                            sku, name, category_id
                        )
                        VALUES (%s, %s, %s)
                        ON CONFLICT (sku) DO UPDATE SET
                            name = EXCLUDED.name,
                            category_id = EXCLUDED.category_id
                        """,
                        (
                            row.sku,
                            row.product_name,
                            category_ids[row.category],
                        ),
                    )

                # 3. Charger les identifiants des produits.
                skus = df["sku"].unique().tolist()

                product_rows = cur.execute(
                    """
                    SELECT id, sku
                    FROM products
                    WHERE sku = ANY(%s)
                    """,
                    (skus,),
                ).fetchall()

                product_ids = {
                    sku: product_id
                    for product_id, sku in product_rows
                }

                # 4. Insérer les ventes et ignorer les références
                # déjà présentes en base.
                for row in df.itertuples(index=False):
                    cur.execute(
                        """
                        INSERT INTO sales (
                            sale_ref,
                            product_id,
                            import_batch_id,
                            sale_date,
                            quantity,
                            unit_price
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (sale_ref) DO NOTHING
                        """,
                        (
                            row.sale_ref,
                            product_ids[row.sku],
                            batch_id,
                            row.sale_date,
                            row.quantity,
                            row.unit_price,
                        ),
                    )

                    if cur.rowcount == 1:
                        inserted += 1
                    else:
                        db_duplicates += 1

    # À ce stade, la transaction est validée.
    return {
        "rows_read": rows_read,
        "valid_rows": len(df),
        "inserted": inserted,
        "duplicates": file_duplicates + db_duplicates,
        "rejected": rejected,
    }


if __name__ == "__main__":
    try:
        result = import_sales()

        print("\n=== Bilan SalesPulse ===")
        print(f"Lignes lues          : {result['rows_read']}")
        print(f"Lignes valides       : {result['valid_rows']}")
        print(f"Ventes insérées      : {result['inserted']}")
        print(f"Doublons ignorés     : {result['duplicates']}")
        print(f"Lignes rejetées      : {result['rejected']}")

    except (FileNotFoundError, ValueError, psycopg.Error) as exc:
        print(f"Échec de l'import : {exc}")
        raise SystemExit(1)