import { defineStore } from "pinia";

/**
 * User display/analysis preferences, persisted to localStorage.
 * Kept separate from server/session state so it can be read anywhere
 * (formatters, charts, views) without pulling in the data layer.
 */
export const usePreferences = defineStore("preferences", {
  state: () => ({
    weightUnit: (localStorage.getItem("weight_unit") || "kg") as "kg" | "lbs",
    plateauDetectionSessions: parseInt(localStorage.getItem("plateau_detection_sessions") || "5"),
    dateFormat: (localStorage.getItem("date_format") || "iso") as "iso" | "eu" | "us" | "uk",
    graphAxisFormat: (localStorage.getItem("graph_axis_format") || "short") as "numeric" | "short" | "long",
    userHeight: parseFloat(localStorage.getItem("user_height") || "0"),
  }),

  actions: {
    setWeightUnit(unit: "kg" | "lbs") {
      this.weightUnit = unit;
      localStorage.setItem("weight_unit", unit);
    },

    setPlateauDetectionSessions(sessions: number) {
      this.plateauDetectionSessions = sessions;
      localStorage.setItem("plateau_detection_sessions", sessions.toString());
    },

    setDateFormat(format: "iso" | "eu" | "us" | "uk") {
      this.dateFormat = format;
      localStorage.setItem("date_format", format);
    },

    setGraphAxisFormat(format: "numeric" | "short" | "long") {
      this.graphAxisFormat = format;
      localStorage.setItem("graph_axis_format", format);
    },

    setUserHeight(height: number) {
      this.userHeight = height;
      localStorage.setItem("user_height", height.toString());
    },
  },
});
