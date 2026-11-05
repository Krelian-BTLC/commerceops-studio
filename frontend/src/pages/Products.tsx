import { useEffect, useState } from "react";
import { ProductDrawer } from "../components/dialogs";
import { Empty, ErrorState, Icon, Loading, NoAudit, Pagination, ScoreBadge, SeverityBadge, SortHeader } from "../components/ui";
import { api, exportUrls } from "../lib/api";
import { useAudits } from "../lib/audits";
import { SEVERITY_LABEL, SEVERITY_ORDER, fmt } from "../lib/format";
import { useAsync, useDebounced, useDocumentTitle } from "../lib/hooks";
import { useFilters } from "../lib/params";

const PAGE_SIZE = 25;
const KEYS = ["q", "status", "severity", "has_issues", "sort"] as const;

export function Products() {
  useDocumentTitle("Produits");
  const { current, loading: listLoading } = useAudits();
  const { values, page, set, reset, active } = useFilters(KEYS);
  const [search, setSearch] = useState(values.q);
  const q = useDebounced(search);
  const [openProduct, setOpenProduct] = useState<string | null>(null);

  useEffect(() => {
    if (q !== values.q) set({ q });
  }, [q]); // eslint-disable-line react-hooks/exhaustive-deps

  const sort = values.sort || "score";
  const filters = { q: values.q, status: values.status, severity: values.severity, has_issues: values.has_issues, sort };
  const state = useAsync(current ? () => api.products(current.id, { ...filters, page, page_size: PAGE_SIZE }) : null, [
    current?.id,
    JSON.stringify(filters),
    page,
  ]);

  if (listLoading) return <Loading />;
  if (!current) return <NoAudit />;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Produits</h1>
          <p className="lede">
            Triés par défaut du plus fragile au plus complet. Ouvrez une fiche pour voir le détail de son indice et les corrections suggérées.
          </p>
        </div>
        <div className="actions">
          <a className="btn" href={exportUrls.productsCsv(current.id)} download>
            {Icon.download} Exporter les produits en CSV
          </a>
        </div>
      </div>

      <form className="toolbar" role="search" onSubmit={(e) => e.preventDefault()}>
        <label className="field grow">
          <span>Rechercher</span>
          <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Identifiant, SKU ou titre" maxLength={100} />
        </label>
        <label className="field">
          <span>Statut</span>
          <select value={values.status} onChange={(e) => set({ status: e.target.value })}>
            <option value="">Tous</option>
            <option value="active">Actifs</option>
            <option value="draft">Brouillons</option>
          </select>
        </label>
        <label className="field">
          <span>Priorité la plus haute</span>
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
          <span>Anomalies</span>
          <select value={values.has_issues} onChange={(e) => set({ has_issues: e.target.value })}>
            <option value="">Avec ou sans</option>
            <option value="true">Avec anomalies</option>
            <option value="false">Actifs sans anomalie</option>
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
              <Empty title="Aucun produit ne correspond">
                <p>Modifiez la recherche ou effacez les filtres.</p>
              </Empty>
            ) : (
              <table className="data">
                <caption className="visually-hidden">Produits de l'audit #{current.id}</caption>
                <thead>
                  <tr>
                    <SortHeader label="Produit" field="title" sort={sort} onSort={(s) => set({ sort: s })} />
                    <SortHeader label="SKU" field="sku" sort={sort} onSort={(s) => set({ sort: s })} />
                    <SortHeader label="Prix" field="price" sort={sort} onSort={(s) => set({ sort: s })} className="num" />
                    <SortHeader label="Statut" field="status" sort={sort} onSort={(s) => set({ sort: s })} />
                    <SortHeader label="Anomalies" field="issues" sort={sort} onSort={(s) => set({ sort: s })} className="num" initial="desc" />
                    <th>Priorité max.</th>
                    <SortHeader label="Indice" field="score" sort={sort} onSort={(s) => set({ sort: s })} className="num" />
                  </tr>
                </thead>
                <tbody>
                  {state.data.items.map((p) => (
                    <tr key={p.product_id}>
                      <td className="cell-title">
                        <button type="button" className="link-btn" onClick={() => setOpenProduct(p.product_id)}>
                          {p.title_fr || <em>Sans titre</em>}
                        </button>
                        <span className="cell-sub">{p.product_id}</span>
                      </td>
                      <td className="nowrap">{p.sku || <span className="empty-value">vide</span>}</td>
                      <td className="num nowrap">{fmt.price(p.price_eur)}</td>
                      <td>{p.status === "active" ? "Actif" : "Brouillon"}</td>
                      <td className="num">{p.status === "draft" ? "—" : p.issue_count}</td>
                      <td>{p.status === "draft" ? <span className="muted small">Non audité</span> : <SeverityBadge severity={p.worst_severity} />}</td>
                      <td className="num">
                        <ScoreBadge score={p.score} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <Pagination page={page} pageSize={PAGE_SIZE} total={state.data.total} onPage={(p) => set({ page: p })} noun={["produit", "produits"]} />
        </>
      )}
      <ProductDrawer auditId={current.id} productId={openProduct} onClose={() => setOpenProduct(null)} />
    </>
  );
}
