import axios from "axios";
import type { z } from "zod";
import {
  authStatusResponseSchema,
  bodyMeasurementResponseSchema,
  bodyMeasurementsSchema,
  loginResponseSchema,
  userAccountSchema,
  validateApiKeyResponseSchema,
  versionCheckResponseSchema,
  workoutsResponseSchema,
} from "../schemas/api";

// Use relative API in production (proxied by Nginx); localhost in dev
const API_BASE_URL = import.meta.env.PROD ? "/api" : "http://localhost:5000/api";

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
  withCredentials: true, // Enable sending cookies with requests
});

function parseApiResponse<T>(schema: z.ZodType<T>, data: unknown, endpoint: string): T {
  const result = schema.safeParse(data);
  if (!result.success) {
    console.error(`Invalid API response from ${endpoint}:`, result.error);
    throw result.error;
  }
  return result.data;
}

// ===============================================================================

// Authentication Service
export const authService = {
  async login(emailOrUsername: string, password: string): Promise<any> {
    // OAuth2 login with automatic reCAPTCHA token generation
    // Backend will set HttpOnly cookies automatically
    const response = await api.post("/login", {
      emailOrUsername,
      password,
    });
    return parseApiResponse(loginResponseSchema, response.data, "/login");
  },

  async validateApiKey(apiKey: string): Promise<any> {
    // Validate Hevy API key
    // Backend will set HttpOnly cookies if valid
    const response = await api.post("/validate_api_key", {
      api_key: apiKey,
    });
    return parseApiResponse(validateApiKeyResponseSchema, response.data, "/validate_api_key");
  },

  async logout() {
    // Call backend to clear authentication cookies
    try {
      await api.post("/logout");
    } catch (error) {
      console.error("Logout error:", error);
    }
  },

  async getAuthStatus(): Promise<any> {
    // Check authentication status from backend
    try {
      const response = await api.get("/auth/status");
      return parseApiResponse(authStatusResponseSchema, response.data, "/auth/status");
    } catch (error) {
      return {
        authenticated: false,
        auth_mode: null,
      };
    }
  },
};

// User Service
export const userService = {
  async getAccount(): Promise<any> {
    const response = await api.get("/user/account");
    return parseApiResponse(userAccountSchema, response.data, "/user/account");
  },
};

// Workout Service
export const workoutService = {
  async getWorkouts(username: string, offset: number = 0): Promise<any> {
    // Backend determines OAuth2 vs API key mode from cookies
    // Hevy API-key mode uses page-based pagination
    const page = Math.floor(offset / 10) + 1;
    const response = await api.get("/workouts", {
      params: { username, offset, page, page_size: 10 },
    });
    return parseApiResponse(workoutsResponseSchema, response.data, "/workouts");
  },
};

// Body Measurement Service
export const bodyMeasurementService = {
  async getMeasurements(): Promise<any[]> {
    const response = await api.get("/body_measurements");
    return parseApiResponse(bodyMeasurementsSchema, response.data, "/body_measurements");
  },

  async addMeasurement(data: { weight_kg: number; date: string }): Promise<any> {
    const response = await api.post("/body_measurements_batch", data);
    return parseApiResponse(bodyMeasurementResponseSchema, response.data, "/body_measurements_batch");
  },
};

// Version Service
export const versionService = {
  async checkForUpdates(): Promise<any> {
    try {
      const response = await api.get("/version/check");
      return parseApiResponse(versionCheckResponseSchema, response.data, "/version/check");
    } catch (error) {
      console.error("Failed to check for updates:", error);
      return {
        current_version: null,
        latest_version: null,
        update_available: false,
        error: "Failed to check for updates",
      };
    }
  },
};

export default api;
