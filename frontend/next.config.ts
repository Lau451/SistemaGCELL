import type { NextConfig } from "next";
import withSerwistInit from "@serwist/next";
import { buildProductPhotoPattern } from "./src/lib/supabase/image-pattern";
import { getCatalogSupabaseEnv } from "./src/lib/supabase/env";

const { url: supabaseUrl } = getCatalogSupabaseEnv();

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [buildProductPhotoPattern(supabaseUrl)],
  },
};

const withSerwist = withSerwistInit({
  swSrc: "src/app/sw.ts",
  swDest: "public/sw.js",
});

export default withSerwist(nextConfig);
