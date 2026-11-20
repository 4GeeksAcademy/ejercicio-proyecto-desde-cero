import { setRequestLocale } from "next-intl/server";
import { CoursesAdmin } from "@/components/admin/CoursesAdmin";

export default async function Page({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <CoursesAdmin />;
}
