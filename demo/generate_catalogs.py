"""Génère deux catalogues 100 % fictifs, déterministes : avant et après corrections.

Boutique imaginaire « Maison Ardoise » (décoration). Aucune donnée réelle.

- catalog_before.csv : export de type Excel FR (séparateur ;, prix « 34,90 »)
  avec des anomalies volontaires de chaque famille de règles.
- catalog_after.csv : la même boutique après un lot de corrections. Certaines
  anomalies restent ouvertes (traductions en cours) et de nouveaux produits
  arrivent, dont un incomplet : la comparaison montre donc des anomalies
  résolues, persistantes et nouvelles.

Exécution : python demo/generate_catalogs.py
"""
from __future__ import annotations

import csv
import random
from pathlib import Path

HEADERS = ["product_id", "sku", "title_fr", "description_fr", "price_eur", "image_url", "title_en", "status"]
BASE = Path(__file__).parent
IMAGE_HOST = "https://images.example.com/maison-ardoise"  # domaine réservé (RFC 2606), jamais appelé

TYPES = [
    # (code, nom FR, nom EN, prix min, prix max, usage)
    ("LAM", "Lampe à poser", "Table lamp", 39, 149, "éclairer un bureau ou une table de chevet"),
    ("VAS", "Vase", "Vase", 18, 79, "mettre en valeur un bouquet ou des branches séchées"),
    ("COU", "Coussin", "Cushion", 19, 49, "apporter du confort et de la couleur à un canapé"),
    ("PLD", "Plaid", "Throw blanket", 35, 119, "réchauffer les soirées au salon"),
    ("BOU", "Bougie parfumée", "Scented candle", 14, 39, "parfumer délicatement une pièce"),
    ("TAS", "Tasse", "Mug", 9, 24, "savourer un café ou un thé"),
    ("CAR", "Carafe", "Carafe", 22, 65, "servir l'eau à table avec élégance"),
    ("PAN", "Panier tressé", "Woven basket", 24, 89, "ranger plaids, jouets ou magazines"),
    ("MIR", "Miroir mural", "Wall mirror", 59, 249, "agrandir visuellement une entrée ou un salon"),
    ("PLA", "Plateau", "Tray", 19, 59, "présenter un service ou organiser une console"),
]
FINISHES = [
    ("en lin naturel", "natural linen"), ("en grès émaillé", "glazed stoneware"),
    ("en verre recyclé", "recycled glass"), ("en chêne massif", "solid oak"),
    ("en laine bouclée", "bouclé wool"), ("en rotin", "rattan"), ("en laiton brossé", "brushed brass"),
    ("en céramique mate", "matte ceramic"), ("en coton bio", "organic cotton"), ("en terracotta", "terracotta"),
]
COLOURS = [
    ("sauge", "sage"), ("ardoise", "slate"), ("sable", "sand"), ("terracotta", "rust"),
    ("ivoire", "ivory"), ("anthracite", "charcoal"), ("bleu nuit", "midnight blue"), ("ocre", "ochre"),
]
GENERIC = "Produit de qualité, idéal pour votre intérieur. Livraison rapide et soignée."


def base_catalog() -> list[dict[str, str]]:
    rng = random.Random(2026)
    rows = []
    for n in range(1, 151):
        t, k = (n - 1) % len(TYPES), (n - 1) // len(TYPES)
        code, fr, en, low, high, usage = TYPES[t]
        # Combinaison type / finition / teinte unique : pas de titre dupliqué involontaire.
        finish_fr, finish_en = FINISHES[(k + t) % len(FINISHES)]
        colour_fr, colour_en = COLOURS[(3 * k + t) % len(COLOURS)]
        price = rng.randrange(low * 100, high * 100, 100) + rng.choice((0, 50, 90))
        rows.append({
            "product_id": f"MA-{n:04d}",
            "sku": f"ARD-{code}-{n:03d}",
            "title_fr": f"{fr} {finish_fr} {colour_fr}",
            "description_fr": (f"{fr} {finish_fr}, teinte {colour_fr}, conçu pour {usage}. "
                               f"Référence {n} de la collection Ardoise, fabriquée en petite série."),
            "price_eur": f"{price / 100:.2f}",
            "image_url": f"{IMAGE_HOST}/{code.lower()}-{n:03d}.jpg",
            "title_en": f"{colour_en.capitalize()} {finish_en} {en.lower()}",
            "status": "draft" if n > 144 else "active",
        })
    return rows


def before_catalog() -> list[dict[str, str]]:
    rows = base_catalog()
    for n, row in enumerate(rows, start=1):
        if n % 9 == 0:
            row["title_en"] = ""
        if n % 13 == 0:
            row["image_url"] = ""
        if n % 29 == 0:
            row["price_eur"] = "0"
        if n % 23 == 0:
            row["description_fr"] = GENERIC
    for n in (19, 38, 57):
        rows[n - 1]["sku"] = rows[17]["sku"]          # SKU recopié de MA-0018
    for n in (44, 88):
        rows[n - 1]["sku"] = ""
    rows[40]["price_eur"] = str(int(float(rows[40]["price_eur"]) * 100))  # virgule oubliée : 3490 au lieu de 34.90
    rows[26]["description_fr"] = rows[80]["description_fr"] = ""
    rows[65]["description_fr"] = "Lorem ipsum dolor sit amet, texte provisoire de la fiche."
    rows[119]["description_fr"] = "À compléter par l'équipe contenu avant mise en ligne."
    rows[74]["description_fr"] = "<p>" + rows[74]["description_fr"] + "</p>"
    rows[51]["image_url"] = "images/lampe-052.jpg"
    rows[96]["image_url"] = rows[96]["image_url"].replace("https://", "http://")
    rows[132]["image_url"] = rows[132]["image_url"].replace("https://", "http://")
    for i in (60, 101):
        rows[i]["title_en"] = rows[i]["title_fr"]
    rows[109]["description_fr"] = "Joli vase."
    rows[139]["title_fr"] = ""
    rows[146]["image_url"] = ""                         # brouillon : non audité
    for row in rows:
        row["price_eur"] = row["price_eur"].replace(".", ",")  # export Excel FR
    return rows


def after_catalog() -> list[dict[str, str]]:
    rows = base_catalog()
    # Corrections encore en cours : quelques traductions et une photo manquante.
    for n in (27, 54, 81, 108):
        rows[n - 1]["title_en"] = ""
    rows[77]["image_url"] = ""
    rows[60]["title_en"] = rows[60]["title_fr"]
    # Nouveaux produits ajoutés entre les deux audits, dont un incomplet.
    rows += [
        {"product_id": "MA-0151", "sku": "ARD-LAM-151", "title_fr": "Lampe à poser en laiton brossé ivoire",
         "description_fr": "Lampe à poser en laiton brossé, abat-jour ivoire, pour une lumière douce au salon.",
         "price_eur": "129.00", "image_url": f"{IMAGE_HOST}/lam-151.jpg", "title_en": "Ivory brushed brass table lamp",
         "status": "active"},
        {"product_id": "MA-0152", "sku": "ARD-VAS-152", "title_fr": "Vase soliflore",
         "description_fr": "", "price_eur": "21.90", "image_url": "",
         "title_en": "", "status": "active"},
    ]
    return rows


def write(rows: list[dict[str, str]], name: str, delimiter: str) -> None:
    dest = BASE / name
    with dest.open("w", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=HEADERS, delimiter=delimiter)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Créé {dest.name} : {len(rows)} produits fictifs")


if __name__ == "__main__":
    write(before_catalog(), "catalog_before.csv", ";")
    write(after_catalog(), "catalog_after.csv", ",")
