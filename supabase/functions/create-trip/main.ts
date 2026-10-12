// Plan_Travel Edge Function `create-trip` entry point · version 3.0.0-alpha.4.1 · F04
// CHANGE 2026-10-12 F04-NAME-02: version line only.
// CHANGE 2026-10-12 F04-FN-02: new file (no previous version). Deployed entry point; starts the server defined in
//   index.ts (which stays importable by tests without starting a server). Same split as invite-manager/main.ts.
import { startServer } from "./index.ts";

startServer();
