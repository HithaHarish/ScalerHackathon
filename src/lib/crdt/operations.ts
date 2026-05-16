import { v4 as uuidv4 } from 'uuid';
import { PeerId, Operation } from './types';

export function createInsertOperation<T>(
  peerId: PeerId,
  clock: number,
  tableName: string,
  rowId: string,
  data: T
): Operation {
  return {
    id: uuidv4(),
    peerId,
    logicalClock: clock,
    tableName,
    rowId,
    type: 'INSERT',
    data,
  };
}

export function createUpdateOperation<T>(
  peerId: PeerId,
  clock: number,
  tableName: string,
  rowId: string,
  field: keyof T,
  value: T[keyof T]
): Operation {
  return {
    id: uuidv4(),
    peerId,
    logicalClock: clock,
    tableName,
    rowId,
    type: 'UPDATE',
    field,
    value,
  };
}

export function createDeleteOperation(
  peerId: PeerId,
  clock: number,
  tableName: string,
  rowId: string
): Operation {
  return {
    id: uuidv4(),
    peerId,
    logicalClock: clock,
    tableName,
    rowId,
    type: 'DELETE',
  };
}
