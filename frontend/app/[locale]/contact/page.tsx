import { getTranslations, setRequestLocale } from "next-intl/server";
import { titled } from "@/lib/meta";

export const generateMetadata = titled("contact", "title");

export default async function Page({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("contact");
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <h1 className="text-3xl font-bold">{t("title")}</h1>
      <p>{t("body")}</p>
      <p className="font-semibold">{t("location")}</p>
      <p className="text-sm text-muted">{t("pending")}</p>
    </div>
  );
}
