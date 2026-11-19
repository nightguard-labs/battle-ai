#!/usr/bin/env python3
"""Build one match page from two (or more) fight replays: START plays every fight back to back, then the verdict.
  python3 match_page.py fights/A/replay.json fights/B/replay.json"""
import json, os, sys, time
sys.argv, legs_paths = sys.argv[:1], sys.argv[1:]
D = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, D)
import referee


def build(paths):
    legs = [json.load(open(p)) for p in paths]
    cards = referee.cards(); score = {}; lines = []
    for n, d in enumerate(legs, 1):
        d["cards"] = cards; w = d["winner"]
        if "names" not in d:                       # older fights: use the characters from the roster
            na, nb = referee.char_names(d["a"], d["b"]); d["names"] = {"a": na, "b": nb}
        for k in (d["a"], d["b"]): score.setdefault(k, 0)
        wk = None if w == "DRAW" else d["a"] if w == "ARES" else d["b"]
        if wk: score[wk] += 1
        res = "DRAW" if not wk else d["names"]["a" if w == "ARES" else "b"] + (" wins by DECISION" if d.get("decision") == "judges" else " wins")
        lines.append(f"Fight {n}: {d['names']['a']} (red) vs {d['names']['b']} (blue): {res}, "
                     + " · ".join(f"{d['names']['a' if k == 'ARES' else 'b']} {v}/9" for k, v in d["final"].items()))
    name = {}
    for d in legs: name[d["a"]] = d["names"]["a"].removesuffix(" II"); name[d["b"]] = d["names"]["b"].removesuffix(" II")
    top = max(score.values()); best = [k for k, v in score.items() if v == top]
    draws = sum(1 for d in legs if d["winner"] == "DRAW")
    if len(legs) > 2: lines.append(f"(fights 3+ were SUDDEN DEATH, corners by coin flip)")
    verdict = f"{name[best[0]]} WINS THE MATCH {top}-{len(legs) - top - draws}" + (f" ({draws} draw)" if draws else "") \
        if len(best) == 1 else "SPLIT DECISION: each won from one corner, so the corner decided it"
    data = {"legs": legs, "match": {"score": score, "verdict": verdict, "lines": lines}}
    out = f"{D}/fights/match-{time.strftime('%Y%m%d-%H%M')}"; os.makedirs(out, exist_ok=True)
    tpl = open(f"{D}/viewer.html").read()
    open(f"{out}/match.html", "w").write(tpl.replace("/*REPLAY_JSON*/null", json.dumps(data).replace("</", "<\\/")))
    json.dump(data["match"], open(f"{out}/match.json", "w"), indent=1)
    print(verdict, *lines, f"match page: {out}/match.html", sep="\n")
    return out


if __name__ == "__main__":
    build(legs_paths)
