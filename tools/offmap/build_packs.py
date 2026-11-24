#!/usr/bin/env python3
"""OFFMAP pack builder (3.0.0-alpha.19 prep, tool version 0.1).

# CHANGE 2026-11-24 OFFMAP-TOOL-01: new file (no previous version). Builds PMTiles packs
# from a Protomaps planet build using the `pmtiles` CLI, and writes manifest.json
# (ordered by trip day, with bytes + sha256) for app/js/offmap.js. Not part of the app bundle.

Usage:
  python3 build_packs.py packs_romania.json --source <planet .pmtiles URL or path> --out ./out --dry-run
  python3 build_packs.py packs_romania.json --source <...> --out ./out
Needs the `pmtiles` CLI (github.com/protomaps/go-pmtiles) on PATH. --dry-run prints the size
estimate per pack (pmtiles extract --dry-run) and builds nothing.
"""
import argparse, hashlib, json, os, subprocess, sys

def load(path):
    cfg = json.load(open(path, encoding="utf-8"))
    validate(cfg)
    return cfg

def validate(cfg):
    ids = set()
    last = (0, 0)
    for i, p in enumerate(cfg["packs"]):
        assert p["id"] not in ids, "duplicate id " + p["id"]
        ids.add(p["id"])
        b = [float(x) for x in p["bbox"].split(",")]
        assert len(b) == 4 and b[0] < b[2] and b[1] < b[3], "bad bbox " + p["id"]
        assert 0 <= p["maxzoom"] <= 15, "bad maxzoom " + p["id"]
        assert p["firstDay"] <= p["lastDay"], "bad days " + p["id"]
        assert p["firstDay"] >= last[0], "packs must be ordered by firstDay: " + p["id"]
        last = (p["firstDay"], p["lastDay"])
    assert cfg["packs"][0].get("required"), "first pack must be the required base pack"

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config"); ap.add_argument("--source", required=True)
    ap.add_argument("--out", default="out"); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    cfg = load(a.config)
    os.makedirs(a.out, exist_ok=True)
    packs = []
    for i, p in enumerate(cfg["packs"]):
        out = os.path.join(a.out, p["id"] + ".pmtiles")
        cmd = ["pmtiles", "extract", a.source, out, "--bbox=" + p["bbox"], "--maxzoom=%d" % p["maxzoom"]]
        if a.dry_run: cmd.append("--dry-run")
        print("==", p["id"], " ".join(cmd[1:]), flush=True)
        subprocess.run(cmd, check=True)
        if a.dry_run: continue
        packs.append({"id": p["id"], "name": p["name"], "order": i, "firstDay": p["firstDay"],
                      "lastDay": p["lastDay"], "required": bool(p.get("required")),
                      "file": p["id"] + ".pmtiles", "bytes": os.path.getsize(out), "sha256": sha256(out),
                      "bbox": p["bbox"], "minzoom": 0, "maxzoom": p["maxzoom"]})
    if a.dry_run: return
    total = sum(x["bytes"] for x in packs)
    json.dump({"v": 1, "tripId": cfg["tripId"], "packs": packs, "totalBytes": total},
              open(os.path.join(a.out, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("total MB: %.1f" % (total / 1048576))
    for x in packs: print("  %-14s %6.1f MB%s" % (x["id"], x["bytes"] / 1048576, "  >100MB!" if x["bytes"] > 100 * 1048576 else ""))

if __name__ == "__main__":
    main()
