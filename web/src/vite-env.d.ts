/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Backend origin for a split-service deployment (see src/lib/apiClient.ts).
   * Unset locally — the dev proxy in vite.config.ts handles same-origin. */
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
