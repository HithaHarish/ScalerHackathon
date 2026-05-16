import React, { useState } from 'react';
import {
  Database, Network, Settings, Plus, RotateCcw,
  Info, Shield, Clock, Users, Zap as FastIcon, Layers,
  ChevronDown, ChevronUp
} from 'lucide-react';
import { useSimulationStore } from '../store/useSimulationStore';
import { useChaosMode } from '../hooks/useChaosMode';

export function Layout({ children }: { children: React.ReactNode }) {
  const { peers, addPeer, resetSimulation } = useSimulationStore();
  const { isChaosActive, toggleChaosMode } = useChaosMode();

  const [isAboutExpanded, setIsAboutExpanded] = useState(false);

  // Global convergence
  const activePeers = Object.values(peers).filter(p => p.isOnline);
  const hashes = activePeers.map(p => p.snapshotHash);
  const isConverged = hashes.length > 0 && hashes.every(h => h === hashes[0]);

  return (
    <div className="flex h-screen w-full text-slate-800 overflow-hidden bg-slate-50 relative z-0">

      {/* Animated Background Blobs (Behind Sidebar & Main) */}
      <div className="absolute top-0 -left-4 w-96 h-96 bg-cyan-300 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob pointer-events-none -z-10"></div>
      <div className="absolute top-0 -right-4 w-96 h-96 bg-purple-300 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-2000 pointer-events-none -z-10"></div>
      <div className="absolute -bottom-8 left-1/2 w-96 h-96 bg-pink-300 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-4000 pointer-events-none -z-10"></div>

      {/* Massive Left Sidebar */}
      <aside className="w-[420px] shrink-0 border-r border-slate-200/60 bg-white/80 backdrop-blur-3xl flex flex-col z-20 shadow-[8px_0_30px_rgba(0,0,0,0.03)] overflow-hidden">

        {/* Branding Header */}
        <div className="px-6 py-8 border-b border-slate-200/60 bg-gradient-to-br from-white to-slate-50">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-gradient-to-br from-cyan-500 to-blue-600 rounded-2xl shadow-lg shadow-cyan-500/20">
              <Database className="w-8 h-8 text-white" />
            </div>
            <div>
              <h1 className="text-3xl font-extrabold bg-clip-text text-transparent bg-gradient-to-r from-cyan-600 to-blue-700 tracking-tight">
                CRDT-OLTP
              </h1>
              <p className="text-xs text-slate-500 font-bold uppercase tracking-widest mt-1">
                Distributed Relational Simulator
              </p>
            </div>
          </div>
        </div>

        {/* Sidebar Scrollable Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-8 hide-scrollbar">
          {/* Global Controls */}
          <section>
            <h2 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-3 px-1">Simulation Controls</h2>
            <div className="space-y-2">
              <button
                onClick={() => addPeer(`Peer-${Object.keys(peers).length + 1}`)}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-cyan-50 hover:bg-cyan-100 border border-cyan-200 rounded-xl text-sm transition-all text-cyan-700 font-bold shadow-sm"
              >
                <Plus className="w-4 h-4" /> Initialize New Peer Node
              </button>
              <button
                onClick={toggleChaosMode}
                className={`w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-sm transition-all font-bold border shadow-sm ${isChaosActive
                  ? 'bg-orange-500 border-orange-600 text-white animate-pulse'
                  : 'bg-white hover:bg-orange-50 border-orange-200 text-orange-600'
                  }`}
              >
                <FastIcon className="w-4 h-4" /> {isChaosActive ? 'HALT CHAOS MODE' : 'ENGAGE CHAOS MODE'}
              </button>
              <button
                onClick={resetSimulation}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-white hover:bg-red-50 border border-red-100 rounded-xl text-sm transition-all text-red-500 font-bold shadow-sm mt-4"
              >
                <RotateCcw className="w-4 h-4" /> Purge Network State
              </button>
            </div>
          </section>

          {/* Network Node Status Tracker */}
          <section>
            <div className="flex items-center justify-between mb-3 px-1">
              <h2 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Active Nodes</h2>
              <span className="text-[10px] font-bold bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full">{Object.keys(peers).length} Total</span>
            </div>
            <div className="space-y-2">
              {Object.values(peers).map(peer => (
                <div key={peer.id} className="flex items-center justify-between p-3 rounded-xl bg-white border border-slate-100 shadow-sm hover:shadow-md transition-shadow">
                  <div className="flex items-center gap-3">
                    <div className="relative flex h-3 w-3">
                      {peer.isOnline && <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>}
                      <span className={`relative inline-flex rounded-full h-3 w-3 ${peer.isOnline ? 'bg-emerald-500' : 'bg-red-400'}`}></span>
                    </div>
                    <span className="text-sm font-bold text-slate-700">{peer.id}</span>
                  </div>
                  <div className="flex flex-col items-end">
                    <span className="font-mono text-[10px] text-cyan-700 bg-cyan-50 px-2 py-0.5 rounded border border-cyan-100">
                      #{peer.snapshotHash}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* Features Grid */}
          <section>
            <h2 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-3 px-1">Key Features</h2>
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-slate-50 border border-slate-100 p-3 rounded-xl hover:bg-cyan-50 transition-colors group">
                <Shield className="w-4 h-4 text-cyan-500 mb-2 group-hover:scale-110 transition-transform" />
                <div className="text-xs font-bold text-slate-700">Conflict Resolution</div>
                <div className="text-[10px] text-slate-500 mt-0.5">LWW Timestamp Engine</div>
              </div>
              <div className="bg-slate-50 border border-slate-100 p-3 rounded-xl hover:bg-purple-50 transition-colors group">
                <Network className="w-4 h-4 text-purple-500 mb-2 group-hover:scale-110 transition-transform" />
                <div className="text-xs font-bold text-slate-700">Gossip Sync</div>
                <div className="text-[10px] text-slate-500 mt-0.5">Pairwise P2P Merging</div>
              </div>
              <div className="bg-slate-50 border border-slate-100 p-3 rounded-xl hover:bg-orange-50 transition-colors group">
                <Clock className="w-4 h-4 text-orange-500 mb-2 group-hover:scale-110 transition-transform" />
                <div className="text-xs font-bold text-slate-700">Logical Clocks</div>
                <div className="text-[10px] text-slate-500 mt-0.5">Vector Time Tracking</div>
              </div>
              <div className="bg-slate-50 border border-slate-100 p-3 rounded-xl hover:bg-emerald-50 transition-colors group">
                <Layers className="w-4 h-4 text-emerald-500 mb-2 group-hover:scale-110 transition-transform" />
                <div className="text-xs font-bold text-slate-700">Relational Rules</div>
                <div className="text-[10px] text-slate-500 mt-0.5">FK & Unique Bounds</div>
              </div>
            </div>
          </section>
          {/* About Project Section */}
          <section className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm transition-all hover:shadow-md">
            <button
              onClick={() => setIsAboutExpanded(!isAboutExpanded)}
              className="w-full flex items-center justify-between group"
            >
              <div className="flex items-center gap-2">
                <Info className="w-5 h-5 text-purple-500" />
                <h2 className="font-bold text-slate-700">About the Protocol</h2>
              </div>
              {isAboutExpanded ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
            </button>

            {isAboutExpanded && (
              <div className="mt-4 text-sm text-slate-600 space-y-3 leading-relaxed border-t border-slate-100 pt-4">
                <p>
                  <strong className="text-purple-600">CRDT</strong> (Conflict-Free Replicated Data Type) guarantees eventual consistency across distributed nodes without a central coordinating server.
                </p>
                <p>
                  <strong className="text-cyan-600">Local-First Architecture:</strong> Each peer maintains an independent materialized view of the database. Edits are instantaneous locally.
                </p>
                <p>
                  <strong className="text-orange-600">Tombstones & FKs:</strong> Deletions use tombstones to ensure "Delete-Wins" semantics. Relational constraints (Foreign Keys) are validated during pairwise gossip sync.
                </p>
              </div>
            )}
          </section>

          {/* Team Section */}
          <section>

            <h2 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-3 px-1">
              Engineering Team
            </h2>

            <div className="space-y-4">

              {/* MEMBER 1 */}

              <div className="group flex items-center gap-4 p-4 bg-white/90 backdrop-blur-xl border border-cyan-100 rounded-2xl hover:shadow-xl hover:-translate-y-1 transition-all duration-300">

                {/* PHOTO */}

                <img
                  src="/team/member1.jpeg"
                  alt="Team Member"
                  className="w-14 h-14 rounded-full object-cover border-4 border-cyan-200 shadow-md"
                />

                {/* DETAILS */}

                <div className="flex-1">

                  <div className="text-sm font-bold text-cyan-600">
                    HARSHITHA H G
                  </div>

                  <div className="text-[11px] text-slate-500 mt-1">
                    harshithahrgopal@gmail.com
                  </div>


                </div>

              </div>

              {/* MEMBER 2 */}

              <div className="group flex items-center gap-4 p-4 bg-white/90 backdrop-blur-xl border border-purple-100 rounded-2xl hover:shadow-xl hover:-translate-y-1 transition-all duration-300">

                <img
                  src="/team/member2.jpeg"
                  alt="Team Member"
                  className="w-14 h-14 rounded-full object-cover border-4 border-purple-200 shadow-md"
                />

                <div className="flex-1">

                  <div className="text-sm font-bold text-purple-600">
                    HITHA HARISH
                  </div>

                  <div className="text-[11px] text-slate-500 mt-1">
                    hitha22harish@gmail.com
                  </div>

                </div>

              </div>

              {/* MEMBER 3 */}

              <div className="group flex items-center gap-4 p-4 bg-white/90 backdrop-blur-xl border border-emerald-100 rounded-2xl hover:shadow-xl hover:-translate-y-1 transition-all duration-300">

                <img
                  src="/team/member3.jpeg"
                  alt="Team Member"
                  className="w-14 h-14 rounded-full object-cover border-4 border-emerald-200 shadow-md"
                />

                <div className="flex-1">

                  <div className="text-sm font-bold text-green-600">
                    SIRIPURAPU MANASWI
                  </div>

                  <div className="text-[11px] text-slate-500 mt-1">
                    siripurapu.cs23@gmail.com
                  </div>

                </div>

              </div>

            </div>

          </section>



        </div>
      </aside>

      {/* Main Right Area */}
      <main className="flex-1 flex flex-col relative z-10 overflow-hidden">

        {/* Top Navbar */}
        <header className="h-20 shrink-0 border-b border-slate-200/60 bg-white/60 backdrop-blur-3xl flex items-center justify-between px-10 shadow-[0_4px_30px_rgba(0,0,0,0.02)]">
          <div>
            <h2 className="text-xl font-extrabold text-slate-800 tracking-tight">Interactive Network Dashboard</h2>
            <div className="flex items-center gap-2 mt-1">
              <Users className="w-3.5 h-3.5 text-slate-400" />
              <span className="text-xs font-semibold text-slate-500">Peer-to-Peer Relational Database Platform</span>
            </div>
          </div>

          <div className="flex items-center gap-6">
            <div className="flex items-center gap-4 bg-white border border-slate-200 px-5 py-2.5 rounded-2xl shadow-sm">
              <Network className="w-5 h-5 text-purple-500" />
              <div className="flex flex-col">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">State Convergence</span>
                <span className={`text-sm font-bold flex items-center gap-2 ${hashes.length === 0 ? 'text-slate-500' : isConverged ? 'text-emerald-600' : 'text-orange-500'
                  }`}>
                  {hashes.length === 0 ? 'NO PEERS' : isConverged ? 'FULLY SYNCHRONIZED' : 'DIVERGED (SYNC REQUIRED)'}
                  {!isConverged && hashes.length > 0 && <span className="flex h-2 w-2 relative"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-orange-400 opacity-75"></span><span className="relative inline-flex rounded-full h-2 w-2 bg-orange-500"></span></span>}
                </span>
              </div>
            </div>
            <button className="p-3 bg-white border border-slate-200 hover:bg-slate-50 text-slate-500 hover:text-slate-700 rounded-2xl transition-all shadow-sm hover:shadow">
              <Settings className="w-5 h-5" />
            </button>
          </div>
        </header>

        {/* Dashboard Area (Scrollable) */}
        <div className="flex-1 overflow-y-auto relative hide-scrollbar flex flex-col">
          {/* Peer Topology / Workspace */}
          <div className="flex-1 w-full relative min-h-[calc(100vh-140px)]">
            {children}
          </div>

          {/* Minimal Glass Footer */}

          <footer className="w-full border-t border-slate-200/60 bg-white/60 backdrop-blur-3xl relative z-20">

            <div className="w-full px-10 py-4 flex flex-col md:flex-row items-center justify-between gap-4">

              {/* LEFT */}

              <div>

                <div className="text-sm font-bold tracking-wide text-slate-800">
                  CRDT-OLTP PLATFORM
                </div>

                <div className="text-[11px] text-slate-500 mt-0.5">
                  Distributed Relational Database Simulator
                </div>

              </div>

              {/* CENTER */}

              <div className="hidden md:flex items-center gap-5 text-[11px] font-medium text-slate-500">

                <span>React</span>

                <span className="w-1 h-1 rounded-full bg-slate-400"></span>

                <span>TypeScript</span>

                <span className="w-1 h-1 rounded-full bg-slate-400"></span>

                <span>CRDT Sync</span>

                <span className="w-1 h-1 rounded-full bg-slate-400"></span>

                <span>P2P Architecture</span>

              </div>

              {/* RIGHT */}

              <div className="flex items-center gap-4">

                {/* GitHub */}

                <a
                  href="https://github.com/your-repository-link"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white border border-slate-200 hover:border-cyan-300 hover:bg-cyan-50 transition-all shadow-sm group"
                >

                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 24 24"
                    fill="currentColor"
                    className="w-4 h-4 text-slate-700 group-hover:text-cyan-600 transition-colors"
                  >
                    <path
                      fillRule="evenodd"
                      d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.866-.013-1.7-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.004.07 1.532 1.033 1.532 1.033.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.03-2.688-.103-.253-.447-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.748-1.027 2.748-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.31.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.481A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
                      clipRule="evenodd"
                    />
                  </svg>

                  <span className="text-[11px] font-semibold text-slate-700 group-hover:text-cyan-600 transition-colors">
                    GitHub
                  </span>

                </a>

                {/* STATUS */}

                <div className="flex items-center gap-2">

                  <span className="relative flex h-2.5 w-2.5">

                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>

                    <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>

                  </span>

                  <span className="text-[11px] font-semibold text-emerald-600 uppercase tracking-wider">
                    System Online
                  </span>

                </div>

              </div>

            </div>

          </footer>
        </div>
      </main>
    </div>
  );
}
