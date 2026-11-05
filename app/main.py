from __future__ import annotations

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from .core import (
    MAX_FILE_BYTES, CatalogValidationError, analyze, get_products,
    import_catalog, parse_csv, summary,
)

app = FastAPI(
    title="CommerceOps Studio",
    description="Audit de qualité d'un catalogue e-commerce (données autorisées uniquement).",
    version="0.1.0",
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/catalog/import", status_code=201)
async def upload_catalog(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Veuillez envoyer un fichier .csv")
    raw = await file.read(MAX_FILE_BYTES + 1)
    try:
        parsed = parse_csv(raw)
    except CatalogValidationError as exc:
        raise HTTPException(422, str(exc)) from exc
    import_catalog(parsed)
    issues = analyze(parsed)
    return {"imported": len(parsed), "issues": len(issues), "message": "Catalogue remplacé."}


@app.get("/catalog/summary")
def get_summary():
    products = get_products()
    return summary(products, analyze(products))


@app.get("/catalog/issues")
def get_issues(
    severity: str | None = Query(None, pattern="^(high|medium|low)$"),
    code: str | None = None,
):
    issues = analyze(get_products())
    if severity:
        issues = [issue for issue in issues if issue["severity"] == severity]
    if code:
        issues = [issue for issue in issues if issue["code"] == code]
    return {"count": len(issues), "items": issues}
