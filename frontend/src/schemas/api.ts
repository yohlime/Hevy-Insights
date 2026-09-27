import { z } from "zod";

const nullableStringSchema = z.string().nullable().optional();
const nullableNumberSchema = z.number().nullable().optional();
const timestampSchema = z.union([z.string(), z.number()]).nullable().optional();

export const loginResponseSchema = z.object({
  access_token: z.string(),
  user_id: z.string(),
  username: nullableStringSchema,
  email: nullableStringSchema,
  refresh_token: nullableStringSchema,
  expires_at: timestampSchema,
  session_id: nullableStringSchema,
}).catchall(z.unknown());

export const validateApiKeyResponseSchema = z.object({
  valid: z.boolean(),
  error: nullableStringSchema,
}).catchall(z.unknown());

export const authStatusResponseSchema = z.object({
  authenticated: z.boolean(),
  auth_mode: z.enum(["oauth2", "api_key", "csv"]).nullable(),
}).catchall(z.unknown());

export const userAccountSchema = z.object({
  id: z.union([z.string(), z.number()]).optional(),
  username: nullableStringSchema,
  name: nullableStringSchema,
  email: nullableStringSchema,
  url: nullableStringSchema,
  profile_pic: nullableStringSchema,
}).catchall(z.unknown());

const workoutSetSchema = z.object({
  index: nullableNumberSchema,
  type: nullableStringSchema,
  weight_kg: nullableNumberSchema,
  reps: nullableNumberSchema,
  distance_meters: nullableNumberSchema,
  duration_seconds: nullableNumberSchema,
  rpe: nullableNumberSchema,
  custom_metric: nullableNumberSchema,
}).catchall(z.unknown());

const workoutExerciseSchema = z.object({
  index: nullableNumberSchema,
  title: nullableStringSchema,
  notes: nullableStringSchema,
  exercise_template_id: nullableStringSchema,
  supersets_id: nullableNumberSchema,
  sets: z.array(workoutSetSchema).default([]),
}).catchall(z.unknown());

export const workoutSchema = z.object({
  id: z.union([z.string(), z.number()]),
  title: nullableStringSchema,
  name: nullableStringSchema,
  routine_id: nullableStringSchema,
  description: nullableStringSchema,
  start_time: timestampSchema,
  end_time: timestampSchema,
  updated_at: timestampSchema,
  created_at: timestampSchema,
  exercises: z.array(workoutExerciseSchema).default([]),
}).catchall(z.unknown());

export const workoutsResponseSchema = z.object({
  workouts: z.array(workoutSchema),
  page: nullableNumberSchema,
  page_count: nullableNumberSchema,
  page_size: nullableNumberSchema,
  total_count: nullableNumberSchema,
}).catchall(z.unknown());

export const bodyMeasurementSchema = z.object({
  id: z.union([z.string(), z.number()]).optional(),
  date: z.string(),
  weight_kg: z.number(),
  created_at: nullableStringSchema,
}).catchall(z.unknown());

export const bodyMeasurementsSchema = z.array(bodyMeasurementSchema);

export const bodyMeasurementResponseSchema = z.object({
  message: nullableStringSchema,
  success: z.boolean().optional(),
}).catchall(z.unknown());

export const routineFolderResponseSchema = z.object({
  id: z.number(),
  index: z.number(),
  title: z.string(),
  updated_at: z.string(),
  created_at: z.string(),
}).catchall(z.unknown());

export const routineFoldersResponseSchema = z.object({
  routine_folders: z.array(z.record(z.string(), z.unknown())).optional(),
}).catchall(z.unknown());

export const routineFolderMutationResponseSchema = z.object({
  folderId: nullableStringSchema,
  title: nullableStringSchema,
}).catchall(z.unknown());

export const routineResponseSchema = z.object({
  routineId: z.string(),
}).catchall(z.unknown());

export const routineMutationResponseSchema = z.object({
  routineId: nullableStringSchema,
}).catchall(z.unknown());

export const routineDetailResponseSchema = z.object({
  routine: z.record(z.string(), z.unknown()).nullable().optional(),
}).catchall(z.unknown());

export const versionCheckResponseSchema = z.object({
  current_version: nullableStringSchema,
  latest_version: nullableStringSchema,
  update_available: z.boolean(),
  release_url: nullableStringSchema,
  error: nullableStringSchema,
}).catchall(z.unknown());

export type LoginResponse = z.infer<typeof loginResponseSchema>;
export type ValidateApiKeyResponse = z.infer<typeof validateApiKeyResponseSchema>;
export type AuthStatusResponse = z.infer<typeof authStatusResponseSchema>;
export type UserAccount = z.infer<typeof userAccountSchema>;
export type WorkoutsResponse = z.infer<typeof workoutsResponseSchema>;
export type BodyMeasurement = z.infer<typeof bodyMeasurementSchema>;
export type RoutineFolderResponse = z.infer<typeof routineFolderResponseSchema>;
export type RoutineFoldersResponse = z.infer<typeof routineFoldersResponseSchema>;
export type RoutineFolderMutationResponse = z.infer<typeof routineFolderMutationResponseSchema>;
export type RoutineResponse = z.infer<typeof routineResponseSchema>;
export type RoutineMutationResponse = z.infer<typeof routineMutationResponseSchema>;
export type RoutineDetailResponse = z.infer<typeof routineDetailResponseSchema>;
export type VersionCheckResponse = z.infer<typeof versionCheckResponseSchema>;
