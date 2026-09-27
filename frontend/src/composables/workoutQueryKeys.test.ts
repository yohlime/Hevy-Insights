import { describe, expect, it } from "vitest";
import { workoutQueryKeys, type WorkoutFilters } from "./workoutQueryKeys";

const base: WorkoutFilters = { name: undefined, startEpoch: null, endEpoch: null };

describe("workoutQueryKeys", () => {
  it("is stable for identical inputs", () => {
    expect(workoutQueryKeys.page(base, 1, 9)).toEqual(workoutQueryKeys.page({ ...base }, 1, 9));
    expect(workoutQueryKeys.infinite(base, 20)).toEqual(workoutQueryKeys.infinite({ ...base }, 20));
  });

  it("partitions by page and page size", () => {
    expect(workoutQueryKeys.page(base, 1, 9)).not.toEqual(workoutQueryKeys.page(base, 2, 9));
    expect(workoutQueryKeys.page(base, 1, 9)).not.toEqual(workoutQueryKeys.page(base, 1, 20));
  });

  it("separates infinite from page mode", () => {
    expect(workoutQueryKeys.infinite(base, 20)).not.toEqual(workoutQueryKeys.page(base, 1, 20));
  });

  it("partitions by filters", () => {
    expect(workoutQueryKeys.infinite(base, 20)).not.toEqual(
      workoutQueryKeys.infinite({ ...base, name: "push" }, 20),
    );
    expect(workoutQueryKeys.infinite(base, 20)).not.toEqual(
      workoutQueryKeys.infinite({ ...base, startEpoch: 1000 }, 20),
    );
  });
});
