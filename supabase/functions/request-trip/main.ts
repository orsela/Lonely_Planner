// Lonely Planner Edge Function `request-trip` entry point · version 3.0.0-alpha.8.0 · F21
// CHANGE 2026-10-27 F21-FN-02: new file (no previous version). Deployed entry point; starts the server defined in index.ts
//   (which stays importable by tests without starting a server). Same split as invite-manager/main.ts.
import { startServer } from "./index.ts";

startServer();
