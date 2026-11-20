import { getTranslations } from "next-intl/server";
import { AdminNav } from "@/components/admin/AdminNav";
import { RequireAuth } from "@/components/auth/RequireAuth";

export const metadata = { robots: { index: false, follow: false } };

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const t = await getTranslations("admin");
  return (
    <RequireAuth permission="course:write">
      <h1 className="mb-4 text-3xl font-bold">{t("title")}</h1>
      <AdminNav />
      {children}
    </RequireAuth>
  );
}
