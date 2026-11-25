import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

import { loginRequest } from '../api/auth';

export const TOKEN_STORAGE_KEY = 'recepie-book.token';
export const EMAIL_STORAGE_KEY = 'recepie-book.email';

interface AuthContextValue {
  token: string | null;
  email: string | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function readStorage(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    // Private mode or a blocked storage: the app still works, it just forgets the login.
    return null;
  }
}

function writeStorage(key: string, value: string | null): void {
  try {
    if (value === null) {
      window.localStorage.removeItem(key);
    } else {
      window.localStorage.setItem(key, value);
    }
  } catch {
    // The in-memory state remains correct for the current page.
  }
}

/**
 * Login state of the whole application.
 *
 * The token is kept in `localStorage` so a reload does not log the user out; the e-mail
 * is stored only to greet the user in the header.  The API never trusts these values:
 * the server verifies the signature and expiration of the JWT on every request.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => readStorage(TOKEN_STORAGE_KEY));
  const [email, setEmail] = useState<string | null>(() => readStorage(EMAIL_STORAGE_KEY));

  const login = useCallback(async (nextEmail: string, password: string) => {
    const response = await loginRequest(nextEmail, password);
    writeStorage(TOKEN_STORAGE_KEY, response.token);
    writeStorage(EMAIL_STORAGE_KEY, nextEmail);
    setToken(response.token);
    setEmail(nextEmail);
  }, []);

  const logout = useCallback(() => {
    writeStorage(TOKEN_STORAGE_KEY, null);
    writeStorage(EMAIL_STORAGE_KEY, null);
    setToken(null);
    setEmail(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      token,
      email,
      isAuthenticated: token !== null,
      login,
      logout,
    }),
    [token, email, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/** Access the login state; fails loudly outside `AuthProvider` instead of returning null. */
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error('useAuth must be used inside AuthProvider');
  }
  return context;
}
