import { getTranslations, setRequestLocale } from "next-intl/server";
import { MyBookings } from "@/components/bookings/MyBookings";
import { titled } from "@/lib/meta";

export const generateMetadata = titled("booking", "title", true);

export default async function AccountPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("booking");
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">{t("title")}</h1>
      <MyBookings />
    </div>
  );
}
