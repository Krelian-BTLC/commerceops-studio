import { useRef, useState, type DragEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Icon } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { useAudits } from "../lib/audits";
import { fmt } from "../lib/format";
import { useDocumentTitle } from "../lib/hooks";
import type { ImportResult } from "../lib/types";

export const MAX_BYTES = 2_000_000;
const COLUMNS: [string, string][] = [
  ["product_id", "Identifiant unique, obligatoire. Un doublon fait rejeter le fichier."],
  ["sku", "Référence de stock. Vide ou partagée : anomalie de priorité haute."],
  ["title_fr", "Titre français. Vide, très court ou très long : anomalie."],
  ["description_fr", "Description. Absente, courte, dupliquée ou provisoire : anomalie."],
  ["price_eur", "Prix TTC strictement positif. « 29,95 » et « 29.95 » sont acceptés."],
  ["image_url", "URL https:// de l'image. Elle n'est jamais téléchargée, seule sa forme est vérifiée."],
  ["title_en", "Traduction anglaise du titre. Vide ou identique au français : anomalie."],
  ["status", "active ou draft. Les brouillons sont importés mais pas audités."],
];

/** Contrôles côté navigateur : retour immédiat. Le serveur reste l'autorité. */
export function checkFile(file: File): string | null {
  if (!file.name.toLowerCase().endsWith(".csv")) return "Ce fichier n'est pas un .csv. Exportez le catalogue au format CSV UTF-8.";
  if (file.size === 0) return "Le fichier est vide.";
  if (file.size > MAX_BYTES) return `Le fichier fait ${(file.size / 1_000_000).toFixed(1)} Mo : la limite est de 2 Mo.`;
  return null;
}

function downloadTemplate() {
  const csv =
    "product_id,sku,title_fr,description_fr,price_eur,image_url,title_en,status\r\n" +
    'EX-001,SKU-001,Vase en grès sauge,"Vase en grès émaillé, 25 cm, pour bouquets et branches séchées.",34.90,https://images.example.com/vase.jpg,Sage stoneware vase,active\r\n';
  const url = URL.createObjectURL(new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = "modele-catalogue.csv";
  a.click();
  URL.revokeObjectURL(url);
}

export function ImportPage() {
  useDocumentTitle("Importer");
  const { refresh, select } = useAudits();
  const navigate = useNavigate();
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [label, setLabel] = useState("");
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState<"upload" | "demo" | null>(null);
  const [clientError, setClientError] = useState<string | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);

  function choose(next: File | undefined) {
    setResult(null);
    setError(null);
    if (!next) return;
    const problem = checkFile(next);
    setClientError(problem);
    setFile(problem ? null : next);
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    choose(e.dataTransfer.files[0]);
  }

  async function upload() {
    if (!file) return;
    setBusy("upload");
    setError(null);
    try {
      const res = await api.upload(file, label);
      setResult(res);
      setFile(null);
      setLabel("");
      if (input.current) input.current.value = "";
      await refresh();
      select(res.audit.id);
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, "unknown", String(err)));
    } finally {
      setBusy(null);
    }
  }

  async function loadDemo() {
    setBusy("demo");
    setError(null);
    try {
      const demo = await api.loadDemo();
      await refresh();
      navigate(`/compare?base=${demo.before.id}&target=${demo.after.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, "unknown", String(err)));
      setBusy(null);
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Importer un catalogue</h1>
          <p className="lede">
            Chaque import crée un nouvel audit, conservé dans l'historique. Un fichier rejeté ne modifie rien.
          </p>
        </div>
      </div>

      <div className="grid-2">
        <section aria-labelledby="upload-title">
          <h2 id="upload-title" className="visually-hidden">
            Fichier à importer
          </h2>
          <label
            className="drop"
            data-active={dragging}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
          >
            {Icon.upload}
            <strong>Déposez un fichier CSV ici</strong>
            <span className="muted">ou cliquez pour le choisir. UTF-8, séparateur virgule ou point-virgule, 2 Mo maximum.</span>
            <input
              ref={input}
              type="file"
              accept=".csv,text/csv"
              className="visually-hidden"
              data-testid="file-input"
              onChange={(e) => choose(e.target.files?.[0])}
            />
            {file && (
              <span className="file-chip">
                {file.name} ({fmt.int(Math.ceil(file.size / 1000))} Ko)
              </span>
            )}
          </label>

          <div className="toolbar" style={{ marginTop: "var(--s4)" }}>
            <label className="field grow">
              <span>Nom de l'audit (facultatif)</span>
              <input type="text" value={label} onChange={(e) => setLabel(e.target.value)} maxLength={80} placeholder="Par défaut : le nom du fichier" />
            </label>
            <button type="button" className="btn btn-primary" onClick={upload} disabled={!file || busy !== null}>
              {busy === "upload" ? "Analyse en cours…" : "Lancer l'audit"}
            </button>
          </div>

          <div aria-live="polite">
            {clientError && (
              <div className="notice notice-error" role="alert">
                <h3>Fichier refusé</h3>
                <p>{clientError}</p>
              </div>
            )}

            {error && (
              <div className="notice notice-error" role="alert">
                <h3>{error.code === "invalid_catalog" ? "Le fichier a été rejeté, aucun audit créé" : "L'import a échoué"}</h3>
                <p>{error.message}</p>
                {error.errors.length > 1 && (
                  <ul>
                    {error.errors.map((e, i) => (
                      <li key={i}>
                        {e.line !== null && <>Ligne {e.line}</>}
                        {e.column && <> (colonne {e.column})</>}
                        {e.line !== null || e.column ? " : " : ""}
                        {e.message}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {result && (
              <div className="notice notice-ok" role="status">
                <h3>Audit #{result.audit.id} créé</h3>
                <p>
                  {fmt.plural(result.imported, "produit importé", "produits importés")}, {fmt.plural(result.issues, "anomalie détectée", "anomalies détectées")}
                  {result.audit.quality_score !== null && <>, indice qualité moyen {fmt.score(result.audit.quality_score)} sur 100</>}.
                </p>
                {result.warnings.length > 0 && (
                  <ul>
                    {result.warnings.map((w) => (
                      <li key={w.code}>{w.message}</li>
                    ))}
                  </ul>
                )}
                <div className="actions">
                  <Link className="btn btn-primary btn-sm" to={`/?audit=${result.audit.id}`}>
                    Voir le tableau de bord
                  </Link>
                  <Link className="btn btn-sm" to={`/issues?audit=${result.audit.id}`}>
                    Voir les anomalies
                  </Link>
                </div>
              </div>
            )}
          </div>

          <section className="panel section" aria-labelledby="demo-title">
            <h2 id="demo-title">Essayer avec la démonstration</h2>
            <p className="muted" style={{ margin: "var(--s2) 0 var(--s4)" }}>
              Importe deux catalogues fictifs de la boutique imaginaire « Maison Ardoise » : la version initiale (150 produits), puis la
              version corrigée, et ouvre la comparaison.
            </p>
            <button type="button" className="btn" onClick={loadDemo} disabled={busy !== null}>
              {busy === "demo" ? "Import de la démo…" : "Charger la démonstration"}
            </button>
          </section>
        </section>

        <section className="panel" aria-labelledby="schema-title">
          <div className="section-head">
            <h2 id="schema-title">Colonnes attendues</h2>
            <button type="button" className="btn btn-sm" onClick={downloadTemplate}>
              {Icon.download} Modèle CSV
            </button>
          </div>
          <dl className="schema">
            {COLUMNS.map(([name, help]) => (
              <div key={name}>
                <dt>
                  <code>{name}</code>
                </dt>
                <dd>{help}</dd>
              </div>
            ))}
          </dl>
          <p className="muted small">Les autres colonnes sont ignorées et signalées. Limite : 10 000 produits.</p>
        </section>
      </div>
    </>
  );
}
