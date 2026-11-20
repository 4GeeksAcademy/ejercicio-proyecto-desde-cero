"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { api } from "./api";
import { errorMessage } from "./errors";

/** Carga un GET y expone data/error/reload. Cancela resultados obsoletos si cambia la ruta. */
export function useApiData<T>(path: string | null) {
  const te = useTranslations("errors");
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!path) return;
    let live = true;
    api<T>(path)
      .then((d) => live && (setData(d), setError(null)))
      .catch((e) => live && setError(errorMessage(e, te)))
      .finally(() => live && setLoading(false));
    return () => {
      live = false;
    };
  }, [path, tick, te]);

  const reload = useCallback(() => setTick((n) => n + 1), []);
  return { data, error, loading, reload };
}
