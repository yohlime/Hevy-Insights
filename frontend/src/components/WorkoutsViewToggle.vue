<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";

const route = useRoute();
const router = useRouter();

type ViewMode = "card" | "list";

const current = computed<ViewMode>(() => {
  const queryView = route.query.view;
  if (queryView === "card" || queryView === "list") return queryView;
  return localStorage.getItem("workouts_view_mode") === "list" ? "list" : "card";
});

function setView(view: ViewMode) {
  localStorage.setItem("workouts_view_mode", view);
  if (route.path !== "/workouts" || route.query.view !== view) {
    router.replace({ path: "/workouts", query: { ...route.query, view } });
  }
}
</script>

<template>
  <div class="view-mode-toggle" role="group" :aria-label="$t('workouts.view.label')">
    <button
      type="button"
      class="view-mode-btn"
      :class="{ active: current === 'card' }"
      :title="$t('workouts.view.card')"
      :aria-pressed="current === 'card'"
      @click="setView('card')"
    >
      <span class="view-mode-icon">▦</span>
      <span class="view-mode-label">{{ $t("workouts.view.card") }}</span>
    </button>
    <button
      type="button"
      class="view-mode-btn"
      :class="{ active: current === 'list' }"
      :title="$t('workouts.view.list')"
      :aria-pressed="current === 'list'"
      @click="setView('list')"
    >
      <span class="view-mode-icon">☰</span>
      <span class="view-mode-label">{{ $t("workouts.view.list") }}</span>
    </button>
  </div>
</template>

<style scoped>
.view-mode-toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.25rem;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background: var(--bg-card);
}
.view-mode-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.4rem 0.7rem;
  border: none;
  border-radius: 7px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}
.view-mode-btn:hover {
  color: var(--text-primary);
}
.view-mode-btn.active {
  background: var(--color-primary, #10b981);
  color: #fff;
}
.view-mode-icon {
  font-size: 0.9rem;
  line-height: 1;
}
@media (max-width: 480px) {
  .view-mode-label {
    display: none;
  }
}
</style>
