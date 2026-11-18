import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { api, clearToken, getToken, setToken } from "./api";

export type Role = "owner" | "manager" | "staff";
export type User = { username: string; role: Role; full_name: string };
type Ctx = { user: User | null; loading: boolean; login: (u: string, p: string) => Promise<void>; logout: () => void };
const AuthCtx = createContext<Ctx>(null as unknown as Ctx);
export const useAuth = () => useContext(AuthCtx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    if (!getToken()) return setLoading(false);
    api<User>("/me").then(setUser).catch(() => clearToken()).finally(() => setLoading(false));
  }, []);
  const login = async (username: string, password: string) => {
    const r = await api<{ token: string; user: User }>("/auth/login", { body: { username, password } });
    setToken(r.token);
    setUser(r.user);
  };
  const logout = () => { clearToken(); setUser(null); };
  return <AuthCtx.Provider value={{ user, loading, login, logout }}>{children}</AuthCtx.Provider>;
}
