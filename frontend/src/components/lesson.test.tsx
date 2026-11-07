import { render, screen } from "@testing-library/react";
import { prepareMarkdown } from "./Manuscript";
import LessonClock from "./LessonClock";
import type { Lesson } from "../types";

describe("prepareMarkdown", () => {
  it("turns grouped citations into one link per source", () => {
    expect(prepareMarkdown("GET is safe [S1, S3].", [])).toBe("GET is safe [S1](#cite-S1)[S3](#cite-S3).");
  });

  it("marks a flagged claim once and leaves unsafe text alone", () => {
    const out = prepareMarkdown("POST requests are idempotent [S1].", [{ id: "F1", text: "POST requests are idempotent", high: true }]);
    expect(out).toBe("[POST requests are idempotent](#flag-F1-high) [S1](#cite-S1).");
    expect(prepareMarkdown("Use `curl` here.", [{ id: "F2", text: "Use `curl` here", high: false }])).toBe("Use `curl` here.");
  });
});

describe("LessonClock", () => {
  const lesson = {
    content: {
      summary: "",
      knowledge_checks: [],
      videos: [],
      sections: [
        { id: "sec-1", kind: "hook", title: "Hook", minutes: 5, atom_ids: [], body_md: "", instructor_notes: "" },
        { id: "sec-2", kind: "activity", title: "Practice", minutes: 40, atom_ids: [], body_md: "", instructor_notes: "" },
      ],
    },
    instruction_report: null,
  } as unknown as Lesson;

  it("sizes segments by minutes and reports the total", () => {
    render(<LessonClock lesson={lesson} active="sec-2" onSelect={() => {}} />);
    expect(screen.getByText("45 minutes")).toBeTruthy();
    const segments = screen.getAllByRole("listitem");
    expect(segments[0].style.flexGrow).toBe("5");
    expect(segments[1].style.flexGrow).toBe("40");
    expect(segments[1].getAttribute("aria-current")).toBe("true");
  });
});
