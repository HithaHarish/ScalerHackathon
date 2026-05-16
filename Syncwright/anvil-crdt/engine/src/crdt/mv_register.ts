import { clockKey, clockSum, dominates } from "./causal_clock.js";

function versionKey(version) {
  return `${version.writerId}:${clockKey(version.clock)}:${JSON.stringify(version.value)}`;
}

export function writeRegister(register = [], value, writerId, localClock) {
  const version = { value, writerId, clock: { ...localClock } };
  return mergeRegister(register, [version]);
}

export function mergeRegister(a = [], b = []) {
  const byKey = new Map();
  for (const version of [...a, ...b]) byKey.set(versionKey(version), version);
  const versions = [...byKey.values()];
  return versions
    .filter((candidate) => !versions.some((other) => other !== candidate && dominates(other.clock, candidate.clock)))
    .sort(compareVersions);
}

export function readRegister(register = []) {
  if (register.length === 0) return null;
  return [...register].sort(compareVersions)[0].value;
}

export function compareVersions(a, b) {
  const sumDiff = clockSum(b.clock) - clockSum(a.clock);
  if (sumDiff !== 0) return sumDiff;
  const peerDiff = String(a.writerId).localeCompare(String(b.writerId));
  if (peerDiff !== 0) return peerDiff;
  return JSON.stringify(a.value).localeCompare(JSON.stringify(b.value));
}

