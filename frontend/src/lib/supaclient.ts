import { createClient } from "@supabase/supabase-js";

export const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY
);

export const signIn = (email: string, password: string) =>
  supabase.auth.signInWithPassword({ email, password });

export const signUp = (email: string, password: string) =>
  supabase.auth.signUp({
    email,
    password,
    // After the user clicks the confirmation link in their email, Supabase
    // redirects here with the session tokens in the URL. supabase-js detects
    // them automatically, so the user lands on the dashboard already signed in.
    options: { emailRedirectTo: `${window.location.origin}/dashboard` },
  });

export const resetPassword = (email: string) =>
  supabase.auth.resetPasswordForEmail(email, {
    redirectTo: `${window.location.origin}/sign-in`,
  });

export const signOut = () => supabase.auth.signOut();

export const getSession = () => supabase.auth.getSession();

export const onAuthStateChange = (callback: (user: unknown) => void) =>
  supabase.auth.onAuthStateChange((_, session) => {
    callback(session?.user ?? null);
  });
