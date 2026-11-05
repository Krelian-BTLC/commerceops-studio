"""Persistance SQLite : chaque import crée un audit conservé dans l'historique.

Les anomalies sont calculées une seule fois à l'import et stockées avec la
version des règles utilisée, pour que les résultats d'un audit passé restent
stables et comparables.
"""
from __future__ import annotations

import json
import sqlite3
from collections import Counter
from contextlib import contextmanager
from datetime import UTC, datetime

from .config import get_settings
from .importer import FIELDS
from .rules import PENALTIES, RULES_VERSION, SEVERITY_ORDER, product_score, run_rules

SCHEMA = """
CREATE TABLE IF NOT EXISTS audits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    source_filename TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    rules_version TEXT NOT NULL,
    total_products INTEGER NOT NULL,
    active_products INTEGER NOT NULL,
    affected_products INTEGER NOT NULL,
    issue_count INTEGER NOT NULL,
    high_count INTEGER NOT NULL,
    medium_count INTEGER NOT NULL,
    low_count INTEGER NOT NULL,
    quality_score REAL,
    warnings_json TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS audit_products (
    audit_id INTEGER NOT NULL REFERENCES audits(id) ON DELETE CASCADE,
    product_id TEXT NOT NULL,
    sku TEXT NOT NULL,
    title_fr TEXT NOT NULL,
    description_fr TEXT NOT NULL,
    price_eur TEXT NOT NULL,
    image_url TEXT NOT NULL,
    title_en TEXT NOT NULL,
    status TEXT NOT NULL,
    score INTEGER,
    issue_count INTEGER NOT NULL DEFAULT 0,
    worst_severity INTEGER,
    PRIMARY KEY (audit_id, product_id)
);
CREATE TABLE IF NOT EXISTS audit_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    audit_id INTEGER NOT NULL REFERENCES audits(id) ON DELETE CASCADE,
    product_id TEXT NOT NULL,
    sku TEXT NOT NULL,
    title_fr TEXT NOT NULL,
    code TEXT NOT NULL,
    severity TEXT NOT NULL,
    severity_rank INTEGER NOT NULL,
    category TEXT NOT NULL,
    field TEXT NOT NULL,
    message TEXT NOT NULL,
    explanation TEXT NOT NULL,
    suggestion TEXT NOT NULL,
    confidence TEXT NOT NULL,
    evidence TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_issues_audit ON audit_issues(audit_id, severity_rank, code);
CREATE INDEX IF NOT EXISTS ix_issues_product ON audit_issues(audit_id, product_id);
"""

ISSUE_COLUMNS = ("product_id", "sku", "title_fr", "code", "severity", "category", "field",
                 "message", "explanation", "suggestion", "confidence", "evidence")


@contextmanager
def connection():
    path = get_settings().db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path), timeout=10)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("PRAGMA foreign_keys=ON")
        db.executescript(SCHEMA)
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _audit_row(row: sqlite3.Row) -> dict:
    data = dict(row)
    data["warnings"] = json.loads(data.pop("warnings_json"))
    data["draft_products"] = data["total_products"] - data["active_products"]
    data["issues_by_severity"] = {"high": data.pop("high_count"), "medium": data.pop("medium_count"), "low": data.pop("low_count")}
    return data


def create_audit(rows: list[dict[str, str]], *, label: str, filename: str, sha256: str,
                 warnings: list[dict] | None = None) -> dict:
    issues = run_rules(rows)
    by_product: dict[str, list[dict]] = {}
    for issue in issues:
        by_product.setdefault(issue["product_id"], []).append(issue)
    active = [r for r in rows if r["status"] == "active"]
    scores = {p["product_id"]: product_score(by_product.get(p["product_id"], [])) for p in active}
    severity = Counter(i["severity"] for i in issues)
    quality = round(sum(scores.values()) / len(scores), 1) if scores else None

    with connection() as db:
        cur = db.execute(
            """INSERT INTO audits (label, source_filename, source_sha256, created_at, rules_version,
               total_products, active_products, affected_products, issue_count, high_count,
               medium_count, low_count, quality_score, warnings_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (label, filename, sha256, datetime.now(UTC).isoformat(timespec="seconds"), RULES_VERSION,
             len(rows), len(active), len(by_product), len(issues), severity["high"],
             severity["medium"], severity["low"], quality, json.dumps(warnings or [], ensure_ascii=False)),
        )
        audit_id = cur.lastrowid
        db.executemany(
            f"INSERT INTO audit_products VALUES (?, {', '.join('?' * len(FIELDS))}, ?, ?, ?)",
            (
                (audit_id, *(r[f] for f in FIELDS), scores.get(r["product_id"]),
                 len(by_product.get(r["product_id"], [])),
                 min((SEVERITY_ORDER[i["severity"]] for i in by_product.get(r["product_id"], [])), default=None))
                for r in rows
            ),
        )
        db.executemany(
            f"""INSERT INTO audit_issues (audit_id, severity_rank, {', '.join(ISSUE_COLUMNS)})
                VALUES (?, ?, {', '.join('?' * len(ISSUE_COLUMNS))})""",
            ((audit_id, SEVERITY_ORDER[i["severity"]], *(i[c] for c in ISSUE_COLUMNS)) for i in issues),
        )
        return _audit_row(db.execute("SELECT * FROM audits WHERE id = ?", (audit_id,)).fetchone())


def list_audits() -> list[dict]:
    with connection() as db:
        return [_audit_row(r) for r in db.execute("SELECT * FROM audits ORDER BY id DESC")]


def get_audit(audit_id: int) -> dict | None:
    with connection() as db:
        row = db.execute("SELECT * FROM audits WHERE id = ?", (audit_id,)).fetchone()
        return _audit_row(row) if row else None


def latest_audit_id() -> int | None:
    with connection() as db:
        row = db.execute("SELECT MAX(id) FROM audits").fetchone()
        return row[0]


def delete_audit(audit_id: int) -> bool:
    with connection() as db:
        return db.execute("DELETE FROM audits WHERE id = ?", (audit_id,)).rowcount > 0


def audit_breakdown(audit_id: int) -> dict:
    """Répartition des anomalies par règle et par catégorie, et produits prioritaires."""
    with connection() as db:
        by_code = {r["code"]: r["n"] for r in db.execute(
            "SELECT code, COUNT(*) n FROM audit_issues WHERE audit_id = ? GROUP BY code ORDER BY code", (audit_id,))}
        by_category = {r["category"]: r["n"] for r in db.execute(
            "SELECT category, COUNT(*) n FROM audit_issues WHERE audit_id = ? GROUP BY category ORDER BY category", (audit_id,))}
        by_confidence = {r["confidence"]: r["n"] for r in db.execute(
            "SELECT confidence, COUNT(*) n FROM audit_issues WHERE audit_id = ? GROUP BY confidence", (audit_id,))}
        priority = [dict(r) for r in db.execute(
            """SELECT product_id, sku, title_fr, score, issue_count, worst_severity FROM audit_products
               WHERE audit_id = ? AND issue_count > 0 ORDER BY score ASC, issue_count DESC, product_id LIMIT 10""",
            (audit_id,))]
        buckets = Counter()
        for r in db.execute("SELECT score FROM audit_products WHERE audit_id = ? AND score IS NOT NULL", (audit_id,)):
            s = r["score"]
            buckets["excellent" if s >= 90 else "good" if s >= 70 else "fair" if s >= 40 else "poor"] += 1
    for item in priority:
        item["worst_severity"] = _severity_name(item["worst_severity"])
    return {
        "issues_by_type": by_code, "issues_by_category": by_category,
        "issues_by_confidence": {"certain": by_confidence.get("certain", 0), "heuristic": by_confidence.get("heuristic", 0)},
        "score_distribution": {k: buckets.get(k, 0) for k in ("excellent", "good", "fair", "poor")},
        "priority_products": priority,
    }


def _severity_name(rank: int | None) -> str | None:
    return None if rank is None else next(k for k, v in SEVERITY_ORDER.items() if v == rank)


def _like(term: str) -> str:
    return "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


PRODUCT_SORTS = {
    "product_id": "product_id", "sku": "sku", "title": "title_fr", "score": "score",
    "issues": "issue_count", "price": "CAST(price_eur AS REAL)", "status": "status",
}
ISSUE_SORTS = {
    "severity": "severity_rank", "product_id": "product_id", "code": "code",
    "category": "category", "sku": "sku",
}


def _order(sort: str, sorts: dict[str, str], tiebreak: str) -> str:
    desc = sort.startswith("-")
    column = sorts.get(sort.lstrip("-"), next(iter(sorts.values())))
    # Les valeurs NULL (brouillons sans score) sont toujours placées en fin de liste.
    return f"{column} IS NULL, {column} {'DESC' if desc else 'ASC'}, {tiebreak}"


def query_products(audit_id: int, *, q: str | None = None, status: str | None = None,
                   severity: str | None = None, has_issues: bool | None = None,
                   sort: str = "score", page: int = 1, page_size: int = 25) -> dict:
    where, params = ["audit_id = ?"], [audit_id]
    if q:
        where.append("(product_id LIKE ? ESCAPE '\\' OR sku LIKE ? ESCAPE '\\' OR title_fr LIKE ? ESCAPE '\\')")
        params += [_like(q)] * 3
    if status:
        where.append("status = ?")
        params.append(status)
    if severity:
        where.append("worst_severity = ?")
        params.append(SEVERITY_ORDER[severity])
    if has_issues is not None:
        where.append("issue_count > 0" if has_issues else "issue_count = 0")
    clause = " AND ".join(where)
    with connection() as db:
        total = db.execute(f"SELECT COUNT(*) FROM audit_products WHERE {clause}", params).fetchone()[0]
        rows = db.execute(
            f"SELECT * FROM audit_products WHERE {clause} ORDER BY {_order(sort, PRODUCT_SORTS, 'product_id')} LIMIT ? OFFSET ?",
            [*params, page_size, (page - 1) * page_size],
        ).fetchall()
    items = []
    for r in rows:
        item = dict(r)
        item.pop("audit_id")
        item["worst_severity"] = _severity_name(item["worst_severity"])
        items.append(item)
    return {"total": total, "page": page, "page_size": page_size, "items": items}


def get_product(audit_id: int, product_id: str) -> dict | None:
    with connection() as db:
        row = db.execute("SELECT * FROM audit_products WHERE audit_id = ? AND product_id = ?", (audit_id, product_id)).fetchone()
        if not row:
            return None
        issues = [dict(r) for r in db.execute(
            f"SELECT {', '.join(ISSUE_COLUMNS)} FROM audit_issues WHERE audit_id = ? AND product_id = ? ORDER BY severity_rank, code",
            (audit_id, product_id))]
    product = dict(row)
    product.pop("audit_id")
    product["worst_severity"] = _severity_name(product["worst_severity"])
    product["issues"] = issues
    product["score_breakdown"] = [{"code": i["code"], "severity": i["severity"], "penalty": PENALTIES[i["severity"]]} for i in issues]
    return product


def _issue_filters(audit_id, severity, code, category, confidence, q):
    where, params = ["audit_id = ?"], [audit_id]
    for column, value in (("severity", severity), ("code", code), ("category", category), ("confidence", confidence)):
        if value:
            where.append(f"{column} = ?")
            params.append(value)
    if q:
        where.append("(product_id LIKE ? ESCAPE '\\' OR sku LIKE ? ESCAPE '\\' OR title_fr LIKE ? ESCAPE '\\')")
        params += [_like(q)] * 3
    return " AND ".join(where), params


def query_issues(audit_id: int, *, severity: str | None = None, code: str | None = None,
                 category: str | None = None, confidence: str | None = None, q: str | None = None,
                 sort: str = "severity", page: int = 1, page_size: int | None = 50) -> dict:
    clause, params = _issue_filters(audit_id, severity, code, category, confidence, q)
    order = _order(sort, ISSUE_SORTS, "severity_rank, product_id, code")
    sql = f"SELECT {', '.join(ISSUE_COLUMNS)} FROM audit_issues WHERE {clause} ORDER BY {order}"
    with connection() as db:
        total = db.execute(f"SELECT COUNT(*) FROM audit_issues WHERE {clause}", params).fetchone()[0]
        if page_size is None:
            rows = db.execute(sql, params).fetchall()
        else:
            rows = db.execute(sql + " LIMIT ? OFFSET ?", [*params, page_size, (page - 1) * page_size]).fetchall()
    return {"total": total, "page": page, "page_size": page_size, "items": [dict(r) for r in rows]}


def _issue_keys(db, audit_id: int) -> dict[tuple[str, str], dict]:
    return {(r["product_id"], r["code"]): dict(r) for r in db.execute(
        "SELECT product_id, sku, title_fr, code, severity, message FROM audit_issues WHERE audit_id = ?", (audit_id,))}


def compare_audits(base_id: int, target_id: int, *, limit: int = 200) -> dict | None:
    """Comparaison avant/après. Une anomalie est identifiée par (product_id, règle)."""
    base, target = get_audit(base_id), get_audit(target_id)
    if not base or not target:
        return None
    with connection() as db:
        before, after = _issue_keys(db, base_id), _issue_keys(db, target_id)
        base_products = {r[0] for r in db.execute("SELECT product_id FROM audit_products WHERE audit_id = ?", (base_id,))}
        target_products = {r[0] for r in db.execute("SELECT product_id FROM audit_products WHERE audit_id = ?", (target_id,))}
    resolved = [before[k] for k in sorted(before.keys() - after.keys(), key=lambda k: (SEVERITY_ORDER[before[k]["severity"]], k))]
    new = [after[k] for k in sorted(after.keys() - before.keys(), key=lambda k: (SEVERITY_ORDER[after[k]["severity"]], k))]
    persisting = [after[k] for k in sorted(after.keys() & before.keys(), key=lambda k: (SEVERITY_ORDER[after[k]["severity"]], k))]

    codes = sorted({k[1] for k in before} | {k[1] for k in after})
    count_b, count_a = Counter(k[1] for k in before), Counter(k[1] for k in after)

    def metric(name):
        b, a = base[name], target[name]
        return {"before": b, "after": a, "delta": None if a is None or b is None else round(a - b, 1)}

    change = (round((target["issue_count"] - base["issue_count"]) / base["issue_count"] * 100, 1)
              if base["issue_count"] else None)
    return {
        "base": base, "target": target,
        "metrics": {name: metric(name) for name in
                    ("total_products", "active_products", "affected_products", "issue_count", "quality_score")},
        "issue_change_percent": change,
        "by_severity": {s: {"before": base["issues_by_severity"][s], "after": target["issues_by_severity"][s]}
                        for s in ("high", "medium", "low")},
        "by_type": [{"code": c, "before": count_b[c], "after": count_a[c], "delta": count_a[c] - count_b[c]} for c in codes],
        "counts": {"resolved": len(resolved), "new": len(new), "persisting": len(persisting)},
        "products": {"added": len(target_products - base_products), "removed": len(base_products - target_products),
                     "common": len(base_products & target_products)},
        "resolved": resolved[:limit], "new": new[:limit], "persisting": persisting[:limit],
        "same_rules_version": base["rules_version"] == target["rules_version"],
    }
