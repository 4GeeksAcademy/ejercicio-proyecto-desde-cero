import { useId } from "react";
import type { InputHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

type Common = { label: string; hint?: string; error?: string; optionalLabel?: string };

const control =
  "mt-1 block w-full min-h-11 rounded-lg border border-line bg-surface-2 px-3 py-2 text-base text-ink placeholder:text-muted aria-[invalid=true]:border-bad";

function Wrapper({ id, label, hint, error, optionalLabel, children }: Common & { id: string; children: React.ReactNode }) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium">
        {label}
        {optionalLabel ? <span className="ml-1 font-normal text-muted">({optionalLabel})</span> : null}
      </label>
      {children}
      {hint ? (
        <p id={`${id}-hint`} className="mt-1 text-sm text-muted">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={`${id}-error`} role="alert" className="mt-1 text-sm font-medium text-bad">
          {error}
        </p>
      ) : null}
    </div>
  );
}

function describedBy(id: string, hint?: string, error?: string) {
  return [hint ? `${id}-hint` : null, error ? `${id}-error` : null].filter(Boolean).join(" ") || undefined;
}

export function TextField({ label, hint, error, optionalLabel, ...rest }: Common & InputHTMLAttributes<HTMLInputElement>) {
  const id = useId();
  return (
    <Wrapper id={id} label={label} hint={hint} error={error} optionalLabel={optionalLabel}>
      <input id={id} {...rest} aria-invalid={error ? true : undefined} aria-describedby={describedBy(id, hint, error)} className={control} />
    </Wrapper>
  );
}

export function SelectField({
  label, hint, error, optionalLabel, children, ...rest
}: Common & SelectHTMLAttributes<HTMLSelectElement>) {
  const id = useId();
  return (
    <Wrapper id={id} label={label} hint={hint} error={error} optionalLabel={optionalLabel}>
      <select id={id} {...rest} aria-invalid={error ? true : undefined} aria-describedby={describedBy(id, hint, error)} className={control}>
        {children}
      </select>
    </Wrapper>
  );
}

export function TextAreaField({ label, hint, error, optionalLabel, ...rest }: Common & TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const id = useId();
  return (
    <Wrapper id={id} label={label} hint={hint} error={error} optionalLabel={optionalLabel}>
      <textarea id={id} rows={4} {...rest} aria-invalid={error ? true : undefined} aria-describedby={describedBy(id, hint, error)} className={control} />
    </Wrapper>
  );
}

export function CheckboxField({
  label, hint, error, ...rest
}: { label: string; hint?: string; error?: string } & Omit<InputHTMLAttributes<HTMLInputElement>, "type">) {
  const id = useId();
  return (
    <div>
      <div className="flex items-start gap-3">
        <input id={id} type="checkbox" {...rest} aria-invalid={error ? true : undefined} aria-describedby={describedBy(id, hint, error)} className="mt-1 size-5 accent-[var(--brand)]" />
        <label htmlFor={id} className="text-sm">
          {label}
        </label>
      </div>
      {hint ? <p id={`${id}-hint`} className="ml-8 mt-1 text-sm text-muted">{hint}</p> : null}
      {error ? <p id={`${id}-error`} role="alert" className="ml-8 mt-1 text-sm font-medium text-bad">{error}</p> : null}
    </div>
  );
}
