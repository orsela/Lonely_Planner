// Lonely Planner Edge Function `approve-member` entry point · version 3.0.0-alpha.16.0 · F05 (CHANGE 2026-11-16 F07-FN-02: version only, was 3.0.0-alpha.6.0)
// CHANGE 2026-10-19 F05-FN-03: new file (no previous version). Deployed entry point; starts the server defined in index.ts
//   (which stays importable by tests without starting a server). Same split as create-trip/main.ts.
import { startServer } from "./index.ts";

startServer();
