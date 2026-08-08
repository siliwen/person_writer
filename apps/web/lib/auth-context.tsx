"use client";

import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import type { AuthMode, CurrentUser } from "./types";
import { apiBase, parseJson } from "./api";
import { AuthModal } from "@/components/AuthModal";

type AuthContextValue = {
  /** Current logged-in user, or null if not logged in */
  currentUser: CurrentUser | null;
  /** Whether the auth modal is currently open */
  authDialogOpen: boolean;
  /** Current auth modal mode ("login" | "register") */
  authMode: AuthMode;
  /** Returns true if logged in; if not, opens the auth modal and returns false */
  requireAuth: () => boolean;
  /** Open the auth modal with an optional mode (defaults to "login") */
  openAuth: (mode?: AuthMode) => void;
  /** Close the auth modal */
  closeAuth: () => void;
  /** Programmatically set the current user (e.g. after phone binding) */
  setCurrentUser: (user: CurrentUser | null) => void;
  /** Log in: set user and close modal. Calls onLogin callback if provided. */
  login: (user: CurrentUser) => void;
  /** Log out: call API, clear user. Calls onLogout callback if provided. */
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

type AuthProviderProps = {
  children: ReactNode;
  /** Called after successful login/register, before modal closes. Useful for loading user data. */
  onLogin?: (user: CurrentUser) => void | Promise<void>;
  /** Called after logout API succeeds, before user state is cleared. Useful for clearing user data. */
  onLogout?: () => void | Promise<void>;
};

export function AuthProvider({ children, onLogin, onLogout }: AuthProviderProps) {
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [authDialogOpen, setAuthDialogOpen] = useState(false);
  const [authMode, setAuthMode] = useState<AuthMode>("login");

  const requireAuth = useCallback((): boolean => {
    if (currentUser) return true;
    if (!authDialogOpen) {
      setAuthMode("login");
      setAuthDialogOpen(true);
    }
    return false;
  }, [currentUser, authDialogOpen]);

  const openAuth = useCallback((mode: AuthMode = "login") => {
    setAuthMode(mode);
    setAuthDialogOpen(true);
  }, []);

  const closeAuth = useCallback(() => {
    setAuthDialogOpen(false);
  }, []);

  const login = useCallback(
    (user: CurrentUser) => {
      setCurrentUser(user);
      setAuthDialogOpen(false);
    },
    []
  );

  const logout = useCallback(async () => {
    try {
      await fetch(`${apiBase()}/v1/auth/logout`, {
        method: "POST",
        credentials: "include",
      });
    } catch {
      // Even if the API call fails, clear local state
    }
    if (onLogout) {
      await onLogout();
    }
    setCurrentUser(null);
  }, [onLogout]);

  // Internal handler for AuthModal success — calls onLogin callback then updates state
  const handleAuthSuccess = useCallback(
    async (user: CurrentUser) => {
      if (onLogin) {
        await onLogin(user);
      }
      setCurrentUser(user);
      setAuthDialogOpen(false);
    },
    [onLogin]
  );

  return (
    <AuthContext.Provider
      value={{
        currentUser,
        authDialogOpen,
        authMode,
        requireAuth,
        openAuth,
        closeAuth,
        setCurrentUser,
        login,
        logout,
      }}
    >
      {children}
      {authDialogOpen ? (
        <AuthModal
          mode={authMode}
          onClose={closeAuth}
          onSuccess={handleAuthSuccess}
          onModeChange={setAuthMode}
        />
      ) : null}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
