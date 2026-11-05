import { BAND_LABEL, scoreBand } from "../lib/format";

/**
 * Part des fiches actives sans anomalie, présentée comme une étiquette de prix
 * suspendue. Ce ratio ne peut pas être « dilué » comme une moyenne d'indices.
 */
export function HangTag({ active, affected }: { active: number; affected: number }) {
  const percent = active ? Math.round(((active - affected) / active) * 100) : null;
  const band = scoreBand(percent);
  const label = percent === null ? "Aucune fiche active" : `${percent} % des fiches actives sans anomalie`;
  return (
    <div className="hangtag-wrap">
      <span className="hangtag-string" aria-hidden="true" />
      <figure className="hangtag" style={{ margin: 0 }} aria-label={label}>
        <figcaption className="hangtag-label">Fiches sans anomalie</figcaption>
        <strong className="hangtag-value">{percent === null ? "—" : `${percent} %`}</strong>
        <span className="hangtag-scale">
          {active - affected} sur {active} actives
        </span>
        <br />
        <span className="hangtag-band">{BAND_LABEL[band]}</span>
      </figure>
    </div>
  );
}
