<script setup lang="ts">
import { ref } from "vue";
import { formatDurationFromTimestamps, formatWeight, getWeightUnit, formatPRValue, formatDateTime } from "../utils/formatters";
import { detectExerciseType, formatDurationSeconds, formatDistance } from "../utils/exerciseTypeDetector";
import WorkoutsViewToggle from "../components/WorkoutsViewToggle.vue";
import { useWorkoutsView, type TimeRange } from "../composables/useWorkoutsView";

const {
  store,
  userAccount,
  timeRange,
  loading,
  isError,
  errorMessage,
  pageItems,
  totalPages,
  hasMore,
  hasPrev,
  currentPage,
  nextPage,
  prevPage,
  firstPage,
  lastPage,
  workoutIndexAt,
  load,
  totalSets,
  bpmDisplay,
  caloriesDisplay,
  exercisePRs,
  getLocalizedPRType,
} = useWorkoutsView(9);

// Card-specific UI state
const expandedExercises = ref<Record<string, boolean>>({}); // exercise.id -> expanded

const formatDate = (timestamp: number) => formatDateTime(new Date(timestamp * 1000));
const exerciseHasPR = (exercise: any) => exercisePRs(exercise).length > 0;

const onChangeRange = (event: Event) => {
  timeRange.value = (event.target as HTMLSelectElement).value as TimeRange;
};

const toggleExercise = (exerciseId: string) => {
  // Create a new object to ensure reactivity
  expandedExercises.value = {
    ...expandedExercises.value,
    [exerciseId]: !expandedExercises.value[exerciseId],
  };
};
</script>

<!-- ===============================================================================  -->

<template>
  <div class="workouts">
    <!-- Header Section -->
    <div class="workouts-card-header">
      <div class="header-content">
        <div class="title-section">
          <h1>{{ $t('workouts.card.title') }}</h1>
          <p class="subtitle">{{ $t('workouts.card.subtitle') }}</p>
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

    <!-- Loading state -->
    <div v-if="loading" class="loading-container">
      <div class="loading-spinner"></div>
      <p>{{ $t('global.loadingSpinnerText') }}</p>
    </div>

    <!-- Error state -->
    <div v-else-if="isError" class="error-container">
      <p>{{ errorMessage }}</p>
      <button class="retry-btn" @click="load()">{{ $t('global.sw.retry') }}</button>
    </div>

    <div v-else>
      <!-- Top pagination -->
      <div class="pagination top">
        <div class="pagination-controls">
          <button @click="firstPage" :disabled="!hasPrev" class="pagination-btn">《 {{ $t('global.pagination.first') }}</button>
          <button @click="prevPage" :disabled="!hasPrev" class="pagination-btn">← {{ $t('global.pagination.previous') }}</button>
          <span class="page-info">{{ $t('global.pagination.indicator', { current: currentPage, total: totalPages }) }}</span>
          <button @click="nextPage" :disabled="!hasMore" class="pagination-btn">{{ $t('global.pagination.next') }} →</button>
          <button @click="lastPage" :disabled="!hasMore" class="pagination-btn">{{ $t('global.pagination.last') }} 》</button>
        </div>
        <div class="filters">
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
      </div>

      <div class="grid">
        <!--  Workout Cards  -->
        <div v-for="(workout, i) in pageItems" :key="workout.id" class="card">
          <!-- Workout Card Header  -->
          <div class="card-header">
            <div class="title-row">
              <span class="index-pill">#{{ workoutIndexAt(i) }}</span>
              <h2>{{ workout.title || workout.name || "Unnamed Workout" }}</h2>
            </div>
            <div class="header-meta">
              <span class="date">{{ formatDate(workout.start_time) }}</span>
              <span v-if="bpmDisplay(workout)" class="pill pill-red" title="Average Heart Rate">❤️ {{ bpmDisplay(workout) }}</span>
              <span v-if="caloriesDisplay(workout)" class="pill pill-orange" title="Total Calories">🔥 {{ caloriesDisplay(workout) }}</span>
            </div>
          </div>

          <!--  Middle Row with Stats  -->
          <div class="stats-row">
            <div class="stat"><strong>{{ formatWeight(workout.estimated_volume_kg || 0) }} {{ getWeightUnit() }}</strong><span>{{ $t('global.sw.volume') }}</span></div>
            <div class="stat"><strong>{{ formatDurationFromTimestamps(workout.start_time, workout.end_time) }}</strong><span>{{ $t('global.sw.duration') }}</span></div>
            <div class="stat"><strong>{{ workout.exercises?.length || 0 }}</strong><span>{{ $t('global.sw.exercises') }}</span></div>
            <div class="stat"><strong>{{ totalSets(workout) }}</strong><span>{{ $t('workouts.card.totalSets') }}</span></div>
          </div>

          <div v-if="workout.description" class="workout-description">
            <em>{{ workout.description }}</em>
          </div>

          <!--  Exercises List  -->
          <div class="exercises">
            <h3>{{ $t('global.sw.exercises') }}</h3>
            <div v-for="exercise in workout.exercises" :key="exercise.id" class="exercise" :class="{ 'pr-highlight': exerciseHasPR(exercise) }">
              <button class="exercise-toggle" @click="toggleExercise(exercise.id)">
                <span class="exercise-title">{{ exercise.title || "Unknown Exercise" }}</span>
                <span class="toggle-icon">{{ expandedExercises[exercise.id] ? "▾" : "▸" }}</span>
              </button>

              <div v-show="expandedExercises[exercise.id]" class="exercise-content">
                <div v-if="exerciseHasPR(exercise)" class="pr-summary">
                  <span v-for="(pr, i) in exercisePRs(exercise)" :key="i" class="pr-chip">{{ getLocalizedPRType(pr.type) }}: <strong>{{ formatPRValue(pr.type, pr.value) }}</strong></span>
                </div>
                <table class="sets-table">
                  <thead>
                    <tr>
                      <th>{{ $t('workouts.card.set') }}</th>
                      <!-- Dynamic headers based on exercise type -->
                      <template v-if="detectExerciseType(exercise) === 'cardio'">
                        <th>{{ $t('global.sw.distance') }}</th>
                        <th>{{ $t('global.sw.duration') }}</th>
                      </template>
                      <template v-else>
                        <th>{{ $t('global.sw.weight') }} ({{ getWeightUnit() }})</th>
                        <th>{{ $t('workouts.card.reps') }}</th>
                      </template>
                      <th>RPE</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="set in exercise.sets" :key="set.id">
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

                <div v-if="exercise.notes" class="exercise-notes">
                  <em>{{ $t('global.sw.notes') }}: {{ exercise.notes }}</em>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Bottom pagination -->
      <div class="pagination bottom">
        <div class="pagination-controls">
          <button @click="firstPage" :disabled="!hasPrev" class="pagination-btn">《 {{ $t('global.pagination.first') }}</button>
          <button @click="prevPage" :disabled="!hasPrev" class="pagination-btn">← {{ $t('global.pagination.previous') }}</button>
          <span class="page-info">{{ $t('global.pagination.indicator', { current: currentPage, total: totalPages }) }}</span>
          <button @click="nextPage" :disabled="!hasMore" class="pagination-btn">{{ $t('global.pagination.next') }} →</button>
          <button @click="lastPage" :disabled="!hasMore" class="pagination-btn">{{ $t('global.pagination.last') }} 》</button>
        </div>
        <div class="filters">
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
      </div>
    </div>
  
  </div>
</template>

<!-- ===============================================================================  -->

<style scoped>

.workouts {
  padding: 1.5rem 1.25rem;
  width: 100%;
  min-height: 100vh;
  background: var(--bg-primary);
}

/* Header Styles */
.workouts-card-header {
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

@media (max-width: 768px) {
  .user-badge {
    display: none;
  }
  
  .settings-btn {
    display: none;
  }
  
  .workouts-card-header {
    margin-bottom: 1rem;
    padding-bottom: 1rem;
  }
}

.filters { display: flex; align-items: center; gap: 0.75rem; }
.filter-label { color: var(--text-secondary); font-size: 0.9rem; }
.filter-select { background: var(--bg-card); color: var(--text-primary); border: 1px solid var(--border-color); border-radius: 8px; padding: 0.5rem 0.75rem; }

.loading-container { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 4rem; gap: 1rem; }
.loading-spinner { width: 48px; height: 48px; border: 4px solid color-mix(in srgb, var(--color-primary, #10b981) 25%, transparent); border-top-color: var(--color-primary, #10b981); border-radius: 50%; animation: spin 0.9s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
.loading-container p { color: var(--text-secondary); font-size: 1.1rem; }
.error-container { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 4rem; gap: 1rem; color: var(--text-secondary); }
.retry-btn { background: var(--bg-secondary); color: var(--text-primary); border: 1px solid var(--border-color); border-radius: 8px; padding: 0.5rem 0.875rem; cursor: pointer; }
.retry-btn:hover { border-color: var(--color-primary, #10b981); }

.grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1rem; }
.card { min-width: 0; display: flex; flex-direction: column; }
.card { background: var(--bg-card); padding: 1rem; border-radius: 12px; box-shadow: 0 4px 15px var(--shadow); border: 1px solid var(--border-color); transition: all 0.3s ease; }
.card:hover { transform: translateY(-2px); box-shadow: 0 8px 25px var(--shadow); border-color: var(--color-primary, #10b981); }

.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; padding-bottom: 0.75rem; border-bottom: 1px solid var(--border-color); }
.title-row { display: flex; align-items: center; gap: 0.5rem; }
.index-pill { display: inline-block; background: color-mix(in srgb, var(--color-primary, #10b981) 15%, transparent); color: var(--color-primary, #10b981); border: 1px solid color-mix(in srgb, var(--color-primary, #10b981) 30%, transparent); border-radius: 999px; padding: 0.15rem 0.5rem; font-size: 0.8rem; font-weight: 600; }
.card-header h2 { margin: 0; color: var(--text-primary); font-size: 1.125rem; font-weight: 600; }
.header-meta { display: flex; align-items: center; gap: 0.5rem; }
.date { color: var(--text-secondary); font-size: 0.85rem; }
.pill { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 999px; font-size: 0.8rem; font-weight: 600; border: 1px solid transparent; }
.pill-red { background: rgba(239, 68, 68, 0.15); color: #ef4444; border-color: rgba(239, 68, 68, 0.35); }
.pill-orange { background: rgba(245, 158, 11, 0.15); color: #f59e0b; border-color: rgba(245, 158, 11, 0.35); }
.pill-pr { background: rgba(245, 158, 11, 0.15); color: #f59e0b; border-color: rgba(245, 158, 11, 0.35); }

.stats-row { display: flex; gap: 1.25rem; margin-bottom: 1rem; }
.stat { display: flex; flex-direction: column; gap: 0.15rem; }
.stat strong { color: var(--text-primary); font-size: 1rem; }
.stat span { color: var(--text-secondary); font-size: 0.8rem; }

.workout-description { margin: 0.5rem 0 1rem; color: var(--text-secondary); }

.exercises h3 { margin: 0 0 0.5rem; color: var(--text-primary); font-size: 1rem; }
.exercise { border: 1px solid var(--border-color); border-radius: 8px; margin-bottom: 0.5rem; overflow: hidden; background: rgba(0, 0, 0, 0.2); }
.exercise-toggle { width: 100%; display: flex; align-items: center; justify-content: space-between; background: rgba(0, 0, 0, 0.3); color: var(--text-primary); border: none; padding: 0.6rem 0.75rem; cursor: pointer; transition: all 0.2s ease; }
.exercise-toggle:hover { background: rgba(0, 0, 0, 0.4); }
.exercise-title { font-weight: 600; font-size: 0.95rem; }
.toggle-icon { color: var(--text-secondary); }
.exercise-content { background: rgba(0, 0, 0, 0.15); padding: 0.75rem; }

.sets-table { width: 100%; border-collapse: collapse; }
.sets-table th, .sets-table td { padding: 0.5rem; border-bottom: 1px solid var(--border-color); text-align: left; color: var(--text-primary); }
.sets-table th { color: var(--text-secondary); font-weight: 500; }
.exercise-notes { padding: 0.5rem 0.75rem; color: var(--text-secondary); }

/* PR highlighting */
.pr-highlight { border: 2px solid #f59e0b; }
.pr-summary { display: flex; flex-wrap: wrap; gap: 0.5rem; margin: 0.5rem 0; padding: 0.25rem 0.5rem; }
.pr-chip { background: rgba(245, 158, 11, 0.22); color: #eedebc; border: 2px solid #f59e0b; border-radius: 999px; padding: 0.15rem 0.6rem; font-size: 0.85rem; font-weight: 600; box-shadow: 0 1px 3px rgba(0,0,0,0.15); margin: 2px; }

.pagination { grid-column: 1 / -1; display: flex; justify-content: space-between; align-items: center; gap: 1rem; margin-top: 1rem; flex-wrap: wrap; }
.pagination.top { margin-bottom: 1rem; }
.pagination.bottom { margin-top: 1rem; }
.pagination-controls { display: flex; justify-content: center; align-items: center; gap: 1rem; }
.pagination-btn { background: var(--bg-secondary); color: var(--text-primary); border: 1px solid var(--border-color); border-radius: 8px; padding: 0.5rem 0.875rem; cursor: pointer; }
.pagination-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.page-info { color: var(--text-secondary); }

/* Mobile Responsive */
@media (max-width: 1024px) { .grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 640px) {
  .workouts { padding: 1rem; }
  .header-row { flex-direction: column; align-items: flex-start; gap: 0.5rem; }
  .grid { grid-template-columns: 1fr; }
  .card { padding: 0.75rem; }
  .card-header { flex-direction: column; align-items: flex-start; gap: 0.5rem; }
  .stats-row { flex-wrap: wrap; gap: 0.75rem; }
  .stat strong { font-size: 0.95rem; }
  .sets-table { display: block; overflow-x: auto; width: 100%; }
  .sets-table table { min-width: 100%; width: 100%; }
  
  .pagination {
    flex-direction: column;
    gap: 0.75rem;
  }
  
  .pagination-controls {
    flex-wrap: wrap;
    justify-content: center;
    gap: 0.5rem;
  }
  
  .pagination-btn {
    padding: 0.375rem 0.625rem;
    font-size: 0.875rem;
  }
  
  .filter-select {
    font-size: 0.875rem;
  }
}
@media (max-width: 480px) {
  .workouts {
    padding: 1rem;
  }
  
  .title-section h1 {
    font-size: 1.625rem;
  }
  
  .user-badge {
    padding: 0.5rem 0.75rem;
  }
  
  .user-avatar {
    display: none;
  }
  
  .user-details span {
    display: none;
  }
}

</style>
