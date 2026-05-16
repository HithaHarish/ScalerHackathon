# Anvil CRDT: Syncwright

Conflict-free embeddable OLTP prototype for the Anvil P-01 benchmark. The engine exposes a small SQLite-like SQL subset while representing row membership, cell values, uniqueness recovery, foreign-key deletes, and sync metadata as CRDT state.

## Policy

This submission declares `--fk-policy tombstone`.

Deleted parent rows are preserved as tombstones. Child rows continue to point at the tombstoned parent, joins return `NULL` parent fields, and tombstones are included in the deterministic snapshot hash.

## Quickstart

```bash
cd anvil-crdt
docker build -t anvil-crdt .
docker run anvil-crdt
```

Without Docker:

```bash
cd anvil-crdt/engine
npm ci
npm run build
cd ..
python bench/self_check.py --adapter adapters.myteam:Engine --fk-policy tombstone --quick
```

On Windows PowerShell with script execution disabled, use `npm.cmd`:

```powershell
cd anvil-crdt\engine
npm.cmd ci
npm.cmd run build
cd ..
python bench\self_check.py --adapter adapters.myteam:Engine --fk-policy tombstone --quick
```

## Commands

```bash
make build
make test
make demo
python bench/run.py --adapter adapters.myteam:Engine --fk-policy tombstone --randomized-seeds 9999 31415 27182
```

## Architecture Summary

| SQL primitive | CRDT type | Convergence argument |
|---|---|---|
| Row membership | OR-Set | Add tags and observed removes merge by union. Concurrent inserts survive deletes that did not observe their tags. |
| Cell values | MV-register per cell | Non-dominated versions are retained. Reads use a deterministic tie-break without discarding conflict versions. |
| Primary key | Immutable row id | Inserts address a stable row id; later updates target cells only. |
| Unique email | Post-hoc escrow arbitration | Duplicate values are detected after merge. The deterministic winner survives and losers are copied to `_conflict_log`. |
| Foreign key | Tombstone policy | Deletes preserve parent data in metadata, so child references remain auditable. |
| Secondary index | Derived view | Rebuilt from live rows after sync; never authoritative. |
| Causal ordering | Bounded vector clock | One entry per distinct writer, not per write. |

## SQL Subset

The reference schema is built in:

```sql
CREATE TABLE users (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  name TEXT
);

CREATE TABLE orders (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  status TEXT NOT NULL,
  total_cents INTEGER NOT NULL DEFAULT 0
);
```

Supported operations are `INSERT`, `UPDATE ... WHERE id = ?`, `DELETE ... WHERE id = ?`, simple `SELECT`, filtered `SELECT`, ordered filtered `SELECT`, and the reference `users JOIN orders` query.

## Dependencies

The bench adapter is Python stdlib-only. The TypeScript engine package has no runtime dependencies; `npm ci` is present for reproducible Node workflow and uses the pinned empty lockfile.

