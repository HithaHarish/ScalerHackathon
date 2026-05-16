from __future__ import annotations

import copy
import hashlib
import itertools
import json
import re
from dataclasses import dataclass, field
from typing import Any


SqlValue = str | int | None
Clock = dict[str, int]


def _stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _clock_key(clock: Clock) -> str:
    return json.dumps(sorted(clock.items()), separators=(",", ":"))


def _clock_sum(clock: Clock) -> int:
    return sum(clock.values())


def _merge_clock(left: Clock, right: Clock) -> Clock:
    out = dict(left)
    for peer, value in right.items():
        out[peer] = max(out.get(peer, 0), value)
    return out


def _logical_peer_id(peer_id: str) -> str:
    scoped = str(peer_id).rsplit(":", 1)[-1]
    return scoped.split("@", 1)[0]


def _canonical_clock(clock: Clock) -> Clock:
    out: Clock = {}
    for peer, value in clock.items():
        logical = _logical_peer_id(peer)
        out[logical] = max(out.get(logical, 0), value)
    return out


def _dominates(left: Clock, right: Clock) -> bool:
    greater = False
    for peer in set(left) | set(right):
        lv = left.get(peer, 0)
        rv = right.get(peer, 0)
        if lv < rv:
            return False
        greater = greater or lv > rv
    return greater


def _split_csv(text: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    quoted = False
    depth = 0
    for ch in text:
        if ch == "'":
            quoted = not quoted
        elif ch == "(" and not quoted:
            depth += 1
        elif ch == ")" and not quoted and depth:
            depth -= 1
        if ch == "," and not quoted and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def _parse_value(raw: str, params: list[Any]) -> SqlValue:
    text = raw.strip()
    if text == "?":
        return params.pop(0) if params else None
    if text.lower() == "null":
        return None
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if len(text) >= 2 and text[0] == "'" and text[-1] == "'":
        return text[1:-1].replace("''", "'")
    return text


@dataclass
class Version:
    value: SqlValue
    clock: Clock
    writer_id: str

    def key(self) -> tuple[str, str, str]:
        return self.writer_id, _clock_key(self.clock), _stable(self.value)

    def to_json(self) -> dict[str, Any]:
        return {"value": self.value, "clock": dict(self.clock), "writer_id": self.writer_id}

    @staticmethod
    def from_json(data: dict[str, Any]) -> "Version":
        return Version(data["value"], dict(data["clock"]), data["writer_id"])


def _merge_register(left: list[Version], right: list[Version]) -> list[Version]:
    versions = {version.key(): version for version in [*left, *right]}.values()
    kept = [
        candidate
        for candidate in versions
        if not any(other is not candidate and _dominates(other.clock, candidate.clock) for other in versions)
    ]
    return sorted(kept, key=lambda version: (-_clock_sum(version.clock), version.writer_id, _stable(version.value)))


def _read_register(versions: list[Version]) -> SqlValue:
    return _merge_register(versions, [])[0].value if versions else None


@dataclass
class TableSchema:
    columns: list[str]
    pk: str
    defaults: dict[str, SqlValue] = field(default_factory=dict)
    unique: list[tuple[str, tuple[str, ...]]] = field(default_factory=list)
    fks: list[tuple[str, str, str]] = field(default_factory=list)


@dataclass
class Row:
    row_id: str
    add_tags: dict[str, dict[str, Any]] = field(default_factory=dict)
    removed_tags: set[str] = field(default_factory=set)
    cells: dict[str, list[Version]] = field(default_factory=dict)
    conflict_removed: bool = False
    unique_overrides: dict[str, SqlValue] = field(default_factory=dict)

    def present(self) -> bool:
        return any(key not in self.removed_tags for key in self.add_tags)

    def raw_read(self, schema: TableSchema) -> dict[str, SqlValue]:
        return {column: _read_register(self.cells.get(column, [])) for column in schema.columns}

    def read(self, schema: TableSchema) -> dict[str, SqlValue]:
        data = self.raw_read(schema)
        for column, value in self.unique_overrides.items():
            if column in data:
                data[column] = value
        return data

    def to_json(self) -> dict[str, Any]:
        return {
            "row_id": self.row_id,
            "add_tags": copy.deepcopy(self.add_tags),
            "removed_tags": sorted(self.removed_tags),
            "cells": {col: [version.to_json() for version in versions] for col, versions in self.cells.items()},
            "conflict_removed": self.conflict_removed,
            "unique_overrides": copy.deepcopy(self.unique_overrides),
        }

    @staticmethod
    def from_json(data: dict[str, Any]) -> "Row":
        return Row(
            row_id=data["row_id"],
            add_tags=copy.deepcopy(data["add_tags"]),
            removed_tags=set(data["removed_tags"]),
            cells={col: [Version.from_json(v) for v in versions] for col, versions in data["cells"].items()},
            conflict_removed=data["conflict_removed"],
            unique_overrides=copy.deepcopy(data.get("unique_overrides", {})),
        )


class Peer:
    def __init__(self, peer_id: str, fk_policy: str) -> None:
        self.peer_id = peer_id
        self.fk_policy = fk_policy
        self.clock: Clock = {}
        self.known_peers = {peer_id}
        self.schemas: dict[str, TableSchema] = {}
        self.tables: dict[str, dict[str, Row]] = {}
        self.tombstones: dict[str, dict[str, Any]] = {}
        self.conflict_log: dict[str, dict[str, Any]] = {}

    def tick(self) -> Clock:
        self.clock[self.peer_id] = self.clock.get(self.peer_id, 0) + 1
        return dict(self.clock)

    def apply_schema(self, stmt: str) -> None:
        text = stmt.strip()
        if re.match(r"^create\s+index\b", text, re.I):
            return
        match = re.match(r"create\s+table\s+(\w+)\s*\((.*)\)\s*$", text, re.I | re.S)
        if not match:
            return
        table, body = match.groups()
        columns: list[str] = []
        pk = "id"
        defaults: dict[str, SqlValue] = {}
        unique: list[tuple[str, tuple[str, ...]]] = []
        fks: list[tuple[str, str, str]] = []
        for item in _split_csv(body):
            part = " ".join(item.split())
            unique_match = re.match(r"(?:constraint\s+(\w+)\s+)?unique\s*\(([^)]*)\)", part, re.I)
            if unique_match:
                constraint = unique_match.group(1) or f"{table}_{'_'.join(c.strip() for c in unique_match.group(2).split(','))}_key"
                unique.append((constraint, tuple(c.strip() for c in unique_match.group(2).split(","))))
                continue
            col_match = re.match(r"(\w+)\s+(.+)$", part, re.I)
            if not col_match:
                continue
            col, rest = col_match.groups()
            columns.append(col)
            if re.search(r"\bprimary\s+key\b", rest, re.I):
                pk = col
            if re.search(r"\bunique\b", rest, re.I):
                unique.append((f"{table}_{col}_key", (col,)))
            default_match = re.search(r"\bdefault\s+([^\s]+)", rest, re.I)
            if default_match:
                defaults[col] = _parse_value(default_match.group(1), [])
            fk_match = re.search(r"\breferences\s+(\w+)\s*\((\w+)\)", rest, re.I)
            if fk_match:
                fks.append((col, fk_match.group(1), fk_match.group(2)))
        self.schemas[table] = TableSchema(columns=columns, pk=pk, defaults=defaults, unique=unique, fks=fks)
        self.tables.setdefault(table, {})

    def ensure_row(self, table: str, row_id: str) -> Row:
        rows = self.tables.setdefault(table, {})
        if row_id not in rows:
            rows[row_id] = Row(row_id)
        return rows[row_id]

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        text = sql.strip().rstrip(";")
        values = list(params)
        if re.match(r"^create\s+", text, re.I):
            self.apply_schema(text)
            return
        insert = re.match(r"insert\s+into\s+(\w+)(?:\s*\(([^)]*)\))?\s+values\s*\((.*)\)$", text, re.I | re.S)
        if insert:
            table, cols_text, vals_text = insert.groups()
            schema = self.schemas[table]
            columns = [c.strip() for c in _split_csv(cols_text)] if cols_text else schema.columns
            parsed = [_parse_value(raw, values) for raw in _split_csv(vals_text)]
            self.insert(table, dict(zip(columns, parsed)))
            return
        update = re.match(r"update\s+(\w+)\s+set\s+(.+)\s+where\s+id\s*=\s*(.+)$", text, re.I | re.S)
        if update:
            table, assigns, raw_id = update.groups()
            changes = {}
            for assignment in _split_csv(assigns):
                col, raw = assignment.split("=", 1)
                changes[col.strip()] = _parse_value(raw, values)
            self.update(table, str(_parse_value(raw_id, values)), changes)
            return
        delete = re.match(r"delete\s+from\s+(\w+)\s+where\s+id\s*=\s*(.+)$", text, re.I)
        if delete:
            table, raw_id = delete.groups()
            self.delete(table, str(_parse_value(raw_id, values)))
            return
        raise ValueError(f"unsupported SQL: {sql}")

    def insert(self, table: str, values: dict[str, SqlValue]) -> None:
        schema = self.schemas[table]
        full = {**schema.defaults, **values}
        row_id = str(full[schema.pk])
        clock = self.tick()
        row = self.ensure_row(table, row_id)
        tag = {"peer_id": self.peer_id, "clock": clock}
        row.add_tags[f"{self.peer_id}:{_clock_key(clock)}"] = tag
        for column in schema.columns:
            if column in full:
                row.cells[column] = _merge_register(
                    row.cells.get(column, []),
                    [Version(full[column], clock, self.peer_id)],
                )
        self.resolve_conflicts()

    def update(self, table: str, row_id: str, values: dict[str, SqlValue]) -> None:
        schema = self.schemas[table]
        clock = self.tick()
        row = self.ensure_row(table, row_id)
        for column, value in values.items():
            row.cells[column] = _merge_register(row.cells.get(column, []), [Version(value, clock, self.peer_id)])
        key = f"{table}:{row_id}"
        if key in self.tombstones:
            self.tombstones[key]["originalData"] = row.raw_read(schema)
        self.resolve_conflicts()

    def delete(self, table: str, row_id: str) -> None:
        clock = self.tick()
        row = self.ensure_row(table, row_id)
        row.removed_tags.update(row.add_tags)
        if self.fk_policy == "tombstone":
            self.merge_tombstone(table, row_id, clock, origin="explicit", deleted_by=self.peer_id)
        self.apply_fk_delete(table, row_id, clock)
        self.resolve_conflicts()

    def apply_fk_delete(self, parent_table: str, parent_id: str, clock: Clock | None = None) -> None:
        delete_clock = dict(clock or self.clock)
        for child_table, schema in list(self.schemas.items()):
            for col, ref_table, _ref_col in schema.fks:
                if ref_table != parent_table:
                    continue
                for child_id, child in list(self.tables.get(child_table, {}).items()):
                    if child.read(schema).get(col) != parent_id:
                        continue
                    if self.fk_policy == "cascade":
                        child.removed_tags.update(child.add_tags)
                        self.apply_fk_delete(child_table, child_id, delete_clock)
                    elif self.fk_policy == "orphan":
                        self.update(child_table, child_id, {col: None})
                    elif self.fk_policy == "tombstone":
                        if self.should_preserve_tombstone_child(parent_table, child_table, parent_id):
                            continue
                        child.removed_tags.update(child.add_tags)
                        self.merge_tombstone(
                            child_table,
                            child_id,
                            delete_clock,
                            origin="fk",
                            deleted_by=self.tombstones.get(f"{parent_table}:{parent_id}", {}).get("deletedBy", self.peer_id),
                        )
                        self.apply_fk_delete(child_table, child_id, delete_clock)

    def table_has_dependents(self, table: str) -> bool:
        return any(
            ref_table == table
            for schema in self.schemas.values()
            for _col, ref_table, _ref_col in schema.fks
        )

    def should_preserve_tombstone_child(self, parent_table: str, child_table: str, parent_id: str) -> bool:
        parent_tombstone = self.tombstones.get(f"{parent_table}:{parent_id}")
        return (
            bool(parent_tombstone)
            and parent_tombstone.get("origin", "explicit") == "explicit"
            and not self.table_has_dependents(child_table)
        )

    def merge_tombstone(
        self,
        table: str,
        row_id: str,
        clock: Clock,
        *,
        origin: str = "explicit",
        deleted_by: str | None = None,
    ) -> None:
        schema = self.schemas.get(table)
        row = self.tables.get(table, {}).get(row_id)
        original = row.raw_read(schema) if schema and row else {"id": row_id}
        key = f"{table}:{row_id}"
        existing = self.tombstones.get(key)
        incoming = {
            "tableId": table,
            "rowId": row_id,
            "deletedBy": deleted_by or self.peer_id,
            "deletedAt": dict(clock),
            "originalData": original,
            "origin": origin,
        }
        if not existing:
            self.tombstones[key] = incoming
            return
        existing["deletedAt"] = _merge_clock(existing.get("deletedAt", {}), incoming["deletedAt"])
        existing["deletedBy"] = min(str(existing.get("deletedBy", "")), str(incoming["deletedBy"]))
        existing["origin"] = "explicit" if "explicit" in {existing.get("origin"), incoming["origin"]} else "fk"
        existing["originalData"] = incoming["originalData"]

    def visible_rows(self, table: str) -> list[dict[str, Any]]:
        schema = self.schemas[table]
        rows = []
        for row_id, row in sorted(self.tables.get(table, {}).items()):
            if row.present():
                rows.append(row.read(schema))
        return rows

    def resolve_conflicts(self) -> None:
        for rows in self.tables.values():
            for row in rows.values():
                row.conflict_removed = False
                row.unique_overrides = {}
        self.conflict_log = {}
        self.repair_foreign_keys()
        for table, schema in self.schemas.items():
            for constraint, columns in schema.unique:
                self.resolve_unique(table, constraint, columns)
        self.repair_foreign_keys()

    def resolve_unique(self, table: str, constraint: str, columns: tuple[str, ...]) -> None:
        schema = self.schemas[table]
        groups: dict[tuple[Any, ...], list[tuple[str, Row, dict[str, Any]]]] = {}
        for row_id, row in self.tables.get(table, {}).items():
            if not row.present():
                continue
            data = row.raw_read(schema)
            keys = [self.unique_values(row, col) for col in columns]
            if not keys or any(not values for values in keys):
                continue
            for key in itertools.product(*[sorted(values, key=_stable) for values in keys]):
                groups.setdefault(tuple(key), []).append((row_id, row, data))
        for key, contenders in sorted(groups.items(), key=lambda item: _stable(item[0])):
            if len(contenders) < 2:
                continue
            contenders.sort(key=lambda item: self.arbitration_tuple(item[1], item[0]))
            winner_id = contenders[0][0]
            for loser_id, loser_row, loser_data in contenders[1:]:
                loser_row.conflict_removed = True
                rewrite_column = columns[-1]
                rewrite_value = key[-1]
                loser_row.unique_overrides[rewrite_column] = self.conflict_value(
                    table,
                    constraint,
                    loser_id,
                    rewrite_column,
                    rewrite_value,
                )
                conflict_id = f"{table}:{constraint}:{_stable(key)}:{loser_id}"
                self.conflict_log[conflict_id] = {
                    "conflict_id": conflict_id,
                    "table_name": table,
                    "constraint_name": constraint,
                    "conflicting_value": _stable(key[0] if len(key) == 1 else key),
                    "winner_row_id": winner_id,
                    "loser_row_id": loser_id,
                    "loser_row_data": _stable(loser_data),
                    "detected_at": "logical-time",
                }

    def unique_values(self, row: Row, column: str) -> set[SqlValue]:
        if column in row.unique_overrides:
            return {row.unique_overrides[column]}
        return {version.value for version in row.cells.get(column, []) if version.value is not None}

    def conflict_value(
        self,
        table: str,
        constraint: str,
        row_id: str,
        column: str,
        value: SqlValue,
    ) -> SqlValue:
        suffix = hashlib.sha256(_stable([table, constraint, row_id, column, value]).encode("utf-8")).hexdigest()[:12]
        if isinstance(value, str):
            return f"{value}#conflict:{row_id}:{suffix}"
        return f"__conflict__:{row_id}:{suffix}"

    def repair_foreign_keys(self) -> None:
        if self.fk_policy not in {"cascade", "tombstone"}:
            return
        changed = True
        while changed:
            changed = False
            for child_table, schema in list(self.schemas.items()):
                for col, parent_table, _parent_col in schema.fks:
                    parent_schema = self.schemas.get(parent_table)
                    if parent_schema is None:
                        continue
                    for child_id, child in list(self.tables.get(child_table, {}).items()):
                        if not child.present():
                            continue
                        parent_id = child.read(schema).get(col)
                        if parent_id is None:
                            continue
                        parent = self.tables.get(parent_table, {}).get(str(parent_id))
                        if parent and parent.present():
                            continue
                        parent_tombstone = self.tombstones.get(f"{parent_table}:{parent_id}", {})
                        parent_deleted = bool(parent_tombstone) or (
                            parent is not None and bool(parent.add_tags) and not parent.present()
                        )
                        if not parent_deleted:
                            continue
                        if self.fk_policy == "tombstone" and self.should_preserve_tombstone_child(
                            parent_table,
                            child_table,
                            str(parent_id),
                        ):
                            continue
                        child.removed_tags.update(child.add_tags)
                        repair_clock = parent_tombstone.get("deletedAt", self.clock)
                        if self.fk_policy == "tombstone":
                            self.merge_tombstone(
                                child_table,
                                child_id,
                                repair_clock,
                                origin="fk",
                                deleted_by=parent_tombstone.get("deletedBy", self.peer_id),
                            )
                        changed = True

    def arbitration_tuple(self, row: Row, row_id: str) -> tuple[int, str, str]:
        versions = [version for versions in row.cells.values() for version in versions]
        if not versions:
            return 0, "", row_id
        return min(_clock_sum(version.clock) for version in versions), sorted(v.writer_id for v in versions)[0], row_id

    def export_state(self) -> dict[str, Any]:
        return {
            "peer_id": self.peer_id,
            "fk_policy": self.fk_policy,
            "clock": dict(self.clock),
            "known_peers": sorted(self.known_peers),
            "schemas": copy.deepcopy(self.schemas),
            "tables": {
                table: {row_id: row.to_json() for row_id, row in rows.items()}
                for table, rows in self.tables.items()
            },
            "tombstones": copy.deepcopy(self.tombstones),
        }

    def import_state(self, state: dict[str, Any]) -> None:
        self.clock = _merge_clock(self.clock, state["clock"])
        self.known_peers.update(state.get("known_peers", []))
        self.known_peers.add(state["peer_id"])
        self.schemas.update(copy.deepcopy(state.get("schemas", {})))
        for table in self.schemas:
            self.tables.setdefault(table, {})
        for table, rows in state["tables"].items():
            for row_id, incoming_json in rows.items():
                incoming = Row.from_json(incoming_json)
                local = self.ensure_row(table, row_id)
                local.add_tags.update(copy.deepcopy(incoming.add_tags))
                local.removed_tags.update(incoming.removed_tags)
                local.conflict_removed = local.conflict_removed or incoming.conflict_removed
                for column, versions in incoming.cells.items():
                    local.cells[column] = _merge_register(local.cells.get(column, []), versions)
        for key, incoming in state.get("tombstones", {}).items():
            table, row_id = key.split(":", 1)
            self.merge_tombstone(
                table,
                row_id,
                incoming.get("deletedAt", {}),
                origin=incoming.get("origin", "explicit"),
                deleted_by=incoming.get("deletedBy"),
            )
            self.tombstones[key]["originalData"] = copy.deepcopy(
                incoming.get("originalData", self.tombstones[key].get("originalData"))
            )
        self.resolve_conflicts()

    def snapshot_state(self) -> dict[str, list[dict[str, Any]]]:
        state = {table: self.visible_rows(table) for table in sorted(self.schemas)}
        if self.conflict_log:
            state["_conflict_log"] = [copy.deepcopy(row) for _, row in sorted(self.conflict_log.items())]
        if self.tombstones:
            state["_tombstones"] = [{"key": key, **copy.deepcopy(value)} for key, value in sorted(self.tombstones.items())]
        return state

    def snapshot_hash(self) -> str:
        return hashlib.sha256(_stable(self.snapshot_state_for_hash()).encode("utf-8")).hexdigest()

    def snapshot_state_for_hash(self) -> dict[str, Any]:
        state = copy.deepcopy(self.snapshot_state())
        for tombstone in state.get("_tombstones", []):
            if "deletedBy" in tombstone:
                tombstone["deletedBy"] = _logical_peer_id(tombstone["deletedBy"])
            if "deletedAt" in tombstone:
                tombstone["deletedAt"] = _canonical_clock(tombstone["deletedAt"])
        return state


class Engine:
    def __init__(self, fk_policy: str = "tombstone", **_: Any) -> None:
        self.fk_policy = fk_policy
        self.peers: dict[str, Peer] = {}

    def open_peer(self, peer_id: str) -> None:
        self.peers[peer_id] = Peer(peer_id, self.fk_policy)

    def peer(self, peer_id: str) -> Peer:
        if peer_id not in self.peers:
            self.open_peer(peer_id)
        return self.peers[peer_id]

    def apply_schema(self, peer_id: str, stmts: list[str] | tuple[str, ...] | str) -> None:
        if isinstance(stmts, str):
            stmts = [stmts]
        peer = self.peer(peer_id)
        for stmt in stmts:
            peer.apply_schema(stmt)

    def execute(self, peer_id: str, sql: str, params: tuple[Any, ...] = ()) -> None:
        self.peer(peer_id).execute(sql, params)

    def sync(self, peer_a: str, peer_b: str) -> None:
        left = self.peer(peer_a)
        right = self.peer(peer_b)
        left_state = left.export_state()
        right_state = right.export_state()
        left.import_state(right_state)
        right.import_state(left_state)

    def snapshot_hash(self, peer_id: str) -> str:
        return self.peer(peer_id).snapshot_hash()

    def snapshot_state(self, peer_id: str) -> dict[str, list[dict[str, Any]]]:
        return self.peer(peer_id).snapshot_state()

    def close(self) -> None:
        self.peers.clear()
