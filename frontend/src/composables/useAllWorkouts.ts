import { useQuery } from "@tanstack/vue-query";
import { useHevyCache } from "../stores/hevy_cache";

export const allWorkoutsQueryKey = ["workouts", "all"] as const;

/**
 * Full workout history (all pages) used by the analytics views
 * (Dashboard / Exercises / Share). Shared across views via one query key.
 */
export function useAllWorkoutsQuery() {
  const store = useHevyCache();
  return useQuery({
    queryKey: allWorkoutsQueryKey,
    queryFn: () => store.fetchWorkouts(),
  });
}
