import { describe, it, expect } from "vitest";
import { mergeActivity, type Activity } from "./api";

describe("activity replay", () => {
  const event = (sequence: number) =>
    ({
      sequence,
      eventId: String(sequence),
      createdAt: "",
      kind: "contribution.accepted",
      details: {},
    }) satisfies Activity;
  it("deduplicates repeated batches and preserves sequence order", () => {
    expect(
      mergeActivity([event(2), event(1)], [event(2), event(3)]).map(
        (e) => e.sequence,
      ),
    ).toEqual([1, 2, 3]);
  });
  it("bounds retained history without reversing arrival order", () => {
    expect(
      mergeActivity([event(1)], [event(2), event(3)], 2).map((e) => e.sequence),
    ).toEqual([2, 3]);
  });
});
