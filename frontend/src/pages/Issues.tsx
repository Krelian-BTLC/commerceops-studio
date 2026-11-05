import { useEffect, useState } from "react";
import { ProductDrawer } from "../components/dialogs";
import { ConfidenceBadge, Empty, ErrorState, Icon, Loading, NoAudit, Pagination, SeverityBadge, SortHeader } from "../components/ui";
import { api, exportUrls } from "../lib/api";
import { useAudits } from "../lib/audits";
import { CATEGORY_LABEL, CONFIDENCE_LABEL, SEVERITY_LABEL, SEVERITY_ORDER, fmt } from "../lib/format";
import { useAsync, useDebounced, useDocumentTitle } from "../lib/hooks";
import { useFilters } from "../lib/params";
import type { Category } from "../lib/types";

const PAGE_SIZE = 25;
const KEYS = ["q", "severity", "category", "code", "confidence", "sort"] as const;

export function Issues() {
  useDocumentTitle("Anomalies");
  const { current, loading: listLoading, rules } = useAudits();
  const { values, page, set, reset, active } = useFilters(KEYS);
  const [search, setSearch] = useState(values.q);
  const q = useDebounced(search);
  const [openProduct, setOpenProduct] = useState<string | null>(null);

  useEffect(() => {
    if (q !== values.q) set({ q });
  }, [q]); // eslint-disable-line react-hooks/exhaustive-deps

  const sort = values.sort || "severity";
  const filters = { severity: values.severity, category: values.category, code: values.code, confidence: values.confidence, q: values.q, sort };
  const state = useAsync(current ? () => api.issues(current.id, { ...filters, page, page_size: PAGE_SIZE }) : null, [
    current?.id,
    JSON.stringify(filters),
    page,
  ]);

  if (listLoading) return <Loading />;
  if (!current) return <NoAudit />;

  const total = state.data?.total ?? 0;
  const codes = rules?.rules.filter((r) => !values.category || r.category === values.category) ?? [];

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Anomalies</h1>
          <p className="lede">
            Chaque ligne indique le constat, sa priorité et une correction possible. Les signaux « À vérifier » sont des heuristiques :
            confirmez-les avant de modifier la fiche.
          </p>
        </div>
        <div className="actions">
          {total > 0 ? (
            <a className="btn" href={exportUrls.issuesCsv(current.id, filters)} download>
              {Icon.download} Exporter {active ? "la sélection" : "tout"} en CSV
            </a>
          ) : (
            <button type="button" className="btn" disabled>
              {Icon.download} Rien à exporter
            </button>
          )}
        </div>
      </div>

      <form className="toolbar" role="search" onSubmit={(e) => e.preventDefault()}>
        <label className="field grow">
          <span>Rechercher un produit</span>
          <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Identifiant, SKU ou titre" maxLength={100} />
        </label>
        <label className="field">
          <span>Priorité</span>
          <select value={values.severity} onChange={(e) => set({ severity: e.target.value })}>
            <option value="">Toutes</option>
            {SEVERITY_ORDER.map((s) => (
              <option key={s} value={s}>
                {SEVERITY_LABEL[s]}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Famille</span>
          <select value={values.category} onChange={(e) => set({ category: e.target.value, code: "" })}>
            <option value="">Toutes</option>
            {(Object.keys(CATEGORY_LABEL) as Category[]).map((c) => (
              <option key={c} value={c}>
                {CATEGORY_LABEL[c]}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Règle</span>
          <select value={values.code} onChange={(e) => set({ code: e.target.value })} style={{ maxWidth: "16rem" }}>
            <option value="">Toutes</option>
            {codes.map((r) => (
              <option key={r.code} value={r.code}>
                {r.title}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Nature</span>
          <select value={values.confidence} onChange={(e) => set({ confidence: e.target.value })}>
            <option value="">Toutes</option>
            <option value="certain">{CONFIDENCE_LABEL.certain}</option>
            <option value="heuristic">{CONFIDENCE_LABEL.heuristic}</option>
          </select>
        </label>
        {active && (
          <button
            type="button"
            className="btn btn-quiet"
            onClick={() => {
              setSearch("");
              reset();
            }}
          >
            Effacer les filtres
          </button>
        )}
      </form>

      {state.error && <ErrorState error={state.error} onRetry={state.reload} />}
      {!state.error && !state.data && <Loading lines={8} />}
      {state.data && (
        <>
          <div className="table-wrap" aria-busy={state.loading}>
            {state.data.items.length === 0 ? (
              <Empty title={active ? "Aucune anomalie ne correspond à ces filtres" : "Aucune anomalie dans cet audit"}>
                {active && <p>Élargissez la recherche ou effacez les filtres.</p>}
              </Empty>
            ) : (
              <table className="data">
                <caption className="visually-hidden">Anomalies de l'audit #{current.id}</caption>
                <thead>
                  <tr>
                    <SortHeader label="Priorité" field="severity" sort={sort} onSort={(s) => set({ sort: s })} />
                    <SortHeader label="Produit" field="product_id" sort={sort} onSort={(s) => set({ sort: s })} />
                    <SortHeader label="Anomalie" field="code" sort={sort} onSort={(s) => set({ sort: s })} />
                    <th>Constat</th>
                    <th>Correction suggérée</th>
                  </tr>
                </thead>
                <tbody>
                  {state.data.items.map((i) => (
                    <tr key={`${i.product_id}-${i.code}`}>
                      <td>
                        <SeverityBadge severity={i.severity} />
                      </td>
                      <td className="cell-title">
                        <button type="button" className="link-btn" onClick={() => setOpenProduct(i.product_id)}>
                          {i.title_fr || <em>Sans titre</em>}
                        </button>
                        <span className="cell-sub">
                          {i.product_id}
                          {i.sku ? `, SKU ${i.sku}` : ", sans SKU"}
                        </span>
                      </td>
                      <td>
                        <strong>{i.message}</strong>
                        <span className="cell-sub">
                          {CATEGORY_LABEL[i.category]} <ConfidenceBadge confidence={i.confidence} />
                        </span>
                      </td>
                      <td>{i.evidence}</td>
                      <td className="muted">{i.suggestion}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPage={(p) => set({ page: p })} noun={["anomalie", "anomalies"]} />
          <p className="muted small">{fmt.plural(current.issue_count, "anomalie", "anomalies")} au total dans cet audit.</p>
        </>
      )}
      <ProductDrawer auditId={current.id} productId={openProduct} onClose={() => setOpenProduct(null)} />
    </>
  );
}
