import { useState, useEffect } from 'react';
import { Trash2, Save, X } from 'lucide-react';

interface UserRowProps {
  row: any;
  isTombstoned: boolean;
  onUpdate: (rowId: string, field: string, value: string) => void;
  onDelete: (rowId: string) => void;
}

export function UserRow({ row, isTombstoned, onUpdate, onDelete }: UserRowProps) {
  const [name, setName] = useState(row.name?.value || '');
  const [email, setEmail] = useState(row.email?.value || '');

  // Reset local state if external state changes significantly,
  // but be careful not to overwrite active local edits.
  // For simplicity in this demo, we'll just track if we have unsaved changes.
  const hasNameChanges = name !== row.name?.value;
  const hasEmailChanges = email !== row.email?.value;
  const hasChanges = hasNameChanges || hasEmailChanges;

  useEffect(() => {
    // If external update comes in (e.g. from sync) and we aren't actively editing, update local state
    if (!hasChanges) {
      setName(row.name?.value || '');
      setEmail(row.email?.value || '');
    }
  }, [row.name?.value, row.email?.value, hasChanges]);

  const handleApply = () => {
    if (hasNameChanges) onUpdate(row.id.value, 'name', name);
    if (hasEmailChanges) onUpdate(row.id.value, 'email', email);
  };

  const handleCancel = () => {
    setName(row.name?.value || '');
    setEmail(row.email?.value || '');
  };

  return (
    <div
      className={`relative rounded-2xl border p-5 transition-all bg-white shadow-sm hover:shadow-md ${isTombstoned
          ? 'border-red-200 bg-red-50/50 opacity-70'
          : hasChanges
            ? 'border-yellow-300 bg-yellow-50/30 shadow-[0_4px_20px_rgba(234,179,8,0.1)]'
            : 'border-slate-200 hover:border-cyan-300'
        }`}
    >
      <div className="grid grid-cols-[1fr_2fr_2fr_auto] gap-4 items-center">
        {/* ID */}
        <div>
          <div className="text-[10px] text-slate-400 uppercase font-bold tracking-wider mb-1.5">
            User ID
          </div>
          <div className="text-slate-700 font-mono text-sm bg-slate-100 px-2.5 py-1.5 rounded-lg border border-slate-200 inline-block font-medium">
            {row.id.value}
          </div>
        </div>

        {/* NAME */}
        <div>
          <div className="text-[10px] text-slate-400 uppercase font-bold tracking-wider mb-1.5">
            Name
          </div>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={isTombstoned}
            className={`w-full border rounded-xl px-3 py-2 text-sm transition-all focus:outline-none focus:ring-2 ${hasNameChanges
                ? 'border-yellow-300 bg-yellow-50 text-yellow-900 focus:ring-yellow-200'
                : 'border-slate-200 bg-slate-50 focus:border-cyan-400 focus:bg-white focus:ring-cyan-100 text-slate-800'
              }`}
          />
        </div>

        {/* EMAIL */}
        <div>
          <div className="text-[10px] text-slate-400 uppercase font-bold tracking-wider mb-1.5">
            Email
          </div>
          <input
            type="text"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={isTombstoned}
            className={`w-full border rounded-xl px-3 py-2 text-sm transition-all focus:outline-none focus:ring-2 ${hasEmailChanges
                ? 'border-yellow-300 bg-yellow-50 text-yellow-900 focus:ring-yellow-200'
                : 'border-slate-200 bg-slate-50 focus:border-cyan-400 focus:bg-white focus:ring-cyan-100 text-slate-800'
              }`}
          />
        </div>

        {/* ACTIONS */}
        <div className="flex justify-end gap-2 items-end h-full pb-0.5">
          {isTombstoned ? (
            <div className="px-3 py-1.5 rounded-lg bg-red-100 border border-red-200 text-red-600 text-[10px] uppercase tracking-wider font-bold shadow-sm">
              Tombstoned
            </div>
          ) : hasChanges ? (
            <>
              <button
                onClick={handleCancel}
                className="p-2 rounded-xl bg-white border border-red-200 text-red-500 hover:text-white hover:bg-red-500 transition-colors shadow-sm"
                title="Keep Existing Version"
              >
                <X className="w-4 h-4" />
              </button>

              <button
                onClick={handleApply}
                className="px-4 py-2 rounded-xl bg-green-100 border border-green-200 hover:bg-green-200 text-green-700 flex items-center gap-2 text-xs font-bold uppercase tracking-wider transition-colors shadow-sm"
                title="Apply Incoming Update"
              >
                <Save className="w-4 h-4" />
                Apply Incoming Update
              </button>
            </>
          ) : (
            <button
              onClick={() => onDelete(row.id.value)}
              className="p-2.5 rounded-xl bg-red-50 border border-red-100 hover:bg-red-100 text-red-500 flex items-center gap-2 transition-colors shadow-sm"
              title="Delete User"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* METADATA FOOTER */}
      <div className="mt-5 pt-3 border-t border-slate-100 flex gap-8 text-[10px] font-mono text-slate-400 uppercase tracking-wider font-medium">
        <div className="flex gap-2 items-center">
          <span>Name Meta:</span>
          <span className="text-cyan-600 bg-cyan-50 px-1.5 py-0.5 rounded">T:{row.name?.timestamp}</span>
          <span className="text-purple-600 bg-purple-50 px-1.5 py-0.5 rounded">P:{row.name?.peerId}</span>
        </div>
        <div className="flex gap-2 items-center">
          <span>Email Meta:</span>
          <span className="text-cyan-600 bg-cyan-50 px-1.5 py-0.5 rounded">T:{row.email?.timestamp}</span>
          <span className="text-purple-600 bg-purple-50 px-1.5 py-0.5 rounded">P:{row.email?.peerId}</span>
        </div>
      </div>
    </div>
  );
}
