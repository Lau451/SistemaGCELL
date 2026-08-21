import type { NextConfig } from "next";
import withSerwistInit from "@serwist/next";
import { buildProductPhotoPattern } from "./src/lib/supabase/image-pattern";
import { getCatalogSupabaseEnv } from "./src/lib/supabase/env";

const { url: supabaseUrl } = getCatalogSupabaseEnv();

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [buildProductPhotoPattern(supabaseUrl)],
    // Local Supabase storage serves from a private IP (127.0.0.1); only
    // relevant outside production, where the real Supabase host is public.
    dangerouslyAllowLocalIP: process.env.NODE_ENV !== "production",
  },
};

const withSerwist = withSerwistInit({
  swSrc: "src/app/sw.ts",
  swDest: "public/sw.js",
});

export default withSerwist(nextConfig);
