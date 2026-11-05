from __future__ import annotations

import hashlib
import logging
import re
import time
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__, storage
from .config import get_settings
from .exports import audit_pdf, issues_csv, products_csv
from .importer import CatalogValidationError, parse_catalog
from .rules import CATEGORIES, PENALTIES, REGISTRY, RULES_VERSION, describe_rules
from .schemas import (
    Audit,
    AuditDetail,
    Comparison,
    DemoResult,
    ErrorResponse,
    ImportResult,
    IssuePage,
    ProductDetail,
    ProductPage,
    RulesCatalog,
)

settings = get_settings()
logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("commerceops")

app = FastAPI(
    title="CommerceOps Studio API",
    description=(
        "Audit de qualité d'un catalogue e-commerce. Usage prévu : poste local ou réseau de confiance, "
        "avec des données fictives ou explicitement autorisées. Aucune URL du catalogue n'est appelée."
    ),
    version=__version__,
    responses={422: {"model": ErrorResponse}},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
    expose_headers=["Content-Disposition", "X-Request-ID"],
)

_DOC_PATHS = ("/docs", "/redoc", "/openapi.json")
_CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; font-src 'self'; "
        "connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = uuid.uuid4().hex[:12]
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    if not request.url.path.startswith(_DOC_PATHS):
        response.headers["Content-Security-Policy"] = _CSP
    # Seul le chemin est journalisé : ni paramètres de recherche, ni contenu de fichier.
    log.info("%s %s %s %.0fms rid=%s", request.method, request.url.path, response.status_code,
             (time.perf_counter() - started) * 1000, request_id)
    return response


# --- Erreurs homogènes : {"detail", "code", "errors"} --------------------------

class ApiError(HTTPException):
    def __init__(self, status: int, code: str, detail: str, errors: list | None = None):
        super().__init__(status, detail)
        self.code, self.errors = code, errors or []


_STATUS_CODES = {400: "bad_request", 404: "not_found", 405: "method_not_allowed", 413: "file_too_large",
                 415: "unsupported_media_type", 422: "invalid_request"}


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    code = getattr(exc, "code", None) or _STATUS_CODES.get(exc.status_code, "error")
    detail = exc.detail if isinstance(exc.detail, str) else "Erreur."
    return JSONResponse({"detail": detail, "code": code, "errors": getattr(exc, "errors", [])},
                        status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    errors = [{"line": None, "column": ".".join(str(p) for p in e.get("loc", [])[1:]) or None, "message": e.get("msg", "")}
              for e in exc.errors()]
    return JSONResponse(jsonable_encoder({"detail": "Paramètres de requête invalides.", "code": "validation_error",
                                          "errors": errors}), status_code=422)


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    log.exception("Erreur non gérée sur %s %s", request.method, request.url.path)
    return JSONResponse({"detail": "Erreur interne. Consultez les journaux du serveur.", "code": "internal_error",
                         "errors": []}, status_code=500)


# --- Services ---------------------------------------------------------------

_ACCEPTED_TYPES = {"text/csv", "application/csv", "application/vnd.ms-excel", "text/plain",
                   "application/octet-stream", ""}
_UNSAFE_FILENAME = re.compile(r"[^\w.\- ()]+")


def _clean_filename(name: str) -> str:
    base = Path(name.replace("\\", "/")).name
    return (_UNSAFE_FILENAME.sub("_", base).strip() or "catalogue.csv")[:120]


def _clean_label(label: str | None, filename: str) -> str:
    text = " ".join((label or "").split())[:80]
    return text or Path(filename).stem[:80]


def _import_bytes(raw: bytes, filename: str, label: str | None) -> dict:
    cfg = get_settings()
    try:
        parsed = parse_catalog(raw, max_bytes=cfg.max_file_bytes, max_rows=cfg.max_rows,
                               max_field_chars=cfg.max_field_chars)
    except CatalogValidationError as exc:
        raise ApiError(422, "invalid_catalog", str(exc), exc.errors) from exc
    sha = hashlib.sha256(raw).hexdigest()
    audit = storage.create_audit(parsed.rows, label=_clean_label(label, filename), filename=filename,
                                 sha256=sha, warnings=parsed.warnings)
    log.info("audit créé id=%s lignes=%s anomalies=%s sha256=%s", audit["id"], audit["total_products"],
             audit["issue_count"], sha[:12])
    return audit


async def _read_upload(request: Request, file: UploadFile) -> tuple[bytes, str]:
    cfg = get_settings()
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > cfg.max_file_bytes + 64_000:
        raise ApiError(413, "file_too_large", f"Fichier trop volumineux (limite : {cfg.max_file_bytes // 1_000_000} Mo).")
    filename = _clean_filename(file.filename or "")
    if not filename.lower().endswith(".csv"):
        raise ApiError(400, "invalid_extension", "Veuillez envoyer un fichier .csv")
    if (file.content_type or "").split(";")[0].strip().lower() not in _ACCEPTED_TYPES:
        raise ApiError(415, "unsupported_media_type", "Type de fichier non pris en charge : un CSV texte est attendu.")
    raw = await file.read(cfg.max_file_bytes + 1)
    if len(raw) > cfg.max_file_bytes:
        raise ApiError(413, "file_too_large", f"Fichier trop volumineux (limite : {cfg.max_file_bytes // 1_000_000} Mo).")
    return raw, filename


def _audit_or_404(audit_id: int) -> dict:
    audit = storage.get_audit(audit_id)
    if not audit:
        raise ApiError(404, "audit_not_found", f"Audit {audit_id} introuvable.")
    return audit


def _download(content: bytes, filename: str, media_type: str) -> Response:
    return Response(content, media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})


SeverityQ = Literal["high", "medium", "low"]
CodeQ = Literal[tuple(r.code for r in REGISTRY)]  # type: ignore[valid-type]
CategoryQ = Literal[tuple(CATEGORIES)]  # type: ignore[valid-type]
ConfidenceQ = Literal["certain", "heuristic"]
Delimiter = Literal["semicolon", "comma"]
_DELIMITERS = {"semicolon": ";", "comma": ","}

# --- API /api ---------------------------------------------------------------

api = APIRouter(prefix="/api")


@api.get("/health", tags=["système"])
def api_health():
    return {"status": "ok", "version": __version__, "rules_version": RULES_VERSION}


@api.get("/rules", response_model=RulesCatalog, tags=["règles"], summary="Catalogue des règles d'audit")
def rules_catalog():
    return {"version": RULES_VERSION, "penalties": PENALTIES, "categories": CATEGORIES, "rules": describe_rules()}


@api.post("/audits", response_model=ImportResult, status_code=201, tags=["audits"],
          summary="Importer un CSV et créer un audit",
          responses={400: {"model": ErrorResponse}, 413: {"model": ErrorResponse}, 415: {"model": ErrorResponse}})
async def create_audit(request: Request, file: UploadFile = File(..., description="Catalogue CSV UTF-8, séparateur , ou ;"),
                       label: str | None = Form(None, max_length=200, description="Nom de l'audit (facultatif)")):
    raw, filename = await _read_upload(request, file)
    audit = _import_bytes(raw, filename, label)
    return {"audit": audit, "imported": audit["total_products"], "issues": audit["issue_count"],
            "warnings": audit["warnings"], "message": "Audit créé."}


@api.get("/audits", response_model=list[Audit], tags=["audits"], summary="Historique des audits")
def audits():
    return storage.list_audits()


@api.get("/audits/{audit_id}", response_model=AuditDetail, tags=["audits"], responses={404: {"model": ErrorResponse}})
def audit_detail(audit_id: int):
    return {**_audit_or_404(audit_id), **storage.audit_breakdown(audit_id)}


@api.delete("/audits/{audit_id}", status_code=204, tags=["audits"], responses={404: {"model": ErrorResponse}})
def remove_audit(audit_id: int):
    if not storage.delete_audit(audit_id):
        raise ApiError(404, "audit_not_found", f"Audit {audit_id} introuvable.")
    log.info("audit supprimé id=%s", audit_id)
    return Response(status_code=204)


@api.get("/audits/{audit_id}/products", response_model=ProductPage, tags=["produits"])
def audit_products(audit_id: int, q: str | None = Query(None, max_length=100),
                   status: Literal["active", "draft"] | None = None, severity: SeverityQ | None = None,
                   has_issues: bool | None = None,
                   sort: str = Query("score", pattern=r"^-?(product_id|sku|title|score|issues|price|status)$"),
                   page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200)):
    _audit_or_404(audit_id)
    return storage.query_products(audit_id, q=q, status=status, severity=severity, has_issues=has_issues,
                                  sort=sort, page=page, page_size=page_size)


@api.get("/audits/{audit_id}/products/{product_id:path}", response_model=ProductDetail, tags=["produits"],
         responses={404: {"model": ErrorResponse}})
def audit_product(audit_id: int, product_id: str):
    _audit_or_404(audit_id)
    product = storage.get_product(audit_id, product_id)
    if not product:
        raise ApiError(404, "product_not_found", "Produit introuvable dans cet audit.")
    return product


def _issue_args(severity, code, category, confidence, q):
    return {"severity": severity, "code": code, "category": category, "confidence": confidence, "q": q}


@api.get("/audits/{audit_id}/issues", response_model=IssuePage, tags=["anomalies"])
def audit_issues(audit_id: int, severity: SeverityQ | None = None, code: CodeQ | None = None,
                 category: CategoryQ | None = None, confidence: ConfidenceQ | None = None,
                 q: str | None = Query(None, max_length=100),
                 sort: str = Query("severity", pattern=r"^-?(severity|product_id|code|category|sku)$"),
                 page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=500)):
    _audit_or_404(audit_id)
    return storage.query_issues(audit_id, **_issue_args(severity, code, category, confidence, q),
                                sort=sort, page=page, page_size=page_size)


@api.get("/audits/{audit_id}/exports/issues.csv", tags=["exports"], summary="Export CSV des anomalies (mêmes filtres)",
         response_class=Response, responses={200: {"content": {"text/csv": {}}}})
def export_issues(audit_id: int, severity: SeverityQ | None = None, code: CodeQ | None = None,
                  category: CategoryQ | None = None, confidence: ConfidenceQ | None = None,
                  q: str | None = Query(None, max_length=100),
                  sort: str = Query("severity", pattern=r"^-?(severity|product_id|code|category|sku)$"),
                  delimiter: Delimiter = "semicolon"):
    _audit_or_404(audit_id)
    items = storage.query_issues(audit_id, **_issue_args(severity, code, category, confidence, q),
                                 sort=sort, page_size=None)["items"]
    return _download(issues_csv(items, _DELIMITERS[delimiter]), f"audit-{audit_id}-anomalies.csv", "text/csv; charset=utf-8")


@api.get("/audits/{audit_id}/exports/products.csv", tags=["exports"], summary="Export CSV des produits et indices",
         response_class=Response, responses={200: {"content": {"text/csv": {}}}})
def export_products(audit_id: int, delimiter: Delimiter = "semicolon"):
    _audit_or_404(audit_id)
    items = storage.query_products(audit_id, sort="product_id", page_size=1_000_000)["items"]
    return _download(products_csv(items, _DELIMITERS[delimiter]), f"audit-{audit_id}-produits.csv", "text/csv; charset=utf-8")


@api.get("/audits/{audit_id}/exports/report.pdf", tags=["exports"], summary="Rapport d'audit PDF",
         response_class=Response, responses={200: {"content": {"application/pdf": {}}}})
def export_pdf(audit_id: int):
    audit = _audit_or_404(audit_id)
    issues = storage.query_issues(audit_id, page_size=None)["items"]
    return _download(audit_pdf(audit, storage.audit_breakdown(audit_id), issues),
                     f"audit-{audit_id}-rapport.pdf", "application/pdf")


@api.get("/compare", response_model=Comparison, tags=["comparaison"], summary="Comparer deux audits (avant / après)",
         responses={404: {"model": ErrorResponse}})
def compare(base: int = Query(..., ge=1), target: int = Query(..., ge=1)):
    result = storage.compare_audits(base, target)
    if result is None:
        raise ApiError(404, "audit_not_found", "Un des deux audits est introuvable.")
    return result


@api.post("/demo", response_model=DemoResult, status_code=201, tags=["démonstration"],
          summary="Importer les catalogues fictifs avant / après",
          responses={404: {"model": ErrorResponse}})
def load_demo():
    cfg = get_settings()
    if not cfg.demo_enabled:
        raise ApiError(404, "demo_disabled", "Le mode démonstration est désactivé.")
    paths = [cfg.demo_dir / "catalog_before.csv", cfg.demo_dir / "catalog_after.csv"]
    if not all(p.is_file() for p in paths):
        raise ApiError(404, "demo_missing", "Catalogues de démonstration absents : exécutez python demo/generate_catalogs.py.")
    before = _import_bytes(paths[0].read_bytes(), paths[0].name, "Démo — catalogue initial")
    after = _import_bytes(paths[1].read_bytes(), paths[1].name, "Démo — après corrections")
    return {"before": before, "after": after}


app.include_router(api)

# --- Routes v0.1 conservées pour compatibilité --------------------------------
# Elles opèrent sur le dernier audit importé.


@app.get("/health", tags=["v0.1 (compatibilité)"])
def health():
    return {"status": "ok"}


@app.post("/catalog/import", status_code=201, tags=["v0.1 (compatibilité)"], deprecated=True)
async def upload_catalog(request: Request, file: UploadFile = File(...)):
    raw, filename = await _read_upload(request, file)
    audit = _import_bytes(raw, filename, None)
    return {"imported": audit["total_products"], "issues": audit["issue_count"], "audit_id": audit["id"],
            "warnings": audit["warnings"], "message": "Catalogue importé (nouvel audit créé)."}


@app.get("/catalog/summary", tags=["v0.1 (compatibilité)"], deprecated=True)
def get_summary():
    audit_id = storage.latest_audit_id()
    audit = storage.get_audit(audit_id) if audit_id else None
    if not audit:
        return {"total_products": 0, "active_products": 0, "draft_products": 0, "affected_active_products": 0,
                "active_products_without_issues": 0, "issue_count": 0,
                "issues_by_severity": {"high": 0, "medium": 0, "low": 0}, "issues_by_type": {},
                "scope": "Les anomalies sont calculées uniquement sur les produits actifs."}
    return {"total_products": audit["total_products"], "active_products": audit["active_products"],
            "draft_products": audit["draft_products"], "affected_active_products": audit["affected_products"],
            "active_products_without_issues": audit["active_products"] - audit["affected_products"],
            "issue_count": audit["issue_count"], "issues_by_severity": audit["issues_by_severity"],
            "issues_by_type": storage.audit_breakdown(audit["id"])["issues_by_type"],
            "quality_score": audit["quality_score"], "audit_id": audit["id"],
            "scope": "Les anomalies sont calculées uniquement sur les produits actifs."}


@app.get("/catalog/issues", tags=["v0.1 (compatibilité)"], deprecated=True)
def get_issues(severity: SeverityQ | None = None, code: str | None = Query(None, max_length=64)):
    audit_id = storage.latest_audit_id()
    if not audit_id:
        return {"count": 0, "items": []}
    page = storage.query_issues(audit_id, severity=severity, code=code, page_size=None)
    return {"count": page["total"], "items": page["items"]}


# --- Interface web compilée (frontend/dist), si présente ----------------------

_dist = settings.frontend_dist.resolve()
if (_dist / "index.html").is_file():
    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith(("api/", "catalog/")):
            raise ApiError(404, "not_found", "Route inconnue.")
        candidate = (_dist / full_path).resolve()
        if full_path and candidate.is_file() and _dist in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(_dist / "index.html", headers={"Cache-Control": "no-cache"})
