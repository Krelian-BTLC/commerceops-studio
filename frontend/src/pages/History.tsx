import { useState } from "react";
import { Link } from "react-router-dom";
import { ConfirmDialog } from "../components/dialogs";
import { ErrorState, Icon, Loading, NoAudit, ScoreBadge } from "../components/ui";
import { api, ApiError, exportUrls } from "../lib/api";
import { useAudits } from "../lib/audits";
import { fmt } from "../lib/format";
import { useDocumentTitle } from "../lib/hooks";
import type { Audit } from "../lib/types";

export function History() {
  useDocumentTitle("Historique");
  const { audits, loading, error, refresh } = useAudits();
  const [pending, setPending] = useState<Audit | null>(null);
  const [busy, setBusy] = useState(false);
  const [deleteError, setDeleteError] = useState<ApiError | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function confirmDelete() {
    if (!pending) return;
    setBusy(true);
    setDeleteError(null);
    try {
      await api.deleteAudit(pending.id);
      setMessage(`Audit #${pending.id} supprimé.`);
      setPending(null);
      await refresh();
    } catch (err) {
      setDeleteError(err instanceof ApiError ? err : new ApiError(0, "unknown", String(err)));
      setPending(null);
    } finally {
      setBusy(false);
    }
  }

  if (error) return <ErrorState error={error} onRetry={() => void refresh()} />;
  if (loading) return <Loading />;
  if (audits.length === 0) return <NoAudit />;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Historique des audits</h1>
          <p className="lede">
            Les résultats de chaque audit sont conservés tels qu'ils ont été calculés, avec la version des règles et l'empreinte du
            fichier source.
          </p>
        </div>
        {audits.length >= 2 && (
          <Link className="btn" to={`/compare?base=${audits[1]!.id}&target=${audits[0]!.id}`}>
            Comparer les deux derniers
          </Link>
        )}
      </div>

      <div aria-live="polite">
        {message && <p className="notice notice-ok section">{message}</p>}
        {deleteError && <ErrorState error={deleteError} />}
      </div>

      <div className="table-wrap section">
        <table className="data">
          <caption className="visually-hidden">Audits enregistrés</caption>
          <thead>
            <tr>
              <th>Audit</th>
              <th>Date</th>
              <th className="num">Produits</th>
              <th className="num">Anomalies</th>
              <th className="num">Priorité haute</th>
              <th className="num">Indice moyen</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {audits.map((a) => (
              <tr key={a.id}>
                <td className="cell-title">
                  <Link to={`/?audit=${a.id}`}>
                    #{a.id} {a.label}
                  </Link>
                  <span className="cell-sub" title={`SHA-256 ${a.source_sha256}`}>
                    {a.source_filename}, règles {a.rules_version}
                  </span>
                </td>
                <td className="nowrap">{fmt.date(a.created_at)}</td>
                <td className="num">{fmt.int(a.total_products)}</td>
                <td className="num">{fmt.int(a.issue_count)}</td>
                <td className="num">{fmt.int(a.issues_by_severity.high)}</td>
                <td className="num">
                  <ScoreBadge score={a.quality_score === null ? null : Math.round(a.quality_score)} />
                </td>
                <td>
                  <div className="actions" style={{ flexWrap: "nowrap" }}>
                    <a className="btn btn-sm" href={exportUrls.pdf(a.id)} download aria-label={`Télécharger le rapport PDF de l'audit ${a.id}`}>
                      {Icon.download} PDF
                    </a>
                    <button type="button" className="btn btn-sm btn-danger" onClick={() => setPending(a)} aria-label={`Supprimer l'audit ${a.id}`}>
                      Supprimer
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ConfirmDialog
        open={pending !== null}
        title={`Supprimer l'audit #${pending?.id ?? ""} ?`}
        confirmLabel="Supprimer définitivement"
        busy={busy}
        onConfirm={confirmDelete}
        onCancel={() => setPending(null)}
      >
        <p>
          « {pending?.label} » et ses {fmt.int(pending?.issue_count ?? 0)} anomalies seront effacés de la base locale. Le fichier CSV
          d'origine n'est pas concerné. Cette action est irréversible.
        </p>
      </ConfirmDialog>
    </>
  );
}
