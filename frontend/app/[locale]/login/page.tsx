import { Suspense } from "react";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { LoginForm } from "@/components/auth/AuthForms";
import { titled } from "@/lib/meta";

export const generateMetadata = titled("auth", "loginTitle", true);

export default async function Page({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("auth");
  return (
    <div className="mx-auto max-w-md rounded-xl border border-line bg-surface-2 p-6 shadow-sm">
      <h1 className="mb-6 text-2xl font-bold">{t("loginTitle")}</h1>
      <Suspense>
        <LoginForm />
      </Suspense>
    </div>
  );
}
