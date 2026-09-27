import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { bodyMeasurementService } from "../services/api";

export const bodyMeasurementKeys = {
  all: ["body-measurements"] as const,
};

export interface BodyMeasurementInput {
  weight_kg: number;
  date: string;
}

/** Cached body-measurement history (shared across views, deduped by query key). */
export function useBodyMeasurementsQuery() {
  return useQuery({
    queryKey: bodyMeasurementKeys.all,
    queryFn: () => bodyMeasurementService.getMeasurements(),
  });
}

/** Add a measurement and refresh the cached history. */
export function useAddBodyMeasurementMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (measurement: BodyMeasurementInput) => bodyMeasurementService.addMeasurement(measurement),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: bodyMeasurementKeys.all }),
  });
}
