import { useState, useEffect, useRef } from 'react';
import { useSimulationStore } from '../store/useSimulationStore';
import { createInsertOperation, createUpdateOperation, createDeleteOperation } from '../lib/crdt/operations';
import { v4 as uuidv4 } from 'uuid';

export function useChaosMode() {
  const [isChaosActive, setIsChaosActive] = useState(false);
  const { peers, applyLocalOperation, syncPeers, togglePeerOnline } = useSimulationStore();
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (isChaosActive) {
      timerRef.current = setInterval(() => {
        const peerIds = Object.keys(peers);
        if (peerIds.length === 0) return;

        // 1. Randomly perform an action
        const actionType = Math.random();
        
        // Pick a random peer
        const peerId = peerIds[Math.floor(Math.random() * peerIds.length)];
        const peer = peers[peerId];

        if (actionType < 0.2) {
          // Toggle online/offline (simulate partition)
          togglePeerOnline(peerId);
        } else if (actionType < 0.5) {
          // Sync with another random peer if both online
          const otherId = peerIds[Math.floor(Math.random() * peerIds.length)];
          if (peerId !== otherId && peers[peerId].isOnline && peers[otherId].isOnline) {
            syncPeers(peerId, otherId);
          }
        } else if (actionType < 0.8) {
          // Insert a new row or update an existing
          if (Math.random() > 0.5) {
             const id = uuidv4().slice(0, 8);
             const op = createInsertOperation(peer.id, peer.logicalClock, 'users', id, {
               id,
               name: `Chaos ${id}`,
               email: `${id}@chaos.net`
             });
             applyLocalOperation(peer.id, op);
          } else {
             const userIds = Object.keys(peer.tables.users || {});
             if (userIds.length > 0) {
               const rId = userIds[Math.floor(Math.random() * userIds.length)];
               const op = createUpdateOperation(peer.id, peer.logicalClock, 'users', rId, 'name', `Updated ${Math.floor(Math.random()*1000)}`);
               applyLocalOperation(peer.id, op);
             }
          }
        } else {
          // Delete
          const userIds = Object.keys(peer.tables.users || {});
          if (userIds.length > 0) {
            const rId = userIds[Math.floor(Math.random() * userIds.length)];
            const op = createDeleteOperation(peer.id, peer.logicalClock, 'users', rId);
            applyLocalOperation(peer.id, op);
          }
        }

      }, 1000); // Action every 1 second
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isChaosActive, peers, applyLocalOperation, syncPeers, togglePeerOnline]);

  return {
    isChaosActive,
    toggleChaosMode: () => setIsChaosActive(!isChaosActive)
  };
}
