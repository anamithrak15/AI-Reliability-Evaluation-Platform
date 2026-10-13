import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { fetchMe, registerAccount, signIn, signOut, type User } from "../api/auth";
import { ApiError, describeError, UNAUTHORIZED_EVENT } from "../api/client";

type AuthState =
  | { status: "loading" }
  | { status: "anonymous"; notice: string | null }
  | { status: "authenticated"; user: User };

interface AuthApi {
  state: AuthState;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  // Replace the signed-in user's details (e.g. after verifying the email); ignored for other accounts.
  updateUser: (user: User) => void;
}

const AuthContext = createContext<AuthApi | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading" });

  useEffect(() => {
    let current = true;
    fetchMe()
      .then((user) => {
        if (current) setState({ status: "authenticated", user });
      })
      .catch((e: unknown) => {
        // A 401 just means nobody is signed in; any other failure is worth telling the user about.
        if (current) {
          setState({ status: "anonymous", notice: e instanceof ApiError && e.status === 401 ? null : describeError(e) });
        }
      });
    return () => {
      current = false;
    };
  }, []);

  useEffect(() => {
    const expired = () => setState({ status: "anonymous", notice: "Your session has ended. Please sign in again." });
    window.addEventListener(UNAUTHORIZED_EVENT, expired);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, expired);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    setState({ status: "authenticated", user: await signIn(email, password) });
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    setState({ status: "authenticated", user: await registerAccount(email, password) });
  }, []);

  const logout = useCallback(async () => {
    try {
      await signOut();
    } catch {
      // The cookie expires on its own; the user asked to leave, so leave locally regardless.
    }
    setState({ status: "anonymous", notice: null });
  }, []);

  const updateUser = useCallback((user: User) => {
    setState((s) => (s.status === "authenticated" && s.user.id === user.id ? { status: "authenticated", user } : s));
  }, []);

  const value = useMemo(() => ({ state, login, register, logout, updateUser }), [state, login, register, logout, updateUser]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthApi {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
