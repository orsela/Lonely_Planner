// Plan_Travel Edge Function `invite-manager` entry point · version 3.0.0-alpha.8.0 · F21 (first version: F03)
// CHANGE 2026-10-27 F21-FN-10: version line only (index.ts changed; this file's code is unchanged; was alpha.4.1).
// CHANGE 2026-10-12 F04-NAME-01: version line only.
// CHANGE 2026-10-12 F04-FN-05: version line only (index.ts changed; this file's code is unchanged).
// CHANGE 2026-10-09 F03-FN-02: new file. Deployed entry point; starts the server defined in index.ts (which stays
//   importable by tests without starting a server).
import { startServer } from "./index.ts";

startServer();
