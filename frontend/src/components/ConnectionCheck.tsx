import { useMutation } from "@tanstack/react-query";
import { api, ApiError } from "../api";
import type { Health, PreflightCheck } from "../types";

const ROLE_NOTE: Record<PreflightCheck["role"], string> = {
  required: "needed",
  recommended: "recommended",
  keyless: "no key needed",
};

/**
 * Shows what Lectern is configured to use and, on request, sends one tiny real
 * request to each service. A wrong key or a retired model shows up here in
 * seconds instead of halfway through a lesson.
 */
export default function ConnectionCheck({ health }: { health: Health }) {
  const check = useMutation({ mutationFn: api.preflight });
  const r = health.research;
  const rows = check.data?.checks;

  return (
    <section className="conn" aria-labelledby="conn-h">
      <div className="conn-head">
        <h2 id="conn-h">Connections</h2>
        <button type="button" className="btn btn-quiet" onClick={() => check.mutate()} disabled={check.isPending}>
          {check.isPending ? "Checking…" : rows ? "Check again" : "Check connections"}
        </button>
      </div>
      {!rows && (
        <p className="providers">
          <Item label="Writer" value={health.writer && `${health.writer.provider} · ${health.writer.model}`} />
          <Item label="Reviewer" value={health.reviewer &&
            `${health.reviewer.provider} · ${health.reviewer.model}${health.independent_reviewer ? " (independent)" : " (same model as writer)"}`} />
          <br />
          <Item label="Web search" value={r.web_search && r.web_search[0].toUpperCase() + r.web_search.slice(1)} />
          <Item label="Videos" value={r.youtube && "YouTube"} />
          <span>Books: Google Books, Open Library. Encyclopedia: Wikipedia.</span>
        </p>
      )}
      {check.isError && (
        <p className="alert" role="alert">{check.error instanceof ApiError ? check.error.message : "The check could not run."}</p>
      )}
      {rows && (
        <ul className="conn-list" aria-live="polite">
          {rows.map((row) => (
            <li key={row.name} className={row.ok ? "ok" : row.role === "required" ? "bad" : "warn"}>
              <span className="dot" aria-hidden="true" />
              <span className="n">{row.name}<small>{ROLE_NOTE[row.role]}</small></span>
              <span className="d">{row.ok ? row.detail : row.detail}</span>
              <span className="ms">{row.ms ? `${(row.ms / 1000).toFixed(1)} s` : ""}</span>
            </li>
          ))}
        </ul>
      )}
      {check.data && (
        <p className={check.data.ok ? "conn-verdict ok" : "conn-verdict bad"}>
          {check.data.ok ? "Ready: the models answer and research can run." : "Fix the red rows in .env, restart Lectern, then check again."}
        </p>
      )}
    </section>
  );
}

function Item({ label, value }: { label: string; value: string | null | false }) {
  return value ? <span>{label}: {value}. </span> : <span className="missing">{label}: not set. </span>;
}
