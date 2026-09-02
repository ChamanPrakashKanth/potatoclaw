/**
 * PotatoClaw BMW - Bounded Working Memory
 *
 * Deterministic, zero-overhead task state management designed for 3B-4B local models
 * with strict token budgets (2048 tokens). Replaces unbounded multi-turn conversation
 * history with a compact structured state block.
 *
 * State Sections:
 *   GOAL              - Active primary objective
 *   CURRENT STATE     - Current execution step
 *   IMPORTANT FACTS   - Core environmental or retrieved facts
 *   COMPLETED ACTIONS - Pruned list of accomplished steps
 *   PENDING ACTIONS   - Next immediate actions
 *   ERRORS            - Active unresolved errors
 *   RESULTS           - Final or intermediate task outputs
 */

export type BmwState = {
  goal: string;
  currentState: string;
  importantFacts: string[];
  completedActions: string[];
  pendingActions: string[];
  errors: string[];
  results: string[];
};

export type BmwBudgetConfig = {
  maxGoalChars: number;
  maxStateChars: number;
  maxFacts: number;
  maxFactChars: number;
  maxCompletedActions: number;
  maxPendingActions: number;
  maxErrors: number;
  maxResults: number;
  maxTotalChars: number;
};

export const DEFAULT_BMW_BUDGET: BmwBudgetConfig = {
  maxGoalChars: 120,
  maxStateChars: 100,
  maxFacts: 4,
  maxFactChars: 120,
  maxCompletedActions: 3,
  maxPendingActions: 2,
  maxErrors: 2,
  maxResults: 3,
  maxTotalChars: 850, // ~200-250 tokens
};

export class BoundedWorkingMemory {
  private state: BmwState;
  private budget: BmwBudgetConfig;

  constructor(initialGoal = "", budget = DEFAULT_BMW_BUDGET) {
    this.budget = budget;
    this.state = {
      goal: initialGoal.slice(0, budget.maxGoalChars),
      currentState: "INITIALIZED",
      importantFacts: [],
      completedActions: [],
      pendingActions: [],
      errors: [],
      results: [],
    };
  }

  setGoal(goal: string): void {
    this.state.goal = goal.trim().slice(0, this.budget.maxGoalChars);
  }

  setCurrentState(state: string): void {
    this.state.currentState = state.trim().slice(0, this.budget.maxStateChars);
  }

  addFact(fact: string): void {
    const clean = fact.trim().slice(0, this.budget.maxFactChars);
    if (!clean || this.state.importantFacts.includes(clean)) return;

    this.state.importantFacts.push(clean);
    if (this.state.importantFacts.length > this.budget.maxFacts) {
      // FIFO eviction of older facts
      this.state.importantFacts.shift();
    }
  }

  recordCompletedAction(action: string): void {
    const clean = action.trim().slice(0, 100);
    if (!clean) return;

    this.state.completedActions.push(clean);
    if (this.state.completedActions.length > this.budget.maxCompletedActions) {
      this.state.completedActions.shift();
    }
    // Clear matching pending action
    this.state.pendingActions = this.state.pendingActions.filter(
      (p) => !p.toLowerCase().includes(clean.toLowerCase()),
    );
  }

  addPendingAction(action: string): void {
    const clean = action.trim().slice(0, 100);
    if (!clean || this.state.pendingActions.includes(clean)) return;

    this.state.pendingActions.push(clean);
    if (this.state.pendingActions.length > this.budget.maxPendingActions) {
      this.state.pendingActions.shift();
    }
  }

  recordError(error: string): void {
    const clean = error.trim().slice(0, 150);
    if (!clean) return;

    this.state.errors.push(clean);
    if (this.state.errors.length > this.budget.maxErrors) {
      this.state.errors.shift();
    }
  }

  clearErrors(): void {
    this.state.errors = [];
  }

  addResult(result: string): void {
    const clean = result.trim().slice(0, 200);
    if (!clean) return;

    this.state.results.push(clean);
    if (this.state.results.length > this.budget.maxResults) {
      this.state.results.shift();
    }
  }

  /**
   * Formats the structured bounded memory block for prompt injection.
   */
  formatPromptBlock(): string {
    const parts: string[] = ["[TASK STATE (BMW)]"];

    if (this.state.goal) {
      parts.push(`GOAL: ${this.state.goal}`);
    }
    if (this.state.currentState) {
      parts.push(`STATE: ${this.state.currentState}`);
    }
    if (this.state.importantFacts.length > 0) {
      parts.push(`FACTS:\n- ${this.state.importantFacts.join("\n- ")}`);
    }
    if (this.state.completedActions.length > 0) {
      parts.push(`COMPLETED: ${this.state.completedActions.join(" -> ")}`);
    }
    if (this.state.pendingActions.length > 0) {
      parts.push(`PENDING: ${this.state.pendingActions.join(", ")}`);
    }
    if (this.state.errors.length > 0) {
      parts.push(`ACTIVE ERRORS:\n- ${this.state.errors.join("\n- ")}`);
    }
    if (this.state.results.length > 0) {
      parts.push(`RESULTS:\n- ${this.state.results.join("\n- ")}`);
    }

    const output = parts.join("\n");
    if (output.length > this.budget.maxTotalChars) {
      return output.slice(0, this.budget.maxTotalChars) + "\n[...]";
    }
    return output;
  }

  getState(): Readonly<BmwState> {
    return this.state;
  }

  reset(): void {
    this.state = {
      goal: "",
      currentState: "INITIALIZED",
      importantFacts: [],
      completedActions: [],
      pendingActions: [],
      errors: [],
      results: [],
    };
  }
}
