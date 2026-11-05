import pytest

from app.importer import CatalogValidationError, normalize_price, parse_catalog
from tests.conftest import make_csv, product

HEADER = "product_id,sku,title_fr,description_fr,price_eur,image_url,title_en,status\n"


@pytest.mark.parametrize("raw, expected", [
    ("29.95", "29.95"), ("29,95", "29.95"), ("34,90", "34.90"), ("1 234,50 €", "1234.50"),
    ("1 234,50", "1234.50"), ("1,234.50", "1234.50"), ("1.234,50", "1234.50"), ("EUR 12", "12"),
    (",5", "0.5"), ("-2", "-2"), ("0", "0"),
])
def test_normalize_price_accepts_common_formats(raw, expected):
    assert normalize_price(raw) == expected


@pytest.mark.parametrize("raw", ["NaN", "Infinity", "abc", "12.3.4", "", "1e5", "12,,5"])
def test_normalize_price_rejects_non_decimal(raw):
    assert normalize_price(raw) is None


def test_semicolon_and_french_prices_are_normalized_with_warning():
    result = parse_catalog(make_csv([product("p1", price_eur="29,95")], delimiter=";"))
    assert result.delimiter == ";"
    assert result.rows[0]["price_eur"] == "29.95"
    assert any(w["code"] == "normalized_prices" for w in result.warnings)


def test_valid_price_is_not_reported_as_normalized():
    result = parse_catalog(make_csv([product("p1", price_eur="103.90")]))
    assert result.rows[0]["price_eur"] == "103.90"
    assert result.warnings == []


def test_status_case_and_whitespace_are_normalized():
    result = parse_catalog(make_csv([product(" p1 ", status=" Active ", title_fr="Lampe   en  lin")]))
    row = result.rows[0]
    assert (row["product_id"], row["status"], row["title_fr"]) == ("p1", "active", "Lampe en lin")
    assert any(w["code"] == "normalized_status" for w in result.warnings)


def test_extra_columns_and_blank_lines_are_warnings():
    raw = (b"product_id,sku,title_fr,description_fr,price_eur,image_url,title_en,status,notes\n"
           b"p1,a,T,D,1,,x,active,interne\n,,,,,,,,\n")
    result = parse_catalog(raw)
    codes = {w["code"] for w in result.warnings}
    assert {"ignored_columns", "blank_lines"} <= codes
    assert "notes" not in result.rows[0]


def test_headers_are_case_insensitive():
    raw = HEADER.upper().encode() + b"p1,a,T,D,1,,x,active\n"
    assert parse_catalog(raw).rows[0]["product_id"] == "p1"


def test_utf8_bom_is_accepted():
    assert parse_catalog(b"\xef\xbb\xbf" + make_csv([product("p1")])).rows[0]["product_id"] == "p1"


@pytest.mark.parametrize("raw, fragment", [
    (b"", "vide"),
    (b"   \n", "vide"),
    ((HEADER + "p1,a,Tél,D,1,,x,active\n").encode("latin-1"), "UTF-8"),
    (b"product_id,sku\x00\n", "octets nuls"),
    (b"id,name\n1,x\n", "Colonnes manquantes"),
    ((HEADER.strip() + ",sku\n").encode(), "répétés"),
    (HEADER.encode(), "Aucun produit"),
])
def test_blocking_errors(raw, fragment):
    with pytest.raises(CatalogValidationError) as exc:
        parse_catalog(raw)
    assert fragment in str(exc.value)


def test_all_row_errors_are_reported_with_line_numbers():
    raw = make_csv([product("p1"), product("p1"), product("", ), product("p3", status="archived")])
    with pytest.raises(CatalogValidationError) as exc:
        parse_catalog(raw)
    lines = [(e["line"], e["column"]) for e in exc.value.errors]
    assert lines == [(3, "product_id"), (4, "product_id"), (5, "status")]
    assert "déjà présent ligne 2" in exc.value.errors[0]["message"]


def test_wrong_field_count_is_reported():
    with pytest.raises(CatalogValidationError) as exc:
        parse_catalog((HEADER + "p1,a,T,D,1,,x,active,extra\n").encode())
    assert exc.value.errors[0]["line"] == 2


def test_limits_on_size_rows_and_field_length():
    with pytest.raises(CatalogValidationError, match="volumineux"):
        parse_catalog(b"x" * 101, max_bytes=100)
    with pytest.raises(CatalogValidationError, match="Trop de lignes"):
        parse_catalog(make_csv([product(f"p{i}") for i in range(4)]), max_rows=3)
    with pytest.raises(CatalogValidationError) as exc:
        parse_catalog(make_csv([product("p1", description_fr="x" * 51)]), max_field_chars=50)
    assert exc.value.errors[0]["column"] == "description_fr"


def test_quoted_multiline_description_is_kept():
    raw = (HEADER + 'p1,a,Titre long,"Ligne 1\nLigne 2, avec virgule",1,,x,active\n').encode()
    assert parse_catalog(raw).rows[0]["description_fr"] == "Ligne 1\nLigne 2, avec virgule"
