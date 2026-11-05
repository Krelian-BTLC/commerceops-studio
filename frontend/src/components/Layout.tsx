import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useAudits, useAuditLink } from "../lib/audits";
import { fmt } from "../lib/format";

const LINKS = [
  { to: "/", label: "Tableau de bord" },
  { to: "/issues", label: "Anomalies" },
  { to: "/products", label: "Produits" },
  { to: "/compare", label: "Avant / après" },
  { to: "/history", label: "Historique" },
  { to: "/import", label: "Importer" },
  { to: "/rules", label: "Règles" },
];

function BrandMark() {
  // Étiquette stylisée : rappelle l'indice affiché sur le tableau de bord.
  return (
    <svg className="brand-mark" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 2 20 6.5V20a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6.5Z" fill="var(--tag)" stroke="var(--ink)" strokeWidth="1.5" />
      <circle cx="12" cy="7.5" r="1.6" fill="var(--paper)" stroke="var(--ink)" strokeWidth="1.2" />
      <path d="M8.5 14.5 11 17l4.5-5" fill="none" stroke="var(--pine)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function AuditPicker() {
  const { audits, current, select } = useAudits();
  const { pathname } = useLocation();
  if (audits.length === 0 || pathname === "/compare" || pathname === "/history") return null;
  return (
    <div className="context-bar">
      <label className="audit-picker">
        <span className="small muted">Audit affiché</span>
        <select value={current?.id ?? ""} onChange={(e) => select(Number(e.target.value))}>
          {audits.map((a) => (
            <option key={a.id} value={a.id}>
              #{a.id} {a.label} ({fmt.date(a.created_at)})
            </option>
          ))}
        </select>
      </label>
      {current && (
        <span className="small muted context-meta">
          {fmt.plural(current.total_products, "produit", "produits")}, {fmt.plural(current.issue_count, "anomalie", "anomalies")}
        </span>
      )}
    </div>
  );
}

export function Layout() {
  const link = useAuditLink();
  return (
    <>
      <a href="#main" className="skip-link">
        Aller au contenu
      </a>
      <header className="topbar">
        <div className="topbar-inner">
          <NavLink to={link("/")} className="brand">
            <BrandMark />
            CommerceOps Studio
          </NavLink>
          <nav className="nav" aria-label="Navigation principale">
            {LINKS.map((l) => (
              <NavLink key={l.to} to={link(l.to)} end={l.to === "/"}>
                {l.label}
              </NavLink>
            ))}
          </nav>
        </div>
        <AuditPicker />
      </header>
      <main id="main" tabIndex={-1}>
        <Outlet />
      </main>
      <footer className="footer">
        CommerceOps Studio v0.2 — outil d'audit local. À utiliser avec des catalogues fictifs ou dont vous avez l'autorisation ;
        les URL d'images ne sont jamais téléchargées.
      </footer>
    </>
  );
}
