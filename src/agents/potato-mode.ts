/**
 * Potato Mode configuration, detection, and threshold management for PotatoClaw.
 *
 * Optimizes OpenClaw for small local models (3B-4B) and low-memory hardware (4GB VRAM, 8GB RAM).
 */
import type { OpenClawConfig } from "../config/types.openclaw.js";
import { normalizeAgentId, parseAgentSessionKey } from "../routing/session-key.js";
import { resolveAgentConfig } from "./agent-scope-config.js";
import { resolveSessionAgentIds } from "./agent-scope.js";

export const CONTEXT_WINDOW_HARD_MIN_TOKENS_POTATO = 1024;
export const CONTEXT_WINDOW_WARN_BELOW_TOKENS_POTATO = 2048;

export type PotatoModeConfig = {
  enabled?: boolean;
  maxToolOutputChars?: number;
  maxShellLines?: number;
  maxBrowserTextChars?: number;
  maxBrowserSnapshotChars?: number;
  dynamicTools?: boolean;
  compactSchemas?: boolean;
  compactSystemPrompt?: boolean;
  contextBudget?: number;
};

export const DEFAULT_POTATO_CONFIG: Required<PotatoModeConfig> = {
  enabled: true,
  maxToolOutputChars: 800,
  maxShellLines: 15,
  maxBrowserTextChars: 500,
  maxBrowserSnapshotChars: 800,
  dynamicTools: true,
  compactSchemas: true,
  compactSystemPrompt: true,
  contextBudget: 2048,
};

function resolvePotatoAgentId(params: {
  config?: OpenClawConfig;
  agentId?: string;
  sessionKey?: string;
}): string | undefined {
  const explicitAgentId =
    typeof params.agentId === "string" && params.agentId.trim()
      ? normalizeAgentId(params.agentId)
      : undefined;
  if (params.config) {
    return resolveSessionAgentIds({
      config: params.config,
      agentId: explicitAgentId,
      sessionKey: params.sessionKey,
    }).sessionAgentId;
  }
  const parsedSessionAgentId = parseAgentSessionKey(params.sessionKey)?.agentId;
  return (
    explicitAgentId ?? (parsedSessionAgentId ? normalizeAgentId(parsedSessionAgentId) : undefined)
  );
}

/**
 * Returns true when Potato Mode is explicitly or implicitly enabled for the current execution.
 */
export function isPotatoModeEnabled(params?: {
  config?: OpenClawConfig;
  agentId?: string;
  sessionKey?: string;
  potatoMode?: boolean;
}): boolean {
  if (params?.potatoMode === true) {
    return true;
  }
  if (typeof process !== "undefined" && process.env?.OPENCLAW_POTATO_MODE === "1") {
    return true;
  }
  if ((globalThis as { __OPENCLAW_POTATO_MODE__?: boolean }).__OPENCLAW_POTATO_MODE__ === true) {
    return true;
  }
  if (!params?.config) {
    return false;
  }
  const topLevelPotato = (params.config as unknown as { potatoMode?: boolean }).potatoMode;
  if (topLevelPotato === true) {
    return true;
  }
  const normalizedAgentId = resolvePotatoAgentId(params);
  const resolvedExperimental =
    params.config && normalizedAgentId
      ? (resolveAgentConfig(params.config, normalizedAgentId)?.experimental ??
        params.config.agents?.defaults?.experimental)
      : params.config?.agents?.defaults?.experimental;

  const experimentalPotato = (resolvedExperimental as { potatoMode?: boolean } | undefined)
    ?.potatoMode;
  if (experimentalPotato === true) {
    return true;
  }
  return false;
}

/** Set or toggle runtime Potato Mode flag */
export function setGlobalPotatoMode(enabled: boolean): void {
  (globalThis as { __OPENCLAW_POTATO_MODE__?: boolean }).__OPENCLAW_POTATO_MODE__ = enabled;
  if (typeof process !== "undefined" && process.env) {
    if (enabled) {
      process.env.OPENCLAW_POTATO_MODE = "1";
    } else {
      delete process.env.OPENCLAW_POTATO_MODE;
    }
  }
}

/** Resolve effective potato options */
export function resolvePotatoOptions(params?: {
  config?: OpenClawConfig;
  agentId?: string;
  sessionKey?: string;
}): PotatoModeConfig {
  if (!isPotatoModeEnabled(params)) {
    return { enabled: false };
  }
  return { ...DEFAULT_POTATO_CONFIG };
}
