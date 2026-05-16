import { createHash } from "node:crypto";

export function stable(value) {
  if (Array.isArray(value)) return `[${value.map(stable).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stable(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

export function snapshotHash(engine) {
  return createHash("sha256").update(stable(engine.materializeForHash())).digest("hex");
}

