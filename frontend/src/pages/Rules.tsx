import { Link } from "react-router-dom";
import { ConfidenceBadge, Loading, SeverityBadge } from "../components/ui";
import { useAudits, useAuditLink } from "../lib/audits";
import { CATEGORY_LABEL, CONFIDENCE_HINT, SEVERITY_LABEL, SEVERITY_ORDER } from "../lib/format";
import { useDocumentTitle } from "../lib/hooks";
import type { Category } from "../lib/types";

export function Rules() {
  useDocumentTitle("Règles");
  const { rules, current } = useAudits();
  const link = useAuditLink();
  if (!rules) return <Loading label="Chargement des règles" />;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Règles d'audit</h1>
          <p className="lede">
            {rules.rules.length} règles explicites, version {rules.version}. Seuls les produits actifs sont audités. Aucune URL n'est appelée :
            les images sont contrôlées sur leur forme uniquement.
          </p>
        </div>
      </div>

      <div className="grid-2 section">
        <section className="panel" aria-labelledby="score-title">
          <h2 id="score-title">Calcul de l'indice qualité</h2>
          <p className="muted" style={{ margin: "var(--s2) 0 var(--s4)" }}>
            Chaque produit actif part de 100 points. Chaque anomalie retire des points selon sa priorité, sans descendre sous 0. L'indice
            mesure la complétude et la cohérence du fichier : ce n'est ni une note SEO, ni une prévision de ventes.
          </p>
          <table className="data">
            <thead>
              <tr>
                <th>Priorité</th>
                <th className="num">Points retirés</th>
              </tr>
            </thead>
            <tbody>
              {SEVERITY_ORDER.map((s) => (
                <tr key={s}>
                  <td>
                    <span className={`sev sev-${s}`}>{SEVERITY_LABEL[s]}</span>
                  </td>
                  <td className="num">−{rules.penalties[s]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
        <section className="panel" aria-labelledby="nature-title">
          <h2 id="nature-title">Constats et signaux à vérifier</h2>
          <dl className="schema" style={{ marginTop: "var(--s4)" }}>
            <dt>
              <ConfidenceBadge confidence="certain" />
            </dt>
            <dd>{CONFIDENCE_HINT.certain}</dd>
            <dt>
              <ConfidenceBadge confidence="heuristic" />
            </dt>
            <dd>
              {CONFIDENCE_HINT.heuristic} Exemple : un prix dix fois supérieur à la médiane peut être une erreur de virgule, ou un produit
              premium.
            </dd>
          </dl>
        </section>
      </div>

      {(Object.keys(CATEGORY_LABEL) as Category[]).map((cat) => (
        <section key={cat} className="section panel" aria-labelledby={`cat-${cat}`}>
          <h2 id={`cat-${cat}`} style={{ marginBottom: "var(--s4)" }}>
            {CATEGORY_LABEL[cat]}
          </h2>
          <div className="rule-list">
            {rules.rules
              .filter((r) => r.category === cat)
              .map((r) => (
                <article key={r.code} className="rule-item" id={r.code}>
                  <div>
                    <h3>{r.title}</h3>
                    <p style={{ marginTop: "var(--s1)" }}>{r.explanation}</p>
                    <p style={{ marginTop: "var(--s2)" }}>
                      <strong style={{ color: "var(--pine)" }}>Correction :</strong> {r.suggestion}
                    </p>
                  </div>
                  <div className="rule-tags">
                    <SeverityBadge severity={r.severity} />
                    <ConfidenceBadge confidence={r.confidence} />
                    <code>{r.code}</code>
                    {current && (
                      <Link className="small" to={link("/issues", { code: r.code })}>
                        Voir les cas
                      </Link>
                    )}
                  </div>
                </article>
              ))}
          </div>
        </section>
      ))}
    </>
  );
}
