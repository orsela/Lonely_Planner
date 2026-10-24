// Lonely Planner Edge Function `manage-members` entry point · version 3.0.0-alpha.7.0 · F06
// CHANGE 2026-10-22 F06-FN-03: new file (no previous version). Deployed entry point; starts the server defined in index.ts
//   (which stays importable by tests without starting a server). Same split as approve-member/main.ts.
import { startServer } from "./index.ts";

startServer();
