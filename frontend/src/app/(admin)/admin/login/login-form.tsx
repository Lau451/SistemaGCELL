"use client";

/**
 * Login form — client component wiring `signInAction` through React 19's
 * `useActionState`. Re-renders in place with the returned generic error
 * on failure (never a redirect-with-query-param error page, which would
 * risk the same info-leak the action itself already guards against).
 * `next` is carried as a hidden field so `signInAction` can read it
 * server-side without trusting a client-controlled redirect target any
 * more than `isSafeAdminPath` already allows.
 *
 * @see design.md "Login / logout"
 */
import { useActionState } from "react";
import { Button } from "@/components/ui/button";
import { signInAction, type SignInState } from "./actions";

const INITIAL_STATE: SignInState = { error: null };

export interface LoginFormProps {
  next: string | null;
}

export function LoginForm({ next }: LoginFormProps) {
  const [state, formAction, pending] = useActionState(
    signInAction,
    INITIAL_STATE,
  );

  return (
    <form action={formAction} className="flex flex-col gap-4">
      <input type="hidden" name="next" value={next ?? ""} />

      <div className="flex flex-col gap-1.5">
        <label htmlFor="admin-login-email" className="text-sm font-medium">
          Email
        </label>
        <input
          id="admin-login-email"
          name="email"
          type="email"
          autoComplete="username"
          required
          className="border-border rounded-md border px-3 py-2 text-sm"
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <label htmlFor="admin-login-password" className="text-sm font-medium">
          Password
        </label>
        <input
          id="admin-login-password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          className="border-border rounded-md border px-3 py-2 text-sm"
        />
      </div>

      {state.error && (
        <p role="alert" className="text-destructive text-sm">
          {state.error}
        </p>
      )}

      <Button type="submit" disabled={pending}>
        Sign in
      </Button>
    </form>
  );
}
