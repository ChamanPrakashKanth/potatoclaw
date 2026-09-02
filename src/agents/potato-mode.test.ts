import { describe, expect, it } from "vitest";
import { evaluateContextWindowGuard } from "./context-window-guard.js";
import {
  CONTEXT_WINDOW_HARD_MIN_TOKENS_POTATO,
  CONTEXT_WINDOW_WARN_BELOW_TOKENS_POTATO,
  isPotatoModeEnabled,
} from "./potato-mode.js";
import { classifyPotatoTaskDomain, getPotatoAllowedToolNames, routePotatoTools } from "./potato-tool-router.js";
import { buildAgentSystemPrompt } from "./system-prompt.js";

describe("Potato Mode Core Functionality", () => {
  describe("Context Window Guard in Potato Mode", () => {
    it("allows 2048 tokens without blocking or warning in Potato Mode", () => {
      const guard = evaluateContextWindowGuard({
        info: { tokens: 2048, source: "model" },
        potatoMode: true,
      });
      expect(guard.hardMinTokens).toBe(CONTEXT_WINDOW_HARD_MIN_TOKENS_POTATO);
      expect(guard.warnBelowTokens).toBe(CONTEXT_WINDOW_WARN_BELOW_TOKENS_POTATO);
      expect(guard.shouldBlock).toBe(false);
      expect(guard.shouldWarn).toBe(false);
    });

    it("allows 1024 tokens without blocking in Potato Mode", () => {
      const guard = evaluateContextWindowGuard({
        info: { tokens: 1024, source: "model" },
        potatoMode: true,
      });
      expect(guard.shouldBlock).toBe(false);
      expect(guard.shouldWarn).toBe(true);
    });

    it("blocks 512 tokens even in Potato Mode", () => {
      const guard = evaluateContextWindowGuard({
        info: { tokens: 512, source: "model" },
        potatoMode: true,
      });
      expect(guard.shouldBlock).toBe(true);
    });
  });

  describe("Potato Mode System Prompt", () => {
    it("generates a compact system prompt under 200 tokens", () => {
      const prompt = buildAgentSystemPrompt({
        workspaceDir: "C:/projects/test",
        userDate: "2026-09-02",
        promptMode: "potato",
      });
      expect(prompt).toContain("Potato Mode");
      expect(prompt).toContain("C:/projects/test");
      expect(prompt).not.toContain("## Workspace Files (injected)");
      // Verify length is compact (< 800 chars / ~150 tokens)
      expect(prompt.length).toBeLessThan(800);
    });
  });

  describe("Dynamic Tool Router", () => {
    it("correctly classifies task domains", () => {
      expect(classifyPotatoTaskDomain("Using the browser, open https://example.com")).toBe("browser");
      expect(classifyPotatoTaskDomain("Read file package.json and edit it")).toBe("filesystem");
      expect(classifyPotatoTaskDomain("Run npm test in terminal")).toBe("shell");
      expect(classifyPotatoTaskDomain("What is 2 + 2?")).toBe("core");
    });

    it("routes tools based on domain and filters unneeded tools", () => {
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
      expect(toolNames).toContain("browser");
      expect(toolNames).toContain("read");
      expect(toolNames).not.toContain("image_generate");
      expect(toolNames).not.toContain("tts");
      expect(toolNames).not.toContain("sessions_spawn");
    });
  });
});
