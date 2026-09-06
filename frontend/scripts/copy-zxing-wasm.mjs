// iOS Safari has no native BarcodeDetector, so barcode-detector falls back to
// zxing-wasm and would otherwise fetch the binary from jsDelivr. Copying it out
// of node_modules keeps the served file in lockstep with the installed version.
// Both packages are transitive, so resolve through the chain that pulls them in.
import { copyFile, mkdir } from "node:fs/promises";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));

const scanner = createRequire(join(here, "resolve.cjs")).resolve("@yudiel/react-qr-scanner");
const detector = createRequire(scanner).resolve("barcode-detector/ponyfill");
const wasm = createRequire(detector).resolve("zxing-wasm/reader/zxing_reader.wasm");

const target = join(here, "..", "public", "wasm");
await mkdir(target, { recursive: true });
await copyFile(wasm, join(target, "zxing_reader.wasm"));
