import { createTombstone } from "../crdt/tombstone.js";

export function applyTombstonePolicy(engine, tableName, rowId, deletedBy, deletedAt) {
  const table = engine.tables.get(tableName);
  const row = table?.ensureRow(rowId);
  const originalData = row ? table.readRow(row) : { id: rowId };
  engine.tombstones.set(`${tableName}:${rowId}`, createTombstone(tableName, rowId, deletedBy, deletedAt, originalData));
}

