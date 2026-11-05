"""Exports CSV et PDF d'un audit.

Sécurité CSV : toute cellule commençant par = + - @ tabulation ou retour
chariot est préfixée d'une apostrophe, pour qu'Excel / LibreOffice ne
l'interprète pas comme une formule (injection de formules, CWE-1236).
Le contenu provient d'un fichier importé : il n'est jamais considéré sûr.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime

from fpdf import FPDF
from fpdf.fonts import FontFace

from .rules import CATEGORIES, PENALTIES, REGISTRY

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
SEVERITY_LABELS = {"high": "Haute", "medium": "Moyenne", "low": "Basse"}
CONFIDENCE_LABELS = {"certain": "Constat", "heuristic": "Heuristique"}


def safe_cell(value) -> str:
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(_FORMULA_PREFIXES) else text


def _csv(header: list[str], rows, delimiter: str) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=delimiter, quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    writer.writerow(header)
    for row in rows:
        writer.writerow([safe_cell(v) for v in row])
    # BOM UTF-8 : Excel sous Windows détecte ainsi l'encodage et les accents.
    return ("﻿" + buffer.getvalue()).encode("utf-8")


def issues_csv(issues: list[dict], delimiter: str = ";") -> bytes:
    header = ["product_id", "sku", "titre", "priorite", "categorie", "regle", "anomalie",
              "nature", "constat", "explication", "correction_suggeree"]
    rows = ([i["product_id"], i["sku"], i["title_fr"], SEVERITY_LABELS[i["severity"]],
             CATEGORIES[i["category"]], i["code"], i["message"], CONFIDENCE_LABELS[i["confidence"]],
             i["evidence"], i["explanation"], i["suggestion"]] for i in issues)
    return _csv(header, rows, delimiter)


def products_csv(products: list[dict], delimiter: str = ";") -> bytes:
    header = ["product_id", "sku", "title_fr", "price_eur", "status", "indice_qualite",
              "nb_anomalies", "priorite_max"]
    rows = ([p["product_id"], p["sku"], p["title_fr"], p["price_eur"], p["status"],
             "" if p["score"] is None else p["score"], p["issue_count"],
             SEVERITY_LABELS.get(p["worst_severity"], "")] for p in products)
    return _csv(header, rows, delimiter)


# --- PDF --------------------------------------------------------------------

_PDF_REPLACEMENTS = str.maketrans({
    "’": "'", "‘": "'", "“": '"', "”": '"', "…": "...", "—": "-", "–": "-",
    "œ": "oe", "Œ": "OE", "€": "EUR", "→": "->", "≥": ">=", "≤": "<=", " ": " ",
})


def _t(value) -> str:
    """Les polices PDF standard sont limitées au Latin-1 : on translittère le reste."""
    text = "" if value is None else str(value)
    return text.translate(_PDF_REPLACEMENTS).encode("latin-1", "replace").decode("latin-1")


INK = (23, 30, 28)
MUTED = (96, 105, 101)
ACCENT = (31, 92, 74)
SEVERITY_COLORS = {"high": (176, 46, 38), "medium": (180, 112, 20), "low": (70, 98, 140)}


class _Report(FPDF):
    def __init__(self, title: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.report_title = title
        self.set_auto_page_break(auto=True, margin=16)
        self.set_margins(16, 16, 16)
        self.set_title(_t(title))
        self.set_creator("CommerceOps Studio")

    def header(self):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*ACCENT)
        self.cell(0, 6, "COMMERCEOPS STUDIO", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*ACCENT)
        self.line(16, self.get_y(), 194, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 6, _t(f"{self.report_title} - page {self.page_no()}/{{nb}}"), align="R")

    def h2(self, text: str):
        self.ln(3)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(*INK)
        self.cell(0, 8, _t(text), new_x="LMARGIN", new_y="NEXT")

    def body(self, size: float = 9):
        """Texte courant des tableaux (les titres de section laissent la police en gras)."""
        self.set_font("Helvetica", "", size)
        self.set_text_color(*INK)

    def para(self, text: str, size: float = 9.5):
        self.set_font("Helvetica", "", size)
        self.set_text_color(*MUTED)
        self.multi_cell(0, 5, _t(text), new_x="LMARGIN", new_y="NEXT")


def audit_pdf(audit: dict, breakdown: dict, issues: list[dict], max_issues: int = 300) -> bytes:
    pdf = _Report(f"Rapport d'audit #{audit['id']}")
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*INK)
    pdf.multi_cell(0, 9, _t(f"Audit de catalogue - {audit['label']}"), new_x="LMARGIN", new_y="NEXT")
    created = datetime.fromisoformat(audit["created_at"]).strftime("%d/%m/%Y %H:%M UTC")
    pdf.para(f"Fichier : {audit['source_filename']} - empreinte SHA-256 {audit['source_sha256'][:16]}... - "
             f"réalisé le {created} - règles version {audit['rules_version']}", 8.5)

    pdf.h2("Indicateurs clés")
    score = "-" if audit["quality_score"] is None else f"{audit['quality_score']:.1f} / 100"
    active = audit["active_products"]
    clean = f"{round((active - audit['affected_products']) / active * 100)} %" if active else "-"
    kpis = [
        ("Produits importés", audit["total_products"]), ("Produits actifs audités", audit["active_products"]),
        ("Brouillons (non audités)", audit["draft_products"]), ("Anomalies détectées", audit["issue_count"]),
        ("Produits actifs concernés", audit["affected_products"]),
        ("Fiches actives sans anomalie", clean), ("Indice de qualité moyen par fiche", score),
    ]
    heading = FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=ACCENT)
    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(*INK)
    with pdf.table(col_widths=(70, 40), width=110, align="LEFT", first_row_as_headings=False,
                   line_height=6.5) as table:
        for label, value in kpis:
            row = table.row()
            row.cell(_t(label))
            row.cell(_t(value), align="RIGHT")

    pdf.h2("Anomalies par règle")
    pdf.body()
    titles = {r.code: r for r in REGISTRY}
    with pdf.table(col_widths=(80, 22, 28, 18), headings_style=heading, line_height=6, text_align="LEFT") as table:
        head = table.row()
        for h in ("Règle", "Priorité", "Nature", "Nombre"):
            head.cell(_t(h))
        for code, count in sorted(breakdown["issues_by_type"].items(), key=lambda kv: (-kv[1], kv[0])):
            r = titles.get(code)
            row = table.row()
            row.cell(_t(r.title if r else code))
            row.cell(_t(SEVERITY_LABELS[r.severity] if r else ""))
            row.cell(_t(CONFIDENCE_LABELS[r.confidence] if r else ""))
            row.cell(str(count), align="RIGHT")
    if not breakdown["issues_by_type"]:
        pdf.para("Aucune anomalie détectée sur les produits actifs.")

    if breakdown["priority_products"]:
        pdf.h2("Produits à corriger en priorité")
        pdf.body()
        with pdf.table(col_widths=(24, 34, 84, 18, 18), headings_style=heading, line_height=6, text_align="LEFT") as table:
            head = table.row()
            for h in ("Produit", "SKU", "Titre", "Indice", "Anom."):
                head.cell(_t(h))
            for p in breakdown["priority_products"]:
                row = table.row()
                for v in (p["product_id"], p["sku"], p["title_fr"][:60]):
                    row.cell(_t(v))
                row.cell(str(p["score"]), align="RIGHT")
                row.cell(str(p["issue_count"]), align="RIGHT")

    if issues:
        pdf.h2(f"Détail des anomalies ({min(len(issues), max_issues)} sur {len(issues)})")
        pdf.body(8)
        with pdf.table(col_widths=(20, 30, 46, 16, 66), headings_style=heading, line_height=5, text_align="LEFT") as table:
            head = table.row()
            for h in ("Produit", "SKU", "Anomalie", "Prio.", "Constat"):
                head.cell(_t(h))
            for i in issues[:max_issues]:
                row = table.row()
                row.cell(_t(i["product_id"]))
                row.cell(_t(i["sku"][:30]))
                row.cell(_t(i["message"]))
                row.cell(_t(SEVERITY_LABELS[i["severity"]]),
                         style=FontFace(color=SEVERITY_COLORS[i["severity"]], emphasis="BOLD"))
                row.cell(_t(i["evidence"]))

    pdf.h2("Méthode et limites")
    pdf.para(
        "Chaque produit actif part d'un indice de 100 points ; chaque anomalie retire "
        f"{PENALTIES['high']} points (priorité haute), {PENALTIES['medium']} (moyenne) ou "
        f"{PENALTIES['low']} (basse), sans descendre sous 0. Cet indice mesure la complétude et la "
        "cohérence internes du fichier : ce n'est ni une note SEO, ni une garantie de conversion. "
        "Les règles marquées « Heuristique » signalent un risque probable qui doit être vérifié par "
        "une personne (par exemple un prix atypique peut être légitime). Les URL d'images ne sont pas "
        "téléchargées : seule leur forme est contrôlée. Les brouillons ne sont pas audités."
    )
    return bytes(pdf.output())
