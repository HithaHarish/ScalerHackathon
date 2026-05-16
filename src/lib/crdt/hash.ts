import { CRDTRow, Tombstone } from './types';

// Simple deterministic hash for demo purposes
// In a real system, use something like SHA-256 on a canonical JSON string
export function computeSnapshotHash(
  tables: Record<string, Record<string, CRDTRow<any>>>,
  tombstones: Record<string, Tombstone>
): string {
  const state: any = {};
  
  // Sort table names to ensure determinism
  const tableNames = Object.keys(tables).sort();
  
  for (const tName of tableNames) {
    state[tName] = {};
    const table = tables[tName];
    // Sort row IDs
    const rowIds = Object.keys(table).sort();
    
    for (const rId of rowIds) {
      // Skip if tombstoned
      if (tombstones[rId]) continue;
      
      const row = table[rId];
      state[tName][rId] = {};
      
      // Sort field names
      const fields = Object.keys(row).sort();
      for (const f of fields) {
        state[tName][rId][f] = {
          value: row[f].value,
          timestamp: row[f].timestamp,
          peerId: row[f].peerId
        };
      }
    }
  }

  // Add tombstones to hash (sorted)
  const tKeys = Object.keys(tombstones).sort();
  state.__tombstones = {};
  for (const k of tKeys) {
    state.__tombstones[k] = tombstones[k].deletedAt;
  }

  // A very naive hashing just for visual display
  const jsonString = JSON.stringify(state);
  return simpleHash(jsonString);
}

function simpleHash(str: string): string {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32bit integer
  }
  return Math.abs(hash).toString(16).padStart(8, '0');
}
