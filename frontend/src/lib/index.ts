// Stub exports for missing @/lib module.
// Original lib/ was excluded by .gitignore. These are minimal stubs to boot the app.

export function generateUniqueId(): string {
  return crypto.randomUUID?.() ?? Math.random().toString(36).slice(2);
}

export function hasStackKeys(): boolean {
  return false;
}

export function capitalizeFirstLetter(s: string): string {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : '';
}

export function getProxyBaseURL(): string {
  return import.meta.env.VITE_PROXY_URL || 'http://127.0.0.1:5001';
}

export function uploadLog(..._args: any[]): void {
  // no-op stub
}

export function replayProject(..._args: any[]): void {
  // no-op stub
}

export function replayActiveTask(..._args: any[]): void {
  // no-op stub
}
