import { computed, toValue, type MaybeRefOrGetter } from "vue";
import { useQuery } from "@tanstack/vue-query";
import { routineService } from "../services/api";
import { useSession } from "../stores/session";
import { useAllWorkoutsQuery } from "./useAllWorkouts";

export interface RoutineRepTarget {
  targetReps: number;
  setCount: number;
  routineTitle?: string;
}

export const routineTargetsQueryKey = ["routine-targets"] as const;

async function fetchRoutineTargets(workouts: any[]): Promise<Record<string, RoutineRepTarget>> {
  const routineIds = Array.from(
    new Set(
      workouts
        .map((workout) => workout.routine_id)
        .filter((id): id is string => typeof id === "string" && id.length > 0),
    ),
  ).slice(0, 50);

  const targets: Record<string, RoutineRepTarget> = {};

  await Promise.all(
    routineIds.map(async (routineId) => {
      try {
        const response = await routineService.getRoutine(routineId);
        const routine = response?.routine;
        const exercises = Array.isArray(routine?.exercises) ? routine.exercises : [];
        for (const exercise of exercises) {
          const templateId = exercise?.exercise_template_id;
          if (typeof templateId !== "string" || !templateId) continue;
          const sets = Array.isArray(exercise?.sets) ? exercise.sets : [];
          const reps = sets
            .map((set: any) => Number(set?.reps))
            .filter((value: number) => Number.isFinite(value) && value > 0);
          if (reps.length === 0) continue;
          const targetReps = Math.max(...reps);
          const existing = targets[templateId];
          if (!existing || targetReps > existing.targetReps) {
            targets[templateId] = { targetReps, setCount: reps.length, routineTitle: routine?.title };
          }
        }
      } catch {
        // Routines are optional; a failure falls back to history-inferred targets.
      }
    }),
  );

  return targets;
}

/**
 * Prescribed reps per exercise template, derived from the routines referenced
 * by the user's workouts. Optional data; failures degrade to inferred targets.
 */
export function useRoutineTargetsQuery(enabled: MaybeRefOrGetter<boolean> = true) {
  const session = useSession();
  const { data: workouts } = useAllWorkoutsQuery();
  return useQuery({
    queryKey: routineTargetsQueryKey,
    queryFn: () => fetchRoutineTargets(workouts.value ?? []),
    // Routines require Hevy auth; CSV mode has none.
    enabled: computed(() => toValue(enabled) && session.dataSource !== "csv" && (workouts.value?.length ?? 0) > 0),
  });
}
