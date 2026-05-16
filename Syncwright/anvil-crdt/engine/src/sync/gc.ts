export function compactKnownPeers(engine) {
  const peers = [...engine.knownPeers].sort();
  for (const table of engine.tables.values()) {
    for (const row of table.rows.values()) {
      for (const versions of Object.values(row.cells)) {
        for (const version of versions) {
          version.clock = Object.fromEntries(Object.entries(version.clock).filter(([peer]) => peers.includes(peer)));
        }
      }
    }
  }
}

