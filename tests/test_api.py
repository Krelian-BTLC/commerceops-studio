import csv
import io

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core import parse_csv, CatalogValidationError, FIELDS


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("COMMERCEOPS_DB", str(tmp_path / "test.sqlite"))
    return TestClient(app)


def make_csv(rows):
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def product(product_id, sku, **kwargs):
    row = dict(product_id=product_id, sku=sku, title_fr="Un titre", description_fr="Une description suffisamment longue", price_eur="12.95", image_url="https://example.org/image.jpg", title_en="A title", status="active")
    row.update(kwargs)
    return row


def test_empty_catalog(client):
    assert client.get("/catalog/summary").json()["total_products"] == 0
    assert client.get("/health").json() == {"status": "ok"}


def test_import_and_issue_detection(client):
    rows = [
        product("p1", "dup", title_en="", image_url=""),
        product("p2", "dup", price_eur="-2"),
        product("p3", "draftsku", status="draft", title_fr="", price_eur="invalid"),
    ]
    response = client.post("/catalog/import", files={"file": ("catalog.csv", make_csv(rows), "text/csv")})
    assert response.status_code == 201, response.text
    summary = client.get("/catalog/summary").json()
    assert summary["total_products"] == 3
    assert summary["active_products"] == 2
    assert summary["draft_products"] == 1
    assert summary["affected_active_products"] == 2
    types = summary["issues_by_type"]
    assert types["duplicate_sku"] == 2
    assert types["invalid_price"] == 1
    assert types["missing_image"] == 1
    assert types["missing_title_en"] == 1
    assert types["duplicate_description_fr"] == 2
    high = client.get("/catalog/issues", params={"severity": "high"}).json()
    assert high["count"] == 3
    assert {issue["severity"] for issue in high["items"]} == {"high"}
    assert client.get("/catalog/issues", params={"code": "missing_image"}).json()["count"] == 1


def test_bad_csv_does_not_destroy_previous_catalog(client):
    first = client.post("/catalog/import", files={"file": ("good.csv", make_csv([product("p1", "a")]), "text/csv")})
    assert first.status_code == 201
    malformed = b"product_id,sku\np2,c\n"
    response = client.post("/catalog/import", files={"file": ("bad.csv", malformed, "text/csv")})
    assert response.status_code == 422
    assert "Colonnes manquantes" in response.json()["detail"]
    assert client.get("/catalog/summary").json()["total_products"] == 1


def test_reject_duplicate_ids(client):
    response = client.post("/catalog/import", files={"file": ("catalog.csv", make_csv([product("p1", "a"), product("p1", "b")]), "text/csv")})
    assert response.status_code == 422


def test_price_anomaly_edge_cases(client):
    rows = [product("p1", "p1", price_eur="NaN"), product("p2", "p2", price_eur="Infinity"), product("p3", "p3", price_eur="0")]
    response = client.post("/catalog/import", files={"file": ("catalog.csv", make_csv(rows), "text/csv")})
    assert response.status_code == 201
    assert client.get("/catalog/issues", params={"code": "invalid_price"}).json()["count"] == 3


def test_missing_headers():
    with pytest.raises(CatalogValidationError):
        parse_csv(b"id,name\n123,example\n")
