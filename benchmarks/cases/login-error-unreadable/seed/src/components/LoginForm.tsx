"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

// The sign-in error is a hand-rolled paragraph in a hand-picked colour: pale on
// white, carried by colour alone, and pointed at by nothing.
export function LoginForm() {
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    const response = await fetch("/api/session", {
      method: "POST",
      body: new FormData(event.currentTarget),
    });
    setPending(false);
    if (!response.ok) {
      setError("That email and password do not match an account.");
      return;
    }
    window.location.assign("/bookings");
  }

  return (
    <form onSubmit={onSubmit} className="flex w-full max-w-sm flex-col gap-4">
      <div className="flex flex-col gap-2">
        <Label htmlFor="email">Email</Label>
        <Input id="email" name="email" type="email" autoComplete="email" required />
      </div>

      <div className="flex flex-col gap-2">
        <Label htmlFor="password">Password</Label>
        <Input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
        />
        {error ? (
          <p style={{ color: "#ff8a8a", fontSize: "12px" }}>{error}</p>
        ) : null}
      </div>

      <Button type="submit" disabled={pending}>
        Sign in
      </Button>
    </form>
  );
}
