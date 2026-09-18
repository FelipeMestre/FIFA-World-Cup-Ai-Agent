"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

import { AssistantMark } from "@/components/shared/assistant-mark";
import { FormField } from "@/components/shared/form-field";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/client";
import { login } from "@/features/auth/api/login";
import {
  validateLoginForm,
  type LoginFormErrors,
  type LoginFormValues,
} from "@/features/auth/schemas/login.schema";

/** The login page's form: email + password, real login flow, redirects to "/" on success. */
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
      router.push("/");
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
    <div className="relative flex w-full max-w-[400px] flex-col gap-6 rounded-lg border border-border-strong bg-surface-800 p-6 shadow-md sm:p-8">
      <div className="flex flex-col items-center gap-3 text-center">
        <AssistantMark size={48} radius="rounded-lg" />
        <div className="flex flex-col gap-1">
          <h1 className="text-heading-lg">Owl Analytics</h1>
          <span className="text-label-sm text-ink-muted">
            FIFA World Cup 2026 · stats assistant
          </span>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
        <FormField
          id="email"
          type="email"
          autoComplete="email"
          label="Email"
          placeholder="you@example.com"
          value={values.email}
          onChange={(e) => setValues((v) => ({ ...v, email: e.target.value }))}
          error={errors.email}
        />
        <FormField
          id="password"
          type="password"
          autoComplete="current-password"
          label="Password"
          labelExtra={<span className="text-body-sm text-ink-muted">Forgot password?</span>}
          placeholder="••••••••"
          value={values.password}
          onChange={(e) => setValues((v) => ({ ...v, password: e.target.value }))}
          error={errors.password}
        />

        {formError ? <p className="text-body-sm text-data-negative">{formError}</p> : null}

        <Button
          type="submit"
          disabled={isSubmitting}
          className="mt-1 h-11 bg-brand text-on-brand hover:bg-brand-strong"
        >
          {isSubmitting ? "Signing in…" : "Sign in"}
        </Button>
      </form>

      <div className="flex items-center gap-3">
        <span className="h-px grow bg-border-subtle" />
        <span className="text-label-sm text-ink-muted">or</span>
        <span className="h-px grow bg-border-subtle" />
      </div>

      <Button
        type="button"
        variant="outline"
        disabled
        className="h-11 border-border-strong bg-transparent text-ink-primary opacity-70"
      >
        Continue with SSO
      </Button>
    </div>
  );
}
