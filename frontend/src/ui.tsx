import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import type { Severity, Verdict } from "./types";

// ---------- Toasts ----------

type ToastState = { message: string; error?: boolean } | null;
const ToastContext = createContext<(message: string, error?: boolean) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<ToastState>(null);
  const show = useCallback((message: string, error = false) => setToast({ message, error }), []);
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), toast.error ? 7000 : 3500);
    return () => clearTimeout(t);
  }, [toast]);
  return (
    <ToastContext.Provider value={show}>
      {children}
      {toast && (
        <div className={`toast${toast.error ? " error" : ""}`} role="status" aria-live="polite">
          {toast.message}
        </div>
      )}
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);

// ---------- Small pieces ----------

export function BrandMark() {
  return (
    <svg className="brand-mark" viewBox="0 0 18 22" aria-hidden="true">
      <rect x="1" y="1" width="16" height="3.5" rx="1" fill="#1C2533" />
      <path d="M7 4.5h4l1.6 14.5H5.4z" fill="#1C2533" />
      <rect x="3" y="19" width="12" height="2" fill="#F2D24B" />
    </svg>
  );
}

const VERDICT_LABEL: Record<Verdict, string> = {
  supported: "Supported",
  partially_supported: "Partly supported",
  unsupported: "Not supported",
  contradicted: "Contradicted",
};

export function VerdictTag({ verdict }: { verdict: Verdict }) {
  return (
    <span className={`verdict v-${verdict}`}>
      <span className="dot" aria-hidden="true" />
      {VERDICT_LABEL[verdict]}
    </span>
  );
}

export function SeverityTag({ severity }: { severity: Severity }) {
  const label = { high: "High", medium: "Medium", low: "Low" }[severity];
  return <span className={`sev ${severity}`}>{label}</span>;
}

export function mmss(seconds: number | null | undefined): string {
  if (seconds == null) return "";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  return h ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}` : `${m}:${String(s).padStart(2, "0")}`;
}

export function timeAgo(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} h ago`;
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

export const TIER_LABEL: Record<string, string> = {
  primary: "Standard",
  official_docs: "Official docs",
  academic: "Academic",
  reference: "Encyclopedia",
  publisher: "Publisher",
  community: "Community",
  unknown: "Unrated",
};

export const KIND_LABEL: Record<string, string> = {
  hook: "Hook",
  concept: "Concept",
  example: "Worked example",
  activity: "Activity",
  check: "Knowledge check",
  recap: "Recap",
};
