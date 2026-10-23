"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError, type User } from "./api";

// Loads the logged-in user; sends the visitor to /login when there is no valid session.
// This is only for the UI: the backend checks the token on every request anyway.
export function useCurrentUser() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    api
      .me()
      .then(setUser)
      .catch((error) => {
        if (error instanceof ApiError && error.status === 401) router.replace("/login");
      });
  }, [router]);

  return user;
}
