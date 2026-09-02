/**
 * Dynamic Tool Router for Potato Mode V2.
 *
 * Exposes only the tools necessary for the current task domain, preventing
 * tool-schema bloat in small local models (3B-4B) with limited context windows.
 * Includes a lightweight escape mechanism allowing the model to request another tool family.
 */
import type { OpenClawConfig } from "../config/types.openclaw.js";
import type { AnyAgentTool } from "./agent-tools.types.js";
import { isPotatoModeEnabled, type PotatoModeConfig } from "./potato-mode.js";
import { normalizeToolPolicyName } from "./tool-policy.js";

export type PotatoTaskDomain = "browser" | "filesystem" | "shell" | "memory" | "core";

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
  "search",
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
  "status",
];

const MEMORY_KEYWORDS = ["remember", "previous", "note", "recall", "memory", "state"];

/**
 * Classifies a user prompt or step into a task domain for tool routing.
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

  for (const keyword of MEMORY_KEYWORDS) {
    if (lower.includes(keyword)) {
      return "memory";
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
      // Browser domain: browser tool + lightweight escape
      return new Set(["browser", "request_tool_family"]);
    case "filesystem":
      // Filesystem domain: read, write, edit, patch + lightweight escape
      return new Set(["read", "write", "edit", "apply_patch", "request_tool_family"]);
    case "shell":
      // Shell domain: exec + lightweight escape
      return new Set(["exec", "request_tool_family"]);
    case "memory":
      return new Set(["read", "write", "request_tool_family"]);
    case "core":
    default:
      // Minimal default core tool surface
      return new Set(["browser", "read", "exec", "request_tool_family"]);
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
  forcedDomain?: PotatoTaskDomain;
}): AnyAgentTool[] {
  if (!isPotatoModeEnabled({ config: params.config, potatoMode: params.potatoMode })) {
    return params.tools;
  }

  const domain = params.forcedDomain ?? classifyPotatoTaskDomain(params.userPrompt);
  const allowedNames = getPotatoAllowedToolNames(domain);

  const filtered = params.tools.filter((tool) => {
    const norm = normalizeToolPolicyName(tool.name);
    return allowedNames.has(norm);
  });

  // If filtering yielded empty, return the minimal safe core set
  return filtered.length > 0 ? filtered : params.tools.slice(0, 3);
}
