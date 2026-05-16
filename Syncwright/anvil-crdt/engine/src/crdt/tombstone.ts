import { cloneClock } from "./causal_clock.js";

export function createTombstone(tableId, rowId, deletedBy, deletedAt, originalData) {
  return {
    tableId,
    rowId,
    deletedBy,
    deletedAt: cloneClock(deletedAt),
    originalData: { ...originalData }
  };
}

