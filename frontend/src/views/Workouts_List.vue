<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from "vue";
import { useRoute } from "vue-router";
import { formatDurationFromTimestamps, formatWeight, getWeightUnit, formatPRValue, formatDateTime } from "../utils/formatters";
import { detectExerciseType, formatDurationSeconds, formatDistance } from "../utils/exerciseTypeDetector";
import WorkoutsViewToggle from "../components/WorkoutsViewToggle.vue";
import { useWorkoutsView, type TimeRange } from "../composables/useWorkoutsView";

const route = useRoute();
const initialDay = typeof route.query.day === "string" ? route.query.day : undefined;

const {
  store,
  userAccount,
  t,
  timeRange,
  searchName,
  pageItems,
  totalCount,
  hasMore,
  loading,
  isFetchingMore,
  loadMore,
  workoutIndexAt,
  goToWorkoutNumber,
  setDayFilter,
  clearDayFilter,
  isDayFiltered,
  totalSets,
  bpmDisplay,
  caloriesDisplay,
  extractSetPRs,
  exercisePRs,
  getLocalizedPRType,
} = useWorkoutsView(20, { infinite: true, initialDay });

// List-specific UI state
const expanded = ref<Record<string, boolean>>({});
const workoutNumberInput = ref<number | null>(null);
const sentinel = ref<HTMLElement | null>(null);
let observer: IntersectionObserver | null = null;

// Debounced workout name search (applied server-side)
let workoutNameDebounceTimeout: ReturnType<typeof setTimeout> | null = null;

function handleWorkoutNameInput(event: Event) {
  const value = (event.target as HTMLInputElement).value;

  // Clear existing timeout
  if (workoutNameDebounceTimeout) {
    clearTimeout(workoutNameDebounceTimeout);
  }

  // Only update the query after 300ms of no typing
  workoutNameDebounceTimeout = setTimeout(() => {
    searchName.value = value;
  }, 300);
}

function jumpToWorkoutNumber() {
  goToWorkoutNumber(workoutNumberInput.value);
}

const onChangeRange = (event: Event) => {
  timeRange.value = (event.target as HTMLSelectElement).value as TimeRange;
};

// Helpers
const formatDateFull = (timestamp: number) => {
  const d = new Date(timestamp * 1000);
  const days = [t("global.days.sundayLong"), t("global.days.mondayLong"), t("global.days.tuesdayLong"), t("global.days.wednesdayLong"), t("global.days.thursdayLong"), t("global.days.fridayLong"), t("global.days.saturdayLong")];
  const dayName = days[d.getDay()];

  // Use the shared formatDateTime utility, but extract date and time separately to insert day name
  const formattedDateTime = formatDateTime(d);

  return `${dayName}, ${formattedDateTime}`;
};

const setHasPR = (set: any) => extractSetPRs(set).length > 0;
const workoutPRCount = (workout: any) => {
  let count = 0;
  for (const ex of (workout.exercises || [])) {
    for (const s of (ex.sets || [])) count += extractSetPRs(s).length;
  }
  return count;
};

const toggleItem = (id: string) => { expanded.value[id] = !expanded.value[id]; };

onMounted(() => {
  // Infinite scroll: load the next page as the sentinel enters the viewport.
  observer = new IntersectionObserver(
    (entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        loadMore();
      }
    },
    { rootMargin: "300px" },
  );
  if (sentinel.value) observer.observe(sentinel.value);
});

onBeforeUnmount(() => {
  observer?.disconnect();
  observer = null;
});

watch(() => route.query.day, (d) => {
  if (typeof d === "string") setDayFilter(d);
});

// When viewing a single day (Dashboard deep link), expand its workouts.
watch(pageItems, (items) => {
  if (isDayFiltered.value) {
    for (const w of items as any[]) expanded.value[w.id] = true;
  }
});
</script>

<!-- ===============================================================================  -->

<template>
  <div class="workouts-list">
    <!-- Header Section -->
    <div class="workouts-list-header">
      <div class="header-content">
        <div class="title-section">
          <h1>{{ $t('workouts.list.title') }}</h1>
          <p class="subtitle">{{ $t('workouts.list.subtitle') }}</p>
        </div>

        <div class="header-actions">
          <!-- Card / List view toggle -->
          <WorkoutsViewToggle />

          <!-- Settings Button -->
          <button @click="$router.push('/settings')" class="settings-btn" title="Settings">
            ⚙️
          </button>
          
          <!-- User Badge -->
          <div v-if="userAccount" class="user-badge" @click="$router.push('/profile')" title="View Profile">
            <div class="user-avatar">{{ store.userInitial }}</div>
            <div class="user-details">
              <strong>{{ store.userDisplayName }}</strong>
              <span v-if="store.userEmail">{{ store.userEmail }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Top filters (time range, workout number, name) -->
    <div v-if="!loading || pageItems.length" class="top-filters">
      <div class="filter-group">
        <label class="filter-label">{{ $t('global.timeRangeFilter.timeRange') }}</label>
        <select class="filter-select" :value="timeRange" @change="onChangeRange">
          <option value="all">{{ $t('global.timeRangeFilter.allTime') }}</option>
          <option value="1w">{{ $t('global.timeRangeFilter.lastWeek') }}</option>
          <option value="1m">{{ $t('global.timeRangeFilter.lastMonth') }}</option>
          <option value="3m">{{ $t('global.timeRangeFilter.last3Months') }}</option>
          <option value="6m">{{ $t('global.timeRangeFilter.last6Months') }}</option>
          <option value="12m">{{ $t('global.timeRangeFilter.last12Months') }}</option>
        </select>
      </div>
      <div class="filter-group">
        <label class="filter-label">{{ $t('global.searchFilter.byNumber') }}</label>
        <input class="filter-input" type="number" min="1" placeholder="#" v-model.number="workoutNumberInput" @change="jumpToWorkoutNumber" @keyup.enter="jumpToWorkoutNumber" />
      </div>
      <div class="filter-group">
        <label class="filter-label">{{ $t('global.searchFilter.byName') }}</label>
        <input 
          class="filter-input" 
          type="text" 
          :placeholder="$t('workouts.list.searchContains')" 
          @input="handleWorkoutNameInput"
        />
      </div>

      <div v-if="isDayFiltered" class="day-filter-banner">
        <span>{{ $t('workouts.list.dayFilter') }}</span>
        <button type="button" class="day-filter-clear" @click="clearDayFilter">✕</button>
      </div>
    </div>

    <!-- Infinite scroll count -->
    <div v-if="pageItems.length" class="list-count">
      {{ $t('workouts.list.showingCount', { shown: pageItems.length, total: totalCount }) }}
    </div>

    <!-- Loading state -->
    <div v-if="loading && pageItems.length === 0" class="loading-container">
      <div class="loading-spinner"></div>
      <p>{{ $t('global.loadingSpinnerText') }}</p>
    </div>

    <div v-else class="list">
      <div v-for="(workout, i) in pageItems" :key="workout.id" class="item" :data-workout-index="workoutIndexAt(i)" :data-day="(() => { const d = new Date(workout.start_time * 1000); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; })()">
        <!-- Collapsed line -->
        <button class="item-toggle" @click="toggleItem(workout.id)">
          <div class="line">
            <span class="pill pill-green">#{{ workoutIndexAt(i) }}</span>
            <span class="line-date">{{ formatDateFull(workout.start_time) }}</span>
            <span class="line-sep">•</span>
            <span class="line-name">{{ workout.title || workout.name || "Unnamed" }}</span>
            <span v-if="bpmDisplay(workout)" class="pill pill-red">❤️ {{ bpmDisplay(workout) }}</span>
            <span v-if="caloriesDisplay(workout)" class="pill pill-orange">🔥 {{ caloriesDisplay(workout) }}</span>
            <span v-if="workoutPRCount(workout) > 0" class="pill pill-gold" title="Personal Records">🏆 {{ workoutPRCount(workout) }}</span>
          </div>
          <span class="toggle-icon">{{ expanded[workout.id] ? "▾" : "▸" }}</span>
        </button>

        <!-- Expanded details -->
        <Transition name="item-expand">
        <div v-if="expanded[workout.id]" class="details">
          <!-- Media + Stats row -->
          <div class="row">
            <div class="media" v-if="(workout.media || []).length">
              <div class="media-grid">
                <template v-for="m in workout.media" :key="m.id || m.url">
                  <img v-if="m.type && m.type.includes('image')" :src="m.url" alt="Workout image" />
                  <video v-else-if="m.type && m.type.includes('video')" :src="m.url" controls></video>
                  <img v-else :src="m.url" alt="Workout media" />
                </template>
              </div>
            </div>
            <div class="stats">
              <div class="stat"><strong>{{ formatWeight(workout.estimated_volume_kg || 0) }} {{ getWeightUnit() }}</strong><span>{{ $t('global.sw.volume') }}</span></div>
              <div class="stat"><strong>{{ formatDurationFromTimestamps(workout.start_time, workout.end_time) }}</strong><span>{{ $t('global.sw.duration') }}</span></div>
              <div class="stat"><strong>{{ workout.exercises?.length || 0 }}</strong><span>{{ $t('global.sw.exercises') }}</span></div>
              <div class="stat"><strong>{{ totalSets(workout) }}</strong><span>Sets</span></div>
              <div class="stat" v-if="workout.description"><strong>{{ workout.description }}</strong><span>{{ $t('global.sw.description') }}</span></div>
            </div>
          </div>

          <!-- Exercises list with thumbnails -->
          <div class="exercises">
            <h3>{{ $t('global.sw.exercises') }}</h3>
            <div class="exercise-grid">
              <div v-for="(exercise, exIdx) in workout.exercises" :key="exercise.id" class="exercise">
                <div class="exercise-header">
                  <span class="pill pill-blue">#{{ (+exIdx) + 1 }}</span>
                  <img v-if="exercise.thumbnail_url" :src="exercise.thumbnail_url" class="thumb" alt="Exercise thumbnail" />
                  <div class="exercise-title">{{ exercise.title || "Unknown Exercise" }}</div>
                </div>
              <div v-if="exercisePRs(exercise).length" class="pr-summary">
                <span v-for="(pr, i) in exercisePRs(exercise)" :key="i" class="pr-chip">{{ getLocalizedPRType(pr.type) }}: <strong>{{ formatPRValue(pr.type, pr.value) }}</strong></span>
              </div>
              <table class="sets-table">
                <thead>
                  <tr>
                    <th>{{ $t('workouts.list.set') }}</th>
                    <!-- Dynamic headers based on exercise type -->
                    <template v-if="detectExerciseType(exercise) === 'cardio'">
                      <th>{{ $t('global.sw.distance') }}</th>
                      <th>{{ $t('global.sw.duration') }}</th>
                    </template>
                    <template v-else>
                      <th>{{ $t('global.sw.weight') }} ({{ getWeightUnit() }})</th>
                      <th>{{ $t('workouts.list.reps') }}</th>
                    </template>
                    <th>RPE</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="set in exercise.sets" :key="set.id" :class="{ 'set-pr-highlight': setHasPR(set) }">
                    <td>{{ set.index + 1 }}</td>
                    <!-- Dynamic data based on exercise type -->
                    <template v-if="detectExerciseType(exercise) === 'cardio'">
                      <td>{{ formatDistance(set.distance_km) }}</td>
                      <td>{{ formatDurationSeconds(set.duration_seconds) }}</td>
                    </template>
                    <template v-else>
                      <td>{{ set.weight_kg ? formatWeight(set.weight_kg) : "-" }}</td>
                      <td>{{ set.reps || "-" }}</td>
                    </template>
                    <td>{{ set.rpe || "-" }}</td>
                  </tr>
                </tbody>
              </table>
              <div v-if="exercise.notes" class="exercise-notes"><em>{{ $t('global.sw.notes') }}: {{ exercise.notes }}</em></div>
              </div>
            </div>
          </div>
        </div>
        </Transition>
      </div>
    </div>

    <!-- Infinite scroll sentinel -->
    <div ref="sentinel" class="scroll-sentinel" aria-hidden="true"></div>
    <div v-if="isFetchingMore" class="loading-more">
      <div class="loading-spinner"></div>
    </div>
    <div v-else-if="!hasMore && pageItems.length" class="end-of-list">
      {{ $t('workouts.list.endOfList') }}
    </div>
  </div>
</template>

<!-- ===============================================================================  -->

<style scoped>
  .workouts-list {
    padding: 1.5rem 1.25rem;
    width: 100%;
    min-height: 100vh;
    background: var(--bg-primary);
  }

  /* Header Styles */
  .workouts-list-header {
    margin-bottom: 1.5rem;
    padding-bottom: 1.5rem;
    border-bottom: 1px solid var(--border-color);
  }

  .header-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 1.5rem;
  }

  .title-section h1 {
    margin: 0;
    color: var(--text-primary);
    font-size: 2rem;
    font-weight: 700;
    letter-spacing: -0.5px;
    background: linear-gradient(135deg, var(--color-primary, #10b981), var(--color-secondary, #06b6d4));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  .subtitle {
    margin: 0.5rem 0 0;
    color: var(--text-secondary);
    font-size: 1rem;
    font-weight: 400;
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .settings-btn {
    width: 48px;
    height: 48px;
    border-radius: 12px;
    border: 1px solid var(--border-color);
    background: var(--bg-card);
    backdrop-filter: blur(8px);
    color: var(--text-secondary);
    font-size: 1.5rem;
    cursor: pointer;
    transition: all 0.3s ease;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .settings-btn:hover {
    border-color: var(--color-primary, #10b981);
    color: var(--color-primary, #10b981);
    transform: translateY(-2px);
    box-shadow: 0 4px 16px color-mix(in srgb, var(--color-primary, #10b981) 30%, transparent);
  }

  .user-badge {
    display: flex;
    align-items: center;
    gap: 1rem;
    background: var(--bg-card);
    backdrop-filter: blur(8px);
    padding: 0.75rem 1.25rem;
    border-radius: 50px;
    border: 1px solid var(--border-color);
    transition: all 0.3s ease;
    cursor: pointer;
  }

  .user-badge:hover {
    border-color: var(--color-primary, #10b981);
    box-shadow: 0 4px 16px color-mix(in srgb, var(--color-primary, #10b981) 30%, transparent);
    transform: translateY(-2px);
  }

  .user-avatar {
    width: 42px;
    height: 42px;
    border-radius: 50%;
    background: linear-gradient(135deg, var(--color-primary, #10b981), var(--color-secondary, #06b6d4));
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-weight: 700;
    font-size: 1.125rem;
    text-transform: uppercase;
    box-shadow: 0 2px 8px rgba(16, 185, 129, 0.3);
  }

  .user-details {
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
  }

  .user-details strong {
    font-size: 0.95rem;
    color: var(--text-primary);
    font-weight: 600;
  }

  .user-details span {
    font-size: 0.8rem;
    color: var(--text-secondary);
  }

  .filters { display: flex; align-items: center; gap: 0.75rem; }
  .filter-label { color: var(--text-secondary); font-size: 0.9rem; }
  .filter-select { background: var(--bg-card); color: var(--text-primary); border: 1px solid var(--border-color); border-radius: 8px; padding: 0.5rem 0.75rem; }
  .filter-input { background: var(--bg-card); color: var(--text-primary); border: 1px solid var(--border-color); border-radius: 8px; padding: 0.5rem 0.75rem; width: 120px; }
  
  @media (max-width: 768px) {
    .user-badge {
      display: none;
    }
    
    .settings-btn {
      display: none;
    }
    
    .workouts-list-header {
      margin-bottom: 1rem;
      padding-bottom: 1rem;
    }
    
    .header-content {
      gap: 0rem;
    }
  }

  /* Contribution graph */
  .contrib-graph { margin-bottom: 1.5rem; }
  .contrib-graph .graph-and-filters { display: flex; align-items: flex-start; gap: 1rem; }
  .contrib-graph .graph-area { display: inline-block; }
  .contrib-graph .month-row { display: flex; gap: 3px; margin-bottom: 4px; }
  .contrib-graph .month-label { display: inline-block; width: 12px; font-size: 0.7rem; color: var(--text-secondary); text-align: center; }
  .contrib-graph .grid { display: flex; gap: 6px; align-items: flex-start; width: auto; }
  .contrib-graph .weekday-col { display: flex; flex-direction: column; gap: 3px; }
  .contrib-graph .weekday { width: 28px; font-size: 0.7rem; color: var(--text-secondary); text-align: right; line-height: 12px; }
  .contrib-graph .weeks-wrap { display: flex; gap: 3px; }
  .contrib-graph .week-col { display: flex; flex-direction: column; gap: 3px; }
  .contrib-graph .cell { width: 12px; height: 12px; border-radius: 2px; cursor: pointer; border: 1px solid var(--border-color); }


  .loading-container { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 4rem; gap: 1rem; }
  .loading-spinner { width: 48px; height: 48px; border: 4px solid color-mix(in srgb, var(--color-primary, #10b981) 25%, transparent); border-top-color: var(--color-primary, #10b981); border-radius: 50%; animation: spin 0.9s linear infinite; }
  @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
  .loading-container p { color: var(--text-secondary); font-size: 1.1rem; }

  .list { display: flex; flex-direction: column; gap: 0.75rem; }
  .item { border: 1px solid var(--border-color); border-radius: 10px; background: var(--bg-card); overflow: hidden; transition: all 0.3s ease; }
  .item:hover { transform: translateY(-2px); box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2); border-color: var(--color-primary, #10b981); }
  .item-toggle { width: 100%; display: flex; align-items: center; justify-content: space-between; background: var(--bg-secondary); color: var(--text-primary); border: none; padding: 0.75rem 1rem; cursor: pointer; transition: all 0.2s ease; }
  .item-toggle:hover { background: rgba(30, 41, 59, 0.8); }
  .item .line { display: flex; align-items: center; flex-wrap: wrap; gap: 0.4rem; }
  .line-date { color: var(--text-secondary); font-weight: 600; }
  .line-name { color: var(--text-primary); font-weight: 700; }
  .line-sep { color: var(--text-secondary); }
  .pill { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 999px; font-size: 0.8rem; font-weight: 600; border: 1px solid transparent; }
  .pill-red { background: rgba(239, 68, 68, 0.15); color: #ef4444; border-color: rgba(239, 68, 68, 0.35); }
  .pill-orange { background: rgba(245, 158, 11, 0.15); color: #f59e0b; border-color: rgba(245, 158, 11, 0.35); }
  .pill-green { background: color-mix(in srgb, var(--color-primary, #10b981) 15%, transparent); color: var(--color-primary, #10b981); border-color: color-mix(in srgb, var(--color-primary, #10b981) 35%, transparent); }
  .pill-blue { background: rgba(59,130,246,0.15); color: #3b82f6; border-color: rgba(59,130,246,0.35); }
  .pill-gold { background: rgba(201, 187, 0, 0.205); color: #eeea05; border-color: rgba(253, 228, 3, 0.35); }
  .toggle-icon { color: var(--text-secondary); margin-left: 0.5rem; }

  /* Top filters */
  .list-count { color: var(--text-secondary); font-size: 0.85rem; margin-bottom: 0.75rem; }
  .scroll-sentinel { height: 1px; }
  .loading-more { display: flex; justify-content: center; padding: 1.25rem; }
  .end-of-list { text-align: center; color: var(--text-secondary); font-size: 0.85rem; padding: 1.25rem; }
  .day-filter-banner { display: flex; align-items: center; gap: 0.5rem; margin: 0 0 1rem; padding: 0.5rem 0.75rem; border-radius: 8px; background: rgba(59, 130, 246, 0.12); color: #60a5fa; font-size: 0.85rem; }
  .day-filter-clear { background: transparent; border: none; color: inherit; cursor: pointer; font-size: 0.9rem; }
  .top-filters { display: flex; gap: 1rem; align-items: center; margin-bottom: 1rem; flex-wrap: wrap; }
  .top-filters .filter-group { display: flex; flex-direction: column; gap: 0.25rem; }
  .filter-label { color: var(--text-secondary); font-size: 0.8rem; font-weight: 600; }
  .filter-select, .filter-input { padding: 0.45rem 0.6rem; border-radius: 8px; background: var(--bg-card); border: 1px solid var(--border-color); color: var(--text-primary); }
  .filter-select { min-width: 160px; }

  .details { padding: 1rem; }

  /* Item expand/collapse transition */
  .item-expand-enter-active,
  .item-expand-leave-active {
    transition: opacity 0.15s ease-out, transform 0.15s ease-out;
    transform-origin: top;
  }

  .item-expand-enter-from,
  .item-expand-leave-to {
    opacity: 0;
    transform: scaleY(0.95);
  }

  .row { display: grid; grid-template-columns: 240px 1fr; gap: 1rem; align-items: start; }
  .media-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.5rem; }
  .media-grid img, .media-grid video { width: 100%; height: auto; border-radius: 8px; border: 1px solid var(--border-color); }

  .stats { display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: 0.75rem; }
  .stat { display: flex; flex-direction: column; gap: 0.15rem; }
  .stat strong { color: var(--text-primary); font-size: 1rem; }
  .stat span { color: var(--text-secondary); font-size: 0.8rem; }

  .exercises h3 { margin: 1rem 0 0.5rem; color: var(--text-primary); font-size: 1rem; }
  .exercise { border: 1px solid var(--border-color); border-radius: 8px; margin-bottom: 0.5rem; overflow: hidden; background: rgba(0, 0, 0, 0.2); }
  .exercise-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.75rem; }
  .exercise-header { display: flex; align-items: center; gap: 0.5rem; background: rgba(0, 0, 0, 0.3); padding: 0.6rem 0.75rem; transition: all 0.2s ease; }
  .exercise-header:hover { background: rgba(0, 0, 0, 0.4); }
  .exercise-header .thumb { width: 48px; height: 48px; object-fit: cover; border-radius: 6px; border: 1px solid var(--border-color); }
  .exercise-title { font-weight: 600; font-size: 0.95rem; }
  .sets-table { width: 100%; border-collapse: collapse; }
  .sets-table th, .sets-table td { padding: 0.5rem; border-bottom: 1px solid var(--border-color); text-align: left; color: var(--text-primary); }
  .sets-table th { color: var(--text-secondary); font-weight: 500; }
  .exercise-notes { padding: 0.5rem 0.75rem; color: var(--text-secondary); }

  /* PR styling for list view */
  .set-pr-highlight { border-left: 5px solid #f59e0b; }
  .pr-summary { display: flex; flex-wrap: wrap; gap: 0.5rem; margin: 0.5rem 0; padding: 0.25rem 0.5rem; }
  .pr-chip { background: rgba(245, 158, 11, 0.22); color: #eedebc; border: 2px solid #f59e0b; border-radius: 999px; padding: 0.15rem 0.6rem; font-size: 0.85rem; font-weight: 600; box-shadow: 0 1px 3px rgba(0,0,0,0.15); margin: 2px; }

  @media (max-width: 900px) {
    .row { grid-template-columns: 1fr; }
    .stats { grid-template-columns: repeat(2, minmax(120px, 1fr)); }
  }

  /* Mobile Responsive */
  @media (max-width: 640px) {
    /* Hide contribution graph entirely on mobile */
    .graph-area { display: none !important; }

    .workouts-list { padding: 1rem; }
    .header-row { flex-direction: column; align-items: flex-start; gap: 0.5rem; }
    .filters { flex-wrap: wrap; }
    .contrib-graph .grid { flex-direction: column; gap: 8px; }
    .contrib-graph .weekday-col { flex-direction: row; gap: 6px; }
    .contrib-graph .weekday { width: auto; text-align: left; }
    .weeks-wrap { overflow-x: auto; padding-bottom: 4px; }
    .details { padding: 0.75rem; }
    .media-grid { grid-template-columns: 1fr; }
    .stats { grid-template-columns: repeat(2, minmax(120px, 1fr)); }
    .exercise-grid { grid-template-columns: 1fr; }
    .exercise-header { flex-wrap: wrap; }
    .sets-table { display: block; overflow-x: auto; width: 100%; }
    .sets-table table { min-width: 100%; width: 100%; }
  }

@media (max-width: 480px) {
  .title-section h1 {
    font-size: 1.625rem;
  }
}
</style>
