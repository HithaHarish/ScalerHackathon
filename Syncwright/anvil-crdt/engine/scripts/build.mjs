import { cp, mkdir, rm } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const dist = join(root, "dist");

await rm(dist, { recursive: true, force: true });
await mkdir(dist, { recursive: true });
await cp(join(root, "src"), join(dist, "src"), { recursive: true });
await cp(join(root, "tests"), join(dist, "tests"), { recursive: true });

async function renameTs(dir) {
  const { readdir, rename, stat } = await import("node:fs/promises");
  for (const entry of await readdir(dir)) {
    const path = join(dir, entry);
    const info = await stat(path);
    if (info.isDirectory()) {
      await renameTs(path);
    } else if (path.endsWith(".ts")) {
      await rename(path, path.slice(0, -3) + ".js");
    }
  }
}

await renameTs(dist);
console.log("Built JS test/runtime files into dist/");

