import { useEffect, useRef, useState } from 'react';
import { publicAuthError } from './identity';
import { supabase } from './supabase';

/** Shared TOTP enrollment/verification. It never performs a broker action. */
export function useAuthenticator() {
  const [factor, setFactor] = useState<{ id: string; secret?: string; uri?: string } | null>(null);
  const pendingEnrollment = useRef<string | null>(null);
  const mounted = useRef(true);

  function discardIncompleteEnrollment() {
    const id = pendingEnrollment.current;
    pendingEnrollment.current = null;
    if (id) void supabase.auth.mfa.unenroll({ factorId: id }).catch(() => undefined);
  }

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      discardIncompleteEnrollment();
    };
  }, []);

  async function start() {
    const { data, error } = await supabase.auth.mfa.listFactors();
    if (error) throw new Error(publicAuthError(error));
    if (!mounted.current) return;
    const verified = data.totp.find((item) => item.status === 'verified');
    if (verified) {
      setFactor({ id: verified.id });
    } else if (!factor) {
      const enrolled = await supabase.auth.mfa.enroll({ factorType: 'totp', issuer: 'SignalOS' });
      if (enrolled.error) throw new Error(publicAuthError(enrolled.error));
      pendingEnrollment.current = enrolled.data.id;
      if (!mounted.current) {
        discardIncompleteEnrollment();
        return;
      }
      setFactor({
        id: enrolled.data.id,
        secret: enrolled.data.totp.secret,
        uri: enrolled.data.totp.uri,
      });
    }
  }

  async function verify(code: string) {
    if (!factor || !/^\d{6}$/.test(code))
      throw new Error('Enter your six-digit authenticator code.');
    // An ambiguous response may have activated the factor. Never remove it automatically.
    pendingEnrollment.current = null;
    const { error } = await supabase.auth.mfa.challengeAndVerify({ factorId: factor.id, code });
    if (error) throw new Error(publicAuthError(error));
    if (mounted.current) setFactor(null);
    return mounted.current;
  }

  return { factor, start, verify };
}
