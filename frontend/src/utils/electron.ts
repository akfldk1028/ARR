// Electron environment detection and safe API wrappers

/**
 * Check if running in Electron environment
 */
export const isElectron = (): boolean => {
  return typeof window !== 'undefined' && window.electronAPI !== undefined;
};

/**
 * Safe wrapper for Electron API calls
 * Returns null if not in Electron environment
 */
export const safeElectronAPI = <T = any>(
  fn: (api: typeof window.electronAPI) => T,
  fallback: T | null = null
): T | null => {
  if (isElectron() && window.electronAPI) {
    try {
      return fn(window.electronAPI);
    } catch (error) {
      console.warn('Electron API call failed:', error);
      return fallback;
    }
  }
  return fallback;
};

/**
 * Get platform (electron or web)
 */
export const getPlatform = (): string => {
  return safeElectronAPI(
    (api) => api.getPlatform(),
    'web'
  ) as string;
};

/**
 * Mock Electron API for web environment
 * Provides no-op implementations for common APIs
 */
export const getMockElectronAPI = () => ({
  getPlatform: () => 'web',
  openExternal: (url: string) => window.open(url, '_blank'),
  // Add more mock methods as needed
});

/**
 * Get Electron API (real or mock)
 */
export const getElectronAPI = () => {
  return isElectron() ? window.electronAPI : getMockElectronAPI();
};
