"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { errorMessage, fieldErrors } from "@/lib/errors";
import type { User } from "@/lib/types";
import { useAuth } from "@/components/auth/AuthProvider";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { CheckboxField, SelectField, TextField } from "@/components/ui/Field";

export function ProfileForm() {
  const t = useTranslations("account");
  const ta = useTranslations("auth");
  const te = useTranslations("errors");
  const tc = useTranslations("common");
  const router = useRouter();
  const { user, setUser, logout } = useAuth();
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [emailPref, setEmailPref] = useState(true);
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    api<{ email_enabled: boolean }>("/notifications/preferences").then((p) => setEmailPref(p.email_enabled)).catch(() => {});
  }, []);

  if (!user) return null;

  async function save(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setMsg(null);
    setFields({});
    const f = new FormData(e.currentTarget);
    try {
      setUser(await api<User>("/users/me", { method: "PATCH", body: { full_name: f.get("full_name"), phone: f.get("phone"), preferred_locale: f.get("preferred_locale") } }));
      setMsg(t("profileSaved"));
    } catch (err) {
      const fe = fieldErrors(err);
      setFields(fe);
      setError(Object.keys(fe).length ? ta("fixErrors") : errorMessage(err, te));
    } finally {
      setBusy(false);
    }
  }

  async function toggleMarketing(checked: boolean) {
    try {
      setUser(await api<User>("/users/me/consents", { method: "PUT", body: { marketing: checked } }));
    } catch (err) {
      setError(errorMessage(err, te));
    }
  }

  async function toggleEmail(checked: boolean) {
    setEmailPref(checked);
    try {
      await api("/notifications/preferences", { method: "PUT", body: { email_enabled: checked } });
    } catch (err) {
      setEmailPref(!checked);
      setError(errorMessage(err, te));
    }
  }

  async function remove() {
    try {
      await api("/users/me", { method: "DELETE" });
      await logout();
      router.push("/");
    } catch (err) {
      setError(errorMessage(err, te));
      setConfirmDelete(false);
    }
  }

  return (
    <div className="space-y-10">
      {error ? <Alert kind="error">{error}</Alert> : null}
      {msg ? <Alert kind="success">{msg}</Alert> : null}
      <form onSubmit={save} className="space-y-4" noValidate>
        <TextField label={ta("fullName")} name="full_name" defaultValue={user.full_name} required error={fields.full_name} />
        <TextField label={ta("email")} value={user.email} readOnly disabled />
        <TextField label={ta("phone")} name="phone" type="tel" defaultValue={user.phone ?? ""} hint={ta("phoneHint")} error={fields.phone} />
        <SelectField label={ta("language")} name="preferred_locale" defaultValue={user.preferred_locale}>
          <option value="es">{ta("es")}</option>
          <option value="en">{ta("en")}</option>
        </SelectField>
        <Button type="submit" busy={busy}>{tc("save")}</Button>
      </form>

      <section aria-labelledby="prefs" className="space-y-4">
        <h2 id="prefs" className="text-xl font-bold">{t("preferences")}</h2>
        <CheckboxField label={t("emailNotif")} checked={emailPref} onChange={(e) => void toggleEmail(e.target.checked)} />
        <CheckboxField label={ta("marketing")} hint={ta("marketingHint")} checked={user.marketing_consent} onChange={(e) => void toggleMarketing(e.target.checked)} />
      </section>

      <section aria-labelledby="danger" className="space-y-3 rounded-xl border border-bad p-4">
        <h2 id="danger" className="text-xl font-bold text-bad">{t("danger")}</h2>
        <p className="text-sm">{t("dangerHelp")}</p>
        {confirmDelete ? (
          <Button variant="danger" onClick={remove}>{t("deleteConfirm")}</Button>
        ) : (
          <Button variant="secondary" onClick={() => setConfirmDelete(true)}>{t("danger")}</Button>
        )}
      </section>
    </div>
  );
}

