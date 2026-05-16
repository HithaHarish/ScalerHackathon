import { useEffect } from 'react';
import { motion } from 'framer-motion';
import { useSimulationStore } from '../store/useSimulationStore';
import { PeerCard } from './PeerCard';

export function NetworkTopology() {
  const { peers, addPeer } = useSimulationStore();
  const peerList = Object.values(peers);

  // Auto-initialize some peers for demo if empty
  useEffect(() => {
    if (peerList.length === 0) {
      addPeer('Peer-A');
      addPeer('Peer-B');
      addPeer('Peer-C');
    }
  }, [peerList.length, addPeer]);

  return (
    <div className="w-full h-full flex flex-col relative overflow-hidden">
      {/* Topology Background Connections (placeholder for cool SVG lines) */}
      <div className="absolute inset-0 pointer-events-none opacity-20">
        <svg className="w-full h-full">
          <defs>
             <linearGradient id="neon-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
               <stop offset="0%" stopColor="#00ffcc" />
               <stop offset="100%" stopColor="#ff0055" />
             </linearGradient>
          </defs>
        </svg>
      </div>

      <div className="flex w-full h-full overflow-x-auto snap-x snap-mandatory hide-scrollbar relative z-10 pt-4 pb-4">
        {peerList.map((peer, i) => (
          <motion.div
            key={peer.id}
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ delay: i * 0.1 }}
            className="w-full shrink-0 snap-center px-6 flex justify-center"
          >
            <div className="w-full max-w-7xl">
              <PeerCard peerId={peer.id} />
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
