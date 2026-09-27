import { computed, nextTick, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { keepPreviousData, useInfiniteQuery, useQuery } from "@tanstack/vue-query";
import { useSession } from "../stores/session";
import { workoutService } from "../services/api";
import { workoutQueryKeys, type WorkoutFilters } from "./workoutQueryKeys";

export type TimeRange = "all" | "1w" | "1m" | "3m" | "6m" | "12m";

export interface PRItem {
  type: string;
  value: number | string;
}

interface WorkoutPage {
  workouts: any[];
  total: number;
}

const RANGE_DAYS: Record<Exclude<TimeRange, "all">, number> = {
  "1w": 7,
  "1m": 30,
  "3m": 90,
  "6m": 180,
  "12m": 360,
};

interface UseWorkoutsViewOptions {
  /** Accumulate pages instead of replacing them (infinite scroll). */
  infinite?: boolean;
  /** Initial single-day filter (`YYYY-MM-DD`) from a deep link. */
  initialDay?: string;
}

type SessionStore = ReturnType<typeof useSession>;

async function fetchWorkoutPage(session: SessionStore, page: number, pageSize: number, filters: WorkoutFilters): Promise<WorkoutPage> {
  if (session.dataSource === "csv") {
    const csvWorkouts = session.ensureCsvLoaded();
    const filtered = [...csvWorkouts]
      .sort((a, b) => (b.start_time || 0) - (a.start_time || 0))
      .filter((w) => (filters.startEpoch == null || (w.start_time || 0) >= filters.startEpoch) && (filters.endEpoch == null || (w.start_time || 0) < filters.endEpoch))
      .filter((w) => !filters.name || String(w.title || w.name || "").toLowerCase().includes(filters.name.toLowerCase()));
    return { workouts: filtered.slice((page - 1) * pageSize, page * pageSize), total: filtered.length };
  }

  if (!session.username) {
    await session.fetchUserAccount();
  }
  const result = await workoutService.getWorkouts(session.username ?? "", (page - 1) * pageSize, pageSize, {
    name: filters.name,
    startEpoch: filters.startEpoch,
    endEpoch: filters.endEpoch,
  });
  return { workouts: result.workouts ?? [], total: result.total_count ?? (result.workouts?.length ?? 0) };
}

/**
 * Shared logic for the Workouts card and list views, backed by TanStack Query.
 *
 * `{ infinite: true }` accumulates pages (`loadMore` drives infinite scroll);
 * otherwise page-numbered navigation replaces the page.
 */
export function useWorkoutsView(pageSize = 9, options: UseWorkoutsViewOptions = {}) {
  const infinite = options.infinite === true;
  const { t } = useI18n();
  const session = useSession();
  const userAccount = computed(() => session.userAccount);

  const timeRange = ref<TimeRange>("all");
  const searchName = ref("");
  const currentPage = ref(1);
  const dayStart = ref<number | null>(null);
  const dayEnd = ref<number | null>(null);

  function startEpochForRange(range: TimeRange): number | null {
    if (range === "all") return null;
    const days = RANGE_DAYS[range] ?? 90;
    return Math.floor(Date.now() / 1000) - days * 24 * 3600;
  }

  function applyDay(day: string) {
    const [year, month, dayOfMonth] = day.split("-").map(Number);
    if (!year || !month || !dayOfMonth) return;
    dayStart.value = Math.floor(new Date(year, month - 1, dayOfMonth, 0, 0, 0, 0).getTime() / 1000);
    dayEnd.value = Math.floor(new Date(year, month - 1, dayOfMonth + 1, 0, 0, 0, 0).getTime() / 1000);
  }

  if (options.initialDay) applyDay(options.initialDay);

  const filters = computed<WorkoutFilters>(() => {
    const isDay = dayStart.value != null;
    return {
      name: searchName.value.trim() || undefined,
      startEpoch: isDay ? dayStart.value : startEpochForRange(timeRange.value),
      endEpoch: isDay ? dayEnd.value : null,
    };
  });

  // Any filter change starts again from the first page.
  watch(filters, () => {
    currentPage.value = 1;
  });
  // Picking a date range clears any single-day deep-link filter.
  watch(timeRange, () => {
    dayStart.value = null;
    dayEnd.value = null;
  });

  function setDayFilter(day: string) {
    applyDay(day);
    currentPage.value = 1;
  }
  const isDayFiltered = computed(() => dayStart.value != null);
  function clearDayFilter() {
    if (dayStart.value == null) return;
    dayStart.value = null;
    dayEnd.value = null;
    currentPage.value = 1;
  }

  const totalSets = (workout: any): number =>
    (workout.exercises || []).reduce((sum: number, ex: any) => sum + ((ex.sets || []).length), 0);

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

  const getLocalizedPRType = (prType: string): string => {
    const key = `dashboard.prTypes.${prType}`;
    const translation = t(key);
    if (translation === key) return prType.split("_").join(" ");
    return translation;
  };

  const common = {
    store: session,
    userAccount,
    t,
    timeRange,
    searchName,
    currentPage,
    setDayFilter,
    clearDayFilter,
    isDayFiltered,
    totalSets,
    biometrics,
    bpmDisplay,
    caloriesDisplay,
    extractSetPRs,
    exercisePRs,
    getLocalizedPRType,
  };

  if (infinite) {
    const query = useInfiniteQuery({
      queryKey: computed(() => workoutQueryKeys.infinite(filters.value, pageSize)),
      queryFn: ({ pageParam }) => fetchWorkoutPage(session, pageParam as number, pageSize, filters.value),
      initialPageParam: 1,
      getNextPageParam: (lastPage, allPages, lastPageParam) => {
        const loaded = allPages.reduce((sum, page) => sum + page.workouts.length, 0);
        if (loaded >= lastPage.total || lastPage.workouts.length === 0) return undefined;
        return (lastPageParam as number) + 1;
      },
    });

    const pageItems = computed(() => (query.data.value?.pages ?? []).flatMap((page) => page.workouts));
    const totalCount = computed(() => query.data.value?.pages?.[0]?.total ?? 0);
    const totalPages = computed(() => Math.max(1, Math.ceil(totalCount.value / pageSize)));
    const hasMore = computed(() => query.hasNextPage.value === true);
    const loading = computed(() => query.isLoading.value);
    const isError = computed(() => query.isError.value);
    const errorMessage = computed(() => (query.error.value as Error | null)?.message ?? null);
    const isFetchingMore = computed(() => query.isFetchingNextPage.value);

    const workoutIndexAt = (indexInList: number): number => totalCount.value - indexInList;
    const load = () => query.refetch();
    const loadMore = () => {
      if (query.hasNextPage.value && !query.isFetchingNextPage.value) return query.fetchNextPage();
      return Promise.resolve();
    };
    const goToWorkoutNumber = async (num: number | null): Promise<boolean> => {
      if (!num || num < 1 || num > totalCount.value) return false;
      const targetPage = Math.floor((totalCount.value - num) / pageSize) + 1;
      while ((query.data.value?.pages.length ?? 0) < targetPage && query.hasNextPage.value) {
        await query.fetchNextPage();
      }
      await nextTick();
      document.querySelector(`[data-workout-index="${num}"]`)?.scrollIntoView({ behavior: "smooth", block: "center" });
      return true;
    };

    return {
      ...common,
      infinite: true,
      pageItems,
      totalCount,
      totalPages,
      hasMore,
      hasPrev: computed(() => false),
      loading,
      isError,
      errorMessage,
      isFetchingMore,
      load,
      loadMore,
      workoutIndexAt,
      goToWorkoutNumber,
      nextPage: () => Promise.resolve(),
      prevPage: () => Promise.resolve(),
      firstPage: () => Promise.resolve(),
      lastPage: () => Promise.resolve(),
    };
  }

  const query = useQuery({
    queryKey: computed(() => workoutQueryKeys.page(filters.value, currentPage.value, pageSize)),
    queryFn: () => fetchWorkoutPage(session, currentPage.value, pageSize, filters.value),
    placeholderData: keepPreviousData,
  });

  const pageItems = computed(() => query.data.value?.workouts ?? []);
  const totalCount = computed(() => query.data.value?.total ?? 0);
  const totalPages = computed(() => Math.max(1, Math.ceil(totalCount.value / pageSize)));
  const hasMore = computed(() => currentPage.value < totalPages.value);
  const hasPrev = computed(() => currentPage.value > 1);
  const loading = computed(() => query.isLoading.value);
  const isError = computed(() => query.isError.value);
  const errorMessage = computed(() => (query.error.value as Error | null)?.message ?? null);

  const workoutIndexAt = (indexInList: number): number =>
    totalCount.value - ((currentPage.value - 1) * pageSize + indexInList);
  const load = () => query.refetch();
  const nextPage = () => { if (hasMore.value) currentPage.value += 1; };
  const prevPage = () => { if (hasPrev.value) currentPage.value -= 1; };
  const firstPage = () => { currentPage.value = 1; };
  const lastPage = () => { currentPage.value = totalPages.value; };
  const goToWorkoutNumber = (num: number | null): boolean => {
    if (!num || num < 1 || num > totalCount.value) return false;
    currentPage.value = Math.floor((totalCount.value - num) / pageSize) + 1;
    return true;
  };

  return {
    ...common,
    infinite: false,
    pageItems,
    totalCount,
    totalPages,
    hasMore,
    hasPrev,
    loading,
    isError,
    errorMessage,
    isFetchingMore: computed(() => false),
    load,
    loadMore: () => Promise.resolve(),
    nextPage,
    prevPage,
    firstPage,
    lastPage,
    workoutIndexAt,
    goToWorkoutNumber,
  };
}
