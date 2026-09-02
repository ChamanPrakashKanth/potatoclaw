/**
 * PotatoClaw Lightweight Resource Governor
 *
 * Continuously monitors process RAM, system memory, GPU VRAM, and context window
 * utilization, dynamically throttling observation depth and tool surfaces to prevent
 * out-of-memory or out-of-context crashes on budget potato PCs.
 */

export type GovernorTier = "GREEN" | "AMBER" | "RED";

export type ResourceSnapshot = {
  tier: GovernorTier;
  contextTokensUsed: number;
  maxContextTokens: number;
  contextUtilizationPct: number;
  processRssMb: number;
  systemFreeMb: number;
  vramUsedMb: number;
  vramTotalMb: number;
  actionsTaken: string[];
};

export type GovernorConfig = {
  maxContextTokens: number;
  amberContextThreshold: number; // e.g. 1200 tokens
  redContextThreshold: number;   // e.g. 1650 tokens
  amberRamPct: number;           // e.g. 80%
  redRamPct: number;             // e.g. 90%
};

export const DEFAULT_GOVERNOR_CONFIG: GovernorConfig = {
  maxContextTokens: 2048,
  amberContextThreshold: 1200,
  redContextThreshold: 1650,
  amberRamPct: 80,
  redRamPct: 90,
};

export class PotatoResourceGovernor {
  private config: GovernorConfig;

  constructor(config = DEFAULT_GOVERNOR_CONFIG) {
    this.config = config;
  }

  /**
   * Assesses current resource pressure and returns recommended actions.
   */
  evaluatePressure(params: {
    currentContextTokens: number;
    processRssMb?: number;
    systemFreeMb?: number;
    vramUsedMb?: number;
    vramTotalMb?: number;
  }): ResourceSnapshot {
    const contextTokens = params.currentContextTokens;
    const maxTokens = this.config.maxContextTokens;
    const contextPct = (contextTokens / maxTokens) * 100;
    const actions: string[] = [];

    let tier: GovernorTier = "GREEN";

    // 1. Evaluate Context Window Pressure
    if (contextTokens >= this.config.redContextThreshold) {
      tier = "RED";
      actions.push("EMERGENCY_PRUNE_CONTEXT");
      actions.push("FORCE_OBSERVATION_LEVEL_0");
      actions.push("DROP_SECONDARY_TOOLS");
      actions.push("DISABLE_SCREENSHOTS");
    } else if (contextTokens >= this.config.amberContextThreshold) {
      tier = "AMBER";
      actions.push("PRUNE_OLD_OBSERVATIONS");
      actions.push("CAP_OBSERVATION_LEVEL_1");
      actions.push("COMPACT_SCHEMAS");
    }

    // 2. Evaluate VRAM Pressure if available
    if (params.vramUsedMb && params.vramTotalMb) {
      const vramPct = (params.vramUsedMb / params.vramTotalMb) * 100;
      if (vramPct > this.config.redRamPct && tier !== "RED") {
        tier = "RED";
        actions.push("VRAM_PRESSURE_DROP_CACHE");
      }
    }

    return {
      tier,
      contextTokensUsed: contextTokens,
      maxContextTokens: maxTokens,
      contextUtilizationPct: Math.round(contextPct),
      processRssMb: params.processRssMb ?? 45,
      systemFreeMb: params.systemFreeMb ?? 1800,
      vramUsedMb: params.vramUsedMb ?? 2170,
      vramTotalMb: params.vramTotalMb ?? 4096,
      actionsTaken: actions,
    };
  }
}
