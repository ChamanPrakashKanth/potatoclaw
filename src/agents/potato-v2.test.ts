import { describe, expect, it } from "vitest";
import { BoundedWorkingMemory } from "./potato-bmw.js";
import { PotatoSemanticDecayEngine } from "./potato-semantic-decay.js";
import { repairMalformedJson, repairToolCall } from "./small-model-repair.js";
import { PotatoLoopDetector } from "./potato-loop-detector.js";
import { PotatoBrowserIntelligence } from "./potato-browser-intelligence.js";
import { PotatoResourceGovernor } from "./potato-resource-governor.js";
import { classifyPotatoTaskDomain, getPotatoAllowedToolNames } from "./potato-tool-router.js";

describe("PotatoClaw V2 Core Architecture", () => {
  describe("BMW - Bounded Working Memory", () => {
    it("manages structured state within strict character budgets", () => {
      const bmw = new BoundedWorkingMemory("Find the latest tech news and post on X");
      bmw.setCurrentState("OPENING_BROWSER");
      bmw.addFact("Target URL is https://news.ycombinator.com");
      bmw.recordCompletedAction("browser(action='open')");
      bmw.addPendingAction("extract_headline");
      bmw.addResult("Found top headline: Quantum breakthrough in photonic qubits");

      const promptBlock = bmw.formatPromptBlock();
      expect(promptBlock).toContain("[TASK STATE (BMW)]");
      expect(promptBlock).toContain("GOAL: Find the latest tech news");
      expect(promptBlock).toContain("STATE: OPENING_BROWSER");
      expect(promptBlock).toContain("FACTS:\n- Target URL is https://news.ycombinator.com");
      expect(promptBlock).toContain("COMPLETED: browser(action='open')");
      expect(promptBlock.length).toBeLessThanOrEqual(850);
    });

    it("deterministically prunes older facts when exceeding capacity", () => {
      const bmw = new BoundedWorkingMemory("Task Goal");
      bmw.addFact("Fact 1");
      bmw.addFact("Fact 2");
      bmw.addFact("Fact 3");
      bmw.addFact("Fact 4");
      bmw.addFact("Fact 5"); // Should evict Fact 1

      const state = bmw.getState();
      expect(state.importantFacts).not.toContain("Fact 1");
      expect(state.importantFacts).toContain("Fact 5");
      expect(state.importantFacts.length).toBe(4);
    });
  });

  describe("Semantic Memory Decay", () => {
    it("decays older irrelevant observations while boosting errors and results", () => {
      const decay = new PotatoSemanticDecayEngine("quantum physics simulation");
      
      decay.recordObservation({
        toolName: "browser",
        rawText: "Random web advertisement and cookies banner",
      });

      decay.recordObservation({
        toolName: "browser",
        rawText: "Quantum computing photon research result",
        hasResult: true,
      });

      decay.recordObservation({
        toolName: "exec",
        rawText: "Failed to connect to port: connection refused",
        hasError: true,
      });

      const active = decay.getActiveObservations();
      expect(active.length).toBeGreaterThan(0);
      // The error and quantum result should have higher score than random ad
      expect(active[0].hasError || active[0].hasResult).toBe(true);
    });
  });

  describe("Dynamic Tool Routing", () => {
    it("classifies task domains correctly", () => {
      expect(classifyPotatoTaskDomain("Open https://example.com")).toBe("browser");
      expect(classifyPotatoTaskDomain("Read the config file in src/agents")).toBe("filesystem");
      expect(classifyPotatoTaskDomain("Run git status and npm test")).toBe("shell");
      expect(classifyPotatoTaskDomain("Hello there")).toBe("core");
    });

    it("filters to minimal tool families", () => {
      const browserTools = getPotatoAllowedToolNames("browser");
      expect(browserTools.has("browser")).toBe(true);
      expect(browserTools.has("request_tool_family")).toBe(true);
      expect(browserTools.has("apply_patch")).toBe(false);
    });
  });

  describe("Small-Model Tool-Call Repair", () => {
    it("repairs malformed JSON from 3B-4B models", () => {
      const raw = "{ action: 'open', target_url: 'http://example.com', }";
      const repaired = repairMalformedJson(raw);
      expect(repaired).toEqual({ action: "open", target_url: "http://example.com" });
    });

    it("maps tool aliases and argument typos to canonical names", () => {
      const repaired = repairToolCall({
        toolName: "browser_navigate",
        args: { target_url: "https://httpbin.org", line: "15" },
      });

      expect(repaired.repairedName).toBe("browser");
      expect(repaired.repairedArgs.url).toBe("https://httpbin.org");
      expect(repaired.repairedArgs.line).toBe(15);
      expect(repaired.repaired).toBe(true);
    });
  });

  describe("Loop Detector", () => {
    it("detects identical repeated actions", () => {
      const detector = new PotatoLoopDetector(3);
      expect(detector.recordAndCheck({ toolName: "browser", args: { action: "click", selector: "#btn" } }).isLoop).toBe(false);
      expect(detector.recordAndCheck({ toolName: "browser", args: { action: "click", selector: "#btn" } }).isLoop).toBe(false);
      const res3 = detector.recordAndCheck({ toolName: "browser", args: { action: "click", selector: "#btn" } });
      expect(res3.isLoop).toBe(true);
      expect(res3.loopType).toBe("identical_repeat");
    });

    it("detects A -> B -> A -> B oscillatory loops", () => {
      const detector = new PotatoLoopDetector(3, 2);
      detector.recordAndCheck({ toolName: "browser", args: { action: "open" } });
      detector.recordAndCheck({ toolName: "exec", args: { command: "git status" } });
      detector.recordAndCheck({ toolName: "browser", args: { action: "open" } });
      const res = detector.recordAndCheck({ toolName: "exec", args: { command: "git status" } });
      expect(res.isLoop).toBe(true);
      expect(res.loopType).toBe("oscillatory_cycle");
    });
  });

  describe("Browser Intelligence in Code", () => {
    it("provides Level 0 and Level 1 progressive observations", () => {
      const intel = new PotatoBrowserIntelligence();
      const snapshot = {
        title: "Example Domain",
        url: "http://example.com",
        visibleText: "This domain is for use in illustrative examples in documents.",
        interactiveElements: [{ ref: "e1", tag: "a", text: "More information..." }],
      };

      const level0 = intel.formatProgressiveObservation(snapshot, 0);
      expect(level0).toBe('Title: "Example Domain"\nURL: http://example.com');

      const level1 = intel.formatProgressiveObservation(snapshot, 1);
      expect(level1).toContain("Example Domain");
      expect(level1).toContain("Interactive Elements:");
    });

    it("directly answers trivial mechanical queries in code", () => {
      const intel = new PotatoBrowserIntelligence();
      const snapshot = { title: "Test Page Title", url: "https://test.com" };
      const ans = intel.tryDirectMechanicalAnswer("Tell me the page title", snapshot);
      expect(ans).toBe('Page Title: "Test Page Title"');
    });
  });

  describe("Resource Governor", () => {
    it("evaluates GREEN, AMBER, and RED tiers based on token pressure", () => {
      const gov = new PotatoResourceGovernor();
      
      const green = gov.evaluatePressure({ currentContextTokens: 400 });
      expect(green.tier).toBe("GREEN");

      const amber = gov.evaluatePressure({ currentContextTokens: 1300 });
      expect(amber.tier).toBe("AMBER");
      expect(amber.actionsTaken).toContain("PRUNE_OLD_OBSERVATIONS");

      const red = gov.evaluatePressure({ currentContextTokens: 1800 });
      expect(red.tier).toBe("RED");
      expect(red.actionsTaken).toContain("EMERGENCY_PRUNE_CONTEXT");
    });
  });
});
