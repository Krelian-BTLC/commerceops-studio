import type {
  ApiErrorItem, Audit, AuditDetail, Comparison, ImportResult, Issue, Page, ProductDetail, ProductRow, RulesCatalog,
} from "./types";

/** Erreur renvoyée par l'API au format {detail, code, errors}. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly errors: ApiErrorItem[];

  constructor(status: number, code: string, message: string, errors: ApiErrorItem[] = []) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.errors = errors;
  }
}

type Params = Record<string, string | number | boolean | null | undefined>;

export function query(params: Params = {}): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, { headers: { Accept: "application/json" }, ...init });
  } catch {
    throw new ApiError(0, "network_error", "Le serveur ne répond pas. Vérifiez que l'API est démarrée (uvicorn app.main:app).");
  }
  if (response.status === 204) return undefined as T;
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const data = (body ?? {}) as { detail?: unknown; code?: string; errors?: ApiErrorItem[] };
    const message = typeof data.detail === "string" ? data.detail : `Erreur ${response.status}.`;
    throw new ApiError(response.status, data.code ?? "error", message, data.errors ?? []);
  }
  return body as T;
}

export const api = {
  rules: () => request<RulesCatalog>("/rules"),
  audits: () => request<Audit[]>("/audits"),
  audit: (id: number) => request<AuditDetail>(`/audits/${id}`),
  deleteAudit: (id: number) => request<void>(`/audits/${id}`, { method: "DELETE" }),
  products: (id: number, params: Params) => request<Page<ProductRow>>(`/audits/${id}/products${query(params)}`),
  product: (id: number, productId: string) =>
    request<ProductDetail>(`/audits/${id}/products/${productId.split("/").map(encodeURIComponent).join("/")}`),
  issues: (id: number, params: Params) => request<Page<Issue>>(`/audits/${id}/issues${query(params)}`),
  compare: (base: number, target: number) => request<Comparison>(`/compare${query({ base, target })}`),
  loadDemo: () => request<{ before: Audit; after: Audit }>("/demo", { method: "POST" }),
  upload: (file: File, label: string) => {
    const form = new FormData();
    form.append("file", file);
    if (label.trim()) form.append("label", label.trim());
    return request<ImportResult>("/audits", { method: "POST", body: form });
  },
};

export const exportUrls = {
  issuesCsv: (id: number, params: Params) => `/api/audits/${id}/exports/issues.csv${query(params)}`,
  productsCsv: (id: number) => `/api/audits/${id}/exports/products.csv`,
  pdf: (id: number) => `/api/audits/${id}/exports/report.pdf`,
};
