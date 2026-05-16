import { clockKey } from "./causal_clock.js";

export function tagKey(tag) {
  return `${tag.peerId}:${clockKey(tag.clock)}`;
}

export class OrSet {
  constructor() {
    this.adds = new Map();
    this.removes = new Map();
  }

  add(element, peerId, clock) {
    if (!this.adds.has(element)) this.adds.set(element, new Map());
    const tag = { peerId, clock: { ...clock } };
    this.adds.get(element).set(tagKey(tag), tag);
    return tag;
  }

  remove(element, observedTags) {
    if (!this.removes.has(element)) this.removes.set(element, new Set());
    for (const tag of observedTags) this.removes.get(element).add(tagKey(tag));
  }

  observedTags(element) {
    return [...(this.adds.get(element)?.values() ?? [])];
  }

  contains(element) {
    const removed = this.removes.get(element) ?? new Set();
    return this.observedTags(element).some((tag) => !removed.has(tagKey(tag)));
  }

  merge(other) {
    for (const [element, tags] of other.adds.entries()) {
      if (!this.adds.has(element)) this.adds.set(element, new Map());
      for (const [key, tag] of tags.entries()) this.adds.get(element).set(key, tag);
    }
    for (const [element, keys] of other.removes.entries()) {
      if (!this.removes.has(element)) this.removes.set(element, new Set());
      for (const key of keys) this.removes.get(element).add(key);
    }
  }
}

