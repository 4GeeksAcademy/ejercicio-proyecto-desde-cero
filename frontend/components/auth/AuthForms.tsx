"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { Link, useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { errorMessage, fieldErrors } from "@/lib/errors";
import type { User } from "@/lib/types";
import { useAuth } from "./AuthProvider";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { CheckboxField, SelectField, TextField } from "@/components/ui/Field";

function useAfterAuth() {
  const router = useRouter();
  return () => {
    try {
      const raw = sessionStorage.getItem("tallerya:next");
      sessionStorage.removeItem("tallerya:next");
      if (raw) {
        router.replace(JSON.parse(raw));
        return;
      }
    } catch {
      /* sessionStorage no disponible */
    }
    router.replace("/account");
  };
}

function useFormState() {
  const te = useTranslations("errors");
  const t = useTranslations("auth");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const fail = (e: unknown) => {
    const f = fieldErrors(e);
    setFields(f);
    setError(Object.keys(f).length ? t("fixErrors") : errorMessage(e, te));
    setBusy(false);
  };
  return { busy, setBusy, error, setError, fields, setFields, fail };
}

export function LoginForm() {
  const t = useTranslations("auth");
  const { setUser } = useAuth();
  const after = useAfterAuth();
  const s = useFormState();

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    s.setBusy(true);
    s.setError(null);
    const f = new FormData(e.currentTarget);
    try {
      const u = await api<User>("/auth/login", { method: "POST", body: { email: f.get("email"), password: f.get("password") } });
      setUser(u);
      after();
    } catch (err) {
      s.fail(err);
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-4">
      {s.error ? <Alert kind="error">{s.error}</Alert> : null}
      <TextField label={t("email")} name="email" type="email" autoComplete="email" required error={s.fields.email} />
      <TextField label={t("password")} name="password" type="password" autoComplete="current-password" required error={s.fields.password} />
      <Button type="submit" busy={s.busy} className="w-full">{t("loginCta")}</Button>
      <p className="text-sm"><Link href="/forgot-password" className="underline">{t("forgot")}</Link></p>
      <p className="text-sm text-muted">{t("noAccount")} <Link href="/register" className="font-semibold underline">{t("registerCta")}</Link></p>
    </form>
  );
}

export function RegisterForm() {
  const t = useTranslations("auth");
  const locale = useLocale();
  const { setUser } = useAuth();
  const after = useAfterAuth();
  const s = useFormState();

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    s.setBusy(true);
    s.setError(null);
    s.setFields({});
    const f = new FormData(e.currentTarget);
    try {
      const u = await api<User>("/auth/register", {
        method: "POST",
        body: {
          email: f.get("email"),
          password: f.get("password"),
          full_name: f.get("full_name"),
          phone: f.get("phone"),
          preferred_locale: f.get("preferred_locale"),
          accept_terms: f.get("accept_terms") === "on",
          marketing_consent: f.get("marketing_consent") === "on", // NUNCA preseleccionado
        },
      });
      setUser(u);
      after();
    } catch (err) {
      s.fail(err);
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-4">
      {s.error ? <Alert kind="error">{s.error}</Alert> : null}
      <TextField label={t("fullName")} name="full_name" autoComplete="name" required error={s.fields.full_name} />
      <TextField label={t("email")} name="email" type="email" autoComplete="email" required error={s.fields.email} />
      <TextField label={t("phone")} name="phone" type="tel" autoComplete="tel" placeholder="+573001234567" hint={t("phoneHint")} required error={s.fields.phone} />
      <TextField label={t("password")} name="password" type="password" autoComplete="new-password" minLength={10} hint={t("passwordHint")} required error={s.fields.password} />
      <SelectField label={t("language")} name="preferred_locale" defaultValue={locale}>
        <option value="es">{t("es")}</option>
        <option value="en">{t("en")}</option>
      </SelectField>
      <CheckboxField label={t("acceptTerms")} name="accept_terms" required error={s.fields.accept_terms} />
      <CheckboxField label={t("marketing")} hint={t("marketingHint")} name="marketing_consent" defaultChecked={false} />
      <Button type="submit" busy={s.busy} className="w-full">{t("registerCta")}</Button>
      <p className="text-sm text-muted">{t("haveAccount")} <Link href="/login" className="font-semibold underline">{t("loginCta")}</Link></p>
    </form>
  );
}

export function ForgotForm() {
  const t = useTranslations("auth");
  const s = useFormState();
  const [sent, setSent] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    s.setBusy(true);
    s.setError(null);
    try {
      await api("/auth/forgot-password", { method: "POST", body: { email: new FormData(e.currentTarget).get("email") } });
      setSent(true);
    } catch (err) {
      s.fail(err);
    } finally {
      s.setBusy(false);
    }
  }

  if (sent) return <Alert kind="success">{t("forgotSent")}</Alert>;
  return (
    <form onSubmit={onSubmit} noValidate className="space-y-4">
      <p className="text-sm text-muted">{t("forgotHelp")}</p>
      {s.error ? <Alert kind="error">{s.error}</Alert> : null}
      <TextField label={t("email")} name="email" type="email" autoComplete="email" required error={s.fields.email} />
      <Button type="submit" busy={s.busy} className="w-full">{t("forgotCta")}</Button>
    </form>
  );
}

export function ResetForm() {
  const t = useTranslations("auth");
  const token = useSearchParams().get("token");
  const s = useFormState();
  const [done, setDone] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    s.setBusy(true);
    s.setError(null);
    try {
      await api("/auth/reset-password", { method: "POST", body: { token, new_password: new FormData(e.currentTarget).get("new_password") } });
      setDone(true);
    } catch (err) {
      s.fail(err);
    } finally {
      s.setBusy(false);
    }
  }

  if (!token) return <Alert kind="error">{t("resetMissing")}</Alert>;
  if (done) {
    return (
      <div className="space-y-3">
        <Alert kind="success">{t("resetDone")}</Alert>
        <Link href="/login" className="font-semibold underline">{t("loginCta")}</Link>
      </div>
    );
  }
  return (
    <form onSubmit={onSubmit} noValidate className="space-y-4">
      {s.error ? <Alert kind="error">{s.error}</Alert> : null}
      <TextField label={t("newPassword")} name="new_password" type="password" autoComplete="new-password" minLength={10} hint={t("passwordHint")} required error={s.fields.new_password} />
      <Button type="submit" busy={s.busy} className="w-full">{t("resetCta")}</Button>
    </form>
  );
}

