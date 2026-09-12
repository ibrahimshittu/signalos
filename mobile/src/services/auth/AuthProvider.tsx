import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { AppState, Linking } from 'react-native';
import type { Session } from '@supabase/supabase-js';
import { useQueryClient } from '@tanstack/react-query';
import { SIGNALOS_AUTH_REDIRECT_URL, SIGNALOS_PASSWORD_RECOVERY_URL } from '@/config';
import { useAppStore } from '@/store/useAppStore';
import { authCallbackFromUrl } from './deepLink';
import { accountFromUser, publicAuthError } from './identity';
import { supabase } from './supabase';
import { disablePush } from '@/services/notifications/push';

interface SignUpInput {
  firstName: string;
  lastName: string;
  email: string;
  password: string;
}

interface AuthContextValue {
  session: Session | null;
  initializing: boolean;
  callbackError: string | null;
  recoveryRequested: boolean;
  clearCallbackError(): void;
  clearRecoveryRequest(): void;
  signUp(input: SignUpInput): Promise<{ verificationRequired: boolean }>;
  signIn(email: string, password: string): Promise<void>;
  verifyEmail(email: string, token: string): Promise<void>;
  resendVerification(email: string): Promise<void>;
  requestPasswordReset(email: string): Promise<void>;
  updatePassword(password: string): Promise<void>;
  signOut(): Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function checked(error: unknown): never {
  throw new Error(publicAuthError(error));
}

export function AuthProvider({ children }: PropsWithChildren) {
  const queryClient = useQueryClient();
  const [session, setSession] = useState<Session | null>(null);
  const [initializing, setInitializing] = useState(true);
  const [callbackError, setCallbackError] = useState<string | null>(null);
  const [recoveryRequested, setRecoveryRequested] = useState(false);

  const acceptSession = useCallback(
    (next: Session | null) => {
      if (useAppStore.getState().ownerUserId !== (next?.user.id ?? null)) {
        queryClient.clear();
      }
      setSession(next);
      if (next?.user) {
        useAppStore.getState().bindAuthenticatedUser(next.user.id, accountFromUser(next.user));
      }
    },
    [queryClient],
  );

  const consumeAuthUrl = useCallback(
    async (url: string | null) => {
      if (!url) return;
      const callback = authCallbackFromUrl(url);
      if (callback.kind === 'none') return;
      if (callback.kind === 'error') {
        setCallbackError(callback.message);
        return;
      }

      const response =
        callback.kind === 'session'
          ? await supabase.auth.setSession({
              access_token: callback.accessToken,
              refresh_token: callback.refreshToken,
            })
          : await supabase.auth.exchangeCodeForSession(callback.code);

      if (response.error) {
        setCallbackError(publicAuthError(response.error));
        return;
      }

      acceptSession(response.data.session);
      if (callback.recovery) setRecoveryRequested(true);
    },
    [acceptSession],
  );

  useEffect(() => {
    let active = true;
    const { data: authListener } = supabase.auth.onAuthStateChange((event, nextSession) => {
      if (!active) return;
      acceptSession(nextSession);
      if (event === 'PASSWORD_RECOVERY') setRecoveryRequested(true);
      if (event === 'SIGNED_OUT') {
        queryClient.clear();
        useAppStore.getState().deleteLocalAccount();
      }
    });
    const linkListener = Linking.addEventListener('url', ({ url }) => {
      void consumeAuthUrl(url).catch((error) => setCallbackError(publicAuthError(error)));
    });
    const appStateListener = AppState.addEventListener('change', (state) => {
      if (state === 'active') supabase.auth.startAutoRefresh();
      else supabase.auth.stopAutoRefresh();
    });

    void (async () => {
      try {
        await consumeAuthUrl(await Linking.getInitialURL());
        const { data, error } = await supabase.auth.getSession();
        if (error) setCallbackError(publicAuthError(error));
        else if (active) acceptSession(data.session);
      } catch (error) {
        if (active) setCallbackError(publicAuthError(error));
      } finally {
        if (active) setInitializing(false);
      }
    })();

    return () => {
      active = false;
      authListener.subscription.unsubscribe();
      linkListener.remove();
      appStateListener.remove();
      supabase.auth.stopAutoRefresh();
    };
  }, [acceptSession, consumeAuthUrl, queryClient]);

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      initializing,
      callbackError,
      recoveryRequested,
      clearCallbackError: () => setCallbackError(null),
      clearRecoveryRequest: () => setRecoveryRequested(false),
      async signUp(input) {
        const email = input.email.trim().toLowerCase();
        const { data, error } = await supabase.auth.signUp({
          email,
          password: input.password,
          options: {
            emailRedirectTo: SIGNALOS_AUTH_REDIRECT_URL,
            data: {
              first_name: input.firstName.trim(),
              last_name: input.lastName.trim(),
            },
          },
        });
        if (error) checked(error);
        useAppStore.getState().setAccount({
          firstName: input.firstName.trim(),
          lastName: input.lastName.trim(),
          email,
        });
        if (data.session) acceptSession(data.session);
        return { verificationRequired: !data.session };
      },
      async signIn(email, password) {
        const { data, error } = await supabase.auth.signInWithPassword({
          email: email.trim().toLowerCase(),
          password,
        });
        if (error) checked(error);
        acceptSession(data.session);
      },
      async verifyEmail(email, token) {
        const { data, error } = await supabase.auth.verifyOtp({
          email: email.trim().toLowerCase(),
          token: token.trim(),
          type: 'signup',
        });
        if (error) checked(error);
        acceptSession(data.session);
      },
      async resendVerification(email) {
        const { error } = await supabase.auth.resend({
          type: 'signup',
          email: email.trim().toLowerCase(),
          options: { emailRedirectTo: SIGNALOS_AUTH_REDIRECT_URL },
        });
        if (error) checked(error);
      },
      async requestPasswordReset(email) {
        const { error } = await supabase.auth.resetPasswordForEmail(email.trim().toLowerCase(), {
          redirectTo: SIGNALOS_PASSWORD_RECOVERY_URL,
        });
        if (error) checked(error);
      },
      async updatePassword(password) {
        const { error } = await supabase.auth.updateUser({ password });
        if (error) checked(error);
      },
      async signOut() {
        if (session?.user.id) await disablePush(session.user.id);
        const { error } = await supabase.auth.signOut({ scope: 'local' });
        if (error) checked(error);
        queryClient.clear();
        useAppStore.getState().deleteLocalAccount();
        acceptSession(null);
      },
    }),
    [acceptSession, callbackError, initializing, queryClient, recoveryRequested, session],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error('useAuth must be used inside AuthProvider.');
  return value;
}
