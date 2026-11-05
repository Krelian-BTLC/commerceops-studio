"""Moteur de règles d'audit de catalogue.

Ajouter une règle = écrire une fonction décorée par ``@rule(...)`` qui reçoit
un produit et le contexte du catalogue, et renvoie une **preuve** (texte court)
lorsque l'anomalie est constatée, sinon ``None``.

Chaque règle déclare sa ``confidence`` :
- ``certain`` : constat factuel (champ vide, doublon exact, prix non numérique) ;
- ``heuristic`` : signal probable qui demande une vérification humaine
  (prix atypique, texte générique, traduction identique...). L'interface et
  les exports l'indiquent explicitement.

Aucune règle ne fait de requête réseau : les URLs d'images ne sont jamais
téléchargées, seule leur forme est contrôlée.
"""
from __future__ import annotations

import re
import statistics
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

RULES_VERSION = "2026.11-2"
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
# Pénalités de l'indice de qualité (0-100). Volontairement simples et publiées
# via GET /api/rules pour que chaque point retiré soit explicable.
# Une anomalie haute (vente ou stock compromis) fait tomber la fiche à 50, « fragile ».
PENALTIES = {"high": 50, "medium": 20, "low": 5}
CATEGORIES = {
    "identification": "Identification",
    "content": "Contenu",
    "pricing": "Prix",
    "media": "Médias",
    "translation": "Traduction",
}

Product = dict[str, str]


@dataclass(frozen=True)
class Rule:
    code: str
    severity: str
    category: str
    field: str
    title: str
    explanation: str
    suggestion: str
    confidence: str
    check: Callable[[Product, Context], str | None]

    def describe(self) -> dict:
        return {
            "code": self.code, "severity": self.severity, "category": self.category,
            "category_label": CATEGORIES[self.category], "field": self.field,
            "title": self.title, "explanation": self.explanation,
            "suggestion": self.suggestion, "confidence": self.confidence,
            "penalty": PENALTIES[self.severity],
        }


REGISTRY: list[Rule] = []


def rule(code: str, *, severity: str, category: str, field: str, title: str,
         explanation: str, suggestion: str, confidence: str = "certain"):
    assert severity in PENALTIES and category in CATEGORIES and confidence in ("certain", "heuristic")

    def register(func: Callable[[Product, Context], str | None]):
        if any(r.code == code for r in REGISTRY):
            raise ValueError(f"Règle {code} déjà déclarée")
        REGISTRY.append(Rule(code, severity, category, field, title, explanation, suggestion, confidence, func))
        return func
    return register


def _key(text: str) -> str:
    return " ".join(text.casefold().split())


def parse_price(value: str) -> Decimal | None:
    try:
        price = Decimal(value)
    except InvalidOperation:
        return None
    return price if price.is_finite() else None


def price_is_invalid(value: str) -> bool:
    price = parse_price(value)
    return price is None or price <= 0


class Context:
    """Statistiques calculées une fois sur les produits actifs."""

    MIN_PRICES_FOR_OUTLIERS = 8
    MIN_DESCRIPTION_FOR_DUPLICATE = 20

    def __init__(self, active: list[Product]):
        self.sku_counts = Counter(p["sku"].casefold() for p in active if p["sku"])
        self.description_counts = Counter(
            _key(p["description_fr"]) for p in active
            if len(p["description_fr"].strip()) >= self.MIN_DESCRIPTION_FOR_DUPLICATE
        )
        self.title_counts = Counter(_key(p["title_fr"]) for p in active if p["title_fr"])
        prices = [float(p) for p in (parse_price(x["price_eur"]) for x in active) if p is not None and p > 0]
        self.median_price = statistics.median(prices) if len(prices) >= self.MIN_PRICES_FOR_OUTLIERS else None


def _short(text: str, limit: int = 60) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


# --- Identification ---------------------------------------------------------

@rule("missing_sku", severity="high", category="identification", field="sku",
      title="SKU manquant",
      explanation="Sans référence (SKU), le produit ne peut pas être rapproché du stock, des commandes ou d'un fournisseur.",
      suggestion="Attribuer un SKU unique selon la convention de nommage de la boutique.")
def _missing_sku(p, ctx):
    return "Champ sku vide" if not p["sku"] else None


@rule("duplicate_sku", severity="high", category="identification", field="sku",
      title="SKU utilisé par plusieurs produits",
      explanation="Un même SKU partagé par plusieurs fiches fausse le suivi de stock et peut provoquer des erreurs d'expédition.",
      suggestion="Vérifier s'il s'agit de variantes d'un même produit ; sinon attribuer un SKU distinct à chaque fiche.")
def _duplicate_sku(p, ctx):
    count = ctx.sku_counts[p["sku"].casefold()] if p["sku"] else 0
    return f"« {_short(p['sku'], 30)} » apparaît sur {count} produits actifs" if count > 1 else None


# --- Prix -------------------------------------------------------------------

@rule("invalid_price", severity="high", category="pricing", field="price_eur",
      title="Prix invalide ou non positif",
      explanation="Le prix est vide, non numérique ou inférieur ou égal à zéro : le produit risque d'être vendu gratuitement ou d'être refusé par la plateforme.",
      suggestion="Saisir un prix TTC strictement positif au format décimal (ex. 29.95).")
def _invalid_price(p, ctx):
    return f"Valeur reçue : « {_short(p['price_eur'], 20) or '(vide)'} »" if price_is_invalid(p["price_eur"]) else None


@rule("price_outlier", severity="medium", category="pricing", field="price_eur",
      title="Prix atypique par rapport au catalogue",
      explanation="Le prix est plus de 10 fois supérieur ou inférieur au prix médian des produits actifs. C'est souvent une erreur de saisie (virgule déplacée, centimes), mais cela peut être légitime pour un produit premium ou un accessoire.",
      suggestion="Confirmer le prix avec le responsable catalogue ; corriger s'il s'agit d'une erreur de saisie.",
      confidence="heuristic")
def _price_outlier(p, ctx):
    price = parse_price(p["price_eur"])
    if ctx.median_price is None or price is None or price <= 0:
        return None
    ratio = float(price) / ctx.median_price
    if ratio >= 10 or ratio <= 0.1:
        return f"{price} € pour un prix médian de {ctx.median_price:.2f} €"
    return None


# --- Contenu ----------------------------------------------------------------

@rule("missing_title_fr", severity="high", category="content", field="title_fr",
      title="Titre français manquant",
      explanation="Une fiche sans titre est inexploitable pour le client comme pour les moteurs de recherche.",
      suggestion="Rédiger un titre descriptif : type de produit, caractéristique principale, variante.")
def _missing_title(p, ctx):
    return "Champ title_fr vide" if not p["title_fr"] else None


@rule("short_title_fr", severity="low", category="content", field="title_fr",
      title="Titre très court",
      explanation="Un titre de moins de 10 caractères décrit rarement le produit de façon suffisante.",
      suggestion="Compléter le titre avec le type de produit et sa caractéristique distinctive.",
      confidence="heuristic")
def _short_title(p, ctx):
    n = len(p["title_fr"])
    return f"{n} caractères : « {p['title_fr']} »" if 0 < n < 10 else None


@rule("long_title_fr", severity="low", category="content", field="title_fr",
      title="Titre très long",
      explanation="Au-delà de 150 caractères, le titre est généralement tronqué dans les listes de produits et les résultats de recherche.",
      suggestion="Déplacer les détails secondaires dans la description.",
      confidence="heuristic")
def _long_title(p, ctx):
    n = len(p["title_fr"])
    return f"{n} caractères" if n > 150 else None


@rule("duplicate_title_fr", severity="low", category="content", field="title_fr",
      title="Titre identique à d'autres produits",
      explanation="Plusieurs fiches portent exactement le même titre : le client ne peut pas les distinguer. Peut être voulu pour des variantes non regroupées.",
      suggestion="Ajouter la variante (couleur, taille, matière) au titre ou regrouper les fiches en variantes.",
      confidence="heuristic")
def _duplicate_title(p, ctx):
    count = ctx.title_counts[_key(p["title_fr"])] if p["title_fr"] else 0
    return f"Titre partagé par {count} produits actifs" if count > 1 else None


@rule("missing_description_fr", severity="medium", category="content", field="description_fr",
      title="Description française manquante",
      explanation="Sans description, le client manque d'informations pour acheter et la fiche est moins bien référencée.",
      suggestion="Rédiger une description présentant usage, matière, dimensions et entretien.")
def _missing_description(p, ctx):
    return "Champ description_fr vide" if not p["description_fr"] else None


@rule("short_description_fr", severity="low", category="content", field="description_fr",
      title="Description très courte",
      explanation="Une description de moins de 40 caractères apporte rarement une information utile à l'achat.",
      suggestion="Enrichir la description avec les caractéristiques et bénéfices du produit.",
      confidence="heuristic")
def _short_description(p, ctx):
    n = len(p["description_fr"])
    return f"{n} caractères" if 0 < n < 40 else None


@rule("duplicate_description_fr", severity="medium", category="content", field="description_fr",
      title="Description reprise sur plusieurs produits",
      explanation="Une description identique sur plusieurs fiches (texte modèle) n'aide pas le client à choisir et peut être considérée comme du contenu dupliqué par les moteurs de recherche.",
      suggestion="Personnaliser chaque description avec les caractéristiques propres au produit.",
      confidence="heuristic")
def _duplicate_description(p, ctx):
    text = p["description_fr"].strip()
    if len(text) < Context.MIN_DESCRIPTION_FOR_DUPLICATE:
        return None
    count = ctx.description_counts[_key(text)]
    return f"Texte identique sur {count} produits actifs" if count > 1 else None


_PLACEHOLDER = re.compile(r"(?i)\b(lorem ipsum|todo|tbd|à compléter|a completer|texte à venir|xxx+|placeholder)\b")


@rule("placeholder_text", severity="medium", category="content", field="description_fr",
      title="Texte provisoire détecté",
      explanation="Le titre ou la description contient un marqueur de texte provisoire (lorem ipsum, TODO, « à compléter »...) qui ne devrait pas être publié.",
      suggestion="Remplacer le texte provisoire par le contenu définitif.",
      confidence="heuristic")
def _placeholder(p, ctx):
    for name in ("title_fr", "description_fr"):
        match = _PLACEHOLDER.search(p[name])
        if match:
            return f"« {match.group(0)} » dans {name}"
    return None


_HTML = re.compile(r"<\s*/?\s*[a-zA-Z][^>]*>|&(nbsp|amp|lt|gt|quot|#\d+);")


@rule("html_in_description", severity="low", category="content", field="description_fr",
      title="Balises HTML dans la description",
      explanation="Des balises ou entités HTML brutes risquent de s'afficher telles quelles selon la plateforme d'import.",
      suggestion="Vérifier le rendu sur la boutique ; nettoyer le balisage si la plateforme attend du texte brut.",
      confidence="heuristic")
def _html(p, ctx):
    match = _HTML.search(p["description_fr"])
    return f"Balisage trouvé : « {_short(match.group(0), 30)} »" if match else None


@rule("description_equals_title", severity="low", category="content", field="description_fr",
      title="Description identique au titre",
      explanation="La description se contente de répéter le titre et n'apporte aucune information.",
      suggestion="Rédiger une description qui complète le titre.")
def _description_equals_title(p, ctx):
    return "Description = titre" if p["description_fr"] and _key(p["description_fr"]) == _key(p["title_fr"]) else None


# --- Médias -----------------------------------------------------------------

@rule("missing_image", severity="medium", category="media", field="image_url",
      title="Image produit manquante",
      explanation="Une fiche sans visuel convertit nettement moins et peut être refusée par certains comparateurs.",
      suggestion="Ajouter au moins une photo du produit (URL HTTPS).")
def _missing_image(p, ctx):
    return "Champ image_url vide" if not p["image_url"] else None


def _url_parts(value: str):
    try:
        return urlsplit(value)
    except ValueError:
        return None


@rule("invalid_image_url", severity="medium", category="media", field="image_url",
      title="URL d'image invalide",
      explanation="La valeur n'est pas une URL HTTP(S) bien formée (schéma absent, chemin local, protocole non web) : l'image ne pourra pas être affichée.",
      suggestion="Renseigner une URL absolue commençant par https://.")
def _invalid_image_url(p, ctx):
    if not p["image_url"]:
        return None
    parts = _url_parts(p["image_url"])
    if parts is None or parts.scheme.lower() not in ("http", "https") or not parts.netloc or " " in p["image_url"]:
        return f"Valeur reçue : « {_short(p['image_url'], 50)} »"
    return None


@rule("insecure_image_url", severity="low", category="media", field="image_url",
      title="Image servie en HTTP non chiffré",
      explanation="Une image en http:// sur une boutique en HTTPS peut être bloquée par le navigateur (contenu mixte).",
      suggestion="Utiliser l'URL https:// de l'image si l'hébergeur la propose.")
def _insecure_image(p, ctx):
    parts = _url_parts(p["image_url"]) if p["image_url"] else None
    return "URL en http://" if parts is not None and parts.scheme.lower() == "http" and parts.netloc else None


# --- Traduction -------------------------------------------------------------

@rule("missing_title_en", severity="low", category="translation", field="title_en",
      title="Traduction anglaise du titre manquante",
      explanation="Le titre n'est pas traduit : la fiche s'affichera en français, ou vide, sur la version anglaise de la boutique.",
      suggestion="Traduire le titre ; faire relire les traductions automatiques.")
def _missing_title_en(p, ctx):
    return "Champ title_en vide" if not p["title_en"] else None


@rule("untranslated_title_en", severity="low", category="translation", field="title_en",
      title="Titre anglais identique au français",
      explanation="Le titre anglais reprend mot pour mot le titre français. C'est normal pour un nom de marque ou de modèle, mais c'est souvent une traduction oubliée.",
      suggestion="Vérifier si une traduction est nécessaire.",
      confidence="heuristic")
def _untranslated(p, ctx):
    if p["title_en"] and p["title_fr"] and _key(p["title_en"]) == _key(p["title_fr"]) and len(p["title_fr"].split()) > 1:
        return f"« {_short(p['title_en'], 40)} » dans les deux langues"
    return None


# --- Exécution --------------------------------------------------------------

def run_rules(products: list[Product]) -> list[dict]:
    """Applique toutes les règles aux produits actifs (les brouillons sont exclus)."""
    active = [p for p in products if p["status"] == "active"]
    ctx = Context(active)
    issues = []
    for product in active:
        for r in REGISTRY:
            evidence = r.check(product, ctx)
            if evidence is not None:
                issues.append({
                    "product_id": product["product_id"], "sku": product["sku"],
                    "title_fr": product["title_fr"], "code": r.code, "severity": r.severity,
                    "category": r.category, "field": r.field, "message": r.title,
                    "explanation": r.explanation, "suggestion": r.suggestion,
                    "confidence": r.confidence, "evidence": evidence,
                })
    return sorted(issues, key=lambda i: (SEVERITY_ORDER[i["severity"]], i["product_id"], i["code"]))


def product_score(issues: list[dict]) -> int:
    return max(0, 100 - sum(PENALTIES[i["severity"]] for i in issues))


def describe_rules() -> list[dict]:
    return [r.describe() for r in REGISTRY]
