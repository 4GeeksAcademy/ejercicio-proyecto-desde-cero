import { setRequestLocale } from "next-intl/server";
import { BookingDetail } from "@/components/bookings/BookingDetail";
import { titled } from "@/lib/meta";

export const generateMetadata = titled("booking", "detail", true);

export default async function BookingPage({ params }: { params: Promise<{ locale: string; id: string }> }) {
  const { locale, id } = await params;
  setRequestLocale(locale);
  return <BookingDetail id={id} />;
}
