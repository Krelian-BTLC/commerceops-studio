// Miroir des modèles publiés par FastAPI (app/schemas.py, voir /docs).

export type Severity = "high" | "medium" | "low";
export type Confidence = "certain" | "heuristic";
export type Category = "identification" | "content" | "pricing" | "media" | "translation";

export interface ImportWarning {
  code: string;
  message: string;
  count?: number | null;
}

export interface Audit {
  id: number;
  label: string;
  source_filename: string;
  source_sha256: string;
  created_at: string;
  rules_version: string;
  total_products: number;
  active_products: number;
  draft_products: number;
  affected_products: number;
  issue_count: number;
  issues_by_severity: Record<Severity, number>;
  quality_score: number | null;
  warnings: ImportWarning[];
}

export interface PriorityProduct {
  product_id: string;
  sku: string;
  title_fr: string;
  score: number | null;
  issue_count: number;
  worst_severity: Severity | null;
}

export interface AuditDetail extends Audit {
  issues_by_type: Record<string, number>;
  issues_by_category: Partial<Record<Category, number>>;
  issues_by_confidence: Record<Confidence, number>;
  score_distribution: Record<"excellent" | "good" | "fair" | "poor", number>;
  priority_products: PriorityProduct[];
}

export interface Issue {
  product_id: string;
  sku: string;
  title_fr: string;
  code: string;
  severity: Severity;
  category: Category;
  field: string;
  message: string;
  explanation: string;
  suggestion: string;
  confidence: Confidence;
  evidence: string;
}

export interface Page<T> {
  total: number;
  page: number;
  page_size: number | null;
  items: T[];
}

export interface ProductRow {
  product_id: string;
  sku: string;
  title_fr: string;
  description_fr: string;
  price_eur: string;
  image_url: string;
  title_en: string;
  status: "active" | "draft";
  score: number | null;
  issue_count: number;
  worst_severity: Severity | null;
}

export interface ProductDetail extends ProductRow {
  issues: Issue[];
  score_breakdown: { code: string; severity: Severity; penalty: number }[];
}

export interface RuleInfo {
  code: string;
  severity: Severity;
  category: Category;
  category_label: string;
  field: string;
  title: string;
  explanation: string;
  suggestion: string;
  confidence: Confidence;
  penalty: number;
}

export interface RulesCatalog {
  version: string;
  penalties: Record<Severity, number>;
  categories: Record<Category, string>;
  rules: RuleInfo[];
}

export interface IssueRef {
  product_id: string;
  sku: string;
  title_fr: string;
  code: string;
  severity: Severity;
  message: string;
}

export interface Metric {
  before: number | null;
  after: number | null;
  delta: number | null;
}

export interface Comparison {
  base: Audit;
  target: Audit;
  metrics: Record<"total_products" | "active_products" | "affected_products" | "issue_count" | "quality_score", Metric>;
  issue_change_percent: number | null;
  by_severity: Record<Severity, { before: number; after: number }>;
  by_type: { code: string; before: number; after: number; delta: number }[];
  counts: { resolved: number; new: number; persisting: number };
  products: { added: number; removed: number; common: number };
  resolved: IssueRef[];
  new: IssueRef[];
  persisting: IssueRef[];
  same_rules_version: boolean;
}

export interface ImportResult {
  audit: Audit;
  imported: number;
  issues: number;
  warnings: ImportWarning[];
  message: string;
}

export interface ApiErrorItem {
  line: number | null;
  column: string | null;
  message: string;
}
