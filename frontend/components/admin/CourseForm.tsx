"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Link, useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { errorMessage, fieldErrors } from "@/lib/errors";
import { useApiData } from "@/lib/useApiData";
import type { Category } from "@/lib/types";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { CheckboxField, SelectField, TextAreaField, TextField } from "@/components/ui/Field";

type Venue = { id: string; name: string; address: string };

/** "2026-12-05T09:00" (hora de Bogotá, UTC-5 sin DST) -> ISO con zona. */
const bogotaIso = (local: string) => `${local}:00-05:00`;

export function CourseForm() {
  const t = useTranslations("admin");
  const ta = useTranslations("auth");
  const te = useTranslations("errors");
  const router = useRouter();
  const categories = useApiData<Category[]>("/categories?locale=es");
  const venues = useApiData<Venue[]>("/admin/venues");
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setFields({});
    const f = new FormData(e.currentTarget);
    const get = (k: string) => String(f.get(k) ?? "");
    const translations: Record<string, unknown> = {
      es: { name: get("name_es"), short_description: get("short_es"), description: get("desc_es") },
    };
    if (get("name_en")) translations.en = { name: get("name_en"), short_description: get("short_en") || get("name_en"), description: get("desc_en") || get("short_en") || get("name_en") };
    try {
      await api("/admin/courses", {
        method: "POST",
        body: {
          category_id: get("category_id"),
          venue_id: get("venue_id"),
          starts_at: bogotaIso(get("starts_at")),
          ends_at: bogotaIso(get("ends_at")),
          capacity: Number(get("capacity")),
          price_minor: Math.round(Number(get("price")) * 100), // pesos -> centavos (entero)
          requires_approval: f.get("requires_approval") === "on",
          is_recorded: f.get("is_recorded") === "on",
          translations,
        },
      });
      setDone(true);
      setTimeout(() => router.push("/admin/courses"), 1200);
    } catch (err) {
      const fe = fieldErrors(err);
      setFields(fe);
      setError(Object.keys(fe).length ? ta("fixErrors") : errorMessage(err, te));
      setBusy(false);
    }
  }

  if (done) return <Alert kind="success">{t("created")}</Alert>;
  return (
    <form onSubmit={onSubmit} className="max-w-2xl space-y-4" noValidate>
      {error ? <Alert kind="error">{error}</Alert> : null}
      <TextField label={t("f.nameEs")} name="name_es" required error={fields["translations.es.name"]} />
      <TextField label={t("f.shortEs")} name="short_es" required />
      <TextAreaField label={t("f.descEs")} name="desc_es" required />
      <TextField label={t("f.nameEn")} name="name_en" optionalLabel="opt." />
      <TextField label={t("f.shortEn")} name="short_en" />
      <TextAreaField label={t("f.descEn")} name="desc_en" />
      <SelectField label={t("f.category")} name="category_id" required error={fields.category_id}>
        {(categories.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
      </SelectField>
      <SelectField label={t("f.venue")} name="venue_id" required error={fields.venue_id}>
        {(venues.data ?? []).map((v) => <option key={v.id} value={v.id}>{v.name} — {v.address}</option>)}
      </SelectField>
      <div className="grid gap-4 sm:grid-cols-2">
        <TextField label={t("f.start")} name="starts_at" type="datetime-local" required />
        <TextField label={t("f.end")} name="ends_at" type="datetime-local" required />
        <TextField label={t("f.capacity")} name="capacity" type="number" min={1} max={500} required error={fields.capacity} />
        <TextField label={t("f.price")} name="price" type="number" min={0} step={1} required error={fields.price_minor} />
      </div>
      <CheckboxField label={t("f.approval")} name="requires_approval" defaultChecked />
      <CheckboxField label={t("f.recorded")} name="is_recorded" />
      <div className="flex gap-3">
        <Button type="submit" busy={busy}>{t("newCourse")}</Button>
        <Link href="/admin/courses" className="inline-flex min-h-11 items-center px-4 font-semibold underline">←</Link>
      </div>
    </form>
  );
}
