import { createBrowserClient } from "@supabase/ssr";

import { requireSupabaseEnv } from "./env";

/**
 * Supabase client for Client Components. Created on call, not at import, so a
 * missing env only throws where the client is actually used.
 */
export function createClient() {
  const { url, key } = requireSupabaseEnv();
  return createBrowserClient(url, key);
}
