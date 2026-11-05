import { Link } from "react-router-dom";
import { SEVERITY_LABEL, SEVERITY_ORDER, fmt } from "../lib/format";
import type { Severity } from "../lib/types";

export interface BarItem {
  key: string;
  label: string;
  value: number;
  tone?: Severity | "ok";
  href?: string;
}

/** Barres horizontales triées : lisibles, accessibles, sans bibliothèque de graphiques. */
export function BarList({ items, label }: { items: BarItem[]; label: string }) {
  const max = Math.max(1, ...items.map((i) => i.value));
  return (
    <ul className="bars" aria-label={label}>
      {items.map((item) => (
        <li key={item.key} className="bar-row">
          {item.href ? (
            <Link to={item.href} title={item.label}>
              {item.label}
            </Link>
          ) : (
            <span className="bar-label" title={item.label}>
              {item.label}
            </span>
          )}
          <span className="bar-track" aria-hidden="true">
            <span className={`bar-fill ${item.tone ?? ""}`} style={{ width: `${(item.value / max) * 100}%`, display: "block" }} />
          </span>
          <span className="bar-value">{fmt.int(item.value)}</span>
        </li>
      ))}
    </ul>
  );
}

const STACK_COLOR: Record<Severity, string> = { high: "var(--high)", medium: "var(--medium-bar)", low: "var(--low)" };

/** Une seule barre empilée : la répartition des priorités se lit d'un coup d'œil. */
export function SeverityStack({ counts }: { counts: Record<Severity, number> }) {
  const total = SEVERITY_ORDER.reduce((sum, s) => sum + counts[s], 0);
  const summary = SEVERITY_ORDER.map((s) => `${SEVERITY_LABEL[s]} : ${counts[s]}`).join(", ");
  return (
    <div>
      <div className="stack" role="img" aria-label={`Répartition par priorité. ${summary}`}>
        {total > 0 &&
          SEVERITY_ORDER.filter((s) => counts[s] > 0).map((s) => (
            <span key={s} style={{ flexGrow: counts[s], background: STACK_COLOR[s] }} />
          ))}
      </div>
      <div className="legend">
        {SEVERITY_ORDER.map((s) => (
          <span key={s} className={`sev sev-${s}`}>
            <strong>{fmt.int(counts[s])}</strong>&nbsp;{SEVERITY_LABEL[s].toLowerCase()}
          </span>
        ))}
      </div>
    </div>
  );
}
