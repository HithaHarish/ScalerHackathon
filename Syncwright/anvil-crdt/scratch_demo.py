from adapters.myteam import Engine

a = Engine(peer_id="A", fk_policy="tombstone")
b = Engine(peer_id="B", fk_policy="tombstone")

a.execute("INSERT INTO users VALUES ('u1', 'alice@x.com', 'Alice')")
b.execute("INSERT INTO users VALUES ('u2', 'alice@x.com', 'Alice Prime')")

a.sync(b)

print(a.query("SELECT * FROM users"))
print(a.query("SELECT * FROM _conflict_log"))
print(a.snapshot_hash(), b.snapshot_hash())
