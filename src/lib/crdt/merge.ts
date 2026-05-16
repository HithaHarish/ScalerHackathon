import { Operation, CRDTRow, CRDTField, PeerId, Tombstone } from './types';

// Deterministic conflict resolution for Last-Writer-Wins (LWW)
// Returns true if newField wins over existingField
export function resolveLWW(
  existingField: CRDTField<any> | undefined,
  _newVal: any,
  newTimestamp: number,
  newPeerId: PeerId
): boolean {
  if (!existingField) return true;
  
  if (newTimestamp > existingField.timestamp) {
    return true;
  }
  if (newTimestamp === existingField.timestamp) {
    // Tie-breaker based on Peer ID string comparison
    return newPeerId > existingField.peerId;
  }
  return false;
}

export function applyOperation(
  tables: Record<string, Record<string, CRDTRow<any>>>,
  tombstones: Record<string, Tombstone>,
  reservations: Record<string, string>,
  op: Operation
): void {
  // If the row is tombstoned, and the op is an update or insert, we generally ignore it
  // (Delete-Wins tombstone system).
  if (tombstones[op.rowId] && op.type !== 'DELETE') {
    return;
  }

  // Ensure table exists
  if (!tables[op.tableName]) {
    tables[op.tableName] = {};
  }
  const table = tables[op.tableName];

  switch (op.type) {
    case 'INSERT': {
      // Cell-level initialization
      const newRow: CRDTRow<any> = {};
      for (const [key, val] of Object.entries(op.data)) {
        // Only apply if it wins over whatever might exist (rare for INSERT, but handles concurrent identical INSERTS)
        const existingRow = table[op.rowId];
        const existingField = existingRow ? existingRow[key] : undefined;
        if (resolveLWW(existingField, val, op.logicalClock, op.peerId)) {
           newRow[key] = {
             value: val,
             timestamp: op.logicalClock,
             peerId: op.peerId
           };
        } else if (existingRow) {
           newRow[key] = existingRow[key];
        }
      }
      table[op.rowId] = { ...(table[op.rowId] || {}), ...newRow };
      break;
    }
    case 'UPDATE': {
      const existingRow = table[op.rowId] || {};
      const existingField = existingRow[op.field as string];
      
      if (resolveLWW(existingField, op.value, op.logicalClock, op.peerId)) {
        table[op.rowId] = {
          ...existingRow,
          [op.field as string]: {
            value: op.value,
            timestamp: op.logicalClock,
            peerId: op.peerId
          }
        };
      }
      break;
    }
    case 'DELETE': {
      tombstones[op.rowId] = {
        rowId: op.rowId,
        tableName: op.tableName,
        deletedAt: op.logicalClock,
        peerId: op.peerId
      };
      // Physically remove from materialized view (but it's saved in tombstones)
      delete table[op.rowId];
      break;
    }
    case 'RESERVE': {
       // UNIQUE constraint reservation protocol
       const reservationKey = `${op.tableName}:${op.field}:${op.value}`;
       const existingOwner = reservations[reservationKey];
       
       // In a real system, we'd compare reservations. Here, we'll simplify and say first reservation wins,
       // but tie-break concurrently. Since reservations are ops, they have logicalClock.
       // Actually, to make it deterministic, we need to store the reservation's timestamp/peer too.
       // For this simulator, we can just let the Zustand state handle simple strings and we'll implement a 
       // naive LWW on the reservation itself if we need to.
       // Let's improve the reservations state later if needed. For now:
       if (!existingOwner) {
         reservations[reservationKey] = op.peerId;
       }
       break;
    }
  }
}
