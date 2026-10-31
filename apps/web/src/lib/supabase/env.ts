export type SupabaseEnv = { url: string; key: string };

// NEXT_PUBLIC_* variables are inlined at build time only when referenced as
// literal `process.env.NAME` expressions, so do not read them dynamically.

/** Returns the Supabase env, or null when either value is unset or empty. */
export function getSupabaseEnv(): SupabaseEnv | null {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  if (!url || !key) return null;
  return { url, key };
}

/** Returns the Supabase env, or throws a message naming what is missing. */
export function requireSupabaseEnv(): SupabaseEnv {
  const env = getSupabaseEnv();
  if (env) return env;

  const missing = [
    !process.env.NEXT_PUBLIC_SUPABASE_URL && "NEXT_PUBLIC_SUPABASE_URL",
    !process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY &&
      "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY",
  ].filter(Boolean);

  throw new Error(
    `Supabase is not configured: ${missing.join(" and ")} ${
      missing.length > 1 ? "are" : "is"
    } not set. Copy apps/web/.env.example to apps/web/.env.local and fill in the values.`,
  );
}
