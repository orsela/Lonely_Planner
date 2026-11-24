// Lonely Planner Edge Function `vault-delete` entry point · version 3.0.0-alpha.18.0 · F12
// CHANGE 2026-11-24 F12-FN-01: new file (no previous version). Deployed entry point; starts the server defined in index.ts
//   (which stays importable by tests without starting a server). Same split as manage-members/main.ts.
import { startServer } from "./index.ts";

startServer();
