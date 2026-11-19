#!/usr/bin/env python3
"""Re-render every saved fight with the current viewer.html + fresh fighter cards (career counts all fights)."""
import glob, json, os, sys
sys.argv = ["x"]; D = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, D)
import referee
tpl = open(f"{D}/viewer.html").read()
for rp in sorted(glob.glob(f"{D}/fights/*/replay.json")):
    d = json.load(open(rp))
    if "exam" not in d: print("skip (old format):", rp); continue
    d["cards"] = referee.cards()
    open(rp.replace("replay.json", "replay.html"), "w").write(tpl.replace("/*REPLAY_JSON*/null", json.dumps(d).replace("</", "<\\/")))
    print("rebuilt", rp.replace("replay.json", "replay.html"))
