"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { KeyRound } from "lucide-react";

import { FormField } from "@/components/shared/form-field";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/client";
import { login } from "@/features/auth/api/login";
import {
  validateLoginForm,
  type LoginFormErrors,
  type LoginFormValues,
} from "@/features/auth/schemas/login.schema";

/** Login.dc.html's inputs: taller and darker than the shared field default. */
const FIELD_CLASS =
  "h-12 rounded-lg bg-surface-900 px-3.5 text-[15px] shadow-[inset_0_1px_2px_rgba(2,3,5,0.4)]";

/** The login card: SSO, then email + password. Redirects to /home on success. */
export function LoginForm() {
  const router = useRouter();
  const [values, setValues] = useState<LoginFormValues>({ email: "", password: "" });
  const [errors, setErrors] = useState<LoginFormErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setFormError(null);

    const fieldErrors = validateLoginForm(values);
    setErrors(fieldErrors);
    if (Object.keys(fieldErrors).length > 0) return;

    setIsSubmitting(true);
    try {
      await login(values);
      router.push("/home");
      router.refresh();
    } catch (error) {
      setFormError(
        error instanceof ApiError ? error.message : "Could not sign in. Please try again.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="relative flex w-full max-w-[420px] flex-col gap-[18px] rounded-[20px] border border-border-strong bg-surface-800/78 p-7 shadow-[0_24px_60px_rgba(2,3,5,0.6),inset_0_1px_0_rgba(244,246,249,0.07)] backdrop-blur-[16px]">
      {/* No SSO provider is wired up yet, so this stays disabled. */}
      <Button
        type="button"
        disabled
        className="h-12 gap-2.5 rounded-lg bg-ink-primary text-[15px] font-semibold text-surface-950 hover:bg-ink-primary/90"
      >
        <KeyRound className="size-[18px]" aria-hidden />
        Continue with SSO
      </Button>

      <div className="flex items-center gap-3">
        <span className="h-px grow bg-border-subtle" />
        <span className="text-label-sm text-ink-muted">or with email</span>
        <span className="h-px grow bg-border-subtle" />
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-3.5" noValidate>
        <FormField
          id="email"
          type="email"
          autoComplete="email"
          label="Email"
          placeholder="you@example.com"
          value={values.email}
          onChange={(e) => setValues((v) => ({ ...v, email: e.target.value }))}
          error={errors.email}
          className={FIELD_CLASS}
        />
        <FormField
          id="password"
          type="password"
          autoComplete="current-password"
          label="Password"
          /* Presentational: there is no password-reset flow yet, so this is
             deliberately not styled as a link. */
          labelExtra={<span className="text-body-sm text-ink-muted">Forgot password?</span>}
          placeholder="••••••••"
          value={values.password}
          onChange={(e) => setValues((v) => ({ ...v, password: e.target.value }))}
          error={errors.password}
          className={FIELD_CLASS}
        />

        {formError ? <p className="text-body-sm text-data-negative">{formError}</p> : null}

        <Button
          type="submit"
          disabled={isSubmitting}
          className="mt-1 h-12 rounded-lg bg-brand text-[15px] font-semibold text-on-brand shadow-[0_10px_28px_rgba(126,111,238,0.45),inset_0_1px_0_rgba(255,255,255,0.25)] hover:bg-brand-strong"
        >
          {isSubmitting ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </div>
  );
}
