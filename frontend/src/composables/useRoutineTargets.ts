import type { MaybeRefOrGetter } from "vue";
import { useQuery } from "@tanstack/vue-query";
import { useHevyCache } from "../stores/hevy_cache";

export const routineTargetsQueryKey = ["routine-targets"] as const;

/**
 * Prescribed reps per exercise template, derived from the user's routines.
 * Optional data: a failure just falls back to history-inferred targets.
 */
export function useRoutineTargetsQuery(enabled: MaybeRefOrGetter<boolean> = true) {
  const store = useHevyCache();
  return useQuery({
    queryKey: routineTargetsQueryKey,
    queryFn: () => store.fetchRoutineRepTargets(),
    enabled,
  });
}
