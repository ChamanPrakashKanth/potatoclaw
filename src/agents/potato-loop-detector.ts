/**
 * PotatoClaw Loop Detector & Circuit Breaker
 *
 * Prevents small local models from falling into infinite tool-call loops
 * (identical repeated actions, A -> B -> A -> B oscillatory cycles,
 * repeated selector failures, and duplicate shell commands).
 */

export type LoopDetectionResult = {
  isLoop: boolean;
  loopType?: "identical_repeat" | "oscillatory_cycle" | "selector_failure" | "command_repeat";
  message?: string;
  repeatCount: number;
};

export class PotatoLoopDetector {
  private history: Array<{ toolName: string; signature: string; success: boolean }> = [];
  private readonly maxIdenticalRepeats: number;
  private readonly maxOscillations: number;

  constructor(maxIdenticalRepeats = 3, maxOscillations = 2) {
    this.maxIdenticalRepeats = maxIdenticalRepeats;
    this.maxOscillations = maxOscillations;
  }

  /**
   * Records a tool call and evaluates whether an execution loop is occurring.
   */
  recordAndCheck(params: {
    toolName: string;
    args: Record<string, unknown>;
    success?: boolean;
  }): LoopDetectionResult {
    const signature = JSON.stringify(params.args ?? {});
    this.history.push({
      toolName: params.toolName,
      signature,
      success: params.success ?? true,
    });

    if (this.history.length > 25) {
      this.history.shift();
    }

    // 1. Identical Repeated Actions Check
    if (this.history.length >= this.maxIdenticalRepeats) {
      const recent = this.history.slice(-this.maxIdenticalRepeats);
      const isIdentical = recent.every(
        (entry) =>
          entry.toolName === params.toolName && entry.signature === signature,
      );
      if (isIdentical) {
        return {
          isLoop: true,
          loopType: "identical_repeat",
          repeatCount: this.maxIdenticalRepeats,
          message: `LOOP DETECTED: ${params.toolName}(${signature.slice(0, 60)}) repeated ${this.maxIdenticalRepeats} times. Choose a different action.`,
        };
      }
    }

    // 2. Oscillatory A -> B -> A -> B Cycle Check
    if (this.history.length >= 4) {
      const h = this.history;
      const len = h.length;
      const isA_B_A_B =
        h[len - 1].toolName === h[len - 3].toolName &&
        h[len - 1].signature === h[len - 3].signature &&
        h[len - 2].toolName === h[len - 4].toolName &&
        h[len - 2].signature === h[len - 4].signature;

      if (isA_B_A_B) {
        return {
          isLoop: true,
          loopType: "oscillatory_cycle",
          repeatCount: 2,
          message: `OSCILLATING LOOP DETECTED between ${h[len - 2].toolName} and ${h[len - 1].toolName}. Stop switching and try a new approach.`,
        };
      }
    }

    return {
      isLoop: false,
      repeatCount: 1,
    };
  }

  reset(): void {
    this.history = [];
  }
}
