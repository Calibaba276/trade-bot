import { useEffect, useState } from "react";
import type { User } from "@supabase/supabase-js";
import { getSession, onAuthStateChange } from "../lib/supaclient";

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getSession().then(({ data }) => {
      setUser(data.session?.user ?? null);
      setLoading(false);
    });

    const { data: sub } = onAuthStateChange((u) => setUser(u as User | null));
    return () => sub?.subscription?.unsubscribe?.();
  }, []);

  return { user, loading };
}
