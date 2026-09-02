/**
 * PotatoClaw Semantic Memory Decay
 *
 * Cheap, deterministic memory decay without embeddings or vector databases.
 * Scores observation relevance based on recency, goal relevance, active errors,
 * and result status, pruning stale intermediate chatter from prompt context.
 */

export type ObservationEntry = {
  id: string;
  toolName: string;
  rawText: string;
  summaryText?: string;
  turnIndex: number;
  hasError: boolean;
  hasResult: boolean;
  score?: number;
};

export type SemanticDecayConfig = {
  decayHalfLifeTurns: number;
  errorBoost: number;
  resultBoost: number;
  relevanceThreshold: number;
  maxRetainedObservations: number;
};

export const DEFAULT_DECAY_CONFIG: SemanticDecayConfig = {
  decayHalfLifeTurns: 3,
  errorBoost: 2.5,
  resultBoost: 2.0,
  relevanceThreshold: 1.0,
  maxRetainedObservations: 4,
};

export function extractKeywords(text: string): Set<string> {
  const words = text
    .toLowerCase()
    .replace(/[^a-z0-9_\-\s]/g, " ")
    .split(/\s+/)
    .filter((w) => w.length > 3);
  return new Set(words);
}

export function calculateObservationScore(params: {
  entry: ObservationEntry;
  currentTurn: number;
  goalKeywords: Set<string>;
  currentToolName?: string;
  config?: SemanticDecayConfig;
}): number {
  const cfg = params.config ?? DEFAULT_DECAY_CONFIG;
  const turnsAgo = Math.max(0, params.currentTurn - params.entry.turnIndex);

  // 1. Recency Decay (exponential power of 0.5 per half-life)
  const recencyWeight = Math.pow(0.5, turnsAgo / cfg.decayHalfLifeTurns);

  // 2. Goal Relevance (keyword overlap)
  const obsKeywords = extractKeywords(params.entry.rawText);
  let overlapCount = 0;
  for (const kw of params.goalKeywords) {
    if (obsKeywords.has(kw)) {
      overlapCount++;
    }
  }
  const goalRelevance = 1.0 + Math.min(2.0, overlapCount * 0.4);

  // 3. Current Tool affinity
  const toolAffinity = params.currentToolName && params.entry.toolName === params.currentToolName ? 1.3 : 1.0;

  // 4. Critical Error / Result Boosts
  const errorMultiplier = params.entry.hasError ? cfg.errorBoost : 1.0;
  const resultMultiplier = params.entry.hasResult ? cfg.resultBoost : 1.0;

  return recencyWeight * goalRelevance * toolAffinity * errorMultiplier * resultMultiplier;
}

export class PotatoSemanticDecayEngine {
  private entries: ObservationEntry[] = [];
  private config: SemanticDecayConfig;
  private goalKeywords: Set<string> = new Set();
  private turnCounter = 0;

  constructor(goal = "", config = DEFAULT_DECAY_CONFIG) {
    this.config = config;
    this.setGoal(goal);
  }

  setGoal(goal: string): void {
    this.goalKeywords = extractKeywords(goal);
  }

  advanceTurn(): void {
    this.turnCounter++;
  }

  recordObservation(params: {
    id?: string;
    toolName: string;
    rawText: string;
    summaryText?: string;
    hasError?: boolean;
    hasResult?: boolean;
  }): void {
    this.advanceTurn();
    const entry: ObservationEntry = {
      id: params.id ?? `obs_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      toolName: params.toolName,
      rawText: params.rawText,
      summaryText: params.summaryText,
      turnIndex: this.turnCounter,
      hasError: params.hasError ?? false,
      hasResult: params.hasResult ?? false,
    };
    this.entries.push(entry);
    this.pruneStaleObservations();
  }

  /**
   * Filters and orders active observations by semantic score.
   */
  getActiveObservations(currentToolName?: string): ObservationEntry[] {
    const scored = this.entries.map((entry) => ({
      ...entry,
      score: calculateObservationScore({
        entry,
        currentTurn: this.turnCounter,
        goalKeywords: this.goalKeywords,
        currentToolName,
        config: this.config,
      }),
    }));

    // Filter by threshold and take top N
    return scored
      .filter((e) => (e.score ?? 0) >= this.config.relevanceThreshold)
      .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
      .slice(0, this.config.maxRetainedObservations);
  }

  private pruneStaleObservations(): void {
    const active = this.getActiveObservations();
    const activeIds = new Set(active.map((a) => a.id));
    // Retain only active entries or entries within the last 2 turns
    this.entries = this.entries.filter(
      (e) => activeIds.has(e.id) || this.turnCounter - e.turnIndex <= 1,
    );
  }

  reset(): void {
    this.entries = [];
    this.turnCounter = 0;
  }
}
