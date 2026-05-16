import { mergeRegister, readRegister, writeRegister } from "../crdt/mv_register.js";
import { tagKey } from "../crdt/or_set.js";

export class CrdtTable {
  constructor(name, schema) {
    this.name = name;
    this.schema = schema;
    this.rows = new Map();
  }

  ensureRow(rowId) {
    if (!this.rows.has(rowId)) {
      this.rows.set(rowId, { id: rowId, addTags: new Map(), removedTags: new Set(), cells: {}, conflictRemoved: false });
    }
    return this.rows.get(rowId);
  }

  insert(rowId, values, peerId, clock) {
    const row = this.ensureRow(rowId);
    const tag = { peerId, clock: { ...clock } };
    row.addTags.set(tagKey(tag), tag);
    for (const [column, value] of Object.entries(values)) {
      row.cells[column] = writeRegister(row.cells[column] ?? [], value, peerId, clock);
    }
  }

  update(rowId, values, peerId, clock) {
    const row = this.ensureRow(rowId);
    for (const [column, value] of Object.entries(values)) {
      row.cells[column] = writeRegister(row.cells[column] ?? [], value, peerId, clock);
    }
  }

  delete(rowId) {
    const row = this.ensureRow(rowId);
    for (const key of row.addTags.keys()) row.removedTags.add(key);
  }

  isPresent(row) {
    if (row.conflictRemoved) return false;
    return [...row.addTags.keys()].some((key) => !row.removedTags.has(key));
  }

  readRow(row) {
    const out = {};
    for (const column of this.schema.columns) out[column] = readRegister(row.cells[column] ?? []);
    return out;
  }

  merge(other) {
    for (const [rowId, incoming] of other.rows.entries()) {
      const row = this.ensureRow(rowId);
      for (const [key, tag] of incoming.addTags.entries()) row.addTags.set(key, tag);
      for (const key of incoming.removedTags) row.removedTags.add(key);
      row.conflictRemoved = row.conflictRemoved || incoming.conflictRemoved;
      for (const [column, versions] of Object.entries(incoming.cells)) {
        row.cells[column] = mergeRegister(row.cells[column] ?? [], versions);
      }
    }
  }

  allRows({ includeRemoved = false } = {}) {
    return [...this.rows.values()]
      .filter((row) => includeRemoved || this.isPresent(row))
      .map((row) => ({ row, data: this.readRow(row), present: this.isPresent(row) }))
      .sort((a, b) => String(a.data.id ?? a.row.id).localeCompare(String(b.data.id ?? b.row.id)));
  }
}

