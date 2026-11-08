import { Fragment } from "react";

export function hasRepetition(text: string) {
  const counts = new Map<string, number>();
  for (const fragment of text.split(/[\n.!?•]|\*\s+/)) {
    const normalized = fragment
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, " ")
      .trim();
    if (normalized.split(" ").length < 7) continue;
    const count = (counts.get(normalized) || 0) + 1;
    if (count >= 3) return true;
    counts.set(normalized, count);
  }
  return false;
}

function inline(text: string) {
  return text
    .split(/(\*\*[^*]+\*\*)/g)
    .map((part, i) =>
      part.startsWith("**") && part.endsWith("**") ? (
        <strong key={i}>{part.slice(2, -2)}</strong>
      ) : (
        <Fragment key={i}>{part}</Fragment>
      ),
    );
}

export default function ModelText({ text }: { text: string }) {
  const body = (
    <div className="model-text">
      {text.split("\n").map((line, i) => {
        if (/^#{1,4}\s/.test(line))
          return <h3 key={i}>{inline(line.replace(/^#+\s/, ""))}</h3>;
        if (/^\s*[-*]\s/.test(line))
          return (
            <div className="model-bullet" key={i}>
              • {inline(line.replace(/^\s*[-*]\s/, ""))}
            </div>
          );
        return <div key={i}>{line ? inline(line) : <br />}</div>;
      })}
    </div>
  );
  return hasRepetition(text) ? (
    <details className="repetitive-draft">
      <summary>Repetitive saved draft · expand original text</summary>
      <p>
        This answer contains repeated text. Start a new case from the original
        facts rather than continuing this draft.
      </p>
      {body}
    </details>
  ) : (
    body
  );
}
