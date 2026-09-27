import { useQuery } from "@tanstack/vue-query";
import { authService, workoutService } from "../services/api";
import { useSession, type Workout } from "../stores/session";

export const allWorkoutsQueryKey = ["workouts", "all"] as const;

const PAGE_SIZE = 50;
const MAX_PAGES = 2000;

async function fetchAllWorkouts(session: ReturnType<typeof useSession>): Promise<Workout[]> {
  // CSV mode: never call the API.
  if (session.dataSource === "csv") {
    return session.ensureCsvLoaded();
  }

  const authStatus = await authService.getAuthStatus();
  const isProMode = authStatus.auth_mode === "api_key";
  const allWorkouts: Workout[] = [];

  if (isProMode) {
    for (let page = 1; page <= MAX_PAGES; page += 1) {
      const result = await workoutService.getWorkouts("", (page - 1) * PAGE_SIZE, PAGE_SIZE);
      const batch = result.workouts || [];
      if (batch.length === 0) break;
      allWorkouts.push(...batch);
      if (batch.length < PAGE_SIZE) break;
    }
    return allWorkouts;
  }

  if (!session.username) {
    await session.fetchUserAccount();
  }
  if (!session.username) {
    throw new Error("Username not available for API requests");
  }

  for (let pagesFetched = 0; pagesFetched < MAX_PAGES; pagesFetched += 1) {
    const offset = pagesFetched * PAGE_SIZE;
    const result = await workoutService.getWorkouts(session.username, offset, PAGE_SIZE);
    const batch = result.workouts || [];
    if (batch.length === 0) break;
    allWorkouts.push(...batch);
    if (batch.length < PAGE_SIZE) break;
  }
  return allWorkouts;
}

/**
 * Full workout history (all pages) used by the analytics views
 * (Dashboard / Exercises / Share). Shared across views via one query key.
 */
export function useAllWorkoutsQuery() {
  const session = useSession();
  return useQuery({
    queryKey: allWorkoutsQueryKey,
    queryFn: () => fetchAllWorkouts(session),
  });
}
