import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { api, ApiError } from "../api";
import { BrandMark } from "../ui";

/**
 * When Lectern is hosted with ACCESS_TOKEN set, any 401 from the API raises a
 * "lectern:locked" event and this screen asks for the passphrase once. The
 * server answers with an HttpOnly cookie, so the passphrase never sits in
 * page storage.
 */
export default function AccessGate({ children }: { children: ReactNode }) {
  const [locked, setLocked] = useState(false);
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const client = useQueryClient();

  useEffect(() => {
    const lock = () => setLocked(true);
    window.addEventListener("lectern:locked", lock);
    return () => window.removeEventListener("lectern:locked", lock);
  }, []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.unlock(token);
      setLocked(false);
      setToken("");
      await client.invalidateQueries();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not check the passphrase.");
    } finally {
      setBusy(false);
    }
  }

  if (!locked) return <>{children}</>;
  return (
    <main className="gate">
      <form className="gate-card" onSubmit={submit}>
        <div className="brand"><BrandMark />Lectern</div>
        <h1>This Lectern is private</h1>
        <p>Enter the access passphrase you were given. It is checked on the server and kept in a secure cookie.</p>
        <label htmlFor="gate-token" className="sr-only">Passphrase</label>
        <input id="gate-token" className="input" type="password" autoComplete="current-password" autoFocus
          value={token} onChange={(e) => setToken(e.target.value)} placeholder="Passphrase" aria-invalid={!!error} />
        {error && <span className="field-error" role="alert">{error}</span>}
        <button className="btn btn-primary" type="submit" disabled={busy || !token.trim()}>{busy ? "Checking…" : "Open Lectern"}</button>
      </form>
    </main>
  );
}
