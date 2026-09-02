/**
 * PotatoClaw Browser Intelligence in Code & Progressive Observation.
 *
 * Offloads mechanical browser reasoning (title extraction, URL lookups, link mapping,
 * selector fallback heuristics, unchanged page deduplication) from the LLM into code,
 * and manages 4 progressive observation fidelity tiers.
 *
 * Levels:
 *   LEVEL 0: title + URL (~20 tokens)
 *   LEVEL 1: key visible text + interactive element references (~100 tokens)
 *   LEVEL 2: structured relevant content section (~200 tokens)
 *   LEVEL 3: bounded full extraction (~450 tokens)
 */

export type ProgressiveObservationLevel = 0 | 1 | 2 | 3;

export type BrowserPageSnapshot = {
  title: string;
  url: string;
  interactiveElements?: Array<{ ref: string; tag: string; text: string }>;
  visibleText?: string;
  links?: Array<{ text: string; href: string }>;
  pageHash?: string;
};

export class PotatoBrowserIntelligence {
  private lastPageHash = "";
  private defaultLevel: ProgressiveObservationLevel = 1;

  /**
   * Generates a progressive observation block matching the requested level of detail.
   */
  formatProgressiveObservation(
    snapshot: BrowserPageSnapshot,
    level: ProgressiveObservationLevel = this.defaultLevel,
  ): string {
    const currentHash = `${snapshot.url}::${snapshot.title}::${snapshot.visibleText?.slice(0, 100)}`;

    // Page Unchanged Deduplication
    if (this.lastPageHash && this.lastPageHash === currentHash && level < 3) {
      return `Page state unchanged: "${snapshot.title}" (${snapshot.url})`;
    }
    this.lastPageHash = currentHash;

    switch (level) {
      case 0:
        // LEVEL 0: Title + URL only (~15-25 tokens)
        return `Title: "${snapshot.title}"\nURL: ${snapshot.url}`;

      case 1: {
        // LEVEL 1: Title, URL, top interactive elements & brief text (~80-120 tokens)
        const parts = [`Title: "${snapshot.title}"\nURL: ${snapshot.url}`];
        if (snapshot.visibleText) {
          parts.push(`Summary: ${snapshot.visibleText.slice(0, 200).trim()}`);
        }
        if (snapshot.interactiveElements && snapshot.interactiveElements.length > 0) {
          const elements = snapshot.interactiveElements
            .slice(0, 6)
            .map((el) => `[${el.ref}] <${el.tag}> ${el.text.slice(0, 30)}`)
            .join("\n");
          parts.push(`Interactive Elements:\n${elements}`);
        }
        return parts.join("\n\n");
      }

      case 2: {
        // LEVEL 2: Larger relevant section + links (~200 tokens)
        const parts = [`Title: "${snapshot.title}"\nURL: ${snapshot.url}`];
        if (snapshot.visibleText) {
          parts.push(`Content:\n${snapshot.visibleText.slice(0, 450).trim()}`);
        }
        if (snapshot.links && snapshot.links.length > 0) {
          const links = snapshot.links
            .slice(0, 5)
            .map((l) => `- [${l.text.slice(0, 35)}](${l.href})`)
            .join("\n");
          parts.push(`Links:\n${links}`);
        }
        return parts.join("\n\n");
      }

      case 3:
      default: {
        // LEVEL 3: Full bounded extraction (~450 tokens)
        const parts = [`Title: "${snapshot.title}"\nURL: ${snapshot.url}`];
        if (snapshot.visibleText) {
          parts.push(`Content:\n${snapshot.visibleText.slice(0, 900).trim()}`);
        }
        return parts.join("\n\n");
      }
    }
  }

  /**
   * Directly extracts answers for trivial mechanical queries (title, URL, links).
   */
  tryDirectMechanicalAnswer(query: string, snapshot: BrowserPageSnapshot): string | null {
    const q = query.toLowerCase();

    if (q.includes("page title") || q.includes("what is the title") || q.includes("return the title") || q.includes("tell me the title")) {
      return `Page Title: "${snapshot.title}"`;
    }

    if (q.includes("current url") || q.includes("what is the url") || q.includes("page url")) {
      return `Current URL: ${snapshot.url}`;
    }

    if (q.includes("list links") || q.includes("show links") || q.includes("extract links")) {
      if (snapshot.links && snapshot.links.length > 0) {
        return snapshot.links.map((l) => `- ${l.text}: ${l.href}`).join("\n");
      }
    }

    return null;
  }

  reset(): void {
    this.lastPageHash = "";
  }
}
