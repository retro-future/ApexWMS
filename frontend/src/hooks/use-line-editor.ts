"use client";

import { useState } from "react";

import type { Product } from "@/lib/types";

export type EditableLine = {
  /** Local row key; the server mints the real line id. */
  key: string;
  product: Product | null;
  quantity: number;
  /** Kept as typed text — a price is a string on the wire, never a float. */
  unitCost: string;
};

function emptyLine(): EditableLine {
  return { key: crypto.randomUUID(), product: null, quantity: 1, unitCost: "" };
}

/**
 * Add/remove/update state for a document's editable product lines — shared
 * by the purchase order and receipt forms, which both start from one blank
 * line and build a draft line list before the document exists server-side.
 */
export function useLineEditor() {
  const [lines, setLines] = useState<EditableLine[]>([emptyLine()]);

  function updateLine(key: string, patch: Partial<EditableLine>) {
    setLines((current) =>
      current.map((line) => (line.key === key ? { ...line, ...patch } : line)),
    );
  }

  function addLine() {
    setLines((current) => [...current, emptyLine()]);
  }

  function removeLine(key: string) {
    setLines((current) => current.filter((line) => line.key !== key));
  }

  const filled = lines.filter((line) => line.product !== null);

  return { lines, updateLine, addLine, removeLine, filled };
}
