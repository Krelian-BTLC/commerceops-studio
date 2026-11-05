import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { ApiError } from "../lib/api";
import { BAND_LABEL, CONFIDENCE_HINT, CONFIDENCE_LABEL, SEVERITY_LABEL, fmt, scoreBand } from "../lib/format";
import type { Confidence, Severity } from "../lib/types";

export function SeverityBadge({ severity }: { severity: Severity | null }) {
  if (!severity) return <span className="muted small">Aucune</span>;
  return <span className={`sev sev-${severity}`}>{SEVERITY_LABEL[severity]}</span>;
}

export function ConfidenceBadge({ confidence }: { confidence: Confidence }) {
  return (
    <span className={`conf conf-${confidence}`} title={CONFIDENCE_HINT[confidence]}>
      {CONFIDENCE_LABEL[confidence]}
    </span>
  );
}

export function ScoreBadge({ score }: { score: number | null }) {
  const band = scoreBand(score);
  return (
    <span className={`score score-${band}`} title={`Indice qualité : ${BAND_LABEL[band]}`}>
      {score ?? "—"}
    </span>
  );
}

export function Loading({ label = "Chargement…", lines = 4 }: { label?: string; lines?: number }) {
  return (
    <div className="panel" role="status" aria-live="polite">
      <span className="visually-hidden">{label}</span>
      <div className="skeleton" aria-hidden="true">
        {Array.from({ length: lines }, (_, i) => (
          <span key={i} style={{ width: `${90 - i * 12}%` }} />
        ))}
      </div>
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  return (
    <div className="notice notice-error" role="alert">
      <h2>{error.status === 0 ? "Connexion à l'API impossible" : "Le chargement a échoué"}</h2>
      <p>{error.message}</p>
      {onRetry && (
        <div>
          <button type="button" className="btn btn-sm" onClick={onRetry}>
            Réessayer
          </button>
        </div>
      )}
    </div>
  );
}

export function NoAudit() {
  return (
    <div className="panel state">
      <h2>Aucun audit pour l'instant</h2>
      <p>Importez un catalogue CSV, ou chargez les deux catalogues fictifs de démonstration.</p>
      <div className="actions">
        <Link className="btn btn-primary" to="/import">
          Importer un catalogue
        </Link>
      </div>
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="state">
      <h2>{title}</h2>
      {children}
    </div>
  );
}

interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  onPage: (page: number) => void;
  noun: [string, string];
}

export function Pagination({ page, pageSize, total, onPage, noun }: PaginationProps) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const first = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const last = Math.min(total, page * pageSize);
  return (
    <nav className="pager" aria-label="Pagination">
      <p className="muted small" aria-live="polite">
        {total === 0 ? `0 ${noun[0]}` : `${fmt.int(first)}–${fmt.int(last)} sur ${fmt.plural(total, noun[0], noun[1])}`}
      </p>
      <div className="pager-buttons">
        <button type="button" className="btn btn-sm" onClick={() => onPage(page - 1)} disabled={page <= 1}>
          Précédent
        </button>
        <span className="small">
          Page {page} / {pages}
        </span>
        <button type="button" className="btn btn-sm" onClick={() => onPage(page + 1)} disabled={page >= pages}>
          Suivant
        </button>
      </div>
    </nav>
  );
}

interface SortHeaderProps {
  label: string;
  field: string;
  sort: string;
  onSort: (sort: string) => void;
  className?: string;
  /** Sens appliqué au premier clic. */
  initial?: "asc" | "desc";
}

export function SortHeader({ label, field, sort, onSort, className, initial = "asc" }: SortHeaderProps) {
  const active = sort.replace(/^-/, "") === field;
  const dir = active ? (sort.startsWith("-") ? "desc" : "asc") : undefined;
  const next = active ? (dir === "asc" ? `-${field}` : field) : initial === "desc" ? `-${field}` : field;
  return (
    <th className={className} aria-sort={dir === "asc" ? "ascending" : dir === "desc" ? "descending" : "none"}>
      <button type="button" className="sort-btn" data-dir={dir} onClick={() => onSort(next)}>
        {label}
      </button>
    </th>
  );
}

export const Icon = {
  upload: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path d="M12 16V4m0 0-4.5 4.5M12 4l4.5 4.5M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
    </svg>
  ),
  download: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path d="M12 4v12m0 0 4.5-4.5M12 16l-4.5-4.5M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
    </svg>
  ),
  close: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path d="M6 6l12 12M18 6 6 18" />
    </svg>
  ),
};
