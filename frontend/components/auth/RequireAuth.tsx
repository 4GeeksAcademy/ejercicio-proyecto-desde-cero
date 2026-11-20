"use client";

import { useEffect } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { useAuth, can } from "./AuthProvider";
import { Alert } from "@/components/ui/Alert";

/**
 * Guarda de rutas en el cliente (experiencia de usuario). La seguridad REAL está en la API:
 * aunque alguien eluda esto, el backend responde 401/403 a cada petición.
 */
export function RequireAuth({ children, permission }: { children: React.ReactNode; permission?: string }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const t = useTranslations();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading || !user) {
    return <p role="status" className="py-10 text-center text-muted">{t("common.loading")}</p>;
  }
  if (permission && !can(user, permission)) {
    return <Alert kind="error">{t("admin.noAccess")}</Alert>;
  }
  return <>{children}</>;
}
