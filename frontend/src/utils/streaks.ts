type WorkoutLike = {
  start_time?: number | string | null;
  [key: string]: unknown;
};

function startOfWeek(date: Date): Date {
  const weekStart = new Date(date);
  const day = weekStart.getDay();
  const offsetToMonday = day === 0 ? -6 : 1 - day;
  weekStart.setDate(weekStart.getDate() + offsetToMonday);
  weekStart.setHours(0, 0, 0, 0);
  return weekStart;
}

function weekKey(date: Date): string {
  const weekStart = startOfWeek(date);
  return `${weekStart.getFullYear()}-${String(weekStart.getMonth() + 1).padStart(2, "0")}-${String(weekStart.getDate()).padStart(2, "0")}`;
}

function workoutDate(workout: WorkoutLike): Date | null {
  const value = workout.start_time;
  if (value === null || value === undefined || value === "") return null;

  if (typeof value === "number") {
    const milliseconds = value > 1_000_000_000_000 ? value : value * 1000;
    const date = new Date(milliseconds);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  const numericValue = Number(value);
  if (Number.isFinite(numericValue) && value.trim() !== "") {
    const milliseconds = numericValue > 1_000_000_000_000 ? numericValue : numericValue * 1000;
    const date = new Date(milliseconds);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function calculateWorkoutStreakWeeks(
  workouts: WorkoutLike[],
  options: { year?: number; referenceDate?: Date } = {},
): number {
  const referenceDate = options.referenceDate ?? new Date();
  const currentWeekStart = startOfWeek(referenceDate);
  const weeks = new Set<string>();
  let latestWorkoutWeek: Date | null = null;

  for (const workout of workouts) {
    const date = workoutDate(workout);
    if (!date) continue;
    if (options.year !== undefined && date.getFullYear() !== options.year) continue;

    const workoutWeek = startOfWeek(date);
    if (workoutWeek > currentWeekStart) continue;

    weeks.add(weekKey(workoutWeek));
    if (!latestWorkoutWeek || workoutWeek > latestWorkoutWeek) {
      latestWorkoutWeek = workoutWeek;
    }
  }

  if (!latestWorkoutWeek) return 0;

  let streak = 0;
  const current = new Date(latestWorkoutWeek);
  while (weeks.has(weekKey(current))) {
    streak++;
    current.setDate(current.getDate() - 7);
  }
  return streak;
}
