import { increment, mergeClock } from "./crdt/causal_clock.js";
import { compareArbitration } from "./crdt/escrow.js";
import { CrdtTable } from "./relational/table.js";
import { applyTombstonePolicy } from "./relational/foreign_key.js";
import { rebuildSecondaryIndexes } from "./relational/index.js";
import { referenceSchema } from "./relational/schema.js";
import { executeSql } from "./sql/executor.js";
import { snapshotHash } from "./hash/snapshot.js";

export class CrdtEngine {
  constructor({ peerId, fkPolicy = "tombstone" }) {
    this.peerId = peerId;
    this.fkPolicy = fkPolicy;
    this.clock = {};
    this.knownPeers = new Set([peerId]);
    this.tables = new Map();
    this.tombstones = new Map();
    this.conflictLog = new Map();
    this.indexes = {};
    for (const [name, schema] of Object.entries(referenceSchema)) {
      this.tables.set(name, new CrdtTable(name, schema));
    }
  }

  tick() {
    this.clock = increment(this.clock, this.peerId);
    return { ...this.clock };
  }

  execute(sql, params = []) {
    return executeSql(this, sql, params);
  }

  query(sql, params = []) {
    return executeSql(this, sql, params);
  }

  insert(tableName, values) {
    const schema = referenceSchema[tableName];
    const clock = this.tick();
    const rowId = values[schema.primaryKey];
    this.tables.get(tableName).insert(rowId, values, this.peerId, clock);
    this.resolveConflicts();
  }

  update(tableName, rowId, values) {
    const clock = this.tick();
    this.tables.get(tableName).update(rowId, values, this.peerId, clock);
    const tombstone = this.tombstones.get(`${tableName}:${rowId}`);
    if (tombstone) tombstone.originalData = { ...tombstone.originalData, ...values };
  }

  delete(tableName, rowId) {
    const clock = this.tick();
    this.tables.get(tableName).delete(rowId);
    if (this.fkPolicy === "tombstone") applyTombstonePolicy(this, tableName, rowId, this.peerId, clock);
  }

  selectAll(tableName) {
    if (tableName === "_conflict_log") return [...this.conflictLog.values()].sort((a, b) => a.conflict_id.localeCompare(b.conflict_id));
    const table = this.tables.get(tableName);
    return table.allRows({ includeRemoved: this.fkPolicy === "tombstone" && tableName === "users" })
      .filter(({ row }) => !row.conflictRemoved)
      .map(({ data }) => data);
  }

  joinUsersOrders() {
    const users = new Map(this.selectAll("users").map((user) => [user.id, user]));
    return this.selectAll("orders").map((order) => {
      const tombstoned = this.tombstones.has(`users:${order.user_id}`);
      const user = tombstoned ? null : users.get(order.user_id);
      return {
        user_id: user?.id ?? null,
        email: user?.email ?? null,
        name: user?.name ?? null,
        order_id: order.id,
        status: order.status,
        total_cents: order.total_cents
      };
    });
  }

  resolveConflicts() {
    for (const table of this.tables.values()) {
      for (const row of table.rows.values()) row.conflictRemoved = false;
    }
    this.conflictLog = new Map();
    this.resolveUnique("users", "email", "users_email_key");
    for (const [key, tombstone] of this.tombstones.entries()) {
      const [tableName, rowId] = key.split(":");
      const table = this.tables.get(tableName);
      const row = table?.rows.get(rowId);
      if (row) tombstone.originalData = table.readRow(row);
    }
  }

  resolveUnique(tableName, column, constraintName) {
    const table = this.tables.get(tableName);
    const groups = new Map();
    for (const item of table.allRows({ includeRemoved: true })) {
      if (item.row.conflictRemoved) continue;
      const values = new Set((item.row.cells[column] ?? []).map((version) => version.value).filter((value) => value != null));
      for (const value of values) {
        if (!groups.has(value)) groups.set(value, []);
        groups.get(value).push({ id: item.data.id, row: item.row, data: item.data });
      }
    }
    for (const [value, rows] of groups.entries()) {
      if (rows.length < 2) continue;
      rows.sort((a, b) => compareArbitration({ id: a.id, cells: a.row.cells }, { id: b.id, cells: b.row.cells }));
      const winner = rows[0];
      for (const loser of rows.slice(1)) {
        loser.row.conflictRemoved = true;
        const conflictId = `${tableName}:${constraintName}:${value}:${loser.id}`;
        this.conflictLog.set(conflictId, {
          conflict_id: conflictId,
          table_name: tableName,
          constraint_name: constraintName,
          conflicting_value: String(value),
          winner_row_id: String(winner.id),
          loser_row_id: String(loser.id),
          loser_row_data: JSON.stringify(loser.data, Object.keys(loser.data).sort()),
          detected_at: "logical-time"
        });
      }
    }
  }

  rebuildIndexes() {
    this.indexes = rebuildSecondaryIndexes(this);
  }

  exportState() {
    return JSON.parse(JSON.stringify({
      peerId: this.peerId,
      clock: this.clock,
      knownPeers: [...this.knownPeers],
      tables: [...this.tables.entries()].map(([name, table]) => [name, [...table.rows.entries()].map(([rowId, row]) => [rowId, {
        ...row,
        addTags: [...row.addTags.entries()],
        removedTags: [...row.removedTags]
      }])]),
      tombstones: [...this.tombstones.entries()],
      conflictLog: [...this.conflictLog.entries()]
    }));
  }

  importState(state) {
    this.clock = mergeClock(this.clock, state.clock);
    for (const peer of state.knownPeers ?? [state.peerId]) this.knownPeers.add(peer);
    this.knownPeers.add(state.peerId);
    for (const [name, rows] of state.tables) {
      const table = this.tables.get(name);
      const incoming = new CrdtTable(name, referenceSchema[name]);
      for (const [rowId, row] of rows) {
        row.addTags = new Map(row.addTags);
        row.removedTags = new Set(row.removedTags);
        incoming.rows.set(rowId, row);
      }
      table.merge(incoming);
    }
    for (const [key, tombstone] of state.tombstones) this.mergeTombstone(key, tombstone);
    for (const [key, conflict] of state.conflictLog) this.conflictLog.set(key, conflict);
  }

  mergeTombstone(key, incoming) {
    const existing = this.tombstones.get(key);
    if (!existing) {
      this.tombstones.set(key, incoming);
      return;
    }
    existing.deletedAt = mergeClock(existing.deletedAt ?? {}, incoming.deletedAt ?? {});
    existing.deletedBy = String(existing.deletedBy ?? "").localeCompare(String(incoming.deletedBy ?? "")) <= 0
      ? existing.deletedBy
      : incoming.deletedBy;
    existing.originalData = incoming.originalData ?? existing.originalData;
  }

  materializeForHash() {
    const tables = {};
    for (const [name, table] of this.tables.entries()) {
      tables[name] = table.allRows({ includeRemoved: true }).map(({ row, data, present }) => ({
        id: row.id,
        present,
        conflictRemoved: row.conflictRemoved,
        data,
        cells: row.cells
      }));
    }
    return {
      fkPolicy: this.fkPolicy,
      tables,
      tombstones: [...this.tombstones.entries()].sort(),
      conflictLog: [...this.conflictLog.entries()].sort()
    };
  }

  snapshotHash() {
    return snapshotHash(this);
  }

  metadataStats() {
    let maxClockEntries = 0;
    for (const table of this.tables.values()) {
      for (const row of table.rows.values()) {
        for (const versions of Object.values(row.cells)) {
          for (const version of versions) maxClockEntries = Math.max(maxClockEntries, Object.keys(version.clock).length);
        }
      }
    }
    return { peers: this.knownPeers.size, max_clock_entries_per_version: maxClockEntries };
  }
}
