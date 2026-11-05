import { useEffect, useRef, type ReactNode } from "react";
import { api } from "../lib/api";
import { useAsync } from "../lib/hooks";
import { CATEGORY_LABEL, fmt } from "../lib/format";
import { ConfidenceBadge, ErrorState, Icon, Loading, ScoreBadge, SeverityBadge } from "./ui";

/** <dialog> natif : focus piégé, Échap et retour du focus gérés par le navigateur. */
function useModal(open: boolean) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  return ref;
}

interface ConfirmProps {
  open: boolean;
  title: string;
  children: ReactNode;
  confirmLabel: string;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({ open, title, children, confirmLabel, busy, onConfirm, onCancel }: ConfirmProps) {
  const ref = useModal(open);
  return (
    <dialog ref={ref} className="confirm" aria-labelledby="confirm-title" onCancel={onCancel} onClose={onCancel}>
      <h2 id="confirm-title">{title}</h2>
      <div className="muted" style={{ marginTop: "var(--s3)" }}>
        {children}
      </div>
      <div className="actions">
        <button type="button" className="btn" onClick={onCancel} autoFocus>
          Annuler
        </button>
        <button type="button" className="btn btn-danger-solid" onClick={onConfirm} disabled={busy}>
          {busy ? "Suppression…" : confirmLabel}
        </button>
      </div>
    </dialog>
  );
}

function Value({ value, children }: { value: string; children?: ReactNode }) {
  return value ? <>{children ?? value}</> : <span className="empty-value">vide</span>;
}

export function ProductDrawer({ auditId, productId, onClose }: { auditId: number; productId: string | null; onClose: () => void }) {
  const ref = useModal(productId !== null);
  const state = useAsync(productId ? () => api.product(auditId, productId) : null, [auditId, productId]);
  const product = state.data;

  return (
    <dialog
      ref={ref}
      className="drawer"
      aria-labelledby="drawer-title"
      onClose={onClose}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="drawer-head">
        <div>
          <p className="muted small">Fiche produit {productId}</p>
          <h2 id="drawer-title">{product?.title_fr || (state.loading ? "Chargement…" : "Sans titre")}</h2>
        </div>
        <button type="button" className="btn btn-sm" onClick={onClose} aria-label="Fermer la fiche produit">
          {Icon.close}
        </button>
      </div>
      <div className="drawer-body">
        {state.loading && <Loading lines={6} />}
        {state.error && <ErrorState error={state.error} onRetry={state.reload} />}
        {product && !state.loading && (
          <>
            <section aria-label="Indice qualité">
              <div className="issue-meta">
                <ScoreBadge score={product.score} />
                <span>
                  {product.status === "draft"
                    ? "Brouillon : non audité."
                    : product.issues.length === 0
                      ? "Aucune anomalie détectée."
                      : `100 − ${product.score_breakdown.map((p) => p.penalty).join(" − ")} = ${product.score}`}
                </span>
              </div>
            </section>

            <dl className="kv">
              <dt>SKU</dt>
              <dd>
                <Value value={product.sku} />
              </dd>
              <dt>Prix</dt>
              <dd>
                <Value value={product.price_eur}>{fmt.price(product.price_eur)}</Value>
              </dd>
              <dt>Statut</dt>
              <dd>{product.status === "active" ? "Actif" : "Brouillon"}</dd>
              <dt>Titre anglais</dt>
              <dd>
                <Value value={product.title_en} />
              </dd>
              <dt>Image</dt>
              <dd>
                {/* L'URL est affichée en texte et jamais chargée : aucun appel vers un hôte tiers. */}
                <Value value={product.image_url} />
              </dd>
              <dt>Description</dt>
              <dd style={{ whiteSpace: "pre-line" }}>
                <Value value={product.description_fr} />
              </dd>
            </dl>

            {product.issues.length > 0 && (
              <section>
                <h3 style={{ marginBottom: "var(--s3)" }}>
                  {fmt.plural(product.issues.length, "anomalie à traiter", "anomalies à traiter")}
                </h3>
                <div style={{ display: "grid", gap: "var(--s4)" }}>
                  {product.issues.map((issue) => (
                    <article key={issue.code} className={`issue-card ${issue.severity}`}>
                      <div className="issue-meta">
                        <strong>{issue.message}</strong>
                        <SeverityBadge severity={issue.severity} />
                        <ConfidenceBadge confidence={issue.confidence} />
                        <span className="muted small">
                          {CATEGORY_LABEL[issue.category]}, champ <code>{issue.field}</code>
                        </span>
                      </div>
                      <p className="evidence">{issue.evidence}</p>
                      <p className="small">{issue.explanation}</p>
                      <p className="suggestion">
                        <strong>Correction suggérée :</strong> {issue.suggestion}
                      </p>
                    </article>
                  ))}
                </div>
              </section>
            )}
          </>
        )}
      </div>
    </dialog>
  );
}
