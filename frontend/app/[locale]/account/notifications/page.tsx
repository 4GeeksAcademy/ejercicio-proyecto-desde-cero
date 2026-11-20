import { getTranslations, setRequestLocale } from "next-intl/server";
import { NotificationsList } from "@/components/bookings/NotificationsList";
import { titled } from "@/lib/meta";

export const generateMetadata = titled("account", "notifications", true);

export default async function Page({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("account");
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">{t("notifications")}</h1>
      <NotificationsList />
    </div>
  );
}
