// Lonely Planner Edge Function `chat-assistant` entry point · version 3.0.0-alpha.15.0 · F14
// CHANGE 2026-11-15 F14-FN-02: new file (no previous version). Deployed entry point; starts the server defined in index.ts
//   (which stays importable by tests without starting a server). Same split as manage-members/main.ts.
import { startServer } from "./index.ts";

startServer();
