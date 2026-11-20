import { setRequestLocale } from "next-intl/server";
import { UsersAdmin } from "@/components/admin/ReadOnlyViews";

export default async function Page({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <UsersAdmin />;
}
