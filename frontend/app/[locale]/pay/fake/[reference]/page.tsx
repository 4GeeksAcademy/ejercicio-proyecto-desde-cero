import { setRequestLocale } from "next-intl/server";
import { FakeCheckout } from "@/components/bookings/FakeCheckout";

export const metadata = { title: "Test payment", robots: { index: false, follow: false } };

export default async function Page({ params }: { params: Promise<{ locale: string; reference: string }> }) {
  const { locale, reference } = await params;
  setRequestLocale(locale);
  return <FakeCheckout reference={reference} />;
}
