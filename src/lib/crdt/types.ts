export type PeerId = string;

export type VectorClock = Record<PeerId, number>;

export type CRDTField<T> = {
  value: T;
  timestamp: number;
  peerId: PeerId;
};

export type CRDTRow<T> = {
  [K in keyof T]: CRDTField<T[K]>;
};

export type Tombstone = {
  rowId: string;
  tableName: string;
  deletedAt: number;
  peerId: PeerId;
};

// Represents an operation to be applied to the local state and gossiped
export type OperationType = 'INSERT' | 'UPDATE' | 'DELETE' | 'RESERVE';

export interface BaseOperation {
  id: string; // Globally unique ID
  peerId: PeerId;
  logicalClock: number; // Node's logical clock when op was created
  tableName: string;
  rowId: string;
  type: OperationType;
}

export interface InsertOperation<T> extends BaseOperation {
  type: 'INSERT';
  data: T; // The complete initial row data
}

export interface UpdateOperation<T> extends BaseOperation {
  type: 'UPDATE';
  field: keyof T;
  value: T[keyof T];
}

export interface DeleteOperation extends BaseOperation {
  type: 'DELETE';
}

export interface ReserveOperation extends BaseOperation {
  type: 'RESERVE';
  field: string;
  value: string; // e.g. the email being reserved
}

export type Operation = InsertOperation<any> | UpdateOperation<any> | DeleteOperation | ReserveOperation;

// Example Data Models
export interface User {
  id: string;
  name: string;
  email: string;
}

export interface Order {
  id: string;
  user_id: string;
  status: 'PENDING' | 'COMPLETED' | 'CANCELLED';
  total_cents: number;
}
