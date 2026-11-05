import csv
import io

from tests.conftest import make_csv, product, upload


def test_import_creates_audit_with_history(client):
    first = upload(client, [product("p1"), product("p2", image_url="")], label="Audit janvier")
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["audit"]["label"] == "Audit janvier"
    assert body["issues"] == 1
    second = upload(client, [product("p1")], name="v2.csv")
    assert second.json()["audit"]["label"] == "v2"
    history = client.get("/api/audits").json()
    assert [a["id"] for a in history] == [second.json()["audit"]["id"], body["audit"]["id"]]
    assert len(history[0]["source_sha256"]) == 64


def test_rejected_import_returns_structured_errors_and_keeps_history(client):
    upload(client, [product("p1")])
    response = upload(client, [product("p1"), product("p1")])
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "invalid_catalog"
    assert body["errors"][0]["line"] == 3
    assert len(client.get("/api/audits").json()) == 1


def test_upload_validation(client):
    bad_ext = client.post("/api/audits", files={"file": ("c.xlsx", b"x", "text/csv")})
    assert (bad_ext.status_code, bad_ext.json()["code"]) == (400, "invalid_extension")
    bad_type = client.post("/api/audits", files={"file": ("c.csv", make_csv([product("p1")]), "image/png")})
    assert bad_type.status_code == 415
    windows_type = client.post("/api/audits", files={"file": ("c.csv", make_csv([product("p1")]), "application/vnd.ms-excel")})
    assert windows_type.status_code == 201


def test_file_size_limit(client, monkeypatch):
    monkeypatch.setenv("COMMERCEOPS_MAX_FILE_BYTES", "500")
    response = upload(client, [product(f"p{i}") for i in range(20)])
    assert response.status_code == 413
    assert "volumineux" in response.json()["detail"]


def test_filename_is_sanitized(client):
    response = client.post("/api/audits", files={"file": ("..\\..\\<script>x.csv", make_csv([product("p1")]), "text/csv")})
    assert response.status_code == 201
    name = response.json()["audit"]["source_filename"]
    assert "/" not in name and "\\" not in name and "<" not in name and name.endswith(".csv")


def test_audit_detail_and_breakdown(client):
    audit = upload(client, [product("p1", sku=""), product("p2", image_url=""), product("p3", status="draft")]).json()["audit"]
    detail = client.get(f"/api/audits/{audit['id']}").json()
    assert detail["issues_by_type"] == {"missing_image": 1, "missing_sku": 1}
    assert detail["issues_by_category"] == {"identification": 1, "media": 1}
    assert detail["draft_products"] == 1
    assert detail["priority_products"][0]["product_id"] == "p1"
    assert detail["quality_score"] == round((70 + 88) / 2, 1)
    assert client.get("/api/audits/999").status_code == 404


def test_products_search_filter_sort_paginate(client):
    rows = [product(f"p{i:02d}", price_eur=f"{10 + i}.00") for i in range(30)]
    rows[3]["image_url"] = ""
    rows[4]["sku"] = ""
    rows[5]["status"] = "draft"
    audit_id = upload(client, rows).json()["audit"]["id"]
    url = f"/api/audits/{audit_id}/products"
    page = client.get(url, params={"page_size": 10, "page": 3}).json()
    assert (page["total"], len(page["items"])) == (30, 10)
    worst = client.get(url, params={"sort": "score"}).json()["items"]
    assert [p["product_id"] for p in worst[:2]] == ["p04", "p03"]
    last = client.get(url, params={"sort": "score", "page": 2}).json()["items"]
    assert last[-1]["product_id"] == "p05"  # brouillon sans score en dernier
    assert client.get(url, params={"has_issues": True}).json()["total"] == 2
    assert client.get(url, params={"severity": "high"}).json()["items"][0]["product_id"] == "p04"
    assert client.get(url, params={"status": "draft"}).json()["total"] == 1
    assert client.get(url, params={"q": "p1"}).json()["total"] == 10
    assert client.get(url, params={"q": "%"}).json()["total"] == 0  # caractère joker échappé
    prices = [p["price_eur"] for p in client.get(url, params={"sort": "-price", "page_size": 3}).json()["items"]]
    assert prices == ["39.00", "38.00", "37.00"]
    assert client.get(url, params={"sort": "price; DROP TABLE audits"}).status_code == 422


def test_product_detail_with_score_breakdown(client):
    audit_id = upload(client, [product("a/b", sku="", title_en="")]).json()["audit"]["id"]
    detail = client.get(f"/api/audits/{audit_id}/products/a/b").json()
    assert detail["score"] == 100 - 30 - 4
    assert [i["code"] for i in detail["issues"]] == ["missing_sku", "missing_title_en"]
    assert sum(p["penalty"] for p in detail["score_breakdown"]) == 34
    assert client.get(f"/api/audits/{audit_id}/products/nope").status_code == 404


def test_issue_filters(client):
    audit_id = upload(client, [product("p1", sku="", title_en=""), product("p2", image_url="")]).json()["audit"]["id"]
    url = f"/api/audits/{audit_id}/issues"
    assert client.get(url).json()["total"] == 3
    assert client.get(url, params={"severity": "low"}).json()["items"][0]["code"] == "missing_title_en"
    assert client.get(url, params={"category": "media"}).json()["total"] == 1
    assert client.get(url, params={"confidence": "certain"}).json()["total"] == 3
    assert client.get(url, params={"q": "p2"}).json()["total"] == 1
    assert client.get(url, params={"code": "unknown_rule"}).status_code == 422
    assert client.get(url, params={"page_size": 1, "page": 3}).json()["items"][0]["product_id"] == "p1"


def test_issues_csv_export_respects_filters_and_blocks_formulas(client):
    rows = [product("p1", sku='=HYPERLINK("http://evil")', title_fr="+Lampe en lin", title_en=""),
            product("p2", image_url="")]
    audit_id = upload(client, rows).json()["audit"]["id"]
    response = client.get(f"/api/audits/{audit_id}/exports/issues.csv", params={"severity": "low"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    text = response.content.decode("utf-8-sig")
    records = list(csv.reader(io.StringIO(text), delimiter=";"))
    assert len(records) == 2  # en-tête + la seule anomalie de priorité basse
    assert records[1][1].startswith("'=")
    assert records[1][2].startswith("'+")
    comma = client.get(f"/api/audits/{audit_id}/exports/issues.csv", params={"delimiter": "comma"})
    assert comma.content.decode("utf-8-sig").splitlines()[0].startswith("product_id,sku")


def test_products_csv_and_pdf_exports(client):
    audit_id = upload(client, [product("p1", image_url="", title_fr="Lampe œuvre — 50 €"), product("p2")]).json()["audit"]["id"]
    products = client.get(f"/api/audits/{audit_id}/exports/products.csv").content.decode("utf-8-sig").splitlines()
    assert len(products) == 3
    pdf = client.get(f"/api/audits/{audit_id}/exports/report.pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")
    assert client.get("/api/audits/999/exports/report.pdf").status_code == 404


def test_compare_before_after(client):
    before = upload(client, [product("p1", sku=""), product("p2", image_url=""), product("p3")]).json()["audit"]["id"]
    after = upload(client, [product("p1"), product("p2", image_url=""), product("p3", title_en=""), product("p4")]).json()["audit"]["id"]
    result = client.get("/api/compare", params={"base": before, "target": after}).json()
    assert result["counts"] == {"resolved": 1, "new": 1, "persisting": 1}
    assert result["resolved"][0]["code"] == "missing_sku"
    assert result["new"][0]["code"] == "missing_title_en"
    assert result["products"] == {"added": 1, "removed": 0, "common": 3}
    assert result["metrics"]["issue_count"] == {"before": 2, "after": 2, "delta": 0}
    assert result["issue_change_percent"] == 0
    assert result["same_rules_version"] is True
    assert client.get("/api/compare", params={"base": before, "target": 999}).status_code == 404


def test_delete_audit(client):
    audit_id = upload(client, [product("p1", sku="")]).json()["audit"]["id"]
    assert client.delete(f"/api/audits/{audit_id}").status_code == 204
    assert client.get(f"/api/audits/{audit_id}").status_code == 404
    assert client.delete(f"/api/audits/{audit_id}").status_code == 404
    assert client.get("/catalog/summary").json()["total_products"] == 0


def test_demo_scenario_is_reproducible(client):
    response = client.post("/api/demo")
    assert response.status_code == 201, response.text
    demo = response.json()
    before, after = demo["before"], demo["after"]
    assert before["total_products"] == 150 and after["total_products"] == 152
    # Chiffres mesurés sur les catalogues générés (demo/generate_catalogs.py).
    assert (before["issue_count"], after["issue_count"]) == (55, 9)
    assert before["issues_by_severity"]["high"] == 11 and after["issues_by_severity"]["high"] == 0
    assert any(w["code"] == "normalized_prices" for w in before["warnings"])
    comparison = client.get("/api/compare", params={"base": before["id"], "target": after["id"]}).json()
    assert comparison["counts"]["resolved"] > 40
    assert comparison["counts"]["new"] > 0


def test_demo_can_be_disabled(client, monkeypatch):
    monkeypatch.setenv("COMMERCEOPS_DEMO_ENABLED", "false")
    assert client.post("/api/demo").status_code == 404


def test_rules_catalog_and_openapi(client):
    rules = client.get("/api/rules").json()
    assert rules["penalties"] == {"high": 30, "medium": 12, "low": 4}
    assert any(r["confidence"] == "heuristic" for r in rules["rules"])
    spec = client.get("/openapi.json").json()
    assert spec["info"]["version"] == "0.2.0"
    for path in ("/api/audits", "/api/compare", "/api/audits/{audit_id}/exports/report.pdf"):
        assert path in spec["paths"]


def test_security_headers_and_error_format(client):
    response = client.get("/api/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert response.headers["x-request-id"]
    error = client.get("/api/audits/abc").json()
    assert error["code"] == "validation_error" and error["errors"]


def test_cors_allows_only_configured_origins(client):
    allowed = client.options("/api/audits", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"
    denied = client.options("/api/audits", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in denied.headers


def test_logs_do_not_contain_catalog_content(client, caplog):
    caplog.set_level("INFO", logger="commerceops")
    upload(client, [product("p1", title_fr="Secret produit confidentiel")], name="client-confidentiel.csv")
    assert "audit créé" in caplog.text
    assert "confidentiel" not in caplog.text


def test_legacy_routes_still_work(client):
    response = client.post("/catalog/import", files={"file": ("c.csv", make_csv([product("p1", sku="")]), "text/csv")})
    assert response.status_code == 201
    assert client.get("/catalog/issues", params={"severity": "high"}).json()["count"] == 1
    assert client.get("/catalog/summary").json()["issues_by_type"] == {"missing_sku": 1}
