import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, PanelRight, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import ExportDialog from "../components/ExportDialog";
import LessonClock from "../components/LessonClock";
import Manuscript from "../components/Manuscript";
import Outline from "../components/Outline";
import PipelineView from "../components/PipelineView";
import ReviewRail, { type RailTab } from "../components/ReviewRail";
import type { Issue, Lesson } from "../types";
import { BrandMark, useToast } from "../ui";

export default function LessonPage() {
  const { id = "" } = useParams();
  const queryClient = useQueryClient();
  const toast = useToast();
  const lessonQuery = useQuery({
    queryKey: ["lesson", id],
    queryFn: () => api.lesson(id),
    refetchInterval: (q) => (q.state.data?.running ? 4000 : false),
  });
  const lesson = lessonQuery.data;

  useLessonEvents(id);

  const [activeSection, setActiveSection] = useState<string | null>(null);
  const [selectedIssue, setSelectedIssue] = useState<string | null>(null);
  const [tab, setTab] = useState<RailTab>("facts");
  const [highlightSource, setHighlightSource] = useState<string | null>(null);
  const [showExport, setShowExport] = useState(false);
  const [railOpen, setRailOpen] = useState(false);

  const setLesson = useCallback((next: Lesson) => queryClient.setQueryData(["lesson", id], next), [queryClient, id]);

  const openIssues = useMemo(() => {
    const issues: Issue[] = [...(lesson?.fact_report?.issues ?? []), ...(lesson?.instruction_report?.issues ?? [])];
    return issues.filter((i) => i.status === "open");
  }, [lesson]);

  const selectIssue = useCallback((issue: Issue) => {
    setSelectedIssue(issue.id);
    setTab(issue.layer === "facts" ? "facts" : "teaching");
    setRailOpen(true);
    if (issue.section_id) scrollToSection(issue.section_id);
  }, []);

  const showSource = useCallback((sourceId: string) => {
    setHighlightSource(sourceId);
    setTab("sources");
    setRailOpen(true);
  }, []);

  // Keyboard: [ and ] move between open findings.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement;
      if (target.closest("input, textarea, .cm-editor") || !openIssues.length) return;
      if (e.key !== "[" && e.key !== "]") return;
      const index = openIssues.findIndex((i) => i.id === selectedIssue);
      const next = e.key === "]" ? (index + 1) % openIssues.length : (index - 1 + openIssues.length) % openIssues.length;
      selectIssue(openIssues[next]);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [openIssues, selectedIssue, selectIssue]);

  if (lessonQuery.isError) {
    return (
      <Shell title="">
        <div className="pipeline"><p className="alert">{(lessonQuery.error as Error).message}</p><Link to="/">Back to your lessons</Link></div>
      </Shell>
    );
  }
  if (!lesson) return <Shell title=""><div className="pipeline"><p>Loading lesson…</p></div></Shell>;

  if (!lesson.content) {
    return <Shell title={lesson.request.title}><PipelineView lesson={lesson} onChange={setLesson} /></Shell>;
  }

  async function recheck() {
    try {
      setLesson(await api.recheck(lesson!.id, "both"));
      toast("Re-checking facts and teaching quality.");
    } catch (e) {
      toast((e as Error).message, true);
    }
  }

  return (
    <Shell
      title={lesson.request.title}
      actions={
        <>
          <span className="version-pill">Version {lesson.version}</span>
          <button className="btn btn-small" onClick={recheck} disabled={lesson.running} title="Run both quality checks on the current version">
            <RefreshCw /> Re-check
          </button>
          <button className="btn btn-small btn-primary" onClick={() => setShowExport(true)}><Download /> Export</button>
          <button className="btn btn-small rail-toggle" onClick={() => setRailOpen((o) => !o)} aria-expanded={railOpen}>
            <PanelRight /> Review
          </button>
        </>
      }
    >
      <LessonClock lesson={lesson} active={activeSection} onSelect={scrollToSection} />
      <div className="workspace">
        <Outline lesson={lesson} active={activeSection} onSelect={scrollToSection} issues={openIssues} />
        <Manuscript
          lesson={lesson}
          onChange={setLesson}
          onActiveSection={setActiveSection}
          focusedSection={openIssues.find((i) => i.id === selectedIssue)?.section_id ?? null}
          issues={openIssues}
          selectedIssue={selectedIssue}
          onSelectIssue={selectIssue}
          onShowSource={showSource}
        />
        <ReviewRail
          lesson={lesson}
          tab={tab}
          onTab={setTab}
          open={railOpen}
          selectedIssue={selectedIssue}
          onSelectIssue={selectIssue}
          highlightSource={highlightSource}
          onChange={setLesson}
        />
      </div>
      {showExport && <ExportDialog lesson={lesson} onClose={() => setShowExport(false)} />}
    </Shell>
  );
}

function Shell({ title, actions, children }: { title: string; actions?: React.ReactNode; children: React.ReactNode }) {
  return (
    <>
      <header className="topbar">
        <Link to="/" className="brand"><BrandMark />Lectern</Link>
        <span className="topbar-title">{title && <strong>{title}</strong>}</span>
        <div className="topbar-actions">{actions}</div>
      </header>
      {children}
    </>
  );
}

export function scrollToSection(sectionId: string) {
  document.getElementById(sectionId)?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
}

/** Subscribe to server-sent events and refresh the lesson when something changes. */
function useLessonEvents(id: string) {
  const queryClient = useQueryClient();
  const timer = useRef<number | null>(null);
  useEffect(() => {
    if (!id) return;
    const source = new EventSource(`/api/lessons/${id}/events`);
    const refresh = () => {
      if (timer.current) return;
      timer.current = window.setTimeout(() => {
        timer.current = null;
        queryClient.invalidateQueries({ queryKey: ["lesson", id] });
      }, 250);
    };
    source.addEventListener("step", refresh);
    source.addEventListener("lesson", refresh);
    source.addEventListener("log", refresh);
    return () => {
      source.close();
      if (timer.current) window.clearTimeout(timer.current);
    };
  }, [id, queryClient]);
}
