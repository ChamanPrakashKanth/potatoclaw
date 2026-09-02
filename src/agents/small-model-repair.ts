/**
 * Small Model Robustness & Tool-Call Repair Utilities for Potato Mode V2.
 *
 * Provides deterministic tool-call repair, JSON recovery, argument normalization,
 * and repair tracking for 3B-4B local models that occasionally produce slightly
 * imperfect tool syntax.
 */

export type ToolRepairRecord = {
  rawName: string;
  repairedName: string;
  rawArgs: unknown;
  repairedArgs: Record<string, unknown>;
  repairReason: string[];
  repaired: boolean;
};

// Known near-match tool name mappings
const TOOL_NAME_ALIASES: Record<string, string> = {
  browser_navigate: "browser",
  browser_open: "browser",
  browser_click: "browser",
  browser_snapshot: "browser",
  browser_action: "browser",
  open_url: "browser",
  read_file: "read",
  readFile: "read",
  view_file: "read",
  cat_file: "read",
  write_file: "write",
  writeFile: "write",
  create_file: "write",
  edit_file: "edit",
  run_command: "exec",
  run_shell: "exec",
  execute_command: "exec",
  bash: "exec",
  shell: "exec",
  terminal: "exec",
};

// Known argument aliases per tool
const ARG_ALIASES: Record<string, Record<string, string>> = {
  browser: {
    target_url: "url",
    link: "url",
    address: "url",
    query: "text",
    search_query: "text",
    target: "selector",
  },
  read: {
    file_path: "path",
    filename: "path",
    file: "path",
    target_file: "path",
  },
  write: {
    file_path: "path",
    filename: "path",
    target_file: "path",
    file_content: "content",
    data: "content",
    code: "content",
  },
  exec: {
    cmd: "command",
    shell_command: "command",
    script: "command",
  },
};

/**
 * Repairs common small-model JSON defects: trailing commas, single quotes, unquoted keys, unclosed braces.
 */
export function repairMalformedJson(raw: string): Record<string, unknown> | null {
  if (!raw || typeof raw !== "string") {
    return null;
  }
  let cleaned = raw.trim();

  // Try direct parse first
  try {
    const parsed = JSON.parse(cleaned);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>;
    }
  } catch {
    // Continue with repair heuristics
  }

  // Remove markdown code fences if present
  cleaned = cleaned.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/i, "");

  // Remove trailing commas before } or ]
  cleaned = cleaned.replace(/,\s*([}\]])/g, "$1");

  // Replace single quotes around keys/strings with double quotes
  cleaned = cleaned.replace(/'([^'\\]*(?:\\.[^'\\]*)*)'/g, '"$1"');

  // Fix unquoted keys e.g. { action: "navigate" } -> { "action": "navigate" }
  cleaned = cleaned.replace(/([{,]\s*)([a-zA-Z0-9_$]+)\s*:/g, '$1"$2":');

  // If missing closing brace, append it
  const openBraces = (cleaned.match(/{/g) || []).length;
  const closeBraces = (cleaned.match(/}/g) || []).length;
  if (openBraces > closeBraces) {
    cleaned += "}".repeat(openBraces - closeBraces);
  }

  try {
    const parsed = JSON.parse(cleaned);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>;
    }
  } catch {
    // Unable to repair
  }
  return null;
}

/**
 * Extracts a JSON object from text that may contain markdown fences or surrounding chatter.
 */
export function extractJsonFromModelOutput(text: string): Record<string, unknown> | null {
  if (!text || typeof text !== "string") {
    return null;
  }
  const trimmed = text.trim();

  // Direct parse
  try {
    const parsed = JSON.parse(trimmed);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>;
    }
  } catch {
    // Fall through
  }

  // Check for ```json ... ``` blocks
  const jsonBlockMatch = trimmed.match(/```(?:json)?\s*([\s\S]*?)\s*```/i);
  if (jsonBlockMatch?.[1]) {
    const candidate = repairMalformedJson(jsonBlockMatch[1].trim());
    if (candidate) return candidate;
  }

  // Search for the outermost { ... }
  const firstBrace = trimmed.indexOf("{");
  const lastBrace = trimmed.lastIndexOf("}");
  if (firstBrace !== -1 && lastBrace > firstBrace) {
    const candidate = trimmed.slice(firstBrace, lastBrace + 1);
    const parsed = repairMalformedJson(candidate);
    if (parsed) return parsed;
  }

  return null;
}

/**
 * Performs full deterministic repair and normalization on a tool call.
 */
export function repairToolCall(params: {
  toolName: string;
  args: unknown;
}): ToolRepairRecord {
  const reasons: string[] = [];
  let repairedName = params.toolName.trim();
  let repaired = false;

  // 1. Tool name near-match mapping
  if (TOOL_NAME_ALIASES[repairedName]) {
    reasons.push(`Mapped tool alias '${repairedName}' to '${TOOL_NAME_ALIASES[repairedName]}'`);
    repairedName = TOOL_NAME_ALIASES[repairedName];
    repaired = true;
  }

  // 2. Argument JSON extraction / repair
  let cleanArgs: Record<string, unknown> = {};
  if (typeof params.args === "string") {
    const extracted = extractJsonFromModelOutput(params.args);
    if (extracted) {
      cleanArgs = extracted;
      reasons.push("Extracted JSON from string argument block");
      repaired = true;
    } else {
      // Fallback single-argument heuristic
      cleanArgs = { text: params.args };
      reasons.push("Wrapped raw string argument");
      repaired = true;
    }
  } else if (params.args && typeof params.args === "object" && !Array.isArray(params.args)) {
    cleanArgs = { ...(params.args as Record<string, unknown>) };
  }

  // 3. Normalize Argument Aliases
  const toolArgMap = ARG_ALIASES[repairedName];
  if (toolArgMap) {
    for (const [alias, canonical] of Object.entries(toolArgMap)) {
      if (alias in cleanArgs && !(canonical in cleanArgs)) {
        cleanArgs[canonical] = cleanArgs[alias];
        delete cleanArgs[alias];
        reasons.push(`Mapped argument '${alias}' to canonical '${canonical}'`);
        repaired = true;
      }
    }
  }

  // 4. Primitive coercion (string numbers -> numbers, string booleans -> booleans)
  for (const [k, v] of Object.entries(cleanArgs)) {
    if (typeof v === "string") {
      if (v === "true") {
        cleanArgs[k] = true;
        repaired = true;
      } else if (v === "false") {
        cleanArgs[k] = false;
        repaired = true;
      } else if (/^-?\d+$/.test(v) && (k.toLowerCase().includes("line") || k.toLowerCase().includes("count"))) {
        cleanArgs[k] = parseInt(v, 10);
        repaired = true;
      }
    }
  }

  return {
    rawName: params.toolName,
    repairedName,
    rawArgs: params.args,
    repairedArgs: cleanArgs,
    repairReason: reasons,
    repaired,
  };
}
