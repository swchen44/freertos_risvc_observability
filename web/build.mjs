import { build } from "esbuild";
import { mkdir, copyFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
const root = path.dirname(fileURLToPath(import.meta.url));
await mkdir(path.join(root, "dist/assets"), { recursive: true });
await build({
  entryPoints: [path.join(root, "src/main.js")],
  bundle: true,
  format: "iife",
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
await build({entryPoints:[path.join(root,'src/cache.js')],bundle:true,format:'iife',minify:true,
 outfile:path.join(root,'dist/assets/cache.js'),target:'es2022',legalComments:'eof'});
await copyFile(path.join(root,'cache.html'),path.join(root,'dist/cache.html'));

await build({entryPoints:[path.join(root,'src/tcp.js')],bundle:true,format:'iife',minify:true,
 outfile:path.join(root,'dist/assets/tcp.js'),target:'es2022',legalComments:'eof'});
await copyFile(path.join(root,'tcp.html'),path.join(root,'dist/tcp.html'));

await build({entryPoints:[path.join(root,'src/timing.js')],bundle:true,format:'iife',minify:true,
 outfile:path.join(root,'dist/assets/timing.js'),target:'es2022',legalComments:'eof'});
await copyFile(path.join(root,'timing.html'),path.join(root,'dist/timing.html'));
