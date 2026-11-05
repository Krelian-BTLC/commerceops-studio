"""Un test positif et un test négatif par règle métier."""
import pytest

from app.rules import PENALTIES, REGISTRY, product_score, run_rules
from tests.conftest import product


def codes(products, code):
    return sorted(i["product_id"] for i in run_rules(products) if i["code"] == code)


def catalog(n=10, **overrides):
    """Catalogue sain de n produits, avec des prix variés autour de 50 €."""
    rows = [product(f"p{i}", price_eur=f"{40 + i}.90") for i in range(n)]
    for pid, fields in overrides.items():
        rows[int(pid[1:])].update(fields)
    return rows


def test_healthy_catalog_has_no_issue():
    assert run_rules(catalog()) == []


@pytest.mark.parametrize("code, bad, good", [
    ("missing_sku", {"sku": ""}, {"sku": "A-1"}),
    ("invalid_price", {"price_eur": "-3"}, {"price_eur": "0.50"}),
    ("missing_title_fr", {"title_fr": ""}, {"title_fr": "Vase en grès"}),
    ("short_title_fr", {"title_fr": "Vase"}, {"title_fr": "Vase en grès"}),
    ("long_title_fr", {"title_fr": "V" * 151}, {"title_fr": "V" * 150}),
    ("missing_description_fr", {"description_fr": ""}, {"description_fr": "Une description complète et utile du vase."}),
    ("short_description_fr", {"description_fr": "Joli vase."}, {"description_fr": "Vase en grès émaillé, 25 cm, lavable en machine."}),
    ("placeholder_text", {"description_fr": "Lorem ipsum dolor sit amet consectetur."}, {"description_fr": "Vase lorem-free, texte final et complet."}),
    ("placeholder_text", {"title_fr": "Vase TODO"}, {"title_fr": "Vase Todorov"}),
    ("html_in_description", {"description_fr": "<b>Vase</b> en grès émaillé pour bouquet."}, {"description_fr": "Vase 3 < 5 cm en grès émaillé pour bouquet."}),
    ("description_equals_title", {"title_fr": "Vase en grès", "description_fr": "vase  en GRÈS"}, {"title_fr": "Vase en grès"}),
    ("missing_image", {"image_url": ""}, {"image_url": "https://cdn.example.com/a.jpg"}),
    ("invalid_image_url", {"image_url": "javascript:alert(1)"}, {"image_url": "https://cdn.example.com/a.jpg"}),
    ("invalid_image_url", {"image_url": "images/a.jpg"}, {"image_url": "http://cdn.example.com/a.jpg"}),
    ("invalid_image_url", {"image_url": "https://cdn.example.com/a b.jpg"}, {"image_url": "https://cdn.example.com/a%20b.jpg"}),
    ("insecure_image_url", {"image_url": "http://cdn.example.com/a.jpg"}, {"image_url": "https://cdn.example.com/a.jpg"}),
    ("missing_title_en", {"title_en": ""}, {"title_en": "Stoneware vase"}),
    ("untranslated_title_en", {"title_fr": "Vase en grès", "title_en": "vase en grès"}, {"title_fr": "Vase en grès", "title_en": "Stoneware vase"}),
])
def test_rule_positive_and_negative(code, bad, good):
    assert codes(catalog(p0=bad), code) == ["p0"]
    assert codes(catalog(p0=good), code) == []


def test_untranslated_single_word_brand_is_not_flagged():
    # Un nom de marque d'un seul mot est souvent identique dans les deux langues.
    assert codes(catalog(p0={"title_fr": "Ardoise", "title_en": "Ardoise"}), "untranslated_title_en") == []


@pytest.mark.parametrize("value", ["", "0", "-1", "abc", "NaN", "Infinity"])
def test_invalid_price_values(value):
    assert codes(catalog(p0={"price_eur": value}), "invalid_price") == ["p0"]


def test_duplicate_sku_is_case_insensitive_and_flags_every_copy():
    rows = catalog(p0={"sku": "AB-1"}, p1={"sku": "ab-1"})
    assert codes(rows, "duplicate_sku") == ["p0", "p1"]


def test_empty_sku_is_not_a_duplicate():
    assert codes(catalog(p0={"sku": ""}, p1={"sku": ""}), "duplicate_sku") == []


def test_duplicate_description_requires_20_chars():
    long = {"description_fr": "Texte modèle répété sur plusieurs fiches."}
    assert codes(catalog(p0=long, p1=long), "duplicate_description_fr") == ["p0", "p1"]
    short = {"description_fr": "Vase en grès."}
    assert codes(catalog(p0=short, p1=short), "duplicate_description_fr") == []


def test_duplicate_title():
    same = {"title_fr": "Vase en grès sauge"}
    assert codes(catalog(p0=same, p1=dict(title_fr="vase en  grès SAUGE")), "duplicate_title_fr") == ["p0", "p1"]


def test_price_outlier_uses_median_and_needs_enough_prices():
    assert codes(catalog(p0={"price_eur": "4990"}), "price_outlier") == ["p0"]
    assert codes(catalog(p0={"price_eur": "4.50"}), "price_outlier") == ["p0"]
    assert codes(catalog(p0={"price_eur": "120"}), "price_outlier") == []
    # Moins de 8 prix valides : la médiane n'est pas jugée représentative.
    assert codes(catalog(n=5, p0={"price_eur": "4990"}), "price_outlier") == []


def test_drafts_are_not_audited_and_do_not_count_as_duplicates():
    rows = catalog(p0={"sku": "X"}, p1={"sku": "X", "status": "draft", "image_url": ""})
    assert codes(rows, "duplicate_sku") == []
    assert all(i["product_id"] != "p1" for i in run_rules(rows))


def test_issue_payload_is_explainable():
    issue = run_rules(catalog(p0={"image_url": ""}))[0]
    for key in ("explanation", "suggestion", "evidence", "confidence", "severity", "category", "field"):
        assert issue[key]


def test_every_rule_is_documented_and_heuristics_are_labelled():
    assert len({r.code for r in REGISTRY}) == len(REGISTRY)
    for r in REGISTRY:
        assert r.explanation and r.suggestion and r.title
    heuristics = {r.code for r in REGISTRY if r.confidence == "heuristic"}
    assert {"price_outlier", "duplicate_description_fr", "untranslated_title_en", "placeholder_text"} <= heuristics
    assert "missing_sku" not in heuristics


def test_issues_are_sorted_by_severity():
    issues = run_rules(catalog(p0={"title_en": ""}, p1={"sku": ""}, p2={"image_url": ""}))
    assert [i["severity"] for i in issues] == ["high", "medium", "low"]


def test_product_score():
    assert product_score([]) == 100
    assert product_score([{"severity": "high"}, {"severity": "low"}]) == 100 - PENALTIES["high"] - PENALTIES["low"]
    assert product_score([{"severity": "high"}] * 5) == 0
