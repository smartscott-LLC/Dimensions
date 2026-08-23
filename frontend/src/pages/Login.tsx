import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Hexagon, Loader2, LogIn } from "lucide-react";
import { Toaster } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";

export default function Login() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signIn(email.trim(), password);
      navigate("/", { replace: true });
    } catch (err) {
      const detail =
        err instanceof ApiError && err.body && typeof err.body === "object"
          ? String((err.body as { detail?: string }).detail ?? "sign in failed")
          : "sign in failed";
      setError(detail);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#030712] px-5">
      <Toaster position="bottom-right" richColors />
      <div className="w-full max-w-md">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex size-11 items-center justify-center border border-[#D4AF37]/50 bg-[#002147]">
            <Hexagon className="size-5 text-[#D4AF37]" />
          </div>
          <div>
            <h1 className="font-heading text-lg tracking-wide text-[#F8FAFC]">
              POLYTOPE CONTAINMENT CONSOLE
            </h1>
            <p className="font-mono text-[10px] text-[#64748B]">
              P = {"{"}x ∈ R¹⁴ : Ax ≤ b{"}"} · operator sign-in required
            </p>
          </div>
        </div>

        <form
          onSubmit={submit}
          className="space-y-3 border border-[#1E293B] bg-[#090F1E] p-5"
          data-testid="login-form"
        >
          <div>
            <Label className="label-mono text-[#64748B]">email</Label>
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="username"
              required
              className="mt-1 font-mono text-xs"
              data-testid="login-email-input"
            />
          </div>
          <div>
            <Label className="label-mono text-[#64748B]">password</Label>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
              className="mt-1 font-mono text-xs"
              data-testid="login-password-input"
            />
          </div>

          {error && (
            <p
              className="border border-[#EF4444]/40 bg-[#EF4444]/10 p-2 font-mono text-[11px] text-[#EF4444]"
              data-testid="login-error"
            >
              {error}
            </p>
          )}

          <Button
            type="submit"
            disabled={busy}
            className="h-9 w-full bg-[#D4AF37] font-mono text-xs text-[#002147] transition-colors duration-200 hover:bg-[#e0be4d]"
            data-testid="login-submit-button"
          >
            {busy ? <Loader2 className="size-4 animate-spin" /> : <LogIn className="size-4" />}
            Sign in
          </Button>
          <p className="font-mono text-[10px] leading-relaxed text-[#475569]">
            Accounts are issued by an admin from the Access tab. The engine API
            (/contain, /gate, /chat) keeps using X-API-Key and is unaffected by console
            sign-in.
          </p>
        </form>
      </div>
    </div>
  );
}
