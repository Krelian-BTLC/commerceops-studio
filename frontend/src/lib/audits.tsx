import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { api, ApiError } from "./api";
import type { Audit, RulesCatalog, RuleInfo } from "./types";

interface AuditsValue {
  audits: Audit[];
  loading: boolean;
  error: ApiError | undefined;
  /** Audit sélectionné : paramètre ?audit= de l'URL, sinon le plus récent. */
  current: Audit | undefined;
  select: (id: number) => void;
  refresh: () => Promise<Audit[]>;
  rules: RulesCatalog | undefined;
  rule: (code: string) => RuleInfo | undefined;
}

const AuditsContext = createContext<AuditsValue | null>(null);

export function AuditsProvider({ children }: { children: ReactNode }) {
  const [audits, setAudits] = useState<Audit[]>([]);
  const [rules, setRules] = useState<RulesCatalog>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError>();
  const [params, setParams] = useSearchParams();

  const refresh = useCallback(async () => {
    try {
      const list = await api.audits();
      setAudits(list);
      setError(undefined);
      return list;
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, "unknown", String(err)));
      return [];
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    api.rules().then(setRules).catch(() => undefined);
  }, [refresh]);

  const requested = Number(params.get("audit"));
  const current = audits.find((a) => a.id === requested) ?? audits[0];

  const select = useCallback(
    (id: number) => {
      setParams((prev) => {
        const next = new URLSearchParams(prev);
        next.set("audit", String(id));
        next.delete("page");
        return next;
      });
    },
    [setParams],
  );

  const value = useMemo<AuditsValue>(() => {
    const byCode = new Map(rules?.rules.map((r) => [r.code, r]));
    return { audits, loading, error, current, select, refresh, rules, rule: (code) => byCode.get(code) };
  }, [audits, loading, error, current, select, refresh, rules]);

  return <AuditsContext.Provider value={value}>{children}</AuditsContext.Provider>;
}

export function useAudits(): AuditsValue {
  const value = useContext(AuditsContext);
  if (!value) throw new Error("useAudits doit être utilisé dans <AuditsProvider>");
  return value;
}

/** Conserve ?audit= lors de la navigation entre les pages. */
export function useAuditLink() {
  const { current } = useAudits();
  return (path: string, extra: Record<string, string> = {}) => {
    const search = new URLSearchParams(extra);
    if (current) search.set("audit", String(current.id));
    const text = search.toString();
    return text ? `${path}?${text}` : path;
  };
}
