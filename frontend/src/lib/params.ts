import { useCallback } from "react";
import { useSearchParams } from "react-router-dom";

/**
 * Filtres stockés dans l'URL : la vue survit au rechargement, au bouton
 * Précédent et peut être partagée. Toute modification de filtre revient page 1.
 */
export function useFilters<K extends string>(keys: readonly K[]) {
  const [params, setParams] = useSearchParams();
  const values = Object.fromEntries(keys.map((k) => [k, params.get(k) ?? ""])) as Record<K, string>;
  const page = Math.max(1, Number(params.get("page")) || 1);

  const set = useCallback(
    (changes: Partial<Record<K | "page", string | number>>) => {
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          for (const [key, value] of Object.entries(changes)) {
            if (value === "" || value === undefined || value === null) next.delete(key);
            else next.set(key, String(value));
          }
          if (!("page" in changes)) next.delete("page");
          if (next.get("page") === "1") next.delete("page");
          return next;
        },
        { replace: true },
      );
    },
    [setParams],
  );

  const reset = useCallback(() => {
    setParams(
      (prev) => {
        const next = new URLSearchParams();
        const audit = prev.get("audit");
        if (audit) next.set("audit", audit);
        return next;
      },
      { replace: true },
    );
  }, [setParams]);

  return { values, page, set, reset, active: keys.some((k) => values[k] !== "" && k !== "sort") };
}
