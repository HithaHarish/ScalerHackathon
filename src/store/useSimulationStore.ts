import { create } from 'zustand';
import { PeerId, Operation, CRDTRow, Tombstone, VectorClock } from '../lib/crdt/types';
import { applyOperation } from '../lib/crdt/merge';
import { computeSnapshotHash } from '../lib/crdt/hash';

export interface PeerState {
  id: PeerId;
  isOnline: boolean;
  logicalClock: number;
  vectorClock: VectorClock;
  operationsLog: Operation[];
  tables: Record<string, Record<string, CRDTRow<any>>>;
  tombstones: Record<string, Tombstone>;
  reservations: Record<string, string>;
  snapshotHash: string;
}

interface SimulationState {
  peers: Record<PeerId, PeerState>;
  // global config
  fkPolicy: 'cascade' | 'tombstone' | 'orphan';
  
  // actions
  addPeer: (id: string) => void;
  removePeer: (id: string) => void;
  togglePeerOnline: (id: string) => void;
  setFkPolicy: (policy: 'cascade' | 'tombstone' | 'orphan') => void;
  
  applyLocalOperation: (peerId: PeerId, op: Operation) => void;
  syncPeers: (peerAId: PeerId, peerBId: PeerId) => void;
  resetSimulation: () => void;
}

const initialState = {
  peers: {},
  fkPolicy: 'tombstone' as const,
};

export const useSimulationStore = create<SimulationState>((set) => ({
  ...initialState,

  addPeer: (id: string) => set((state) => {
    if (state.peers[id]) return state; // already exists
    return {
      peers: {
        ...state.peers,
        [id]: {
          id,
          isOnline: true,
          logicalClock: 0,
          vectorClock: { [id]: 0 },
          operationsLog: [],
          tables: { users: {}, orders: {} },
          tombstones: {},
          reservations: {},
          snapshotHash: computeSnapshotHash({ users: {}, orders: {} }, {})
        }
      }
    };
  }),

  removePeer: (id: string) => set((state) => {
    const newPeers = { ...state.peers };
    delete newPeers[id];
    return { peers: newPeers };
  }),

  togglePeerOnline: (id: string) => set((state) => {
    const peer = state.peers[id];
    if (!peer) return state;
    return {
      peers: {
        ...state.peers,
        [id]: { ...peer, isOnline: !peer.isOnline }
      }
    };
  }),

  setFkPolicy: (policy) => set({ fkPolicy: policy }),

  applyLocalOperation: (peerId: PeerId, op: Operation) => set((state) => {
    const peer = state.peers[peerId];
    if (!peer) return state;

    // Deep clone to avoid mutating state directly (though in a real app Immer is better)
    const newTables = JSON.parse(JSON.stringify(peer.tables));
    const newTombstones = JSON.parse(JSON.stringify(peer.tombstones));
    const newReservations = JSON.parse(JSON.stringify(peer.reservations));
    
    // Increment clock
    const newClock = peer.logicalClock + 1;
    op.logicalClock = newClock; // Ensure the op has the latest clock
    
    const newVectorClock = { ...peer.vectorClock, [peerId]: newClock };

    // Apply the operation to the materialized view
    applyOperation(newTables, newTombstones, newReservations, op);

    // Recompute hash
    const newHash = computeSnapshotHash(newTables, newTombstones);

    return {
      peers: {
        ...state.peers,
        [peerId]: {
          ...peer,
          logicalClock: newClock,
          vectorClock: newVectorClock,
          operationsLog: [...peer.operationsLog, op],
          tables: newTables,
          tombstones: newTombstones,
          reservations: newReservations,
          snapshotHash: newHash
        }
      }
    };
  }),

  syncPeers: (peerAId: PeerId, peerBId: PeerId) => set((state) => {
    const peerA = state.peers[peerAId];
    const peerB = state.peers[peerBId];
    if (!peerA || !peerB) return state;
    if (!peerA.isOnline || !peerB.isOnline) return state; // Can't sync if offline

    // Helper to sync one way
    const syncOneWay = (source: PeerState, target: PeerState): PeerState => {
      // Find operations in source that target is missing
      // A naive approach: just filter all ops where source op.id is not in target's log.
      // Better: use vector clocks. But for demo, filtering by ID is bulletproof deduplication.
      const targetOpIds = new Set(target.operationsLog.map(o => o.id));
      const missingOps = source.operationsLog.filter(o => !targetOpIds.has(o.id));

      if (missingOps.length === 0) return target;

      const newTables = JSON.parse(JSON.stringify(target.tables));
      const newTombstones = JSON.parse(JSON.stringify(target.tombstones));
      const newReservations = JSON.parse(JSON.stringify(target.reservations));
      
      // We must apply operations in causal order. Since our log is appended to, 
      // sorting by logicalClock is generally sufficient for this simple simulation.
      const opsToApply = [...missingOps].sort((a, b) => a.logicalClock - b.logicalClock);

      for (const op of opsToApply) {
        applyOperation(newTables, newTombstones, newReservations, op);
      }

      // Merge vector clocks (max of each entry)
      const newVectorClock = { ...target.vectorClock };
      for (const [k, v] of Object.entries(source.vectorClock)) {
        newVectorClock[k] = Math.max(newVectorClock[k] || 0, v);
      }

      return {
        ...target,
        vectorClock: newVectorClock,
        operationsLog: [...target.operationsLog, ...opsToApply],
        tables: newTables,
        tombstones: newTombstones,
        reservations: newReservations,
        snapshotHash: computeSnapshotHash(newTables, newTombstones)
      };
    };

    const newPeerA = syncOneWay(peerB, peerA);
    const newPeerB = syncOneWay(newPeerA, peerB); // now newPeerA has both, give back to B

    // Both should now be converged
    return {
      peers: {
        ...state.peers,
        [peerAId]: newPeerA,
        [peerBId]: newPeerB
      }
    };
  }),

  resetSimulation: () => set(initialState),
}));
