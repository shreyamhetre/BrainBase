"use client";

import { useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, ApiError, type User } from "./api";

// The logged-in user, loaded once for every page inside the app shell. Sends the visitor
// to /login when there is no valid session. This is only for the UI: the backend checks
// the login cookie on every request anyway.
type UserState = { user: User | null; setUser: (user: User) => void };

const UserContext = createContext<UserState>({ user: null, setUser: () => {} });

export function UserProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    api.me().then(setUser).catch((error) => {
      if (error instanceof ApiError && error.status === 401) router.replace("/login");
    });
  }, [router]);

  return <UserContext.Provider value={{ user, setUser }}>{children}</UserContext.Provider>;
}

export const useUser = () => useContext(UserContext);
