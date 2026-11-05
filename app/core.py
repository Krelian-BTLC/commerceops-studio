"""Façade de compatibilité v0.1.

La logique a été répartie en v0.2 entre :
- ``importer`` : lecture, validation et normalisation du CSV ;
- ``rules`` : moteur de règles d'audit extensible ;
- ``storage`` : persistance SQLite et historique des audits ;
- ``exports`` : exports CSV et PDF.
"""
from __future__ import annotations

from collections import Counter

from .importer import FIELDS, MAX_FILE_BYTES, MAX_ROWS, CatalogValidationError, parse_csv
from .rules import price_is_invalid, run_rules

__all__ = ["FIELDS", "MAX_FILE_BYTES", "MAX_ROWS", "CatalogValidationError", "analyze",
           "parse_csv", "price_is_invalid", "summary"]


def analyze(products: list[dict[str, str]]) -> list[dict]:
    return run_rules(products)


def summary(products: list[dict[str, str]], issues: list[dict]) -> dict:
    active_count = sum(p["status"] == "active" for p in products)
    affected = {item["product_id"] for item in issues}
    return {
        "total_products": len(products), "active_products": active_count,
        "draft_products": len(products) - active_count,
        "affected_active_products": len(affected),
        "active_products_without_issues": active_count - len(affected),
        "issue_count": len(issues),
        "issues_by_severity": {s: sum(i["severity"] == s for i in issues) for s in ("high", "medium", "low")},
        "issues_by_type": dict(sorted(Counter(i["code"] for i in issues).items())),
        "scope": "Les anomalies sont calculées uniquement sur les produits actifs.",
    }
