import assert from "node:assert/strict";
import { evaluateContextWindowGuard } from "../src/agents/context-window-guard.js";
import {
  CONTEXT_WINDOW_HARD_MIN_TOKENS_POTATO,
  CONTEXT_WINDOW_WARN_BELOW_TOKENS_POTATO,
} from "../src/agents/potato-mode.js";
import { classifyPotatoTaskDomain } from "../src/agents/potato-tool-router.js";

console.log("Testing guard in Potato Mode...");
const guard = evaluateContextWindowGuard({
  info: { tokens: 2048, source: "model" },
  potatoMode: true,
});
console.log("Result:", guard);
assert.equal(guard.hardMinTokens, CONTEXT_WINDOW_HARD_MIN_TOKENS_POTATO);
assert.equal(guard.warnBelowTokens, CONTEXT_WINDOW_WARN_BELOW_TOKENS_POTATO);
assert.equal(guard.shouldBlock, false);

console.log("Testing domain classifier...");
assert.equal(classifyPotatoTaskDomain("open https://example.com in browser"), "browser");
console.log("All simple checks passed!");
