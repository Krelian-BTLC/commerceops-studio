import { useState } from "react";
import { Link } from "react-router-dom";
import { BarList, SeverityStack } from "../components/charts";
import { ProductDrawer } from "../components/dialogs";
import { HangTag } from "../components/HangTag";
import { ErrorState, Icon, Loading, NoAudit, ScoreBadge, SeverityBadge } from "../components/ui";
import { api, exportUrls } from "../lib/api";
import { useAudits, useAuditLink } from "../lib/audits";
import { BAND_LABEL, CATEGORY_LABEL, fmt } from "../lib/format";
import { useAsync, useDocumentTitle } from "../lib/hooks";
import type { AuditDetail, Category } from "../lib/types";

function statement(a: AuditDetail): { title: string; sub: string } {
  if (a.active_products === 0) {
    return { title: "Aucun produit actif à auditer.", sub: "Les brouillons sont exclus de l'audit." };
  }
  if (a.issue_count === 0) {
    return { title: `Les ${fmt.int(a.active_products)} produits actifs passent toutes les règles.`, sub: "Aucune anomalie détectée." };
  }
  const high = a.issues_by_severity.high;
  return {
    title: `${fmt.int(a.affected_products)} produits actifs sur ${fmt.int(a.active_products)} ont au moins une anomalie.`,
    sub:
      high > 0
        ? `${fmt.plural(high, "problème de priorité haute bloque", "problèmes de priorité haute bloquent")} la vente ou la gestion du stock : commencez par là.`
        : "Aucun problème de priorité haute : il reste des améliorations de contenu et de traduction.",
  };
}

export function Dashboard() {
  useDocumentTitle("Tableau de bord");
  const { current, loading: listLoading, error: listError, refresh, rule } = useAudits();
  const link = useAuditLink();
  const state = useAsync(current ? () => api.audit(current.id) : null, [current?.id]);
  const [openProduct, setOpenProduct] = useState<string | null>(null);

  if (listError) return <ErrorState error={listError} onRetry={() => void refresh()} />;
  if (listLoading) return <Loading label="Chargement des audits" />;
  if (!current) return <NoAudit />;
  if (state.error) return <ErrorState error={state.error} onRetry={state.reload} />;
  if (!state.data) return <Loading label="Chargement de l'audit" lines={6} />;

  const a = state.data;
  const { title, sub } = statement(a);
  const byType = Object.entries(a.issues_by_type)
    .map(([code, value]) => {
      const r = rule(code);
      return { key: code, label: r?.title ?? code, value, tone: r?.severity, href: link("/issues", { code }) };
    })
    .sort((x, y) => y.value - x.value || x.label.localeCompare(y.label));
  const byCategory = (Object.keys(CATEGORY_LABEL) as Category[]).map((c) => ({
    key: c,
    label: CATEGORY_LABEL[c],
    value: a.issues_by_category[c] ?? 0,
    href: link("/issues", { category: c }),
  }));
  const distribution = (["excellent", "good", "fair", "poor"] as const).map((band) => ({
    key: band,
    label: `${BAND_LABEL[band]} (${band === "excellent" ? "90–100" : band === "good" ? "70–89" : band === "fair" ? "40–69" : "0–39"})`,
    value: a.score_distribution[band],
    tone: band === "excellent" ? ("ok" as const) : band === "good" ? ("low" as const) : band === "fair" ? ("medium" as const) : ("high" as const),
  }));

  return (
    <>
      <section className="hero" aria-labelledby="hero-title">
        <HangTag active={a.active_products} affected={a.affected_products} />
        <div>
          <p className="muted small">
            Audit #{a.id}, {a.label}, du {fmt.date(a.created_at)}
          </p>
          <h1 id="hero-title" className="hero-statement" style={{ marginTop: "var(--s2)" }}>
            {title}
          </h1>
          <p className="hero-sub">{sub}</p>
          <div className="actions">
            {a.issue_count > 0 && (
              <Link className="btn btn-primary" to={link("/issues", a.issues_by_severity.high ? { severity: "high" } : {})}>
                {a.issues_by_severity.high ? "Voir les priorités hautes" : "Voir les anomalies"}
              </Link>
            )}
            <a className="btn" href={exportUrls.pdf(a.id)} download>
              {Icon.download} Rapport PDF
            </a>
          </div>
          <dl className="facts">
            <div>
              <dt>Produits importés</dt>
              <dd>{fmt.int(a.total_products)}</dd>
            </div>
            <div>
              <dt>Actifs audités</dt>
              <dd>{fmt.int(a.active_products)}</dd>
            </div>
            <div>
              <dt>Brouillons exclus</dt>
              <dd>{fmt.int(a.draft_products)}</dd>
            </div>
            <div>
              <dt>Anomalies</dt>
              <dd>{fmt.int(a.issue_count)}</dd>
            </div>
            <div>
              <dt>Indice moyen par fiche</dt>
              <dd>{fmt.score(a.quality_score)}</dd>
            </div>
          </dl>
        </div>
      </section>

      {a.warnings.length > 0 && (
        <div className="notice notice-warning section" role="note">
          <h2>Ajustements faits à l'import</h2>
          <ul>
            {a.warnings.map((w) => (
              <li key={w.code}>{w.message}</li>
            ))}
          </ul>
        </div>
      )}

      {a.issue_count > 0 && (
        <>
          <section className="section panel" aria-labelledby="sev-title">
            <div className="section-head">
              <h2 id="sev-title">Répartition par priorité</h2>
              <p className="muted small">
                {fmt.int(a.issues_by_confidence.certain)} constats factuels, {fmt.int(a.issues_by_confidence.heuristic)} signaux
                à vérifier par une personne
              </p>
            </div>
            <SeverityStack counts={a.issues_by_severity} />
          </section>

          <div className="section grid-2">
            <section className="panel" aria-labelledby="types-title">
              <div className="section-head">
                <h2 id="types-title">Anomalies par règle</h2>
                <Link to={link("/rules")} className="small">
                  Comprendre les règles
                </Link>
              </div>
              <BarList items={byType} label="Nombre d'anomalies par règle" />
            </section>

            <section className="panel" aria-labelledby="priority-title">
              <div className="section-head">
                <h2 id="priority-title">À corriger en premier</h2>
                <Link to={link("/products", { has_issues: "true" })} className="small">
                  Tous les produits concernés
                </Link>
              </div>
              <table className="data">
                <thead>
                  <tr>
                    <th>Produit</th>
                    <th>Priorité</th>
                    <th className="num">Indice</th>
                  </tr>
                </thead>
                <tbody>
                  {a.priority_products.map((p) => (
                    <tr key={p.product_id}>
                      <td className="cell-title">
                        <button type="button" className="link-btn" onClick={() => setOpenProduct(p.product_id)}>
                          {p.title_fr || <em>Sans titre</em>}
                        </button>
                        <span className="cell-sub">
                          {p.product_id}, {fmt.plural(p.issue_count, "anomalie", "anomalies")}
                        </span>
                      </td>
                      <td>
                        <SeverityBadge severity={p.worst_severity} />
                      </td>
                      <td className="num">
                        <ScoreBadge score={p.score} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          </div>

          <div className="section grid-2">
            <section className="panel" aria-labelledby="cat-title">
              <h2 id="cat-title" style={{ marginBottom: "var(--s4)" }}>
                Par famille
              </h2>
              <BarList items={byCategory} label="Nombre d'anomalies par famille" />
            </section>
            <section className="panel" aria-labelledby="dist-title">
              <h2 id="dist-title" style={{ marginBottom: "var(--s4)" }}>
                Indice des produits actifs
              </h2>
              <BarList items={distribution} label="Nombre de produits par niveau d'indice" />
              <p className="muted small" style={{ marginTop: "var(--s4)" }}>
                L'indice mesure la complétude et la cohérence internes du fichier. Ce n'est pas une note SEO.
              </p>
            </section>
          </div>
        </>
      )}
      <ProductDrawer auditId={a.id} productId={openProduct} onClose={() => setOpenProduct(null)} />
    </>
  );
}
