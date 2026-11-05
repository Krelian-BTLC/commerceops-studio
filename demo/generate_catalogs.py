"""Génère deux catalogues synthétiques comparables avec et sans erreurs."""
from pathlib import Path
import csv

HEADERS = ["product_id", "sku", "title_fr", "description_fr", "price_eur", "image_url", "title_en", "status"]
BASE = Path(__file__).parent


def generate(fixed: bool):
    rows = []
    for n in range(1, 151):
        sku = f"SKU-{n:04d}"
        title_fr = f"Produit de démonstration n° {n}"
        description_fr = f"Description originale de démonstration pour le produit {n}."
        image_url = f"https://example.org/images/{n}.jpg"
        title_en = f"Demo product number {n}"
        price_eur = "29.95"
        if not fixed:
            if n % 11 == 0: title_en = ""
            if n % 13 == 0: image_url = ""
            if n % 17 == 0: price_eur = "0"
            if n % 19 == 0: sku = "SKU-DUP"
            if n % 23 == 0: description_fr = "Texte modèle répété sans personnalisation de la fiche produit."
        rows.append(dict(product_id=f"demo-{n:03d}", sku=sku, title_fr=title_fr,
            description_fr=description_fr, price_eur=price_eur,
            image_url=image_url, title_en=title_en, status="active"))
    dest = BASE / ("catalog_after.csv" if fixed else "catalog_before.csv")
    with dest.open("w", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Created {dest}: {len(rows)} synthetic products")

if __name__ == "__main__":
    generate(False)
    generate(True)
