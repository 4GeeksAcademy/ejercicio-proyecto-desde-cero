import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "danger" | "ghost";

const styles: Record<Variant, string> = {
  primary: "bg-brand text-brand-ink hover:opacity-90",
  secondary: "border border-line bg-surface-2 text-ink hover:bg-brand-soft",
  danger: "bg-bad text-surface-2 hover:opacity-90",
  ghost: "text-ink hover:bg-brand-soft",
};

type Props = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; busy?: boolean; children: ReactNode };

export function buttonClass(variant: Variant = "primary", extra = ""): string {
  return `inline-flex min-h-11 items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60 ${styles[variant]} ${extra}`;
}

export function Button({ variant = "primary", busy, disabled, className = "", children, ...rest }: Props) {
  return (
    <button
      {...rest}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      className={buttonClass(variant, className)}
    >
      {children}
    </button>
  );
}
