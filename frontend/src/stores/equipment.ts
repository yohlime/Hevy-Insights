import { defineStore } from "pinia";

// Equipment/Vendor configuration for exercise variants
export interface EquipmentConfig {
  id: string; // Unique identifier
  exerciseTitle: string;
  equipmentName: string;
  searchKeyword: string;
  imageUrl?: string;
}

function loadEquipmentConfigs(): EquipmentConfig[] {
  try {
    const stored = localStorage.getItem("exercise_equipment_configs");
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

/** Per-exercise vendor/equipment variants, persisted to localStorage. */
export const useEquipment = defineStore("equipment", {
  state: () => ({
    equipmentConfigs: loadEquipmentConfigs() as EquipmentConfig[],
  }),

  actions: {
    addEquipmentConfig(config: Omit<EquipmentConfig, "id">) {
      const newConfig: EquipmentConfig = {
        ...config,
        id: `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
      };
      this.equipmentConfigs.push(newConfig);
      localStorage.setItem("exercise_equipment_configs", JSON.stringify(this.equipmentConfigs));
    },

    updateEquipmentConfig(id: string, updates: Partial<Omit<EquipmentConfig, "id">>) {
      const index = this.equipmentConfigs.findIndex((c) => c.id === id);
      if (index !== -1) {
        const currentConfig = this.equipmentConfigs[index];
        if (!currentConfig) return;
        this.equipmentConfigs[index] = { ...currentConfig, ...updates };
        localStorage.setItem("exercise_equipment_configs", JSON.stringify(this.equipmentConfigs));
      }
    },

    deleteEquipmentConfig(id: string) {
      this.equipmentConfigs = this.equipmentConfigs.filter((c) => c.id !== id);
      localStorage.setItem("exercise_equipment_configs", JSON.stringify(this.equipmentConfigs));
    },

    getEquipmentConfigsForExercise(exerciseTitle: string): EquipmentConfig[] {
      return this.equipmentConfigs.filter((c) => c.exerciseTitle.toLowerCase() === exerciseTitle.toLowerCase());
    },
  },
});
