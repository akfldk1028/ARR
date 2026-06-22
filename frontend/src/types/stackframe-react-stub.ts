// Stub for @stackframe/react — dist is missing from the published package.
// Provides no-op exports so the app can boot without Stack Auth.

import React from 'react';

export const StackProvider = ({ children }: { children: React.ReactNode }) => children;
export const StackTheme = ({ children }: { children: React.ReactNode }) => children;
export class StackClientApp {
  constructor(_opts: any) {}
}
export function useStackApp() {
  return {
    signInWithOAuth: () => {},
    signInWithCredential: () => {},
    signUpWithCredential: () => {},
    useUser: () => null,
  };
}
