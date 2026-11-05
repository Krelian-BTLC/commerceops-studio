import csv
import io

import pytest
from fastapi.testclient import TestClient

from app.importer import FIELDS
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("COMMERCEOPS_DB", str(tmp_path / "test.sqlite"))
    return TestClient(app)


def make_csv(rows, delimiter=","):
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=FIELDS, delimiter=delimiter)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def product(product_id, sku=None, **kwargs):
    row = dict(product_id=product_id, sku=sku if sku is not None else f"SKU-{product_id}",
               title_fr=f"Lampe en lin naturel {product_id}",
               description_fr=f"Lampe en lin naturel, référence {product_id}, pour éclairer un bureau.",
               price_eur="49.90", image_url=f"https://images.example.com/{product_id}.jpg",
               title_en=f"Natural linen lamp {product_id}", status="active")
    row.update(kwargs)
    return row


def upload(client, rows, name="catalog.csv", label=None, **kw):
    data = {"label": label} if label else None
    return client.post("/api/audits", files={"file": (name, make_csv(rows, **kw), "text/csv")}, data=data)
