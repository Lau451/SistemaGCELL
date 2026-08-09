/// <reference lib="webworker" />

import { defaultCache } from "@serwist/next/worker";
import type { PrecacheEntry, SerwistGlobalConfig } from "serwist";
import { Serwist } from "serwist";

import { catalogRuntimeCaching } from "@/lib/pwa/runtime-caching";

// See https://serwist.pages.dev/docs/next/getting-started for this
// declaration; `@serwist/next` injects the precache manifest into
// `self.__SW_MANIFEST` at build time via `swSrc`/`swDest`.
declare global {
  interface WorkerGlobalScope extends SerwistGlobalConfig {
    __SW_MANIFEST: (PrecacheEntry | string)[] | undefined;
  }
}

declare const self: ServiceWorkerGlobalScope;

const serwist = new Serwist({
  precacheEntries: self.__SW_MANIFEST,
  skipWaiting: true,
  clientsClaim: true,
  navigationPreload: true,
  // Order-sensitive: catalog matchers (including the NetworkOnly /admin
  // guard) MUST run before Serwist's defaultCache fallthrough.
  runtimeCaching: [...catalogRuntimeCaching, ...defaultCache],
});

serwist.addEventListeners();
