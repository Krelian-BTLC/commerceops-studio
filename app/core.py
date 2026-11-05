"""Import et audit d'un catalogue e-commerce de démonstration.

Le code ne fait aucune requête vers les URLs du catalogue et n'utilise
aucune donnée réelle de commerce sans autorisation.
"""
from __future__ import annotations

import csv
import io
import os
import sqlite3
from collections import Counter, defaultdict
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
from pathlib import Path

FIELDS = (
    "product_id", "sku", "title_fr", "description_fr", "price_eur",
    "image_url", "title_en", "status",
)
MAX_FILE_BYTES = 2_000_000
MAX_ROWS = 10_000


class CatalogValidationError(ValueError):
    pass


def db_path() -> Path:
    return Path(os.environ.get("COMMERCEOPS_DB", "./catalog.db"))


@contextmanager
def connection():
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path), timeout=10)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("""CREATE TABLE IF NOT EXISTS products (
           product_id TEXT PRIMARY KEY, sku TEXT NOT NULL,
           title_fr TEXT NOT NULL, description_fr TEXT NOT NULL,
           price_eur TEXT NOT NULL, image_url TEXT NOT NULL,
           title_en TEXT NOT NULL, status TEXT NOT NULL
        )""")
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def parse_csv(raw: bytes) -> list[dict[str, str]]:
    if len(raw) > MAX_FILE_BYTES:
        raise CatalogValidationError("Fichier trop volumineux (limite : 2 Mo).")
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CatalogValidationError("Le CSV doit être encodé en UTF-8.") from exc
    if not content.strip():
        raise CatalogValidationError("Le fichier CSV est vide.")
    try:
        dialect = csv.Sniffer().sniff(content[:4096], delimiters=",;")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(content, newline=""), dialect=dialect)
    headers = reader.fieldnames or []
    if len(set(headers)) != len(headers):
        raise CatalogValidationError("Le fichier comporte des noms de colonnes répétés.")
    missing = [field for field in FIELDS if field not in headers]
    if missing:
        raise CatalogValidationError("Colonnes manquantes : " + ", ".join(missing))
    rows: list[dict[str, str]] = []
    ids = set()
    for line_no, row in enumerate(reader, start=2):
        if line_no > MAX_ROWS + 1:
            raise CatalogValidationError("Trop de lignes (limite : 10 000 produits).")
        if None in row:
            raise CatalogValidationError(f"Ligne {line_no} : trop de champs.")
        data = {key: (row[key] or "").strip() for key in FIELDS}
        if not data["product_id"]:
            raise CatalogValidationError(f"Ligne {line_no} : product_id obligatoire.")
        if data["product_id"] in ids:
            raise CatalogValidationError(f"Ligne {line_no} : product_id dupliqué.")
        ids.add(data["product_id"])
        if data["status"] not in ("active", "draft"):
            raise CatalogValidationError(f"Ligne {line_no} : status doit être active ou draft.")
        rows.append(data)
    if not rows:
        raise CatalogValidationError("Aucun produit trouvé.")
    return rows


def import_catalog(rows: list[dict[str, str]]) -> None:
    with connection() as db:
        db.execute("DELETE FROM products")
        db.executemany(
            "INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ([row[field] for field in FIELDS] for row in rows),
        )


def get_products() -> list[dict[str, str]]:
    with connection() as db:
        return [dict(row) for row in db.execute("SELECT * FROM products ORDER BY product_id")]


def price_is_invalid(value: str) -> bool:
    try:
        price = Decimal(value)
        return not price.is_finite() or price <= 0
    except InvalidOperation:
        return True


def analyze(products: list[dict[str, str]]) -> list[dict[str, str]]:
    active = [p for p in products if p["status"] == "active"]
    sku_counts = Counter(p["sku"].casefold() for p in active if p["sku"])
    # Un texte identique de moins de 20 caractères n'est pas suffisant pour
    # conclure à un problème de description répétée.
    description_counts = Counter(
        p["description_fr"].strip().casefold() for p in active
        if len(p["description_fr"].strip()) >= 20
    )
    rules = (
        ("missing_sku", "high", "SKU manquant", lambda p: not p["sku"]),
        ("duplicate_sku", "high", "SKU utilisé par plusieurs produits", lambda p: bool(p["sku"]) and sku_counts[p["sku"].casefold()] > 1),
        ("invalid_price", "high", "Prix invalide ou non positif", lambda p: price_is_invalid(p["price_eur"])),
        ("missing_title_fr", "high", "Titre français manquant", lambda p: not p["title_fr"]),
        ("missing_description_fr", "medium", "Description française manquante", lambda p: not p["description_fr"]),
        ("duplicate_description_fr", "medium", "Description reprise sur plusieurs produits", lambda p: len(p["description_fr"].strip()) >= 20 and description_counts[p["description_fr"].strip().casefold()] > 1),
        ("missing_image", "medium", "Image produit manquante", lambda p: not p["image_url"]),
        ("missing_title_en", "low", "Traduction anglaise du titre manquante", lambda p: not p["title_en"]),
    )
    issues = []
    for product in active:
        for code, severity, message, test in rules:
            if test(product):
                issues.append({"product_id": product["product_id"], "sku": product["sku"], "code": code, "severity": severity, "message": message})
    severity_order = {"high": 0, "medium": 1, "low": 2}
    return sorted(issues, key=lambda issue: (severity_order[issue["severity"]], issue["product_id"], issue["code"]))


def summary(products: list[dict[str, str]], issues: list[dict[str, str]]) -> dict:
    active_count = sum(p["status"] == "active" for p in products)
    product_ids_with_issues = {item["product_id"] for item in issues}
    count_by_type = dict(sorted(Counter(item["code"] for item in issues).items()))
    count_by_severity = {s: sum(item["severity"] == s for item in issues) for s in ("high", "medium", "low")}
    return {
        "total_products": len(products), "active_products": active_count,
        "draft_products": len(products) - active_count,
        "affected_active_products": len(product_ids_with_issues),
        "active_products_without_issues": active_count - len(product_ids_with_issues),
        "issue_count": len(issues), "issues_by_severity": count_by_severity,
        "issues_by_type": count_by_type,
        "scope": "Les anomalies sont calculées uniquement sur les produits actifs.",
    }
