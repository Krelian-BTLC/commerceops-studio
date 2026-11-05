import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Empty, ErrorState, Loading, Pagination, SeverityBadge } from "../components/ui";
import { api } from "../lib/api";
import { useAudits } from "../lib/audits";
import { SEVERITY_LABEL, SEVERITY_ORDER, fmt } from "../lib/format";
import { useAsync, useDocumentTitle } from "../lib/hooks";
import type { Comparison, IssueRef } from "../lib/types";

type Tab = "resolved" | "new" | "persisting";
const TAB_LABEL: Record<Tab, string> = { resolved: "Résolues", new: "Nouvelles", persisting: "Toujours présentes" };
const LIST_PAGE = 15;

function Delta({ label, before, after, digits = 0, lowerIsBetter = true, suffix = "" }: {
  label: string; before: number | null; after: number | null; digits?: number; lowerIsBetter?: boolean; suffix?: string;
}) {
  const delta = before === null || after === null ? null : after - before;
  const tone = !delta ? "" : (delta < 0) === lowerIsBetter ? "better" : "worse";
  const show = (n: number | null) => (n === null ? "—" : digits ? fmt.score(n) : fmt.int(n));
  return (
    <div className="delta">
      <span className="muted small">{label}</span>
      <span className="figure">
        {show(after)}
        {suffix}
      </span>
      <span className="from">
        avant : {show(before)}
        {suffix}{" "}
        {delta !== null && delta !== 0 && <strong className={tone}>({fmt.signed(delta, digits)})</strong>}
      </span>
    </div>
  );
}

function IssueList({ items, total }: { items: IssueRef[]; total: number }) {
  const [page, setPage] = useState(1);
  if (items.length === 0) return <Empty title="Aucune anomalie dans cette liste" />;
  const slice = items.slice((page - 1) * LIST_PAGE, page * LIST_PAGE);
  return (
    <>
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th>Priorité</th>
              <th>Produit</th>
              <th>Anomalie</th>
            </tr>
          </thead>
          <tbody>
            {slice.map((i) => (
              <tr key={`${i.product_id}-${i.code}`}>
                <td>
                  <SeverityBadge severity={i.severity} />
                </td>
                <td className="cell-title">
                  {i.title_fr || <em>Sans titre</em>}
                  <span className="cell-sub">{i.product_id}</span>
                </td>
                <td>{i.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pagination page={page} pageSize={LIST_PAGE} total={items.length} onPage={setPage} noun={["anomalie", "anomalies"]} />
      {total > items.length && <p className="muted small">Liste limitée aux {items.length} premières sur {total}.</p>}
    </>
  );
}

function Result({ c }: { c: Comparison }) {
  const { rule } = useAudits();
  const [tab, setTab] = useState<Tab>("resolved");
  const pct = c.issue_change_percent;
  const max = Math.max(1, ...c.by_type.flatMap((t) => [t.before, t.after]));

  return (
    <>
      <section className="hero" style={{ gridTemplateColumns: "1fr" }} aria-labelledby="cmp-title">
        <div>
          <h2 id="cmp-title" className="hero-statement" style={{ maxWidth: "26ch" }}>
            {pct === null
              ? `${fmt.plural(c.target.issue_count, "anomalie", "anomalies")} après corrections.`
              : pct < 0
                ? `${fmt.int(Math.round(-pct))} % d'anomalies en moins entre les deux audits.`
                : pct > 0
                  ? `${fmt.int(Math.round(pct))} % d'anomalies en plus entre les deux audits.`
                  : "Le nombre d'anomalies est inchangé."}
          </h2>
          <p className="hero-sub">
            {fmt.plural(c.counts.resolved, "anomalie résolue", "anomalies résolues")}, {fmt.plural(c.counts.new, "nouvelle", "nouvelles")},{" "}
            {fmt.int(c.counts.persisting)} toujours présentes.{" "}
            {(c.products.added > 0 || c.products.removed > 0) &&
              `${fmt.plural(c.products.added, "produit ajouté", "produits ajoutés")}, ${fmt.plural(c.products.removed, "retiré", "retirés")}.`}
          </p>
          {!c.same_rules_version && (
            <p className="notice notice-warning" style={{ marginTop: "var(--s4)" }}>
              Les deux audits n'utilisent pas la même version des règles ({c.base.rules_version} et {c.target.rules_version}) : une partie de
              l'écart peut venir des règles elles-mêmes.
            </p>
          )}
        </div>
      </section>

      <section className="panel" aria-label="Indicateurs avant et après">
        <div className="delta-row">
          <Delta label="Anomalies" before={c.metrics.issue_count.before} after={c.metrics.issue_count.after} />
          <Delta label="Priorité haute" before={c.by_severity.high.before} after={c.by_severity.high.after} />
          <Delta label="Produits concernés" before={c.metrics.affected_products.before} after={c.metrics.affected_products.after} />
          <Delta label="Indice qualité moyen" before={c.metrics.quality_score.before} after={c.metrics.quality_score.after} digits={1} lowerIsBetter={false} />
        </div>
      </section>

      <div className="section grid-2">
        <section className="panel" aria-labelledby="bytype-title">
          <div className="section-head">
            <h2 id="bytype-title">Par règle</h2>
            <span className="legend" style={{ marginTop: 0 }}>
              <span>
                <span className="bar-fill" style={{ display: "inline-block", width: "1rem", height: "0.5rem", background: "var(--rule-strong)" }} /> avant
              </span>
              <span>
                <span className="bar-fill ok" style={{ display: "inline-block", width: "1rem", height: "0.5rem" }} /> après
              </span>
            </span>
          </div>
          <ul className="bars" aria-label="Nombre d'anomalies par règle, avant et après">
            {c.by_type.map((t) => (
              <li key={t.code} className="split-bar">
                <span className="bar-label">{rule(t.code)?.title ?? t.code}</span>
                <span className="pair" aria-hidden="true">
                  <span className="bar-track">
                    <span className="bar-fill" style={{ display: "block", width: `${(t.before / max) * 100}%`, background: "var(--rule-strong)" }} />
                  </span>
                  <span className="bar-track">
                    <span className="bar-fill ok" style={{ display: "block", width: `${(t.after / max) * 100}%` }} />
                  </span>
                </span>
                <span className="bar-value small">
                  {t.before} → {t.after}
                </span>
              </li>
            ))}
          </ul>
        </section>

        <section className="panel" aria-labelledby="sev-cmp-title">
          <h2 id="sev-cmp-title" style={{ marginBottom: "var(--s4)" }}>
            Par priorité
          </h2>
          <table className="data">
            <thead>
              <tr>
                <th>Priorité</th>
                <th className="num">Avant</th>
                <th className="num">Après</th>
                <th className="num">Écart</th>
              </tr>
            </thead>
            <tbody>
              {SEVERITY_ORDER.map((s) => {
                const d = c.by_severity[s].after - c.by_severity[s].before;
                return (
                  <tr key={s}>
                    <td>
                      <span className={`sev sev-${s}`}>{SEVERITY_LABEL[s]}</span>
                    </td>
                    <td className="num">{c.by_severity[s].before}</td>
                    <td className="num">{c.by_severity[s].after}</td>
                    <td className={`num ${d < 0 ? "better" : d > 0 ? "worse" : ""}`}>{fmt.signed(d)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      </div>

      <section className="section" aria-labelledby="detail-title">
        <h2 id="detail-title" style={{ marginBottom: "var(--s3)" }}>
          Détail des anomalies
        </h2>
        <div className="tabs" role="tablist" aria-label="Type de changement">
          {(Object.keys(TAB_LABEL) as Tab[]).map((t) => (
            <button key={t} type="button" role="tab" id={`tab-${t}`} aria-selected={tab === t} aria-controls="tab-panel" onClick={() => setTab(t)}>
              {TAB_LABEL[t]} ({fmt.int(c.counts[t])})
            </button>
          ))}
        </div>
        <div id="tab-panel" role="tabpanel" aria-labelledby={`tab-${tab}`}>
          <IssueList key={tab} items={c[tab]} total={c.counts[tab]} />
        </div>
      </section>
    </>
  );
}

export function Compare() {
  useDocumentTitle("Avant / après");
  const { audits, loading } = useAudits();
  const [params, setParams] = useSearchParams();
  const base = Number(params.get("base")) || audits[1]?.id || 0;
  const target = Number(params.get("target")) || audits[0]?.id || 0;
  const valid = base > 0 && target > 0 && base !== target;
  const state = useAsync(valid ? () => api.compare(base, target) : null, [base, target]);

  if (loading) return <Loading />;
  if (audits.length < 2) {
    return (
      <div className="panel state">
        <h2>Il faut au moins deux audits pour comparer</h2>
        <p>Importez une version corrigée du catalogue, ou chargez la démonstration qui contient déjà un avant et un après.</p>
        <div className="actions">
          <Link className="btn btn-primary" to="/import">
            Importer un catalogue
          </Link>
        </div>
      </div>
    );
  }

  const update = (key: "base" | "target", value: string) =>
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set("base", String(key === "base" ? value : base));
      next.set("target", String(key === "target" ? value : target));
      return next;
    });

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Avant / après</h1>
          <p className="lede">Une anomalie est suivie par produit et par règle : elle est résolue si elle disparaît du second audit.</p>
        </div>
      </div>
      <div className="compare-pickers panel">
        <label className="field">
          <span>Audit de référence (avant)</span>
          <select value={base} onChange={(e) => update("base", e.target.value)}>
            {audits.map((a) => (
              <option key={a.id} value={a.id}>
                #{a.id} {a.label} ({fmt.plural(a.issue_count, "anomalie", "anomalies")})
              </option>
            ))}
          </select>
        </label>
        <span className="compare-arrow" aria-hidden="true">
          comparé à
        </span>
        <label className="field">
          <span>Audit à comparer (après)</span>
          <select value={target} onChange={(e) => update("target", e.target.value)}>
            {audits.map((a) => (
              <option key={a.id} value={a.id}>
                #{a.id} {a.label} ({fmt.plural(a.issue_count, "anomalie", "anomalies")})
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="section">
        {!valid && <p className="notice notice-warning">Choisissez deux audits différents.</p>}
        {state.error && <ErrorState error={state.error} onRetry={state.reload} />}
        {valid && !state.error && !state.data && <Loading lines={6} />}
        {valid && state.data && <Result c={state.data} />}
      </div>
    </>
  );
}
