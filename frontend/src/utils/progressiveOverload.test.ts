import { describe, expect, it } from "vitest";
import { analyzeProgression, estimate1RM, type ProgressiveOverloadDay } from "./progressiveOverload";

function makeDay(daysAgo: number, sets: [number, number][], extra: { distance?: number; duration?: number } = {}): ProgressiveOverloadDay {
  let maxWeight = 0;
  let repsAtMax = 0;
  let volume = 0;
  let best1RM = 0;
  let totalReps = 0;
  for (const [weight, reps] of sets) {
    volume += weight * reps;
    totalReps += reps;
    best1RM = Math.max(best1RM, estimate1RM(weight, reps));
    if (weight > maxWeight) {
      maxWeight = weight;
      repsAtMax = reps;
    } else if (weight === maxWeight) {
      repsAtMax = Math.max(repsAtMax, reps);
    }
  }
  const date = new Date(Date.now() - daysAgo * 86_400_000).toISOString().slice(0, 10);
  return {
    day: date,
    maxWeight,
    repsAtMax,
    volume,
    best1RM,
    totalReps,
    setCount: sets.length,
    totalDistance: extra.distance ?? 0,
    totalDuration: extra.duration ?? 0,
    avgRpe: null,
  };
}

function build(entries: Array<{ daysAgo: number; sets: [number, number][] }>) {
  const byDay: Record<string, ProgressiveOverloadDay> = {};
  const sets: Array<{ day: string; weight: number; reps: number }> = [];
  for (const entry of entries) {
    const day = makeDay(entry.daysAgo, entry.sets);
    byDay[day.day] = day;
    for (const [weight, reps] of entry.sets) sets.push({ day: day.day, weight, reps });
  }
  return { byDay, sets };
}

describe("analyzeProgression", () => {
  it("recommends adding weight once all sets reach the top of the range", () => {
    const { byDay, sets } = build([
      { daysAgo: 28, sets: [[60, 8], [60, 7], [60, 6]] },
      { daysAgo: 21, sets: [[60, 8], [60, 8], [60, 7]] },
      { daysAgo: 14, sets: [[60, 9], [60, 8], [60, 8]] },
      { daysAgo: 7, sets: [[60, 10], [60, 10], [60, 10]] },
    ]);

    const result = analyzeProgression(byDay, { sessions: 4, sets });

    expect(result?.status).toBe("ready_to_increase");
    expect(result?.action).toBe("increase_weight");
    expect(result?.suggestedWeight).toBe(62.5);
  });

  it("treats a rep drop after a load increase as progressing, not regression", () => {
    const { byDay, sets } = build([
      { daysAgo: 10, sets: [[60, 10], [60, 10], [60, 10]] },
      { daysAgo: 3, sets: [[62.5, 7], [62.5, 7], [62.5, 6]] },
    ]);

    const result = analyzeProgression(byDay, { sessions: 2, sets, weightIncrementKg: 2.5 });

    expect(result?.status).toBe("progressing");
    expect(result?.action).toBe("hold");
  });

  it("flags a suspected plateau for repeated identical sessions", () => {
    const { byDay, sets } = build([
      { daysAgo: 28, sets: [[60, 10], [60, 10], [60, 10]] },
      { daysAgo: 21, sets: [[60, 10], [60, 10], [60, 10]] },
      { daysAgo: 14, sets: [[60, 10], [60, 10], [60, 10]] },
      { daysAgo: 7, sets: [[60, 10], [60, 10], [60, 10]] },
    ]);

    const result = analyzeProgression(byDay, { sessions: 4, sets });

    expect(result?.status).toBe("plateau_suspected");
    expect(result?.action).toBe("add_reps");
  });

  it("recommends a deload when performance declines", () => {
    const { byDay, sets } = build([
      { daysAgo: 28, sets: [[80, 8], [80, 8], [80, 8]] },
      { daysAgo: 21, sets: [[80, 7], [80, 7], [80, 7]] },
      { daysAgo: 14, sets: [[75, 7], [75, 7], [75, 7]] },
      { daysAgo: 7, sets: [[70, 6], [70, 6], [70, 6]] },
    ]);

    const result = analyzeProgression(byDay, { sessions: 4, sets });

    expect(result?.status).toBe("regressing");
    expect(result?.action).toBe("deload");
  });

  it("uses a routine target for readiness instead of history inference", () => {
    const { byDay, sets } = build([
      { daysAgo: 14, sets: [[60, 8], [60, 8], [60, 8]] },
      { daysAgo: 7, sets: [[60, 8], [60, 8], [60, 8]] },
    ]);

    const result = analyzeProgression(byDay, { sessions: 2, sets, targetReps: 8 });

    expect(result?.signals.targetSource).toBe("routine");
    expect(result?.status).toBe("ready_to_increase");
  });

  it("progresses bodyweight reps-only exercises by reps", () => {
    const { byDay, sets } = build([
      { daysAgo: 21, sets: [[0, 12], [0, 11], [0, 10]] },
      { daysAgo: 14, sets: [[0, 12], [0, 12], [0, 11]] },
      { daysAgo: 7, sets: [[0, 13], [0, 12], [0, 11]] },
    ]);

    const result = analyzeProgression(byDay, { sessions: 3, sets, isBodyweight: true });

    expect(result?.action).toBe("add_reps");
  });

  it("returns null without history and build_base when insufficient", () => {
    expect(analyzeProgression({}, { sessions: 3 })).toBeNull();

    const { byDay, sets } = build([{ daysAgo: 7, sets: [[60, 8]] }]);
    const result = analyzeProgression(byDay, { sessions: 3, sets });

    expect(result?.status).toBe("insufficient");
    expect(result?.action).toBe("build_base");
  });

  it("returns returning after a long gap", () => {
    const { byDay, sets } = build([
      { daysAgo: 120, sets: [[60, 8], [60, 8]] },
      { daysAgo: 100, sets: [[60, 8], [60, 8]] },
    ]);

    const result = analyzeProgression(byDay, { sessions: 2, sets });

    expect(result?.status).toBe("returning");
    expect(result?.action).toBe("resume");
  });
});

describe("estimate1RM", () => {
  it("uses the Epley formula and can clamp high reps", () => {
    expect(estimate1RM(100, 5)).toBeCloseTo(116.6667, 3);
    expect(estimate1RM(100, 30, 15)).toBeCloseTo(150, 3);
    expect(estimate1RM(0, 10)).toBe(0);
  });
});
