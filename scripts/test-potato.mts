import assert from "node:assert/strict";
import { evaluateContextWindowGuard } from "../src/agents/context-window-guard.js";
import {
  CONTEXT_WINDOW_HARD_MIN_TOKENS_POTATO,
  CONTEXT_WINDOW_WARN_BELOW_TOKENS_POTATO,
  isPotatoModeEnabled,
} from "../src/agents/potato-mode.js";
import {
  classifyPotatoTaskDomain,
  getPotatoAllowedToolNames,
  routePotatoTools,
} from "../src/agents/potato-tool-router.js";
import { buildAgentSystemPrompt } from "../src/agents/system-prompt.js";
import { describeBrowserTool } from "../extensions/browser/src/browser-tool-description.js";

console.log("[test] Running Potato Mode Verification Suite...");

// 1. Context Window Guard in Potato Mode
console.log("-> Testing evaluateContextWindowGuard in Potato Mode");
const guard2048 = evaluateContextWindowGuard({
  info: { tokens: 2048, source: "model" },
  potatoMode: true,
});
assert.equal(guard2048.hardMinTokens, CONTEXT_WINDOW_HARD_MIN_TOKENS_POTATO, "hardMinTokens should be 1024");
assert.equal(guard2048.warnBelowTokens, CONTEXT_WINDOW_WARN_BELOW_TOKENS_POTATO, "warnBelowTokens should be 2048");
assert.equal(guard2048.shouldBlock, false, "2048 should not block");
assert.equal(guard2048.shouldWarn, false, "2048 should not warn");

const guard1024 = evaluateContextWindowGuard({
  info: { tokens: 1024, source: "model" },
  potatoMode: true,
});
assert.equal(guard1024.shouldBlock, false, "1024 should not block in potato mode");
assert.equal(guard1024.shouldWarn, true, "1024 should warn in potato mode");

const guard512 = evaluateContextWindowGuard({
  info: { tokens: 512, source: "model" },
  potatoMode: true,
});
assert.equal(guard512.shouldBlock, true, "512 should block");

// 2. Potato Mode System Prompt
console.log("-> Testing buildAgentSystemPrompt in Potato Mode");
const prompt = buildAgentSystemPrompt({
  workspaceDir: "C:/projects/test",
  userDate: "2026-09-02",
  promptMode: "potato",
});
assert.ok(prompt.includes("Potato Mode"), "Prompt should mention Potato Mode");
assert.ok(prompt.includes("C:/projects/test"), "Prompt should include workspace");
assert.ok(!prompt.includes("## Workspace Files (injected)"), "Prompt should omit heavy workspace files");
assert.ok(prompt.length < 800, `Prompt should be compact (<800 chars, was ${prompt.length})`);
console.log(`   Prompt length: ${prompt.length} chars (~${Math.round(prompt.length / 4)} tokens)`);

// 3. Dynamic Tool Router
console.log("-> Testing classifyPotatoTaskDomain and routePotatoTools");
assert.equal(classifyPotatoTaskDomain("Using the browser, open https://example.com"), "browser");
assert.equal(classifyPotatoTaskDomain("Read file package.json and edit it"), "filesystem");
assert.equal(classifyPotatoTaskDomain("Run npm test in terminal"), "shell");
assert.equal(classifyPotatoTaskDomain("What is 2 + 2?"), "core");

const mockTools = [
  { name: "browser" },
  { name: "read" },
  { name: "write" },
  { name: "edit" },
  { name: "exec" },
  { name: "image_generate" },
  { name: "tts" },
  { name: "sessions_spawn" },
] as any[];

const browserRouted = routePotatoTools({
  tools: mockTools,
  userPrompt: "Using the browser, open https://example.com and get the title",
  potatoMode: true,
});
const toolNames = browserRouted.map((t) => t.name);
assert.ok(toolNames.includes("browser"), "browser tool must be kept for browser tasks");
assert.ok(toolNames.includes("read"), "read tool must be kept");
assert.ok(!toolNames.includes("image_generate"), "image_generate must be filtered");
assert.ok(!toolNames.includes("tts"), "tts must be filtered");
assert.ok(!toolNames.includes("sessions_spawn"), "sessions_spawn must be filtered");

// 4. Compact Browser Description
console.log("-> Testing describeBrowserTool in Potato Mode");
const desc = describeBrowserTool({
  targetDefault: "host",
  hostHint: "",
  capabilities: { actions: ["navigate", "act", "snapshot", "text"], actKinds: ["click", "type"], tabBound: false },
  potatoMode: true,
});
assert.ok(desc.length < 250, `Browser description should be <250 chars, was ${desc.length}`);
console.log(`   Browser tool description length: ${desc.length} chars (~${Math.round(desc.length / 4)} tokens)`);

console.log("\n[PASS] All Potato Mode tests passed successfully!");
