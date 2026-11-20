import { getTranslations, setRequestLocale } from "next-intl/server";
import { Alert } from "@/components/ui/Alert";
import { titled } from "@/lib/meta";

export const generateMetadata = titled("legal", "privacyTitle", false, "/privacy");

export default async function Page({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("legal");
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <h1 className="text-3xl font-bold">{t("privacyTitle")}</h1>
      <Alert kind="warning">{t("draftNotice")}</Alert>
      <p>{t("privacyBody")}</p>
    </div>
  );
}
