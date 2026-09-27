export interface WorkoutFilters {
  name?: string;
  startEpoch: number | null;
  endEpoch: number | null;
}

/**
 * TanStack Query keys for the Workouts views. Kept pure so the cache
 * partitioning can be unit-tested without mounting components.
 */
export const workoutQueryKeys = {
  page: (filters: WorkoutFilters, page: number, pageSize: number) =>
    ["workouts", "page", { ...filters }, page, pageSize] as const,
  infinite: (filters: WorkoutFilters, pageSize: number) =>
    ["workouts", "infinite", { ...filters }, pageSize] as const,
};
