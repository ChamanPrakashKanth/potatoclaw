/**
 * Dynamic Tool Router for Potato Mode.
 *
 * Exposes only the tools necessary for the current task intent, preventing
 * tool-schema bloat in small local models (3B-4B) with limited context windows.
 */
import type { OpenClawConfig } from "../config/types.openclaw.js";
import type { AnyAgentTool } from "./agent-tools.types.js";
import { isPotatoModeEnabled, type PotatoModeConfig } from "./potato-mode.js";
import { normalizeToolPolicyName } from "./tool-policy.js";

export type PotatoTaskDomain = "browser" | "filesystem" | "shell" | "core";

const BROWSER_KEYWORDS = [
  "browser",
  "http://",
  "https://",
  "www.",
  "web",
  "website",
  "url",
  "navigate",
  "page",
  "click",
  "snapshot",
  "scrape",
  "html",
  "chrome",
  "dom",
  "tab",
];

const FILESYSTEM_KEYWORDS = [
  "file",
  "read",
  "write",
  "edit",
  "directory",
  "folder",
  "path",
  "create file",
  "save file",
  "patch",
  "delete file",
  "rename",
];

const SHELL_KEYWORDS = [
  "bash",
  "shell",
  "exec",
  "run command",
  "terminal",
  "execute",
  "npm",
  "pnpm",
  "pip",
  "cargo",
  "git",
  "pytest",
  "vitest",
];

/**
 * Classifies a user prompt into a task domain for tool routing.
 */
export function classifyPotatoTaskDomain(prompt?: string): PotatoTaskDomain {
  if (!prompt || typeof prompt !== "string") {
    return "core";
  }
  const lower = prompt.toLowerCase();

  for (const keyword of BROWSER_KEYWORDS) {
    if (lower.includes(keyword)) {
      return "browser";
    }
  }

  for (const keyword of FILESYSTEM_KEYWORDS) {
    if (lower.includes(keyword)) {
      return "filesystem";
    }
  }

  for (const keyword of SHELL_KEYWORDS) {
    if (lower.includes(keyword)) {
      return "shell";
    }
  }

  return "core";
}

/**
 * Returns allowed tool names for a specific Potato Mode domain.
 */
export function getPotatoAllowedToolNames(domain: PotatoTaskDomain): Set<string> {
  switch (domain) {
    case "browser":
      // Browser tasks only need browser + minimal inspection/completion
      return new Set(["browser", "read", "write", "exec"]);
    case "filesystem":
      // Filesystem tasks need file tools + shell if needed
      return new Set(["read", "write", "edit", "apply_patch", "exec"]);
    case "shell":
      // Shell tasks need exec + file read/write
      return new Set(["exec", "read", "write"]);
    case "core":
    default:
      // Minimal default tool surface for Potato Mode
      return new Set(["browser", "read", "write", "edit", "exec"]);
  }
}

/**
 * Filters the available tool list to the minimal subset required for the task.
 */
export function routePotatoTools(params: {
  tools: AnyAgentTool[];
  userPrompt?: string;
  config?: OpenClawConfig;
  potatoConfig?: PotatoModeConfig;
  potatoMode?: boolean;
}): AnyAgentTool[] {
  if (!isPotatoModeEnabled({ config: params.config, potatoMode: params.potatoMode })) {
    return params.tools;
  }

  const domain = classifyPotatoTaskDomain(params.userPrompt);
  const allowedNames = getPotatoAllowedToolNames(domain);

  return params.tools.filter((tool) => {
    const norm = normalizeToolPolicyName(tool.name);
    return allowedNames.has(norm);
  });
}
