/**
 * What the two documents that only take goods away have in common.
 *
 * A supplier return and a write-off carry the same lines, the same lifecycle
 * and the same confirm invariant; they stay two documents because §5.10
 * reports them in different columns and they send the handset to different
 * terminal statuses. So the shared part is stated once, here.
 *
 * Pure functions over the payload, deliberately free of React.
 */

import type {
  RemovalLine,
  SupplierReturn,
  SupplierReturnReason,
  WriteOff,
  WriteOffReason,
} from "@/lib/types";

/** Either removal document, where only the shared fields are read. */
export type Removal = SupplierReturn | WriteOff;

/** The path segment, and the react-query key prefix that follows from it. */
export type RemovalResource = "supplier-returns" | "write-offs";

export function isSerialLine(line: RemovalLine): boolean {
  return line.trackingType === "serial";
}

/**
 * The one thing the server refuses a removal's confirm over: an empty
 * document. Computing it here is not an enforcement point — it exists so the
 * button can say why it is disabled instead of the operator finding out by
 * pressing it.
 */
export function canConfirmRemoval(removal: Removal): boolean {
  return removal.lineCount > 0;
}

/** How many handsets and how many loose items the document moves. */
export function removalTotals(removal: Removal): {
  units: number;
  quantity: number;
} {
  return removal.lines.reduce(
    (running, line) => ({
      units: running.units + (isSerialLine(line) ? line.quantity : 0),
      quantity: running.quantity + (isSerialLine(line) ? 0 : line.quantity),
    }),
    { units: 0, quantity: 0 },
  );
}

export const SUPPLIER_RETURN_REASON_COLOR: Record<SupplierReturnReason, string> = {
  defective: "red",
  unsold: "blue",
  wrong_item: "orange",
  other: "gray",
};

export const WRITE_OFF_REASON_COLOR: Record<WriteOffReason, string> = {
  damage: "orange",
  loss: "yellow",
  theft: "red",
  other: "gray",
};
