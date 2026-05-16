# Architecture Defense

## Page 1: Lattice Choices and CRDT Type Mapping

Rows are represented as an observed-remove set. Each insert creates an add tag from `(peer_id, causal_clock)`, and deletes remove only the tags observed at delete time. This gives add-wins behavior for concurrent insert/delete and lets row membership converge by set union.

Cells are represented as MV-registers. Each column stores independently versioned values; a write removes dominated versions and preserves concurrent versions. Reads use deterministic ordering by descending clock sum and ascending writer id, but the stored register keeps every non-dominated version. This is why a concurrent `name` update and `email` update on `users.u1` both survive.

Primary keys are immutable row ids. Unique email is handled by post-hoc escrow arbitration because availability under partition cannot also provide strong uniqueness without coordination. Foreign keys use the declared tombstone policy for every FK. Secondary indexes are deterministic derived views. Causal ordering uses bounded vector clocks with one entry per distinct writer.

## Page 2: Protocol Designs

Uniqueness resolution runs after merge. All rows are grouped by unique value. If a group has more than one row, rows are sorted by `(minimum clock sum, writer id, row id)`. The first row wins; every loser is marked non-live and copied into `_conflict_log` with full JSON row data. This is deterministic and recoverable, never silent.

The FK policy is tombstone. When `users.u1` is deleted, the row is removed from live membership but the tombstone stores table id, row id, delete clock, deleting peer, and merged row data. Orders referencing `u1` remain queryable. Joins return `NULL` parent fields for tombstoned parents, preserving auditability.

Sync is pairwise and bidirectional. Peers exchange state summaries and merge by CRDT union/max rules, then resolve uniqueness and rebuild indexes. OR-set merge, MV-register merge, and vector-clock max are commutative, associative, and idempotent; their composition reaches the same fixed point under any sync order.

## Page 3: Metadata Growth and Q&A Preparation

Clock metadata is O(distinct writers) per version because clocks are maps from peer id to max logical time. It is not O(writes). Tombstones are O(deletes) and conflict logs are O(unique violations), both finite during a run. After quiescence, clock entries acknowledged by all known peers can be compacted to the global minimum.

Handled corner cases include tombstone resurrection, empty peer sync, self-sync, sync after quiescence, idempotent double sync, sync ordering invariance, and uniqueness conflicts under partition. A late insert with the same primary key must causally supersede an existing tombstone to be treated as intentional resurrection; otherwise the tombstone continues to win.

