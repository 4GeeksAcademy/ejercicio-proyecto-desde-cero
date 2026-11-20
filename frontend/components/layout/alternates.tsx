"use client";

import { createContext, useContext, useEffect, useState } from "react";

type Alt = { alternates: Record<string, string> | null; set: (a: Record<string, string> | null) => void };
const Ctx = createContext<Alt>({ alternates: null, set: () => {} });

export function AlternatesProvider({ children }: { children: React.ReactNode }) {
  const [alternates, set] = useState<Record<string, string> | null>(null);
  return <Ctx.Provider value={{ alternates, set }}>{children}</Ctx.Provider>;
}

export const useAlternates = () => useContext(Ctx);

/** La página de un curso declara sus slugs por idioma para que el selector de idioma apunte a la URL correcta. */
export function RegisterAlternates({ alternates }: { alternates: Record<string, string> }) {
  const { set } = useAlternates();
  useEffect(() => {
    set(alternates);
    return () => set(null);
  }, [alternates, set]);
  return null;
}
