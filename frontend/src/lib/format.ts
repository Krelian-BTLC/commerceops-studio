import type { Category, Confidence, Severity } from "./types";

export const SEVERITY_LABEL: Record<Severity, string> = { high: "Haute", medium: "Moyenne", low: "Basse" };
export const SEVERITY_ORDER: Severity[] = ["high", "medium", "low"];
export const CONFIDENCE_LABEL: Record<Confidence, string> = { certain: "Constat", heuristic: "À vérifier" };
export const CONFIDENCE_HINT: Record<Confidence, string> = {
  certain: "Constat factuel : la donnée est absente, dupliquée ou mal formée.",
  heuristic: "Signal probable, pas une certitude : une personne doit confirmer avant de corriger.",
};
export const CATEGORY_LABEL: Record<Category, string> = {
  identification: "Identification",
  content: "Contenu",
  pricing: "Prix",
  media: "Médias",
  translation: "Traduction",
};

const number = new Intl.NumberFormat("fr-FR");
const decimal = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const dateTime = new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium", timeStyle: "short" });

export const fmt = {
  int: (n: number) => number.format(n),
  score: (n: number | null) => (n === null ? "—" : decimal.format(n)),
  date: (iso: string) => dateTime.format(new Date(iso)),
  percent: (part: number, total: number) => (total ? `${Math.round((part / total) * 100)} %` : "0 %"),
  signed: (n: number | null, digits = 0) => {
    if (n === null) return "—";
    const text = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(Math.abs(n));
    return n > 0 ? `+${text}` : n < 0 ? `−${text}` : text;
  },
  price: (raw: string) => {
    const value = Number(raw);
    return raw !== "" && Number.isFinite(value)
      ? new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR" }).format(value)
      : raw || "—";
  },
  plural: (n: number, one: string, many: string) => `${number.format(n)} ${n > 1 ? many : one}`,
};

/** Niveau qualitatif de l'indice, tel qu'utilisé par l'API (score_distribution). */
export function scoreBand(score: number | null): "excellent" | "good" | "fair" | "poor" | "none" {
  if (score === null) return "none";
  if (score >= 90) return "excellent";
  if (score >= 70) return "good";
  if (score >= 40) return "fair";
  return "poor";
}

export const BAND_LABEL = { excellent: "Très bon", good: "Correct", fair: "Fragile", poor: "Critique", none: "Non audité" } as const;
