import { useEffect, useState } from "react";
import { api } from "../api";
import type { Lesson } from "../types";

const FORMATS = [
  { key: "zip", label: "Full bundle (ZIP)", note: "Lesson in Markdown and HTML, references, both QC reports and the source list." },
  { key: "md", label: "Markdown", note: "The lesson with front matter, answer key and references." },
  { key: "html", label: "Web page (HTML)", note: "A standalone page. Open it and print to PDF if you need one." },
  { key: "json", label: "Data (JSON)", note: "The full lesson record, sources and reports." },
] as const;

export default function ExportDialog({ lesson, onClose }: { lesson: Lesson; onClose: () => void }) {
  const [format, setFormat] = useState<(typeof FORMATS)[number]["key"]>("zip");
  const openHigh = [...(lesson.fact_report?.issues ?? []), ...(lesson.instruction_report?.issues ?? [])]
    .filter((i) => i.status === "open" && i.severity === "high").length;
  const stale = (lesson.fact_report && lesson.fact_report.version !== lesson.version) ||
    (lesson.instruction_report && lesson.instruction_report.version !== lesson.version);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="overlay" onClick={onClose}>
      <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="export-title" onClick={(e) => e.stopPropagation()}>
        <h2 id="export-title">Export version {lesson.version}</h2>
        {openHigh > 0 && <p className="alert alert-warn">{openHigh} high-priority finding{openHigh > 1 ? "s are" : " is"} still open. The exported reports list {openHigh > 1 ? "them" : "it"}.</p>}
        {stale && <p className="alert alert-warn">The lesson changed after the last check. Re-check first if the reports should match this version.</p>}
        <div className="opts" role="radiogroup">
          {FORMATS.map((f) => (
            <label key={f.key}>
              <input type="radio" name="format" checked={format === f.key} onChange={() => setFormat(f.key)} />
              <span>{f.label}<small>{f.note}</small></span>
            </label>
          ))}
        </div>
        <div className="dialog-actions">
          <button className="btn" onClick={onClose}>Cancel</button>
          <a className="btn btn-primary" href={api.exportUrl(lesson.id, format)} download onClick={() => setTimeout(onClose, 300)} style={{ textDecoration: "none" }}>
            Download
          </a>
        </div>
      </div>
    </div>
  );
}
