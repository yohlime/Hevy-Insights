<script setup lang="ts">
import { computed, watch } from "vue";
import { useRoute } from "vue-router";
import WorkoutsCard from "./Workouts_Card.vue";
import WorkoutsList from "./Workouts_List.vue";

const route = useRoute();

const viewMode = computed<"card" | "list">(() => {
  const queryView = route.query.view;
  if (queryView === "card" || queryView === "list") return queryView;
  return localStorage.getItem("workouts_view_mode") === "list" ? "list" : "card";
});

const currentView = computed(() => (viewMode.value === "list" ? WorkoutsList : WorkoutsCard));

watch(
  viewMode,
  (mode) => {
    localStorage.setItem("workouts_view_mode", mode);
  },
  { immediate: true },
);
</script>

<template>
  <component :is="currentView" />
</template>
