/**
 * Small Model Robustness Utilities for Potato Mode.
 *
 * Provides JSON repair, Markdown code block extraction, and repeated action loop detection
 * tailored for small (3B-4B) local models that may produce slightly malformed tool calls.
 */

/**
 * Extracts a JSON object from text that may contain markdown fences or surrounding chatter.
 */
export function extractJsonFromModelOutput(text: string): Record<string, unknown> | null {
  if (!text || typeof text !== "string") {
    return null;
  }
  const trimmed = text.trim();

  // Try direct parse first
  try {
    const parsed = JSON.parse(trimmed);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>;
    }
  } catch {
    // Continue to extraction heuristics
  }

  // Check for ```json ... ``` blocks
  const jsonBlockMatch = trimmed.match(/```(?:json)?\s*([\s\S]*?)\s*```/i);
  if (jsonBlockMatch?.[1]) {
    try {
      const parsed = JSON.parse(jsonBlockMatch[1].trim());
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        return parsed as Record<string, unknown>;
      }
    } catch {
      const repaired = repairMalformedJson(jsonBlockMatch[1].trim());
      if (repaired) {
        return repaired;
      }
    }
  }

  // Search for the outermost { ... }
  const firstBrace = trimmed.indexOf("{");
  const lastBrace = trimmed.lastIndexOf("}");
  if (firstBrace !== -1 && lastBrace > firstBrace) {
    const candidate = trimmed.slice(firstBrace, lastBrace + 1);
    try {
      const parsed = JSON.parse(candidate);
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        return parsed as Record<string, unknown>;
      }
    } catch {
      return repairMalformedJson(candidate);
    }
  }

  return null;
}

/**
 * Repairs common small-model JSON defects: trailing commas, single quotes, unquoted keys.
 */
export function repairMalformedJson(raw: string): Record<string, unknown> | null {
  if (!raw || typeof raw !== "string") {
    return null;
  }
  let cleaned = raw.trim();

  // Remove trailing commas before } or ]
  cleaned = cleaned.replace(/,\s*([}\]])/g, "$1");

  // Replace single quotes around keys/strings with double quotes
  cleaned = cleaned.replace(/'([^'\\]*(?:\\.[^'\\]*)*)'/g, '"$1"');

  // Fix unquoted keys e.g. { action: "navigate" } -> { "action": "navigate" }
  cleaned = cleaned.replace(/([{,]\s*)([a-zA-Z0-9_$]+)\s*:/g, '$1"$2":');

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
 * Tracks recent tool invocations to detect and break repeated action loops.
 */
export class PotatoLoopDetector {
  private history: string[] = [];
  private readonly maxRepeats: number;

  constructor(maxRepeats = 3) {
    this.maxRepeats = maxRepeats;
  }

  /**
   * Records a tool call and returns true if an infinite loop is detected.
   */
  recordAndCheckLoop(toolName: string, args: unknown): boolean {
    const signature = `${toolName}:${JSON.stringify(args ?? {})}`;
    this.history.push(signature);
    if (this.history.length > 20) {
      this.history.shift();
    }

    if (this.history.length < this.maxRepeats) {
      return false;
    }

    const recent = this.history.slice(-this.maxRepeats);
    return recent.every((entry) => entry === signature);
  }

  reset(): void {
    this.history = [];
  }
}
