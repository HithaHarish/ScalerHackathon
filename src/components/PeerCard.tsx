import { useState, useEffect } from 'react';
import {
  Power,
  PowerOff,
  RefreshCw,
  Database as DbIcon,
  Clock,
} from 'lucide-react';

import { useSimulationStore } from '../store/useSimulationStore';

import {
  createInsertOperation,
  createUpdateOperation,
  createDeleteOperation
} from '../lib/crdt/operations';

import { v4 as uuidv4 } from 'uuid';

import { UserRow } from './UserRow';
import { OrderRow } from './OrderRow';

export function PeerCard({ peerId }: { peerId: string }) {

  const {
    peers,
    togglePeerOnline,
    syncPeers,
    applyLocalOperation
  } = useSimulationStore();

  const peer = peers[peerId];
  const allPeers = Object.values(peers);
  const [selectedUserId, setSelectedUserId] =
    useState('');

  if (!peer) return null;

  // =====================================================
  // INITIAL DEMO DATA
  // =====================================================

  useEffect(() => {

    // USERS
    if (Object.keys(peer.tables.users).length === 0) {

      const user1 = createInsertOperation(
        peer.id,
        peer.logicalClock,
        'users',
        'U1',
        {
          id: 'U1',
          name: 'Harshitha',
          email: 'harshi@gmail.com'
        }
      );

      const user2 = createInsertOperation(
        peer.id,
        peer.logicalClock,
        'users',
        'U2',
        {
          id: 'U2',
          name: 'Hitha',
          email: 'hitha@gmail.com'
        }
      );

      applyLocalOperation(peer.id, user1);
      applyLocalOperation(peer.id, user2);
    }

    // ORDERS
    if (Object.keys(peer.tables.orders || {}).length === 0) {

      const order1 = createInsertOperation(
        peer.id,
        peer.logicalClock,
        'orders',
        'O1',
        {
          id: 'O1',
          user_id: 'U1',
          status: 'Pending',
          total_cents: 2500
        }
      );

      const order2 = createInsertOperation(
        peer.id,
        peer.logicalClock,
        'orders',
        'O2',
        {
          id: 'O2',
          user_id: 'U2',
          status: 'Delivered',
          total_cents: 4800
        }
      );

      applyLocalOperation(peer.id, order1);
      applyLocalOperation(peer.id, order2);
    }

  }, []);

  // =====================================================
  // INSERT USER
  // =====================================================

  const handleInsertUser = () => {

    const id = uuidv4().slice(0, 8);

    const op = createInsertOperation(
      peer.id,
      peer.logicalClock,
      'users',
      id,
      {
        id,
        name: `User ${id}`,
        email: `${id}@example.com`
      }
    );

    applyLocalOperation(peer.id, op);
  };

  // =====================================================
  // UPDATE USER
  // =====================================================

  const handleUpdateUser = (
    rowId: string,
    field: string,
    value: string
  ) => {

    const op = createUpdateOperation<any>(
      peer.id,
      peer.logicalClock,
      'users',
      rowId,
      field,
      value
    );

    applyLocalOperation(peer.id, op);
  };

  // =====================================================
  // DELETE USER
  // =====================================================

  const handleDeleteUser = (rowId: string) => {

    const op = createDeleteOperation(
      peer.id,
      peer.logicalClock,
      'users',
      rowId
    );

    applyLocalOperation(peer.id, op);
  };
  const handleUpdateOrder = (
    rowId: string,
    field: string,
    value: string
  ) => {

    const op = createUpdateOperation<any>(
      peer.id,
      peer.logicalClock,
      'orders',
      rowId,
      field,
      value
    );

    applyLocalOperation(peer.id, op);
  };

  const handleDeleteOrder = (
    rowId: string
  ) => {

    const op = createDeleteOperation(
      peer.id,
      peer.logicalClock,
      'orders',
      rowId
    );

    applyLocalOperation(peer.id, op);
  };
  // =====================================================
  // INSERT ORDER
  // =====================================================

  const handleInsertOrder = (userId: string) => {

    // FK VALIDATION
    const userExists = Object.values(
      peer.tables.users
    ).some(
      (user: any) =>
        user.id?.value === userId &&
        !peer.tombstones[user.id?.value]
    );

    if (!userExists) {

      alert(
        'Foreign Key Constraint Failed: User does not exist'
      );

      return;
    }

    const id = `O-${uuidv4().slice(0, 6)}`;

    const op = createInsertOperation(
      peer.id,
      peer.logicalClock,
      'orders',
      id,
      {
        id,
        user_id: userId,
        status: 'Pending',
        total_cents: Math.floor(Math.random() * 5000)
      }
    );

    applyLocalOperation(peer.id, op);
  };

  // =====================================================
  // FK VALIDATION
  // =====================================================

  const isValidFK = (userId: string) => {

    return Object.values(peer.tables.users).some(
      (user: any) =>
        user.id?.value === userId
    );
  };

  const isParentTombstoned = (userId: string) => {

    return Object.values(peer.tables.users).some(
      (user: any) =>
        user.id?.value === userId &&
        peer.tombstones[user.id?.value]
    );
  };

  return (

    <div
      className={`w-full h-[92vh] rounded-3xl border ${peer.isOnline
        ? 'border-white bg-white/95 shadow-xl shadow-slate-200/50'
        : 'border-red-200 bg-red-50/95 shadow-xl shadow-red-100/50'
        } overflow-hidden backdrop-blur-xl transition-all duration-500`}
    >
      {/* HEADER */}
      <div className="flex items-center justify-between px-8 py-6 border-b border-slate-200/80 bg-white/60">
        <div className="flex items-center gap-4">
          <button
            onClick={() => togglePeerOnline(peer.id)}
            className={`p-3 rounded-2xl transition-all shadow-sm ${peer.isOnline
              ? 'bg-green-100 text-green-600 border border-green-200 hover:bg-green-200'
              : 'bg-red-100 text-red-600 border border-red-200 hover:bg-red-200'
              }`}
          >
            {peer.isOnline ? (
              <Power className="w-5 h-5" />
            ) : (
              <PowerOff className="w-5 h-5" />
            )}
          </button>

          <div>
            <h2 className="font-bold text-3xl text-slate-800 flex items-center gap-3 tracking-tight">
              {peer.id}
              {!peer.isOnline && (
                <span className="text-xs uppercase tracking-widest bg-red-100 border border-red-200 text-red-600 px-3 py-1 rounded-full font-bold">
                  Offline
                </span>
              )}
            </h2>

            <div className="flex gap-5 text-xs text-slate-500 mt-2 font-medium">
              <span className="flex items-center gap-1.5 bg-slate-100 px-2 py-1 rounded-md border border-slate-200">
                <Clock className="w-3 h-3 text-slate-400" />
                Logical Clock: <span className="font-mono text-slate-700">{peer.logicalClock}</span>
              </span>

              <span className="flex items-center gap-1.5 bg-cyan-50 px-2 py-1 rounded-md border border-cyan-100 text-cyan-700">
                Hash: <span className="font-mono font-bold">#{peer.snapshotHash}</span>
              </span>
            </div>
          </div>
        </div>

        {/* SYNC CONTROLS */}
        <div className="flex gap-3">
          {allPeers
            .filter((p) => p.id !== peer.id)
            .map((otherPeer) => (
              <button
                key={otherPeer.id}
                onClick={() =>
                  syncPeers(peer.id, otherPeer.id)
                }
                disabled={
                  !peer.isOnline ||
                  !otherPeer.isOnline
                }
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-cyan-50 border border-cyan-200 hover:bg-cyan-100 text-cyan-700 text-sm font-bold shadow-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <RefreshCw className="w-4 h-4" />
                Sync {otherPeer.id}
              </button>
            ))}
        </div>
      </div>

      {/* BODY */}
      <div className="grid grid-cols-2 gap-8 p-8 h-[calc(100%-120px)] overflow-hidden bg-slate-50/50">
        {/* USERS TABLE */}
        <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden flex flex-col">
          {/* USERS HEADER */}
          <div className="flex items-center justify-between px-6 py-5 border-b border-slate-100 bg-slate-50/80">
            <div>
              <h3 className="text-xl font-bold text-cyan-700 flex items-center gap-2">
                <DbIcon className="w-5 h-5 text-cyan-500" />
                Users Table
              </h3>

              <div className="flex gap-2 mt-2 text-[10px] font-bold uppercase tracking-wider">
                <span className="bg-yellow-100 border border-yellow-200 text-yellow-700 px-2 py-1 rounded shadow-sm">
                  🔑 Primary Key
                </span>
                <span className="bg-pink-100 border border-pink-200 text-pink-700 px-2 py-1 rounded shadow-sm">
                  🔒 Unique Email
                </span>
              </div>
            </div>

            <button
              onClick={handleInsertUser}
              className="px-4 py-2 rounded-xl bg-cyan-100 border border-cyan-200 hover:bg-cyan-200 text-cyan-800 text-sm font-bold shadow-sm flex items-center gap-2 transition-colors"
            >
              + Insert User
            </button>
          </div>

          {/* USERS CONTENT */}
          <div className="flex-1 overflow-y-auto p-5 space-y-4 bg-slate-50/30">
            {Object.keys(peer.tables.users).length === 0 ? (
              <div className="text-center text-slate-400 font-medium py-12 border-2 border-dashed border-slate-200 rounded-xl bg-white">
                No Users found.
              </div>

            ) : (

              Object.values(peer.tables.users).map((row: any) => {

                const isTombstoned =
                  !!peer.tombstones[row.id?.value];

                return (
                  <UserRow
                    key={row.id.value}
                    row={row}
                    isTombstoned={isTombstoned}
                    onUpdate={handleUpdateUser}
                    onDelete={handleDeleteUser}
                  />
                );
              })

            )}

          </div>

        </div>

        {/* ORDERS TABLE */}
        <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden flex flex-col">
          {/* ORDERS HEADER */}
          <div className="flex items-center justify-between px-6 py-5 border-b border-slate-100 bg-slate-50/80">
            <div>
              <h3 className="text-xl font-bold text-purple-700 flex items-center gap-2">
                <DbIcon className="w-5 h-5 text-purple-500" />
                Orders Table
              </h3>
              <div className="flex gap-2 mt-2 text-[10px] font-bold uppercase tracking-wider">
                <span className="bg-yellow-100 border border-yellow-200 text-yellow-700 px-2 py-1 rounded shadow-sm">
                  🔑 Primary Key
                </span>
                <span className="bg-purple-100 border border-purple-200 text-purple-700 px-2 py-1 rounded shadow-sm">
                  🔗 Foreign Key
                </span>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {/* VALID FK DROPDOWN */}
              <select
                value={selectedUserId}
                onChange={(e) =>
                  setSelectedUserId(e.target.value)
                }
                className="bg-white border border-slate-200 rounded-xl px-4 py-2.5 text-sm text-slate-700 font-medium focus:outline-none focus:border-purple-400 focus:ring-2 focus:ring-purple-100 shadow-sm"
              >
                <option value="">
                  Select User (FK)
                </option>

                {Object.values(peer.tables.users)
                  .filter(
                    (user: any) =>
                      !peer.tombstones[user.id?.value]
                  )
                  .map((user: any) => (
                    <option
                      key={user.id?.value}
                      value={user.id?.value}
                    >
                      {user.id?.value} → {user.name?.value}
                    </option>
                  ))}
              </select>

              {/* INSERT VALID ORDER */}
              <button
                onClick={() => {
                  if (!selectedUserId) {
                    alert(
                      'Please select a valid User ID'
                    );
                    return;
                  }
                  handleInsertOrder(selectedUserId);
                }}
                className="px-4 py-2.5 rounded-xl bg-purple-100 border border-purple-200 hover:bg-purple-200 text-purple-800 text-sm font-bold shadow-sm transition-colors"
              >
                + Insert Order
              </button>
            </div>
          </div>

          {/* ORDERS CONTENT */}
          <div className="flex-1 overflow-y-auto p-5 space-y-4 bg-slate-50/30">
            {Object.keys(peer.tables.orders || {}).length === 0 ? (
              <div className="text-center text-slate-400 font-medium py-12 border-2 border-dashed border-slate-200 rounded-xl bg-white">
                No Orders found.
              </div>

            ) : (

              Object.values(peer.tables.orders || {}).map((row: any) => {

                const isTombstoned =
                  !!peer.tombstones[row.id?.value];

                return (

                  <OrderRow
                    key={row.id.value}
                    row={row}
                    isTombstoned={isTombstoned}
                    isValidFK={
                      isValidFK(row.user_id?.value)
                    }
                    isParentTombstoned={
                      isParentTombstoned(
                        row.user_id?.value
                      )
                    }
                    onUpdate={handleUpdateOrder}
                    onDelete={handleDeleteOrder}
                  />

                );
              })

            )}

          </div>

        </div>

      </div>

    </div>
  );
}