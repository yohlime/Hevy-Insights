import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useHevyCache } from "../stores/hevy_cache";

export type TimeRange = "all" | "1w" | "1m" | "3m" | "6m" | "12m";

export interface PRItem {
  type: string;
  value: number | string;
}

/**
 * Shared logic for the Workouts card and list views: data loading, date-range
 * filtering, global workout indexing (#N) and the various display helpers.
 * Card/list specific state (pagination, search, expansion) stays in the views.
 */
export function useWorkoutsView() {
  const { t } = useI18n();
  const store = useHevyCache();
  const userAccount = computed(() => store.userAccount);

  const filterRange = ref<TimeRange>("all");
  const loading = computed(() => store.isLoadingWorkouts || store.isLoadingUser);

  // Sort newest → oldest for consistent indexing (#N)
  const allWorkoutsSorted = computed(() =>
    [...store.workouts].sort((a: any, b: any) => (b.start_time || 0) - (a.start_time || 0)),
  );

  const filteredWorkouts = computed(() => {
    if (filterRange.value === "all") return allWorkoutsSorted.value;
    const nowSec = Math.floor(Date.now() / 1000);
    let days: number;
    switch (filterRange.value) {
      case "1w": days = 7; break;
      case "1m": days = 30; break;
      case "3m": days = 90; break;
      case "6m": days = 180; break;
      case "12m": days = 360; break; // 12 x 30-day months for consistency
      default: days = 90; // fallback
    }
    const cutoff = nowSec - days * 24 * 3600;
    return allWorkoutsSorted.value.filter((w: any) => (w.start_time || 0) >= cutoff);
  });

  // Global index number (#N): oldest = #1, newest = #total
  const workoutIndex = (workoutId: string): string | number => {
    const idx = allWorkoutsSorted.value.findIndex((w: any) => w.id === workoutId);
    if (idx < 0) return "?";
    return allWorkoutsSorted.value.length - idx;
  };

  const totalSets = (workout: any): number =>
    (workout.exercises || []).reduce((sum: number, ex: any) => sum + ((ex.sets || []).length), 0);

  // Biometrics from Hevy API payload
  const biometrics = (workout: any) => {
    const bio = workout?.biometrics;
    if (!bio || typeof bio !== "object") return null;
    const hasData = typeof bio.total_calories === "number" || typeof bio.average_heart_rate === "number";
    return hasData ? bio : null;
  };
  const bpmDisplay = (workout: any) => {
    const bio = biometrics(workout);
    const bpm = bio?.average_heart_rate;
    return typeof bpm === "number" ? `${Math.round(bpm)} bpm` : null;
  };
  const caloriesDisplay = (workout: any) => {
    const bio = biometrics(workout);
    const cal = bio?.total_calories;
    return typeof cal === "number" ? `${Math.round(cal)} kcal` : null;
  };

  // PR helpers based on sets.prs / sets.personalRecords
  const extractSetPRs = (set: any): PRItem[] => {
    const prsArr = Array.isArray(set?.prs) ? set.prs : (set?.prs ? [set.prs] : []);
    const personalArr = Array.isArray(set?.personalRecords) ? set.personalRecords : (set?.personalRecords ? [set.personalRecords] : []);
    const all = [...prsArr, ...personalArr].filter(Boolean).map((p: any) => ({ type: String(p.type || ""), value: p.value }));
    return all.filter((p) => p.type);
  };
  const exercisePRs = (exercise: any): PRItem[] => {
    const sets = Array.isArray(exercise?.sets) ? exercise.sets : [];
    const items: PRItem[] = [];
    for (const s of sets) items.push(...extractSetPRs(s));
    const seen = new Set<string>();
    return items.filter((it) => {
      const k = `${it.type}|${it.value}`;
      if (seen.has(k)) return false;
      seen.add(k);
      return true;
    });
  };

  // Translate PR type names using i18n keys
  const getLocalizedPRType = (prType: string): string => {
    const key = `dashboard.prTypes.${prType}`;
    const translation = t(key);
    if (translation === key) return prType.split("_").join(" ");
    return translation;
  };

  const ensureWorkoutsLoaded = () => store.fetchWorkouts();

  return {
    store,
    userAccount,
    t,
    filterRange,
    loading,
    allWorkoutsSorted,
    filteredWorkouts,
    workoutIndex,
    totalSets,
    biometrics,
    bpmDisplay,
    caloriesDisplay,
    extractSetPRs,
    exercisePRs,
    getLocalizedPRType,
    ensureWorkoutsLoaded,
  };
}
