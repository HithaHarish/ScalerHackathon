export async function sync(peerA, peerB) {
  if (peerA === peerB) return;
  const stateA = peerA.exportState();
  const stateB = peerB.exportState();
  peerA.importState(stateB);
  peerB.importState(stateA);
  peerA.resolveConflicts();
  peerB.resolveConflicts();
  peerA.rebuildIndexes();
  peerB.rebuildIndexes();
}

