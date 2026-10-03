import { build } from "esbuild";
import { mkdir, copyFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
const root = path.dirname(fileURLToPath(import.meta.url));
await mkdir(path.join(root, "dist/assets"), { recursive: true });
await build({
  entryPoints: [path.join(root, "src/main.js")],
  bundle: true,
  minify: true,
  sourcemap: true,
  outfile: path.join(root, "dist/assets/app.js"),
  target: "es2022",
  legalComments: "eof",
});
await copyFile(
  path.join(root, "index.html"),
  path.join(root, "dist/index.html"),
);
