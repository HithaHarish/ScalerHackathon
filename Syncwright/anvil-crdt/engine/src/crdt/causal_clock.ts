export function cloneClock(clock = {}) {
  return Object.fromEntries(Object.entries(clock).filter(([, value]) => value > 0));
}

export function increment(clock, peerId) {
  const next = cloneClock(clock);
  next[peerId] = (next[peerId] ?? 0) + 1;
  return next;
}

export function mergeClock(a = {}, b = {}) {
  const next = cloneClock(a);
  for (const [peerId, value] of Object.entries(b)) {
    next[peerId] = Math.max(next[peerId] ?? 0, value);
  }
  return next;
}

export function dominates(a = {}, b = {}) {
  let strictlyGreater = false;
  for (const peerId of new Set([...Object.keys(a), ...Object.keys(b)])) {
    const av = a[peerId] ?? 0;
    const bv = b[peerId] ?? 0;
    if (av < bv) return false;
    if (av > bv) strictlyGreater = true;
  }
  return strictlyGreater;
}

export function concurrent(a = {}, b = {}) {
  return !dominates(a, b) && !dominates(b, a);
}

export function clockSum(clock = {}) {
  return Object.values(clock).reduce((sum, value) => sum + value, 0);
}

export function clockKey(clock = {}) {
  return JSON.stringify(Object.keys(clock).sort().map((peerId) => [peerId, clock[peerId]]));
}

export function compactClock(clock = {}, peers = []) {
  const allowed = new Set(peers);
  return Object.fromEntries(Object.entries(clock).filter(([peerId]) => allowed.has(peerId)));
}

