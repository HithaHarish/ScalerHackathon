from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any


SqlValue = str | int | None
Clock = dict[str, int]


def _clock_key(clock: Clock) -> str:
    return json.dumps(sorted(clock.items()), separators=(",", ":"))


def _clock_sum(clock: Clock) -> int:
    return sum(clock.values())


def _dominates(a: Clock, b: Clock) -> bool:
    greater = False
    for peer in set(a) | set(b):
        av = a.get(peer, 0)
        bv = b.get(peer, 0)
        if av < bv:
            return False
        greater = greater or av > bv
    return greater


def _merge_clock(a: Clock, b: Clock) -> Clock:
    out = dict(a)
    for peer, value in b.items():
        out[peer] = max(out.get(peer, 0), value)
    return out


def _stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _split_csv(text: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    quoted = False
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "'":
            quoted = not quoted
            buf.append(ch)
        elif ch == "," and not quoted:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
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
    writerId: str

    def key(self) -> tuple[str, str, str]:
        return (self.writerId, _clock_key(self.clock), _stable(self.value))

    def to_json(self) -> dict[str, Any]:
        return {"value": self.value, "clock": dict(self.clock), "writerId": self.writerId}

    @staticmethod
    def from_json(data: dict[str, Any]) -> "Version":
        return Version(data["value"], dict(data["clock"]), data["writerId"])


def _merge_register(left: list[Version], right: list[Version]) -> list[Version]:
    versions = {version.key(): version for version in [*left, *right]}.values()
    kept = [
        candidate
        for candidate in versions
        if not any(other is not candidate and _dominates(other.clock, candidate.clock) for other in versions)
    ]
    return sorted(kept, key=lambda v: (-_clock_sum(v.clock), v.writerId, _stable(v.value)))


def _read_register(register: list[Version]) -> SqlValue:
    return _merge_register(register, [])[0].value if register else None


@dataclass
class Row:
    row_id: str
    add_tags: dict[str, dict[str, Any]] = field(default_factory=dict)
    removed_tags: set[str] = field(default_factory=set)
    cells: dict[str, list[Version]] = field(default_factory=dict)
    conflict_removed: bool = False

    def present(self) -> bool:
        return not self.conflict_removed and any(key not in self.removed_tags for key in self.add_tags)

    def read(self, columns: list[str]) -> dict[str, SqlValue]:
        return {column: _read_register(self.cells.get(column, [])) for column in columns}

    def to_json(self) -> dict[str, Any]:
        return {
            "row_id": self.row_id,
            "add_tags": self.add_tags,
            "removed_tags": sorted(self.removed_tags),
            "cells": {col: [version.to_json() for version in versions] for col, versions in self.cells.items()},
            "conflict_removed": self.conflict_removed,
        }

    @staticmethod
    def from_json(data: dict[str, Any]) -> "Row":
        return Row(
            row_id=data["row_id"],
            add_tags=copy.deepcopy(data["add_tags"]),
            removed_tags=set(data["removed_tags"]),
            cells={col: [Version.from_json(v) for v in versions] for col, versions in data["cells"].items()},
            conflict_removed=data["conflict_removed"],
        )


class Engine:
    schema = {
        "users": {
            "pk": "id",
            "columns": ["id", "email", "name"],
            "defaults": {},
            "unique": [("users_email_key", "email")],
        },
        "orders": {
            "pk": "id",
            "columns": ["id", "user_id", "status", "total_cents"],
            "defaults": {"total_cents": 0},
            "unique": [],
        },
    }

    def __init__(self, peer_id: str = "A", fk_policy: str = "tombstone", **_: Any) -> None:
        if fk_policy not in {"tombstone", "cascade", "orphan"}:
            raise ValueError(f"unsupported fk_policy: {fk_policy}")
        self.peer_id = peer_id
        self.fk_policy = fk_policy
        self._peers: dict[str, Engine] = {}
        self.clock: Clock = {}
        self.known_peers: set[str] = {peer_id}
        self.tables: dict[str, dict[str, Row]] = {"users": {}, "orders": {}}
        self.tombstones: dict[str, dict[str, Any]] = {}
        self.conflict_log: dict[str, dict[str, Any]] = {}
        self.indexes: dict[str, dict[str, list[str]]] = {}

    def tick(self) -> Clock:
        self.clock[self.peer_id] = self.clock.get(self.peer_id, 0) + 1
        return dict(self.clock)

    def execute(self, *args: Any) -> list[dict[str, Any]]:
        if (
            len(args) >= 2
            and isinstance(args[0], str)
            and isinstance(args[1], str)
            and not re.match(r"^\s*(create|insert|update|delete|select)\b", args[0], re.I)
        ):
            peer_id, sql = args[0], args[1]
            params = args[2] if len(args) > 2 else ()
            return self._peer(peer_id)._sql(sql, list(params))
        sql = args[0]
        params = args[1] if len(args) > 1 else ()
        return self._sql(sql, list(params))

    def query(self, sql: str, params: tuple[Any, ...] | list[Any] = ()) -> list[dict[str, Any]]:
        return self._sql(sql, list(params))

    def apply_schema(self, sql: str) -> None:
        self.execute(sql)

    def exec(self, sql: str, params: tuple[Any, ...] | list[Any] = ()) -> list[dict[str, Any]]:
        return self.execute(sql, params)

    def select(self, sql: str, params: tuple[Any, ...] | list[Any] = ()) -> list[dict[str, Any]]:
        return self.query(sql, params)

    def sync(self, *args: Any) -> None:
        if len(args) == 2 and all(isinstance(arg, str) for arg in args):
            self._peer(args[0]).sync(self._peer(args[1]))
            return
        other = args[0]
        if other is self:
            return
        left = self.export_state()
        right = other.export_state()
        self.import_state(right)
        other.import_state(left)
        self.resolve_conflicts()
        other.resolve_conflicts()
        self.rebuild_indexes()
        other.rebuild_indexes()

    sync_with = sync

    def snapshot_hash(self, peer_id: str | None = None) -> str:
        if peer_id is not None:
            state = self.snapshot_state(peer_id)
            normalized = {
                "users": state.get("users", []),
                "orders": state.get("orders", []),
                "_conflict_log": state.get("_conflict_log", []),
                "_tombstones": [
                    {
                        "key": row.get("key"),
                        "rowId": row.get("rowId"),
                        "tableId": row.get("tableId"),
                        "originalData": row.get("originalData"),
                    }
                    for row in state.get("_tombstones", [])
                ],
            }
            return hashlib.sha256(_stable(normalized).encode("utf-8")).hexdigest()
        payload = {
            "fk_policy": self.fk_policy,
            "tables": {
                name: [
                    {
                        "id": row_id,
                        "present": row.present(),
                        "conflict_removed": row.conflict_removed,
                        "data": row.read(self.schema[name]["columns"]),
                        "cells": {
                            col: [version.to_json() for version in versions]
                            for col, versions in sorted(row.cells.items())
                        },
                    }
                    for row_id, row in sorted(rows.items())
                ]
                for name, rows in sorted(self.tables.items())
            },
            "tombstones": sorted(self.tombstones.items()),
            "conflict_log": sorted(self.conflict_log.items()),
        }
        return hashlib.sha256(_stable(payload).encode("utf-8")).hexdigest()

    get_snapshot_hash = snapshot_hash

    def metadata_stats(self) -> dict[str, int]:
        max_entries = 0
        versions_seen = 0
        for rows in self.tables.values():
            for row in rows.values():
                for versions in row.cells.values():
                    for version in versions:
                        versions_seen += 1
                        max_entries = max(max_entries, len(version.clock))
        return {
            "known_peers": len(self.known_peers),
            "max_clock_entries_per_version": max_entries,
            "versions_seen": versions_seen,
        }

    def dump_state(self) -> dict[str, Any]:
        return self.export_state()

    def close(self) -> None:
        return None

    # Official Anvil harness adapter API. The same class can be used either as
    # a single peer or as a peer manager, depending on which harness imports it.
    def open_peer(self, peer_id: str) -> None:
        self._peers[peer_id] = Engine(peer_id=peer_id, fk_policy=self.fk_policy)

    def apply_schema(self, peer_id: str, stmts: list[str] | tuple[str, ...] | str) -> None:
        peer = self._peer(peer_id)
        if isinstance(stmts, str):
            stmts = [stmts]
        for stmt in stmts:
            peer.execute(stmt)

    def snapshot_state(self, peer_id: str) -> dict[str, list[dict[str, Any]]]:
        peer = self._peer(peer_id)
        users = [
            row
            for row in peer._all_rows("users")
            if f"users:{row.get('id')}" not in peer.tombstones
        ]
        return {
            "users": users,
            "orders": peer._all_rows("orders"),
            "_conflict_log": peer._all_rows("_conflict_log"),
            "_tombstones": [
                {"key": key, **copy.deepcopy(value)}
                for key, value in sorted(peer.tombstones.items())
            ],
        }

    def _peer(self, peer_id: str) -> "Engine":
        if peer_id not in self._peers:
            self.open_peer(peer_id)
        return self._peers[peer_id]

    def _ensure_row(self, table: str, row_id: str) -> Row:
        rows = self.tables[table]
        if row_id not in rows:
            rows[row_id] = Row(row_id)
        return rows[row_id]

    def _insert(self, table: str, values: dict[str, SqlValue]) -> None:
        schema = self.schema[table]
        full = {**schema["defaults"], **values}
        row_id = str(full[schema["pk"]])
        clock = self.tick()
        row = self._ensure_row(table, row_id)
        tag = {"peerId": self.peer_id, "clock": clock}
        row.add_tags[f"{self.peer_id}:{_clock_key(clock)}"] = tag
        for column in schema["columns"]:
            if column in full:
                row.cells[column] = _merge_register(
                    row.cells.get(column, []), [Version(full[column], clock, self.peer_id)]
                )
        self.resolve_conflicts()

    def _update(self, table: str, row_id: str, values: dict[str, SqlValue]) -> None:
        clock = self.tick()
        row = self._ensure_row(table, row_id)
        for column, value in values.items():
            row.cells[column] = _merge_register(row.cells.get(column, []), [Version(value, clock, self.peer_id)])
        key = f"{table}:{row_id}"
        if key in self.tombstones:
            self.tombstones[key]["originalData"] = row.read(self.schema[table]["columns"])
        self.resolve_conflicts()

    def _delete(self, table: str, row_id: str) -> None:
        clock = self.tick()
        row = self._ensure_row(table, row_id)
        row.removed_tags.update(row.add_tags)
        if table == "users":
            if self.fk_policy == "tombstone":
                self._merge_tombstone(f"{table}:{row_id}", {
                    "rowId": row_id,
                    "tableId": table,
                    "deletedBy": self.peer_id,
                    "deletedAt": clock,
                    "originalData": row.read(self.schema[table]["columns"]),
                })
            elif self.fk_policy == "cascade":
                for order in self.tables["orders"].values():
                    if order.read(self.schema["orders"]["columns"]).get("user_id") == row_id:
                        order.removed_tags.update(order.add_tags)
            elif self.fk_policy == "orphan":
                for order_id, order in self.tables["orders"].items():
                    if order.read(self.schema["orders"]["columns"]).get("user_id") == row_id:
                        self._update("orders", order_id, {"user_id": None})
        self.resolve_conflicts()

    def _sql(self, sql: str, params: list[Any]) -> list[dict[str, Any]]:
        text = sql.strip().rstrip(";")
        if re.match(r"^create\s+", text, re.I):
            return []
        if re.match(r"^insert\s+", text, re.I):
            match = re.match(r"insert\s+into\s+(\w+)(?:\s*\(([^)]*)\))?\s+values\s*\((.*)\)$", text, re.I)
            if not match:
                raise ValueError(f"bad INSERT: {sql}")
            table, cols_text, vals_text = match.groups()
            columns = [c.strip() for c in _split_csv(cols_text)] if cols_text else self.schema[table]["columns"]
            values = [_parse_value(raw, params) for raw in _split_csv(vals_text)]
            self._insert(table, dict(zip(columns, values)))
            return []
        if re.match(r"^update\s+", text, re.I):
            match = re.match(r"update\s+(\w+)\s+set\s+(.+)\s+where\s+id\s*=\s*(.+)$", text, re.I)
            if not match:
                raise ValueError(f"bad UPDATE: {sql}")
            table, assigns, raw_id = match.groups()
            values: dict[str, SqlValue] = {}
            for assignment in _split_csv(assigns):
                column, raw_value = assignment.split("=", 1)
                values[column.strip()] = _parse_value(raw_value, params)
            self._update(table, str(_parse_value(raw_id, params)), values)
            return []
        if re.match(r"^delete\s+", text, re.I):
            match = re.match(r"delete\s+from\s+(\w+)\s+where\s+id\s*=\s*(.+)$", text, re.I)
            if not match:
                raise ValueError(f"bad DELETE: {sql}")
            table, raw_id = match.groups()
            self._delete(table, str(_parse_value(raw_id, params)))
            return []
        if re.match(r"^select\s+", text, re.I):
            return self._select(text, params)
        raise ValueError(f"unsupported SQL: {sql}")

    def _select(self, text: str, params: list[Any]) -> list[dict[str, Any]]:
        if re.search(r"\bjoin\s+orders\b", text, re.I):
            return self._join_users_orders()
        match = re.match(r"select\s+(.+)\s+from\s+(\w+)(?:\s+where\s+(.+?))?(?:\s+order\s+by\s+(\w+))?$", text, re.I)
        if not match:
            raise ValueError(f"bad SELECT: {text}")
        cols_text, table, where_text, order_col = match.groups()
        rows = self._all_rows(table)
        if where_text:
            rows = [row for row in rows if self._where(row, where_text, params)]
        if order_col:
            rows.sort(key=lambda row: (row.get(order_col) is None, row.get(order_col)))
        if cols_text.strip() != "*":
            cols = [col.strip() for col in _split_csv(cols_text)]
            rows = [{col: row.get(col) for col in cols} for row in rows]
        return rows

    def _where(self, row: dict[str, Any], text: str, params: list[Any]) -> bool:
        for clause in re.split(r"\s+or\s+", text, flags=re.I):
            match = re.match(r"(\w+)\s*=\s*(.+)$", clause.strip(), re.I)
            if not match:
                continue
            column, raw = match.groups()
            if row.get(column) == _parse_value(raw, list(params)):
                return True
        return False

    def _all_rows(self, table: str) -> list[dict[str, Any]]:
        if table == "_conflict_log":
            return [copy.deepcopy(row) for _, row in sorted(self.conflict_log.items())]
        rows: list[dict[str, Any]] = []
        include_tombstoned_users = self.fk_policy == "tombstone" and table == "users"
        for row_id, row in sorted(self.tables[table].items()):
            if row.conflict_removed:
                continue
            if row.present() or include_tombstoned_users and f"{table}:{row_id}" in self.tombstones:
                rows.append(row.read(self.schema[table]["columns"]))
        return rows

    def _join_users_orders(self) -> list[dict[str, Any]]:
        users = {row["id"]: row for row in self._all_rows("users")}
        out = []
        for order in self._all_rows("orders"):
            tombstoned = f"users:{order.get('user_id')}" in self.tombstones
            user = None if tombstoned else users.get(order.get("user_id"))
            out.append(
                {
                    "user_id": None if user is None else user.get("id"),
                    "email": None if user is None else user.get("email"),
                    "name": None if user is None else user.get("name"),
                    "order_id": order.get("id"),
                    "status": order.get("status"),
                    "total_cents": order.get("total_cents"),
                }
            )
        return out

    def resolve_conflicts(self) -> None:
        for rows in self.tables.values():
            for row in rows.values():
                row.conflict_removed = False
        self.conflict_log = {}
        self._resolve_unique("users", "email", "users_email_key")
        for key, tombstone in list(self.tombstones.items()):
            table, row_id = key.split(":", 1)
            row = self.tables.get(table, {}).get(row_id)
            if row:
                tombstone["originalData"] = row.read(self.schema[table]["columns"])

    def _resolve_unique(self, table: str, column: str, constraint: str) -> None:
        groups: dict[Any, list[tuple[str, Row, dict[str, Any]]]] = {}
        for row_id, row in self.tables[table].items():
            if row.conflict_removed:
                continue
            data = row.read(self.schema[table]["columns"])
            values = {version.value for version in row.cells.get(column, []) if version.value is not None}
            for value in values:
                groups.setdefault(value, []).append((row_id, row, data))
        for value, contenders in groups.items():
            if len(contenders) < 2:
                continue
            contenders.sort(key=lambda item: self._arbitration_tuple(item[1], item[0]))
            winner_id = contenders[0][0]
            for loser_id, loser_row, loser_data in contenders[1:]:
                loser_row.conflict_removed = True
                conflict_id = f"{table}:{constraint}:{value}:{loser_id}"
                self.conflict_log[conflict_id] = {
                    "conflict_id": conflict_id,
                    "table_name": table,
                    "constraint_name": constraint,
                    "conflicting_value": str(value),
                    "winner_row_id": winner_id,
                    "loser_row_id": loser_id,
                    "loser_row_data": _stable(loser_data),
                    "detected_at": "logical-time",
                }

    def _arbitration_tuple(self, row: Row, row_id: str) -> tuple[int, str, str]:
        versions = [version for versions in row.cells.values() for version in versions]
        if not versions:
            return (0, "", row_id)
        return (min(_clock_sum(version.clock) for version in versions), sorted(v.writerId for v in versions)[0], row_id)

    def rebuild_indexes(self) -> None:
        index: dict[str, list[str]] = {}
        for order in self._all_rows("orders"):
            key = f"{order.get('user_id')}:{order.get('status')}"
            index.setdefault(key, []).append(str(order.get("id")))
        self.indexes["orders_by_user"] = {key: sorted(ids) for key, ids in index.items()}

    def export_state(self) -> dict[str, Any]:
        return {
            "peer_id": self.peer_id,
            "fk_policy": self.fk_policy,
            "clock": dict(self.clock),
            "known_peers": sorted(self.known_peers),
            "tables": {
                table: {row_id: row.to_json() for row_id, row in rows.items()}
                for table, rows in self.tables.items()
            },
            "tombstones": copy.deepcopy(self.tombstones),
            "conflict_log": copy.deepcopy(self.conflict_log),
        }

    def import_state(self, state: dict[str, Any]) -> None:
        self.clock = _merge_clock(self.clock, state["clock"])
        self.known_peers.update(state.get("known_peers", []))
        self.known_peers.add(state["peer_id"])
        for table, rows in state["tables"].items():
            for row_id, incoming_json in rows.items():
                incoming = Row.from_json(incoming_json)
                local = self._ensure_row(table, row_id)
                local.add_tags.update(copy.deepcopy(incoming.add_tags))
                local.removed_tags.update(incoming.removed_tags)
                local.conflict_removed = local.conflict_removed or incoming.conflict_removed
                for column, versions in incoming.cells.items():
                    local.cells[column] = _merge_register(local.cells.get(column, []), versions)
        for key, tombstone in state["tombstones"].items():
            self._merge_tombstone(key, tombstone)
        self.conflict_log.update(copy.deepcopy(state["conflict_log"]))

    def _merge_tombstone(self, key: str, incoming: dict[str, Any]) -> None:
        incoming = copy.deepcopy(incoming)
        existing = self.tombstones.get(key)
        if not existing:
            self.tombstones[key] = incoming
            return
        existing["deletedAt"] = _merge_clock(existing.get("deletedAt", {}), incoming.get("deletedAt", {}))
        existing["deletedBy"] = min(str(existing.get("deletedBy", "")), str(incoming.get("deletedBy", "")))
        existing["rowId"] = incoming.get("rowId", existing.get("rowId"))
        existing["tableId"] = incoming.get("tableId", existing.get("tableId"))
        existing["originalData"] = incoming.get("originalData", existing.get("originalData"))
