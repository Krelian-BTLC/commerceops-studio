"""Lecture, validation stricte et normalisation d'un catalogue CSV.

Deux niveaux de retour :
- les **erreurs bloquantes** (structure, encodage, identifiants, statut) font
  rejeter tout le fichier, avec le numéro de ligne concerné ;
- les **avertissements** (valeurs normalisées, colonnes ignorées) n'empêchent
  pas l'import. Les champs vides ou douteux sont importés tels quels : ce sont
  justement les anomalies que l'audit doit montrer.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

FIELDS = (
    "product_id", "sku", "title_fr", "description_fr", "price_eur",
    "image_url", "title_en", "status",
)
STATUSES = ("active", "draft")
MAX_FILE_BYTES = 2_000_000
MAX_ROWS = 10_000
MAX_FIELD_CHARS = 20_000
MAX_REPORTED_ERRORS = 50

_SPACES = re.compile(r"\s+")
_CURRENCY = re.compile(r"(?i)(€|eur)")
_NUMBER = re.compile(r"^[+-]?(\d+([.,]\d+)?|[.,]\d+)$")


class CatalogValidationError(ValueError):
    """Fichier rejeté. ``errors`` détaille chaque problème bloquant."""

    def __init__(self, message: str, errors: list[dict] | None = None):
        super().__init__(message)
        self.errors = errors or []


@dataclass
class ParseResult:
    rows: list[dict[str, str]]
    warnings: list[dict] = field(default_factory=list)
    delimiter: str = ","


def normalize_price(raw: str) -> str | None:
    """Convertit '29,95', '1 234,50 €' ou '1,234.50' en '29.95'.

    Renvoie None si la valeur n'est pas un nombre décimal fini : elle sera
    conservée telle quelle et signalée par la règle ``invalid_price``.
    """
    value = _CURRENCY.sub("", raw)
    value = value.replace(" ", "").replace(" ", "").replace(" ", "").replace("'", "")
    if "," in value and "." in value:
        # Le dernier séparateur est le séparateur décimal.
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    if not _NUMBER.match(value):
        return None
    value = value.replace(",", ".")
    try:
        number = Decimal(value)
    except InvalidOperation:
        return None
    if not number.is_finite():
        return None
    # Les chiffres saisis sont conservés tels quels (« 34,90 » → « 34.90 »).
    return ("0" + value) if value.startswith(".") else value


def _detect_delimiter(header_line: str) -> str:
    return ";" if header_line.count(";") > header_line.count(",") else ","


def parse_csv(raw: bytes, *, max_bytes: int = MAX_FILE_BYTES, max_rows: int = MAX_ROWS,
              max_field_chars: int = MAX_FIELD_CHARS) -> list[dict[str, str]]:
    """Compatibilité v0.1 : renvoie uniquement les lignes validées."""
    return parse_catalog(raw, max_bytes=max_bytes, max_rows=max_rows, max_field_chars=max_field_chars).rows


def parse_catalog(raw: bytes, *, max_bytes: int = MAX_FILE_BYTES, max_rows: int = MAX_ROWS,
                  max_field_chars: int = MAX_FIELD_CHARS) -> ParseResult:
    if len(raw) > max_bytes:
        raise CatalogValidationError(f"Fichier trop volumineux (limite : {max_bytes // 1_000_000} Mo).")
    if b"\x00" in raw:
        raise CatalogValidationError("Le fichier contient des octets nuls : ce n'est pas un CSV texte.")
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CatalogValidationError(
            "Le CSV doit être encodé en UTF-8. Dans Excel : Enregistrer sous → « CSV UTF-8 »."
        ) from exc
    if not content.strip():
        raise CatalogValidationError("Le fichier CSV est vide.")

    delimiter = _detect_delimiter(content.splitlines()[0])
    reader = csv.reader(io.StringIO(content, newline=""), delimiter=delimiter, strict=True)
    try:
        raw_headers = next(reader)
    except csv.Error as exc:
        raise CatalogValidationError(f"En-tête illisible : {exc}.") from exc
    headers = [h.strip().lower() for h in raw_headers]
    if len(set(headers)) != len(headers):
        raise CatalogValidationError("Le fichier comporte des noms de colonnes répétés.")
    missing = [name for name in FIELDS if name not in headers]
    if missing:
        raise CatalogValidationError("Colonnes manquantes : " + ", ".join(missing))

    warnings: list[dict] = []
    extra = [h for h in headers if h not in FIELDS]
    if extra:
        warnings.append({"code": "ignored_columns", "message": "Colonnes ignorées : " + ", ".join(extra), "count": len(extra)})

    index = {name: headers.index(name) for name in FIELDS}
    rows: list[dict[str, str]] = []
    errors: list[dict] = []
    ids: dict[str, int] = {}
    normalized_prices = normalized_status = blank_lines = 0

    def error(line: int, column: str | None, message: str) -> None:
        errors.append({"line": line, "column": column, "message": message})

    try:
        for record in reader:
            line_no = reader.line_num
            if not any(cell.strip() for cell in record):
                blank_lines += 1
                continue
            if len(rows) >= max_rows:
                raise CatalogValidationError(f"Trop de lignes (limite : {max_rows:,} produits).".replace(",", " "))
            if len(record) != len(headers):
                error(line_no, None, f"{len(record)} champs au lieu de {len(headers)}.")
                continue
            data = {name: record[index[name]].strip() for name in FIELDS}
            too_long = [name for name, value in data.items() if len(value) > max_field_chars]
            if too_long:
                error(line_no, too_long[0], f"Valeur trop longue (plus de {max_field_chars} caractères).")
                continue
            for name in ("product_id", "sku", "title_fr", "title_en"):
                data[name] = _SPACES.sub(" ", data[name])

            pid = data["product_id"]
            if not pid:
                error(line_no, "product_id", "product_id obligatoire.")
            elif pid in ids:
                error(line_no, "product_id", f"product_id « {pid[:40]} » dupliqué (déjà présent ligne {ids[pid]}).")
            else:
                ids[pid] = line_no

            status = data["status"].lower()
            if status != data["status"]:
                normalized_status += 1
            if status not in STATUSES:
                error(line_no, "status", "status doit être active ou draft.")
            data["status"] = status

            if data["price_eur"]:
                price = normalize_price(data["price_eur"])
                if price is not None and price != data["price_eur"]:
                    normalized_prices += 1
                    data["price_eur"] = price
            rows.append(data)
            if len(errors) >= MAX_REPORTED_ERRORS:
                break
    except csv.Error as exc:
        error(reader.line_num, None, f"Structure CSV invalide : {exc}.")

    if errors:
        first = errors[0]
        raise CatalogValidationError(f"Ligne {first['line']} : {first['message']}", errors)
    if not rows:
        raise CatalogValidationError("Aucun produit trouvé.")

    if normalized_prices:
        warnings.append({"code": "normalized_prices", "count": normalized_prices,
                         "message": f"{normalized_prices} prix convertis au format décimal (ex. « 29,95 » → 29.95)."})
    if normalized_status:
        warnings.append({"code": "normalized_status", "count": normalized_status,
                         "message": f"{normalized_status} statuts convertis en minuscules."})
    if blank_lines:
        warnings.append({"code": "blank_lines", "count": blank_lines,
                         "message": f"{blank_lines} lignes vides ignorées."})
    return ParseResult(rows=rows, warnings=warnings, delimiter=delimiter)
