import { useEffect, useRef, useState } from "react";
import { rest, streamCase } from "./api";
import { navigate } from "./navigation";
import { workspaceApi, type CaseRecord, type CaseReview } from "./workspaceApi";

export function useCaseSession(caseId: string) {
  const [active, setActive] = useState<CaseRecord | null>(null);
  const [title, setTitle] = useState("Untitled case"),
    [prompt, setPrompt] = useState("");
  const [summary, setSummary] = useState(""),
    [reviewed, setReviewed] = useState(false);
  const [confirmed, setConfirmed] = useState(false),
    [useSummary, setUseSummary] = useState(false);
  const [mode, setMode] = useState("organize"),
    [stage, setStage] = useState(0);
  const [reviews, setReviews] = useState<CaseReview[]>([]);
  const [dirty, setDirty] = useState(false),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(false);
  const [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [liveDraft, setLiveDraft] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const executing = useRef(false);
  const activeRef = useRef<CaseRecord | null>(null);
  const archived = active?.status === "archived";
  const messages = active?.details.messages ?? [];
  function assign(row: CaseRecord) {
    activeRef.current = row;
    setActive(row);
  }
  function load(row: CaseRecord) {
    assign(row);
    setTitle(row.title);
    setPrompt(row.details.draft);
    setSummary(row.details.summary);
    setReviewed(row.details.reviewed);
    setReviews(row.reviews ?? []);
    setConfirmed(true);
    setMode(row.details.messages.length ? "chat" : "organize");
    setStage(
      row.details.messages.length
        ? 2
        : row.details.reviewed
          ? 2
          : row.details.summary
            ? 1
            : 0,
    );
    setDirty(false);
    setUseSummary(false);
    setLiveDraft("");
    setError("");
    setNotice("");
  }
  function reset() {
    setLoading(false);
    activeRef.current = null;
    setActive(null);
    setTitle("Untitled case");
    setPrompt("");
    setSummary("");
    setReviewed(false);
    setReviews([]);
    setConfirmed(false);
    setMode("organize");
    setStage(0);
    setDirty(false);
    setUseSummary(false);
    setLiveDraft("");
    setError("");
    setNotice("");
  }
  const previousRoute = useRef(caseId);
  useEffect(() => {
    const changed = previousRoute.current !== caseId;
    previousRoute.current = caseId;
    if (caseId === "new") {
      if (changed) reset();
      return;
    }
    if (activeRef.current?.id === caseId) return;
    reset();
    let disposed = false;
    setLoading(true);
    setError("");
    workspaceApi
      .case(caseId)
      .then((row) => {
        if (!disposed) load(row);
      })
      .catch((e) => {
        if (!disposed) setError(e.message);
      })
      .finally(() => {
        if (!disposed) setLoading(false);
      });
    return () => {
      disposed = true;
    };
  }, [caseId]);
  useEffect(() => {
    if (!busy) return;
    setElapsed(0);
    const timer = window.setInterval(() => setElapsed((n) => n + 1), 1000);
    return () => window.clearInterval(timer);
  }, [busy]);
  useEffect(() => {
    const leave = (e: Event) => {
      if (busy) {
        e.preventDefault();
        setNotice(
          "Please wait for the current request before leaving this case.",
        );
      } else if (
        dirty &&
        !window.confirm("Leave without saving your latest edits?")
      )
        e.preventDefault();
    };
    const unload = (e: BeforeUnloadEvent) => {
      if (dirty || busy) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("medflock-before-navigation", leave);
    window.addEventListener("beforeunload", unload);
    return () => {
      window.removeEventListener("medflock-before-navigation", leave);
      window.removeEventListener("beforeunload", unload);
    };
  }, [dirty, busy]);
  async function perform(action: () => Promise<void>) {
    if (executing.current) return;
    executing.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      executing.current = false;
      setBusy(false);
    }
  }
  async function save(review = reviewed) {
    if (!confirmed)
      throw Error("Confirm this is a synthetic case before saving.");
    const row: CaseRecord =
      activeRef.current ??
      (await rest("/api/cases", "POST", { title, synthetic_only: confirmed }));
    assign(row);
    const result: CaseRecord = await rest(`/api/cases/${row.id}`, "PUT", {
      revision: row.revision,
      title,
      draft: prompt,
      summary,
      reviewed: review,
    });
    assign(result);
    setReviewed(result.details.reviewed);
    setDirty(false);
    const full = await workspaceApi.case(row.id);
    setReviews(full.reviews ?? []);
    navigate(`/cases/${row.id}`, true, false);
    return result;
  }
  const saveDraft = () =>
    perform(async () => {
      await save();
      setNotice("Draft saved. You can reopen it from My cases.");
    });
  const saveReview = () =>
    perform(async () => {
      await save(true);
      setStage(2);
      setMode("chat");
      setNotice(
        "Your reviewed summary is saved. Write your follow-up in your own words.",
      );
    });
  const reload = () => {
    if (
      dirty &&
      !window.confirm(
        "Discard unsaved edits and reload the saved case? Copy any text you need first.",
      )
    )
      return;
    return perform(async () => {
      if (activeRef.current)
        load(await workspaceApi.case(activeRef.current.id));
      else if (caseId !== "new") load(await workspaceApi.case(caseId));
    });
  };
  const changeStatus = () => {
    if (
      !active ||
      !window.confirm(
        `${archived ? "Restore" : "Archive"} this case?${dirty ? " Unsaved edits will be discarded." : ""}`,
      )
    )
      return;
    return perform(async () => {
      await rest(`/api/cases/${active.id}/status`, "PATCH", {
        revision: active.revision,
        status: archived ? "active" : "archived",
      });
      load(await workspaceApi.case(active.id));
    });
  };
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    return perform(async () => {
      const submittedPrompt = prompt;
      const submittedMode = stage === 0 ? mode : "chat";
      setLiveDraft("");
      const row = await save();
      const result = await streamCase(
        {
          prompt: submittedPrompt,
          case_id: row.id,
          case_revision: row.revision,
          mode: submittedMode,
          synthetic_only: confirmed,
          use_reviewed_summary: useSummary,
          continue_response:
            submittedPrompt ===
            "Continue only the unfinished part of your last answer. Do not restart the summary or repeat earlier questions.",
        },
        (text) => setLiveDraft((current) => current + text),
      );
      const final = result.case as CaseRecord;
      assign(final);
      setPrompt("");
      setLiveDraft("");
      setDirty(false);
      if (submittedMode === "organize") {
        setSummary(result.answer);
        setReviewed(false);
        setStage(1);
      } else setStage(3);
      setNotice(
        `Response saved · ${result.seconds.toFixed(1)} seconds · ${result.usage?.completion_tokens ?? "unknown"} output tokens.`,
      );
      if (result.truncated)
        setError(
          "The draft reached its output allowance and is incomplete. Review it, then use Continue response. Do not treat it as a finished assessment.",
        );
    });
  };
  const continueResponse = () => {
    setPrompt(
      "Continue only the unfinished part of your last answer. Do not restart the summary or repeat earlier questions.",
    );
    setMode("chat");
    setStage(2);
    setUseSummary(false);
    setDirty(true);
  };
  const editPrompt = (value: string) => {
    setPrompt(value);
    setDirty(true);
  };
  const editTitle = (value: string) => {
    setTitle(value);
    setDirty(true);
  };
  const editSummary = (value: string) => {
    setSummary(value);
    setReviewed(false);
    setDirty(true);
  };
  return {
    active,
    title,
    prompt,
    summary,
    reviewed,
    confirmed,
    useSummary,
    mode,
    stage,
    reviews,
    dirty,
    busy,
    loading,
    error,
    notice,
    liveDraft,
    elapsed,
    archived,
    messages,
    setConfirmed,
    setUseSummary,
    setMode,
    setStage,
    saveDraft,
    saveReview,
    reload,
    changeStatus,
    submit,
    continueResponse,
    editPrompt,
    editTitle,
    editSummary,
  };
}
export type CaseSession = ReturnType<typeof useCaseSession>;
