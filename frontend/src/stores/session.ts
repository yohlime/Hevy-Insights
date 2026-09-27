import { defineStore } from "pinia";
import { userService } from "../services/api";

export interface UserAccount {
  id?: string | number;
  username?: string | null;
  name?: string | null;
  email?: string | null;
  url?: string | null;
  [key: string]: any;
}

export interface Workout {
  id: string;
  [key: string]: any;
}

/**
 * Session state: the authenticated user and the local CSV data source.
 * Server data (workouts, body measurements, routine targets) lives in
 * TanStack Query composables, not here.
 */
export const useSession = defineStore("session", {
  state: () => ({
    userAccount: null as UserAccount | null,
    isLoadingUser: false,
    dataSource: (localStorage.getItem("data_source") || "api") as "api" | "csv",
    csvWorkouts: [] as Workout[],
  }),

  getters: {
    username: (state) => {
      if (state.dataSource === "csv") {
        return "CSV User";
      }
      return state.userAccount?.username || state.userAccount?.name || null;
    },
    userDisplayName: (state) => {
      if (state.dataSource === "csv") {
        return "CSV User";
      }
      return state.userAccount?.username || state.userAccount?.name || "User";
    },
    userInitial: (state) => {
      const name = state.dataSource === "csv"
        ? "CSV User"
        : state.userAccount?.username || state.userAccount?.name || "User";
      return name.charAt(0).toUpperCase();
    },
    userEmail: (state) => state.userAccount?.email || "",
    isCSVMode: (state) => state.dataSource === "csv",
  },

  actions: {
    async fetchUserAccount(force = false) {
      // In CSV mode, create a mock user account
      if (this.dataSource === "csv") {
        if (!this.userAccount || force) {
          this.userAccount = {
            username: "CSV User",
            email: "csv@import.local",
          };
        }
        return this.userAccount;
      }

      if (this.userAccount && !force) return this.userAccount;

      this.isLoadingUser = true;
      try {
        this.userAccount = await userService.getAccount();
        return this.userAccount;
      } finally {
        this.isLoadingUser = false;
      }
    },

    // CSV workouts are stored in localStorage; load them on demand.
    ensureCsvLoaded(): Workout[] {
      if (this.dataSource !== "csv" || this.csvWorkouts.length > 0) return this.csvWorkouts;

      const csvData = localStorage.getItem("csv_workouts");
      if (csvData) {
        try {
          this.csvWorkouts = JSON.parse(csvData);
        } catch (error) {
          console.error("Failed to parse CSV workouts from localStorage", error);
          this.csvWorkouts = [];
        }
      }
      return this.csvWorkouts;
    },

    loadCSVWorkouts(workouts: Workout[]) {
      this.dataSource = "csv";
      this.csvWorkouts = workouts;
      localStorage.setItem("data_source", "csv");
      localStorage.setItem("csv_workouts", JSON.stringify(workouts));
    },

    switchToAPIMode() {
      this.dataSource = "api";
      this.csvWorkouts = [];
      localStorage.setItem("data_source", "api");
      localStorage.removeItem("csv_workouts");
    },

    logout() {
      this.userAccount = null;
      this.csvWorkouts = [];
      this.dataSource = "api";
      localStorage.removeItem("data_source");
      localStorage.removeItem("csv_workouts");
    },
  },
});
