"use client";

import { useEffect } from "react";

/** Remove stale PWA service workers that break fetch() to /api/* */
export function UnregisterServiceWorker() {
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    navigator.serviceWorker.getRegistrations().then((regs) => {
      regs.forEach((r) => r.unregister());
    });
    if ("caches" in window) {
      caches.keys().then((keys) => Promise.all(keys.map((k) => caches.delete(k))));
    }
  }, []);
  return null;
}
