/**
 * Progressive Overload Utility
 *
 * Pure, framework-agnostic helpers that turn per-session exercise aggregates
 * into a progression *state* (what is happening) and a separate *recommendation*
 * (what to do next).
 *
 * Hevy does not provide bar velocity, so this adapts the load/volume rules from
 * the GymAware progressive-overload guide to the data we do have: top-set
 * weight/reps, estimated 1RM (Epley), volume, RPE and cardio distance/duration.
 * The model is exposure-based (one exposure = one session containing the
 * exercise), so calendar gaps never distort the trend.
 */

/**
 * Estimated one-rep max using the Epley formula: weight * (1 + reps / 30).
 * Returns 0 when the set has no load (e.g. bodyweight) or no reps.
 * `maxReps` optionally caps reps because Epley becomes unreliable at high reps.
 */
export function estimate1RM(weightKg: number, reps: number, maxReps: number = Infinity): number {
  const weight = Number(weightKg) || 0;
  const count = Number(reps) || 0;
  if (weight <= 0 || count <= 0) return 0;
  const effectiveReps = Math.min(count, maxReps);
  return weight * (1 + effectiveReps / 30);
}

export type ProgressionStatus =
  | "progressing"
  | "ready_to_increase"
  | "holding"
  | "plateau_suspected"
  | "regressing"
  | "returning"
  | "insufficient";

export type OverloadAction =
  | "increase_weight"
  | "reduce_assistance"
  | "add_reps"
  | "increase_distance"
  | "increase_duration"
  | "hold"
  | "deload"
  | "build_base"
  | "resume";

export type OverloadReason =
  | "inactive"
  | "insufficient"
  | "plateau_ready_for_load"
  | "plateau_build_reps"
  | "gaining"
  | "gaining_fast"
  | "holding"
  | "losing";

export type OverloadConfidence = "low" | "medium" | "high";

export interface OverloadSet {
  day: string;
  weight: number;
  reps: number;
  rpe?: number | null;
  distance_km?: number;
  duration_seconds?: number;
}

export interface ProgressiveOverloadDay {
  day: string;
  maxWeight: number;
  repsAtMax: number;
  volume: number;
  best1RM: number;
  totalReps: number;
  setCount: number;
  totalDistance: number;
  totalDuration: number;
  avgRpe: number | null;
}

export interface ProgressiveOverloadOptions {
  sessions: number;
  /** Raw per-set history, used for hard-set / top-of-range detection. */
  sets?: OverloadSet[];
  isCardio?: boolean;
  isAssisted?: boolean;
  isBodyweight?: boolean;
  /** Maximum load increase per week, in percent (guide rule of thumb: 10%). */
  maxWeeklyIncreasePct?: number;
  /** Explicit rep target; when omitted the target is inferred from history. */
  targetReps?: number;
  /** Smallest weight plate increment, in kg. */
  weightIncrementKg?: number;
  /** Exposures without meaningful progress before a plateau is suspected. */
  plateauExposures?: number;
  /** e1RM change (percent over the window) treated as measurement noise. */
  regressionTolerancePct?: number;
  /** RPE at or above which a set counts as "hard". */
  rpeHardThreshold?: number;
}

export interface ProgressionSignals {
  exposureCount: number;
  /** Regression-based change in the primary metric over the window, in percent. */
  totalTrendPct: number;
  /** First-half vs second-half e1RM change, in percent. */
  e1rmTrendPct: number;
  /** First-half vs second-half volume change, in percent. */
  volumeTrendPct: number;
  /** First-half vs second-half reps change, in percent. */
  repsTrendPct: number;
  /** Change in top-set load between the first and last exposure, in kg. */
  loadTrendKg: number;
  loadStable: boolean;
  /** Load rose by at least one increment on the latest exposure. */
  latestLoadIncrease: boolean;
  /** Consecutive exposures without a meaningful new best. */
  flatExposures: number;
  hardSetRatio: number;
  avgRpe: number | null;
  /** Top of the target rep range (prescribed by a routine, or inferred from history). */
  targetReps: number;
  targetSource: "routine" | "history";
  atTopOfRepRange: boolean;
  isBodyweight: boolean;
}

export interface ProgressionState {
  status: ProgressionStatus;
  signals: ProgressionSignals;
  sessions: number;
  windowSessions: number;
  confidence: OverloadConfidence;
  currentWeight: number;
  currentReps: number;
  currentDistanceKm: number;
  currentDurationSeconds: number;
}

export interface OverloadRecommendation {
  action: OverloadAction;
  reason: OverloadReason;
  suggestedWeight: number;
  suggestedReps: number;
  suggestedDistanceKm: number;
  suggestedDurationSeconds: number;
  percentChange: number;
}

export interface ProgressiveOverloadResult extends ProgressionState, OverloadRecommendation {}

const MAX_INACTIVE_DAYS = 60;
const DEFAULT_PLATEAU_EXPOSURES = 3;
const DEFAULT_REGRESSION_TOLERANCE_PCT = 2;
const DEFAULT_RPE_HARD_THRESHOLD = 8;
const MIN_WEIGHT_INCREMENT = 0.5;

function average(values: number[]): number {
  if (values.length === 0) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function roundToIncrement(value: number, increment: number): number {
  const safeIncrement = increment > 0 ? increment : 1;
  const rounded = Math.round(value / safeIncrement) * safeIncrement;
  return Math.max(safeIncrement, Math.round(rounded * 100) / 100);
}

function confidenceFor(totalSessions: number, windowSessions: number): OverloadConfidence {
  if (totalSessions >= windowSessions * 2) return "high";
  if (totalSessions >= windowSessions) return "medium";
  return "low";
}

/** Regression slope of `values` against exposure index, normalized to percent. */
function slopeTrendPct(values: number[]): number {
  const count = values.length;
  const mean = average(values);
  if (count < 2 || mean <= 0) return 0;
  const meanX = (count - 1) / 2;
  let numerator = 0;
  let denominator = 0;
  for (let i = 0; i < count; i += 1) {
    numerator += (i - meanX) * (values[i]! - mean);
    denominator += (i - meanX) ** 2;
  }
  const slope = denominator > 0 ? numerator / denominator : 0;
  return ((slope * (count - 1)) / mean) * 100;
}

/** First-half vs second-half change, in percent. */
function halfTrendPct(values: number[]): number {
  const midpoint = Math.floor(values.length / 2);
  const firstAvg = average(values.slice(0, midpoint));
  const secondAvg = average(values.slice(midpoint));
  if (firstAvg <= 0) return 0;
  return ((secondAvg - firstAvg) / firstAvg) * 100;
}

function countFlatExposures(values: number[], tolerancePct: number): number {
  if (values.length < 2) return 0;
  let flat = 0;
  let best = values[0]!;
  for (let i = 1; i < values.length; i += 1) {
    const value = values[i]!;
    const improved = best > 0 ? value > best * (1 + tolerancePct / 100) : value > best;
    if (improved) {
      flat = 0;
      best = value;
    } else {
      flat += 1;
      best = Math.max(best, value);
    }
  }
  return flat;
}

function groupSetsByDay(sets: OverloadSet[] | undefined): Record<string, OverloadSet[]> {
  const grouped: Record<string, OverloadSet[]> = {};
  for (const set of sets ?? []) {
    if (!set || !set.day) continue;
    (grouped[set.day] ||= []).push(set);
  }
  return grouped;
}

function emptySignals(isBodyweight: boolean): ProgressionSignals {
  return {
    exposureCount: 0,
    totalTrendPct: 0,
    e1rmTrendPct: 0,
    volumeTrendPct: 0,
    repsTrendPct: 0,
    loadTrendKg: 0,
    loadStable: true,
    latestLoadIncrease: false,
    flatExposures: 0,
    hardSetRatio: 0,
    avgRpe: null,
    targetReps: 0,
    targetSource: "history",
    atTopOfRepRange: false,
    isBodyweight,
  };
}

/**
 * Classify what is happening with an exercise, independent of what to do about it.
 * Returns null when there is no usable session history.
 */
export function detectProgressionState(
  byDay: Record<string, ProgressiveOverloadDay>,
  options: ProgressiveOverloadOptions,
): ProgressionState | null {
  const days = Object.keys(byDay).sort();
  if (days.length === 0) return null;

  const windowSessions = Math.max(1, Math.floor(options.sessions) || 1);
  const plateauExposures = options.plateauExposures ?? DEFAULT_PLATEAU_EXPOSURES;
  const tolerance = options.regressionTolerancePct ?? DEFAULT_REGRESSION_TOLERANCE_PCT;
  const rpeThreshold = options.rpeHardThreshold ?? DEFAULT_RPE_HARD_THRESHOLD;
  const increment = options.weightIncrementKg ?? 2.5;

  const last = byDay[days[days.length - 1]]!;
  const currentWeight = Number(last.maxWeight) || 0;
  const currentReps = Number(last.repsAtMax) || 0;
  const currentDistance = Number(last.totalDistance) || 0;
  const currentDuration = Number(last.totalDuration) || 0;

  const lastDate = new Date(last.day);
  const daysSince = Math.floor((Date.now() - lastDate.getTime()) / 86_400_000);

  const weights = days.map((day) => byDay[day]!.maxWeight);
  const isBodyweight = options.isBodyweight === true || weights.every((weight) => weight <= 0);
  const confidence = confidenceFor(days.length, windowSessions);

  const base = (
    status: ProgressionStatus,
    signals: ProgressionSignals,
    overrides: Partial<ProgressionState> = {},
  ): ProgressionState => ({
    status,
    signals,
    sessions: days.length,
    windowSessions,
    confidence,
    currentWeight,
    currentReps,
    currentDistanceKm: currentDistance,
    currentDurationSeconds: currentDuration,
    ...overrides,
  });

  if (daysSince > MAX_INACTIVE_DAYS) {
    return base("returning", emptySignals(isBodyweight), { confidence: "low" });
  }
  if (days.length < windowSessions) {
    return base("insufficient", emptySignals(isBodyweight), { confidence: "low" });
  }

  const window = days.slice(-windowSessions).map((day) => byDay[day]!);
  const windowWeights = window.map((day) => day.maxWeight);
  const repsAtMax = window.map((day) => day.repsAtMax);
  const e1rms = window.map((day) => day.best1RM);
  const volumes = window.map((day) => day.volume);

  const loadStable = Math.max(...windowWeights) - Math.min(...windowWeights) <= MIN_WEIGHT_INCREMENT;
  const latestLoadIncrease =
    windowWeights.length >= 2 && windowWeights[windowWeights.length - 1]! - windowWeights[windowWeights.length - 2]! >= increment * 0.999;

  const distanceBased = window.some((day) => day.totalDistance > 0);
  const primaryMetric = options.isCardio
    ? window.map((day) => (distanceBased ? day.totalDistance : day.totalDuration))
    : isBodyweight
      ? repsAtMax
      : e1rms;

  const flatExposures = countFlatExposures(primaryMetric, tolerance);
  const totalTrendPct = slopeTrendPct(primaryMetric);

  const setsByDay = groupSetsByDay(options.sets);
  const latestWorkingSets = (setsByDay[last.day] ?? []).filter((set) => Number(set.reps) > 0);
  const latestWorkingReps = latestWorkingSets.length > 0 ? latestWorkingSets.map((set) => Number(set.reps)) : [currentReps];
  const minLatestReps = Math.min(...latestWorkingReps);
  // A prescribed routine target wins; otherwise infer the top of the range from history.
  const explicitTarget = options.targetReps && options.targetReps > 0 ? options.targetReps : null;
  const targetReps = explicitTarget ?? Math.max(0, ...repsAtMax, ...latestWorkingReps);
  const targetSource: "routine" | "history" = explicitTarget ? "routine" : "history";
  const atTopOfRepRange = !options.isCardio && !isBodyweight && targetReps > 0 && minLatestReps >= targetReps;
  const hardSets = latestWorkingSets.filter((set) => Number(set.rpe ?? 0) >= rpeThreshold);
  const hardSetRatio = latestWorkingSets.length > 0 ? hardSets.length / latestWorkingSets.length : 0;
  const avgRpe = last.avgRpe ?? null;

  const signals: ProgressionSignals = {
    exposureCount: window.length,
    totalTrendPct,
    e1rmTrendPct: halfTrendPct(e1rms),
    volumeTrendPct: halfTrendPct(volumes),
    repsTrendPct: halfTrendPct(repsAtMax),
    loadTrendKg: windowWeights[windowWeights.length - 1]! - windowWeights[0]!,
    loadStable,
    latestLoadIncrease,
    flatExposures,
    hardSetRatio,
    avgRpe,
    targetReps,
    targetSource,
    atTopOfRepRange,
    isBodyweight,
  };

  let status: ProgressionStatus;
  if (totalTrendPct < -tolerance && !latestLoadIncrease) {
    status = "regressing";
  } else if (atTopOfRepRange && loadStable && flatExposures < plateauExposures) {
    // Reached the top of the range after recent progress: time to add load.
    status = "ready_to_increase";
  } else if (flatExposures >= plateauExposures) {
    // No meaningful new best for several exposures: suspected plateau, not merely holding.
    status = "plateau_suspected";
  } else if (totalTrendPct > tolerance || latestLoadIncrease) {
    status = "progressing";
  } else {
    status = "holding";
  }

  // Low RPE at near-top reps is an autoregulation nudge toward adding load.
  if (status === "holding" && avgRpe !== null && avgRpe <= rpeThreshold - 1 && minLatestReps >= targetReps * 0.9) {
    status = "ready_to_increase";
  }

  return base(status, signals);
}

/** Turn a progression state into a concrete recommendation. */
export function recommendOverload(
  state: ProgressionState,
  options: ProgressiveOverloadOptions,
): OverloadRecommendation {
  const increment = options.weightIncrementKg ?? 2.5;
  const maxIncreasePct = options.maxWeeklyIncreasePct ?? 10;
  const { signals } = state;
  const {
    currentWeight,
    currentReps,
    currentDistanceKm,
    currentDurationSeconds,
    status,
  } = state;

  const build = (
    action: OverloadAction,
    reason: OverloadReason,
    overrides: Partial<OverloadRecommendation> = {},
  ): OverloadRecommendation => ({
    action,
    reason,
    suggestedWeight: currentWeight,
    suggestedReps: currentReps,
    suggestedDistanceKm: currentDistanceKm,
    suggestedDurationSeconds: currentDurationSeconds,
    percentChange: 0,
    ...overrides,
  });

  const cardioIncrease = (reason: OverloadReason): OverloadRecommendation => {
    const rawDistance = currentDistanceKm * 1.05;
    const rawDuration = currentDurationSeconds * 1.05;
    return build(
      currentDistanceKm > 0 ? "increase_distance" : "increase_duration",
      reason,
      currentDistanceKm > 0
        ? { suggestedDistanceKm: roundToIncrement(rawDistance, 0.1), percentChange: 5 }
        : { suggestedDurationSeconds: Math.max(30, Math.round(rawDuration / 30) * 30), percentChange: 5 },
    );
  };

  if (status === "returning") return build("resume", "inactive");
  if (status === "insufficient") return build("build_base", "insufficient");

  if (status === "regressing") {
    if (options.isCardio) {
      return build("deload", "losing", {
        ...(currentDistanceKm > 0
          ? { suggestedDistanceKm: roundToIncrement(currentDistanceKm * 0.9, 0.1) }
          : { suggestedDurationSeconds: Math.max(30, Math.round((currentDurationSeconds * 0.9) / 30) * 30) }),
        percentChange: -10,
      });
    }
    if (signals.isBodyweight) return build("hold", "losing");
    const suggestedWeight = options.isAssisted
      ? roundToIncrement(currentWeight * 1.1, increment)
      : Math.max(increment, roundToIncrement(currentWeight * 0.9, increment));
    return build("deload", "losing", { suggestedWeight, percentChange: -10 });
  }

  if (status === "ready_to_increase") {
    if (options.isCardio) return cardioIncrease("plateau_ready_for_load");
    if (signals.isBodyweight) return build("add_reps", "plateau_build_reps", { suggestedReps: currentReps + 1 });
    const raw = Math.min(currentWeight + increment, currentWeight * (1 + maxIncreasePct / 100));
    const target = options.isAssisted
      ? Math.max(0, roundToIncrement(currentWeight - increment, increment))
      : roundToIncrement(raw, increment);
    return build(options.isAssisted ? "reduce_assistance" : "increase_weight", "plateau_ready_for_load", {
      suggestedWeight: target,
      percentChange: currentWeight > 0 ? ((target - currentWeight) / currentWeight) * 100 : 0,
    });
  }

  if (status === "progressing") {
    if (options.isCardio) return build("hold", "gaining");
    if (signals.isBodyweight) return build("add_reps", "gaining", { suggestedReps: currentReps + 1 });
    if (signals.totalTrendPct > maxIncreasePct) return build("hold", "gaining_fast");
    if (signals.latestLoadIncrease) return build("hold", "gaining");
    return build("add_reps", "gaining", { suggestedReps: currentReps + 1 });
  }

  if (status === "plateau_suspected") {
    if (options.isCardio) return cardioIncrease("plateau_ready_for_load");
    if (signals.isBodyweight) return build("add_reps", "plateau_build_reps", { suggestedReps: currentReps + 1 });
    return build("add_reps", "plateau_build_reps", { suggestedReps: currentReps + 1 });
  }

  // holding
  if (options.isCardio) return build("hold", "holding");
  if (signals.isBodyweight) return build("add_reps", "holding", { suggestedReps: currentReps + 1 });
  return build("hold", "holding");
}

/**
 * Convenience composition of state detection and recommendation.
 * Returns null when there is no usable session history.
 */
export function analyzeProgression(
  byDay: Record<string, ProgressiveOverloadDay>,
  options: ProgressiveOverloadOptions,
): ProgressiveOverloadResult | null {
  const state = detectProgressionState(byDay, options);
  if (!state) return null;
  return { ...state, ...recommendOverload(state, options) };
}
