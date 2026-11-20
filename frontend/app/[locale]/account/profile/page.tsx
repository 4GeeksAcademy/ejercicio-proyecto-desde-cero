import { getTranslations, setRequestLocale } from "next-intl/server";
import { ProfileForm } from "@/components/bookings/ProfileForm";
import { titled } from "@/lib/meta";

export const generateMetadata = titled("account", "profile", true);

export default async function Page({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("account");
  return (
    <div className="max-w-xl space-y-6">
      <h1 className="text-3xl font-bold">{t("profile")}</h1>
      <ProfileForm />
    </div>
  );
}
