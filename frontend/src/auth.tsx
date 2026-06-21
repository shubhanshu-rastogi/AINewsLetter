import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { Auth, clearToken, getToken, setToken } from "./api";

interface AuthState {
  ready: boolean; // finished initial check
  authRequired: boolean; // backend requires a token
  authenticated: boolean; // we have a valid token (or auth not required)
  login: (token: string) => Promise<void>;
  logout: () => void;
}

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [authRequired, setAuthRequired] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const cfg = await Auth.config();
        setAuthRequired(cfg.auth_required);
        if (!cfg.auth_required) {
          setAuthenticated(true);
        } else if (getToken()) {
          try {
            await Auth.verify();
            setAuthenticated(true);
          } catch {
            clearToken();
            setAuthenticated(false);
          }
        }
      } catch {
        // Backend unreachable — allow the app to render an error-friendly state.
        setAuthenticated(true);
      } finally {
        setReady(true);
      }
    })();

    const onUnauth = () => setAuthenticated(false);
    window.addEventListener("ainl:unauthorized", onUnauth);
    return () => window.removeEventListener("ainl:unauthorized", onUnauth);
  }, []);

  const login = async (token: string) => {
    await Auth.login(token);
    setToken(token);
    setAuthenticated(true);
  };

  const logout = () => {
    clearToken();
    setAuthenticated(false);
  };

  return (
    <Ctx.Provider value={{ ready, authRequired, authenticated, login, logout }}>{children}</Ctx.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
