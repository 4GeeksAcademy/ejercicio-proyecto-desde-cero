import { setRequestLocale } from "next-intl/server";
import { BookingsAdmin } from "@/components/admin/BookingsAdmin";

export default async function Page({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <BookingsAdmin />;
}
