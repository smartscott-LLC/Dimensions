import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost, getToken, setToken } from "@/lib/api";
import type { AuthUser, TokenResponse } from "@/lib/types";

interface AuthValue {
  user?: AuthUser;
  loading: boolean;
  isAdmin: boolean;
  signIn: (email: string, password: string) => Promise<AuthUser>;
  signOut: () => void;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const qc = useQueryClient();
  const [token, setTokenState] = useState<string | null>(() => getToken());

  const meQ = useQuery({
    queryKey: ["auth-me", token],
    queryFn: () => apiGet<AuthUser>("/auth/me"),
    enabled: Boolean(token),
    retry: false,
  });

  const signIn = useCallback(
    async (email: string, password: string) => {
      const res = await apiPost<TokenResponse>("/auth/login", { email, password });
      setToken(res.access_token);
      setTokenState(res.access_token);
      await qc.invalidateQueries();
      return res.user;
    },
    [qc],
  );

  const signOut = useCallback(() => {
    setToken(null);
    setTokenState(null);
    qc.clear();
  }, [qc]);

  const user = meQ.isError ? undefined : meQ.data;

  const value = useMemo<AuthValue>(
    () => ({
      user,
      loading: Boolean(token) && meQ.isLoading,
      isAdmin: user?.role === "admin",
      signIn,
      signOut,
    }),
    [user, token, meQ.isLoading, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
