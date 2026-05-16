import { clockSum } from "./causal_clock.js";

export function arbitrationKey(row) {
  const clocks = Object.values(row.cells ?? {}).flat().map((version) => version.clock ?? {});
  const minSum = clocks.length ? Math.min(...clocks.map(clockSum)) : 0;
  const firstPeer = clocks.length
    ? Object.values(row.cells).flat().map((version) => version.writerId).sort()[0]
    : "";
  return [minSum, firstPeer, row.id];
}

export function compareArbitration(a, b) {
  const ka = arbitrationKey(a);
  const kb = arbitrationKey(b);
  return ka[0] - kb[0] || String(ka[1]).localeCompare(String(kb[1])) || String(ka[2]).localeCompare(String(kb[2]));
}

