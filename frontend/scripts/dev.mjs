import { spawn } from "node:child_process";
const args = process.argv.slice(2);
const index = args.indexOf("--port");
const port = index >= 0 ? args[index + 1] : process.env.PORT || "3000";
const child = spawn(
  process.execPath,
  [
    "node_modules/next/dist/bin/next",
    "dev",
    "--hostname",
    "0.0.0.0",
    "--port",
    port,
  ],
  { stdio: "inherit", env: process.env },
);
for (const signal of ["SIGTERM", "SIGINT"])
  process.on(signal, () => child.kill(signal));
child.on("exit", (code) => process.exit(code ?? 1));
