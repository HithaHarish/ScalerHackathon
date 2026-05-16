import { useState } from 'react';
import { Trash2, Save, X } from 'lucide-react';

interface OrderRowProps {
  row: any;
  isTombstoned: boolean;
  isValidFK: boolean;
  isParentTombstoned: boolean;

  onUpdate: (
    rowId: string,
    field: string,
    value: string
  ) => void;

  onDelete: (
    rowId: string
  ) => void;
}

export function OrderRow({
  row,
  isTombstoned,
  isValidFK,
  isParentTombstoned,
  onUpdate,
  onDelete
}: OrderRowProps) {

  // =====================================================
  // LOCAL STATE
  // =====================================================

  const [status, setStatus] =
    useState(row.status?.value || '');

  const [total, setTotal] =
    useState(row.total_cents?.value || '');

  // =====================================================
  // CHANGE DETECTION
  // =====================================================

  const hasStatusChanges =
    status !== row.status?.value;

  const hasTotalChanges =
    total !== row.total_cents?.value;

  const hasChanges =
    hasStatusChanges || hasTotalChanges;

  // =====================================================
  // FK STATUS UI
  // =====================================================

  let borderClass = 'border-slate-200 bg-white hover:border-purple-300 shadow-sm';

  let fkBadge = null;

  if (isTombstoned) {
    borderClass = 'border-red-200 bg-red-50/50 opacity-70';
  } else if (!isValidFK) {
    borderClass = 'border-slate-200 bg-white shadow-sm';
    fkBadge = (
      <span className="text-red-700 bg-red-100 px-2 py-0.5 rounded border border-red-200 shadow-sm">
        INVALID FK
      </span>
    );
  } else if (isParentTombstoned) {
    borderClass = 'border-orange-300 bg-orange-50 shadow-[0_4px_20px_rgba(249,115,22,0.1)]';
    fkBadge = (
      <span className="text-orange-700 bg-orange-100 px-2 py-0.5 rounded border border-orange-200 shadow-sm">
        ORPHANED (Parent Deleted)
      </span>
    );
  } else {
    borderClass = hasChanges
      ? 'border-yellow-300 bg-yellow-50/30 shadow-[0_4px_20px_rgba(234,179,8,0.1)]'
      : 'border-slate-200 bg-white hover:border-purple-300 shadow-sm';

    fkBadge = (
      <span className="text-green-700 bg-green-100 px-2 py-0.5 rounded border border-green-200 shadow-sm">
        VALID FK
      </span>
    );
  }

  // =====================================================
  // SAVE CHANGES
  // =====================================================

  const handleSave = () => {

    if (hasStatusChanges) {

      onUpdate(
        row.id.value,
        'status',
        status
      );
    }

    if (hasTotalChanges) {

      onUpdate(
        row.id.value,
        'total_cents',
        total
      );
    }
  };

  // =====================================================
  // CANCEL CHANGES
  // =====================================================

  const handleCancel = () => {

    setStatus(row.status?.value || '');

    setTotal(row.total_cents?.value || '');
  };

  return (
    <div
      className={`rounded-2xl border p-5 transition-all hover:shadow-md ${borderClass}`}
    >
      <div className="grid grid-cols-[1fr_1fr_1fr_1fr_auto] gap-4 items-center">
        {/* ORDER ID */}
        <div>
          <div className="text-[10px] text-slate-400 uppercase font-bold tracking-wider mb-1.5">
            Order ID
          </div>
          <div className="text-slate-700 font-mono text-sm bg-slate-100 px-2.5 py-1.5 rounded-lg border border-slate-200 inline-block font-medium">
            {row.id?.value}
          </div>
        </div>

        {/* USER FK */}
        <div>
          <div className="text-[10px] text-slate-400 uppercase font-bold tracking-wider mb-1.5 flex items-center gap-2">
            User ID
          </div>
          <div className="flex flex-col gap-1.5 items-start">
            <div className="text-purple-700 font-mono text-sm bg-purple-50 px-2.5 py-1.5 rounded-lg border border-purple-200 inline-block font-bold">
              {row.user_id?.value}
            </div>
            <div className="text-[9px] font-bold tracking-wider uppercase mt-1">
              {fkBadge}
            </div>
          </div>
        </div>

        {/* STATUS */}
        <div>
          <div className="text-[10px] text-slate-400 uppercase font-bold tracking-wider mb-1.5">
            Status
          </div>
          <input
            type="text"
            value={status}
            disabled={isTombstoned}
            onChange={(e) =>
              setStatus(e.target.value)
            }
            className={`w-full border rounded-xl px-3 py-2 text-sm transition-all focus:outline-none focus:ring-2 ${hasStatusChanges
              ? 'border-yellow-300 bg-yellow-50 text-yellow-900 focus:ring-yellow-200'
              : 'border-slate-200 bg-slate-50 focus:border-purple-400 focus:bg-white focus:ring-purple-100 text-slate-800'
              }`}
          />
        </div>

        {/* TOTAL */}
        <div>
          <div className="text-[10px] text-slate-400 uppercase font-bold tracking-wider mb-1.5">
            Total
          </div>
          <input
            type="number"
            value={total}
            disabled={isTombstoned}
            onChange={(e) =>
              setTotal(e.target.value)
            }
            className={`w-full border rounded-xl px-3 py-2 text-sm font-mono font-medium transition-all focus:outline-none focus:ring-2 ${hasTotalChanges
              ? 'border-yellow-300 bg-yellow-50 text-yellow-900 focus:ring-yellow-200'
              : 'border-slate-200 bg-slate-50 focus:border-cyan-400 focus:bg-white focus:ring-cyan-100 text-cyan-700'
              }`}
          />
        </div>

        {/* ACTIONS */}
        <div className="flex justify-end items-center gap-2 h-full">
          {isTombstoned ? (
            <div className="px-3 py-1.5 rounded-lg bg-red-100 border border-red-200 text-red-600 text-[10px] uppercase tracking-wider font-bold shadow-sm">
              Tombstoned
            </div>
          ) : hasChanges ? (
            <>
              <button
                onClick={handleSave}
                className="p-2 rounded-xl bg-white border border-red-200 text-red-500 hover:text-white hover:bg-red-500 transition-colors shadow-sm"
                title="Reject Incoming Update (Keep Local)"
              >
                <X className="w-4 h-4" />
              </button>
              <button
                onClick={handleCancel}
                className="px-4 py-2 rounded-xl bg-green-100 border border-green-200 hover:bg-green-200 text-green-700 text-xs font-bold uppercase tracking-wider flex items-center gap-2 shadow-sm transition-colors"
                title="Accept Incoming Update"
              >
                <Save className="w-4 h-4" />
                Apply Incoming Update
              </button>
            </>
          ) : (
            <button
              onClick={() =>
                onDelete(row.id.value)
              }
              className="p-2.5 rounded-xl bg-red-50 border border-red-100 hover:bg-red-100 text-red-500 flex items-center gap-2 transition-colors shadow-sm"
              title="Delete Order"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* METADATA */}
      <div className="mt-5 pt-3 border-t border-slate-100 flex gap-8 text-[10px] font-mono text-slate-400 uppercase tracking-wider font-medium">
        <div className="flex gap-2 items-center">
          <span>Status Meta:</span>
          <span className="text-cyan-600 bg-cyan-50 px-1.5 py-0.5 rounded">T:{row.status?.timestamp}</span>
          <span className="text-purple-600 bg-purple-50 px-1.5 py-0.5 rounded">P:{row.status?.peerId}</span>
        </div>
        <div className="flex gap-2 items-center">
          <span>Total Meta:</span>
          <span className="text-cyan-600 bg-cyan-50 px-1.5 py-0.5 rounded">T:{row.total_cents?.timestamp}</span>
          <span className="text-purple-600 bg-purple-50 px-1.5 py-0.5 rounded">P:{row.total_cents?.peerId}</span>
        </div>
      </div>
    </div>
  );
}