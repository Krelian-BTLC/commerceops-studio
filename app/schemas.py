"""Modèles de réponse publiés dans la documentation OpenAPI (/docs)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["high", "medium", "low"]
Confidence = Literal["certain", "heuristic"]


class ErrorItem(BaseModel):
    line: int | None = None
    column: str | None = None
    message: str


class ErrorResponse(BaseModel):
    detail: str = Field(description="Message lisible par un humain")
    code: str = Field(description="Code d'erreur stable, exploitable par le client")
    errors: list[ErrorItem] = []


class Warning_(BaseModel):
    code: str
    message: str
    count: int | None = None


class SeverityCounts(BaseModel):
    high: int
    medium: int
    low: int


class Audit(BaseModel):
    id: int
    label: str
    source_filename: str
    source_sha256: str
    created_at: str
    rules_version: str
    total_products: int
    active_products: int
    draft_products: int
    affected_products: int
    issue_count: int
    issues_by_severity: SeverityCounts
    quality_score: float | None = Field(description="Moyenne de l'indice de qualité interne (0-100) des produits actifs")
    warnings: list[Warning_]


class ImportResult(BaseModel):
    audit: Audit
    imported: int
    issues: int
    warnings: list[Warning_]
    message: str


class PriorityProduct(BaseModel):
    product_id: str
    sku: str
    title_fr: str
    score: int | None
    issue_count: int
    worst_severity: Severity | None


class AuditDetail(Audit):
    issues_by_type: dict[str, int]
    issues_by_category: dict[str, int]
    issues_by_confidence: dict[Confidence, int]
    score_distribution: dict[str, int]
    priority_products: list[PriorityProduct]


class Issue(BaseModel):
    product_id: str
    sku: str
    title_fr: str
    code: str
    severity: Severity
    category: str
    field: str
    message: str
    explanation: str
    suggestion: str
    confidence: Confidence
    evidence: str


class IssuePage(BaseModel):
    total: int
    page: int
    page_size: int | None
    items: list[Issue]


class ProductRow(BaseModel):
    product_id: str
    sku: str
    title_fr: str
    description_fr: str
    price_eur: str
    image_url: str
    title_en: str
    status: Literal["active", "draft"]
    score: int | None
    issue_count: int
    worst_severity: Severity | None


class ProductPage(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ProductRow]


class Penalty(BaseModel):
    code: str
    severity: Severity
    penalty: int


class ProductDetail(ProductRow):
    issues: list[Issue]
    score_breakdown: list[Penalty]


class RuleInfo(BaseModel):
    code: str
    severity: Severity
    category: str
    category_label: str
    field: str
    title: str
    explanation: str
    suggestion: str
    confidence: Confidence
    penalty: int


class RulesCatalog(BaseModel):
    version: str
    penalties: dict[Severity, int]
    categories: dict[str, str]
    rules: list[RuleInfo]


class Metric(BaseModel):
    before: float | None
    after: float | None
    delta: float | None


class TypeDelta(BaseModel):
    code: str
    before: int
    after: int
    delta: int


class IssueRef(BaseModel):
    product_id: str
    sku: str
    title_fr: str
    code: str
    severity: Severity
    message: str


class Comparison(BaseModel):
    base: Audit
    target: Audit
    metrics: dict[str, Metric]
    issue_change_percent: float | None
    by_severity: dict[Severity, dict[str, int]]
    by_type: list[TypeDelta]
    counts: dict[str, int]
    products: dict[str, int]
    resolved: list[IssueRef]
    new: list[IssueRef]
    persisting: list[IssueRef]
    same_rules_version: bool


class DemoResult(BaseModel):
    before: Audit
    after: Audit
