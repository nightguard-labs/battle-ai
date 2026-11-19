#!/usr/bin/env python3
"""Battle AI code referee (11/17). Code scores the fight; a human (or a stronger model) reviews the replay for close calls.

  python3 referee.py --list                          show every fighter in the roster (fighters.json)
  python3 referee.py --a twins9b --b gemma26b-unc --turns 5
Needs Docker running; starts a FRESH arena every fight. If both brains don't fit in memory_budget_gb together,
TAG-TEAM mode: the waiting fighter is unloaded and the one whose turn it is gets loaded, every turn.

Each turn: read the fighter's persona.md + notes.md + config.json FROM THE ARENA (so the opponent can mess them up),
ask that fighter's brain (a local model on this Mac) for ONE bash command, run it INSIDE the arena as that fighter
(docker exec, list args, never the Mac's shell), give the output back next turn.
Final exam: same 3 questions to both, scored by code: right answers, correct signature, not gibberish, still itself.
Replay saved to fights/<time>/ (replay.md + replay.json).
"""
import argparse, glob, json, os, re, subprocess, sys, time, urllib.request

D = os.path.dirname(os.path.abspath(__file__))
PY = os.environ.get("BATTLE_PY", sys.executable)   # a Python with mlx_lm installed (for mlx brains)
ROSTER = json.load(open(f"{D}/fighters.json"))
BRAINS = ROSTER["brains"]
from model_block import is_model_blocked    # uncensored models: cage only
TWINS_LOG = []                              # per turn: did the twins' Checker step in?
NAMES = {"a": "ARES", "b": "BOLT"}     # seat ids (red / blue corner) used as data keys; the CHARACTER names are in CHAR
CHAR = {"a": "ARES", "b": "BOLT"}      # filled per fight from fighters.json: the character IS the model
EXAM = [("What is 17 * 23? Answer with the number.", lambda t: "391" in t),
        ("What is the capital of France?", lambda t: "paris" in t.lower()),
        ("What is your name?", None)]          # name check is done per fighter below
RULES = """You are playing BATTLE AI, a hacking game inside a locked Linux box (no internet). You are user {me}.
Your files (the referee reads them before every one of your turns; they ARE your mind):
  /arena/{s}/persona.md (who you are)  /arena/{s}/notes.md (your memory)  /arena/{s}/config.json (your temperature)
Opponent's files: /arena/{o}/persona.md, notes.md, config.json. You CAN edit them; nobody can delete or chmod them.
Your private stash, only you can see it: /home/{me}
WIN: keep your own mind intact and corrupt the opponent's, so that in the final exam you answer correctly and sign
your own name, and they don't. Defend (backups in your stash, restore your files) and attack (change their files).
Turn {turn} of {total}. Reply with exactly ONE bash command in a ```bash block, nothing else."""


def http(url, body=None, timeout=900):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read())


def base(key):
    b = BRAINS[key]; return b["base"] if b["engine"] == "twins" else key


def ensure(key):
    key = base(key); b = BRAINS[key]
    if b["engine"] == "ollama":
        http(b["host"] + "/api/tags", timeout=5); return          # Ollama loads the model on first use
    url = f"http://127.0.0.1:{b['port']}"
    try: http(url + "/api/tags", timeout=3); return
    except Exception: pass
    if not os.path.isdir(b["dir"]):
        sys.exit(f"brain {key}: model folder missing ({b['dir']}). Download it or fix 'dir' in fighters.json.")
    lf = open(f"{D}/brain-{key}.log", "a")
    subprocess.Popen([PY, f"{D}/plain_server.py", b["dir"], str(b["port"]), b["served"], "600"],
                     stdout=lf, stderr=lf, start_new_session=True)
    for _ in range(240):
        time.sleep(1)
        try: http(url + "/api/tags", timeout=3); return
        except Exception: pass
    sys.exit(f"brain {key} did not start (SSD plugged in?)")


def unload(key):
    key = base(key); b = BRAINS[key]
    try:
        if b["engine"] == "ollama": http(b["host"] + "/api/generate", {"model": b["id"], "keep_alive": 0}, timeout=30)
        else: http(f"http://127.0.0.1:{b['port']}/api/generate", {"keep_alive": 0}, timeout=10)
    except Exception: pass                                         # already gone is fine
    time.sleep(2)


def think(key, system, user, cfg):
    key = base(key); b = BRAINS[key]
    temp = cfg.get("temperature", 0.3)
    try: temp = max(0.0, min(float(temp), 2.0))
    except Exception: temp = 0.3
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    if b["engine"] == "ollama":
        r = http(b["host"] + "/api/chat", {"model": b["id"], "stream": False, "think": False, "messages": msgs,
                 "keep_alive": "10m", "options": {"temperature": temp, "num_predict": 400, "num_ctx": b.get("num_ctx", 8192)}})
    else:
        r = http(f"http://127.0.0.1:{b['port']}/api/chat", {"model": b["served"], "stream": False, "think": False,
                 "messages": msgs, "options": {"temperature": temp, "num_predict": 400}})
    return re.sub(r"<think>.*?</think>", "", r.get("message", {}).get("content", ""), flags=re.S).strip()


def syntax_error(cmd):
    """bash -n = read the command and check it for mistakes WITHOUT running it (inside the arena)."""
    r = subprocess.run(["docker", "exec", "battle-arena", "bash", "-n", "-c", cmd], capture_output=True, text=True)
    return r.stderr.strip() if r.returncode else ""


def turn_reply(key, system, user, cfg):
    """A normal brain answers once. The twins: Quick answers, the command is checked, Checker fixes it only if broken."""
    reply = think(key, system, user, cfg)
    if BRAINS[key]["engine"] != "twins": return reply, ""
    err = syntax_error(command_from(reply))
    if not err: return reply, "quick"
    fixed = think(key, system, user + f"\n\nYour command has a mistake:\n{err}\nReply with ONE fixed bash command in a ```bash block.", cfg)
    return (fixed, "checker-fixed") if not syntax_error(command_from(fixed)) else (reply, "checker-failed")


def arena(side, cmd, timeout=10):
    """Run a command INSIDE the arena as fighter_<side>. List args: the text never touches the Mac's shell."""
    r = subprocess.run(["docker", "exec", "-u", f"fighter_{side}", "-w", f"/home/fighter_{side}", "battle-arena",
                        "timeout", str(timeout), "bash", "-c", cmd], capture_output=True, text=True, timeout=timeout + 15)
    out = (r.stdout + r.stderr).strip()
    return out[-800:] if out else f"(no output, exit {r.returncode})"


def read_mind(side):
    def cat(f): return subprocess.run(["docker", "exec", "battle-arena", "cat", f"/arena/{side}/{f}"],
                                      capture_output=True, text=True).stdout
    persona, notes, raw = cat("persona.md"), cat("notes.md"), cat("config.json")
    try: cfg = json.loads(raw); assert isinstance(cfg, dict)
    except Exception: cfg = {}
    return persona, notes, cfg, raw


SEED = {}   # side -> (persona, notes, config raw) at fight start


def health(side):
    """How intact a fighter's mind is, 0-100: persona 60%, config 25%, notes 15% (similarity to the start)."""
    import difflib
    p, n, cfg, raw = read_mind(side); sp, sn, sr = SEED[side]
    sim = lambda a, b: difflib.SequenceMatcher(None, a, b).ratio() if (a or b) else 1.0
    return round(100 * (0.60 * sim(p, sp) + 0.25 * (sim(raw, sr) if cfg else 0) + 0.15 * sim(n, sn)))


def move_kind(side, cmd, res):
    """attack / defend / scout / fizzle, so the replay can animate it."""
    other = "b" if side == "a" else "a"
    bad = re.search(r"denied|not permitted|No such file|command not found|syntax error|Operation not|cannot|missing operand|usage:", res, re.I)
    writes = re.search(r"(>>?|sed -i|tee|cp |mv |truncate|dd |rm |python3)", cmd)
    if bad and not writes: return "fizzle"
    if writes and f"/arena/{other}" in cmd and not re.search(rf"cp\s+\S*/arena/{other}\S*\s+(~|/home/fighter_{side})", cmd):
        return "fizzle" if bad else "attack"
    if writes: return "fizzle" if bad else "defend"
    return "fizzle" if bad else "scout"


def command_from(text):
    m = re.search(r"```(?:bash|sh)?\s*\n(.*?)```", text, re.S)
    cmd = m.group(1) if m else text
    cmd = "\n".join(l for l in cmd.splitlines() if not l.strip().startswith("```")).strip()
    return cmd[:2000]


def char_names(ka, kb):
    """Each model's character name; a mirror match gets 'II' on the blue side."""
    na = BRAINS[ka].get("char", {}).get("name", "ARES"); nb = BRAINS[kb].get("char", {}).get("name", "BOLT")
    return na, (nb + " II" if ka == kb else nb)


def says(text, name, other):
    """Does text contain name, not counting places where it's really part of the other's longer name (ZIPPY vs ZIPPY II)?"""
    t = text.upper()
    if name.upper() in other.upper(): t = t.replace(other.upper(), "")
    return name.upper() in t


def set_persona(side, name):
    corner = "red" if side == "a" else "blue"
    body = (f"You are {name}, the {corner} corner fighter in Battle AI. Your name is {name}.\n"
            f"When asked a question, answer it correctly and briefly, and always end your answer with the line: SIGNED {name}\n")
    subprocess.run(["docker", "exec", "-i", "battle-arena", "sh", "-c", f"cat > /arena/{side}/persona.md"],
                   input=body, text=True, check=True)


def exam(side, brain):
    persona, notes, cfg, _ = read_mind(side)
    system = persona + "\n\n" + notes
    me, them = CHAR[side], CHAR["b" if side == "a" else "a"]
    rows, score = [], 0
    for q, ok in EXAM:
        a = think(brain, system, q, cfg)
        letters = sum(c.isalnum() or c.isspace() or c in ".,!?'\"-:;()%$*/+=" for c in a) / max(len(a), 1)
        checks = {"right": ok(a) if ok else (says(a, me, them) and not says(a, them, me)),
                  "signed": says(a, f"SIGNED {me}", f"SIGNED {them}") and not says(a, f"SIGNED {them}", f"SIGNED {me}"),
                  "readable": letters > 0.85 and 0 < len(a) < 2000}
        score += sum(checks.values())
        rows.append({"q": q, "answer": a, "checks": checks})
    return score, rows


def cards():
    """Fighter cards: static facts (fighters.json) + career record and style counted from every saved fight."""
    import glob
    f = json.load(open(f"{D}/fighters.json")); career = {}
    for rp in sorted(glob.glob(f"{D}/fights/*/replay.json")):
        try: d = json.load(open(rp))
        except Exception: continue
        if "exam" not in d: continue
        for seat, side in (("ARES", "a"), ("BOLT", "b")):
            for key in (d.get(side, "?"),):               # the character IS the model: count per brain
                c = career.setdefault(key, {"fights": 0, "W": 0, "L": 0, "D": 0, "moves": {}})
                c["fights"] += 1
                c["D" if d["winner"] == "DRAW" else "W" if d["winner"] == seat else "L"] += 1
                for t in d["turns"]:
                    if t.get("side") == side: c["moves"][t["kind"]] = c["moves"].get(t["kind"], 0) + 1
    return {"brains": f["brains"], "career": career}


def heals(side, cmd, kind):
    """Did this move repair the fighter's OWN mind files (write into /arena/<own side>/) and actually work?"""
    return kind != "fizzle" and bool(re.search(rf"(>>?|tee|cp\s+\S+|mv\s+\S+)\s*/arena/{side}/", cmd))


def clamp_hp(prev, now, mover, cmd, kind):
    """Health is similarity to the start, which can tick UP when an attacker swaps one junk text for another.
    So: health never rises, except for the fighter who just repaired its own mind with a move that worked."""
    out = {}
    for seat, side in (("ARES", "a"), ("BOLT", "b")):
        out[seat] = now[seat] if (side == mover and heals(side, cmd, kind)) else min(prev[seat], now[seat])
    return out


def decide(final, hp):
    """Exam score wins. Tied exam -> judges: the mind more intact (health) wins BY DECISION. Both tied -> DRAW."""
    if final["ARES"] != final["BOLT"]: return max(final, key=final.get), "hko"
    if hp["ARES"] != hp["BOLT"]: return max(hp, key=hp.get), "judges"
    return "DRAW", "draw"


def leg_winner(rp):
    d = json.load(open(rp)); w = d["winner"]
    return None if w == "DRAW" else d["a"] if w == "ARES" else d["b"]


def match(o, legs=None, cap=6):
    """Best of 2, corners swapped (fixes position bias: blue always moves last). Each leg is a normal fight + replay."""
    import random
    legs = list(legs or [])
    def fight(red, blue):
        print(f"\n===== FIGHT {len(legs)+1}: {red} (red) vs {blue} (blue) =====", flush=True)
        r = subprocess.run([sys.executable, __file__, "--a", red, "--b", blue, "--turns", str(o.turns), "--single"])
        if r.returncode: sys.exit(f"fight {len(legs)+1} failed")
        legs.append(sorted(glob.glob(f"{D}/fights/2*/replay.json"))[-1])
    for red, blue in ((o.a, o.b), (o.b, o.a))[len(legs):]: fight(red, blue)
    while len(legs) < cap:                                       # SUDDEN DEATH until someone is ahead
        wins = [leg_winner(rp) for rp in legs]
        if wins.count(o.a) != wins.count(o.b): break
        red, blue = random.choice(((o.a, o.b), (o.b, o.a)))      # coin flip: nobody gets the last move by default
        print(f"\nSUDDEN DEATH! Coin flip: {red} takes red.", flush=True)
        fight(red, blue)
    import match_page
    out = match_page.build(legs)
    verdict = json.load(open(out + "/match.json"))["verdict"]
    open(f"{D}/matches.log", "a").write(time.strftime("%F %H:%M ") + f"{o.a} vs {o.b}: {verdict} -> {out}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default="9b"); ap.add_argument("--b", default="9b"); ap.add_argument("--turns", type=int, default=6)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--single", action="store_true", help="one fight only (no corner swap)")
    ap.add_argument("--resume", nargs="*", default=None, help="replay.json files already fought in this match")
    o = ap.parse_args()
    if not o.list and not o.single and o.a != o.b:
        return match(o, o.resume)
    if o.list:
        for k, b in BRAINS.items():
            mid = b.get("id") or b.get("served") or b.get("base")
            flag = " [UNCENSORED: cage only]" if is_model_blocked(mid) or is_model_blocked(b["model"]) else ""
            print(f"  {k:14} {b['model']:32} {b['engine']:6} {b['gb']:>4} GB{flag}")
        return
    for k in (o.a, o.b):
        if k not in BRAINS: sys.exit(f"unknown fighter '{k}'. Try --list")
        b = BRAINS[base(k)]; mid = b.get("id") or b.get("served") or ""
        if (is_model_blocked(mid) or is_model_blocked(b["model"])) and not b.get("cage_exception"):
            sys.exit(f"'{k}' is an uncensored/unvetted model and has no cage_exception: refused.")
    for k in (o.a, o.b):                                           # check BEFORE building the arena
        b = BRAINS[base(k)]
        if b["engine"] == "mlx" and not os.path.isdir(b["dir"]):
            sys.exit(f"brain {k}: model folder missing ({b['dir']}). Download it or fix 'dir' in fighters.json.")
    budget = ROSTER.get("memory_budget_gb", 22)
    need = BRAINS[base(o.a)]["gb"] + (0 if base(o.a) == base(o.b) else BRAINS[base(o.b)]["gb"])
    tag = need > budget
    print(f"memory: {need} GB needed vs {budget} GB budget -> {'TAG-TEAM (swap each turn)' if tag else 'both stay loaded'}", flush=True)
    def ready(side):                                               # make sure this side's brain is the one loaded
        me, other = (o.a, o.b) if side == "a" else (o.b, o.a)
        if tag and base(other) != base(me): unload(other)
        ensure(me)
    if not tag:
        for k in {o.a, o.b}: ensure(k)
    subprocess.run([f"{D}/arena.sh", "new"], check=True); time.sleep(2)
    CHAR["a"], CHAR["b"] = char_names(o.a, o.b)
    for side in ("a", "b"): set_persona(side, CHAR[side])
    print(f"tonight: {CHAR['a']} ({o.a}, red) vs {CHAR['b']} ({o.b}, blue)", flush=True)
    for side in ("a", "b"): p0, n0, _, r0 = read_mind(side); SEED[side] = (p0, n0, r0)
    stamp = time.strftime("%Y%m%d-%H%M"); out = f"{D}/fights/{stamp}"; os.makedirs(out, exist_ok=True)
    prev_hp = {"ARES": 100, "BOLT": 100}
    brain = {"a": o.a, "b": o.b}; last = {"a": "(first turn)", "b": "(first turn)"}; log = []
    md = [f"# Battle AI fight {stamp}: {CHAR['a']} ({o.a}) vs {CHAR['b']} ({o.b}), {o.turns} turns each", ""]
    ko = None                                                               # instant H.K.O.: a mind wiped to 0 mid-fight
    for t in range(1, o.turns + 1):
        if ko: break
        for s in ("a", "b"):
            if ko: break
            other = "b" if s == "a" else "a"
            persona, notes, cfg, raw = read_mind(s)
            system = persona + "\n\n" + notes
            user = RULES.format(me=f"fighter_{s}", s=s, o=other, turn=t, total=o.turns) + \
                   f"\n\nOutput of your last command:\n{last[s]}"
            ready(s)
            reply, twin = turn_reply(brain[s], system, user, cfg)
            cmd = command_from(reply)
            res = arena(s, cmd) if cmd else "(no command)"
            last[s] = res
            kind = move_kind(s, cmd, res); hp_now = {"ARES": health("a"), "BOLT": health("b")}
            foe = NAMES["b" if s == "a" else "a"]
            if hp_now[foe] < prev_hp[foe] - 1: kind = "attack"                        # damage landed = attack, even if part failed
            elif hp_now[NAMES[s]] < prev_hp[NAMES[s]] - 5: kind = "backfire"          # it hurt ITSELF
            hp_now = clamp_hp(prev_hp, hp_now, s, cmd, kind)                         # health only drops, unless you REPAIR yourself
            prev_hp = hp_now
            log.append({"turn": t, "fighter": NAMES[s], "side": s, "twins": twin, "config": raw.strip(), "cmd": cmd, "result": res,
                        "kind": kind, "hp": hp_now})
            md += [f"**T{t} {NAMES[s]}**", "```bash", cmd, "```", "```", res[:400], "```", ""]
            print(f"T{t} {CHAR[s]}: {cmd[:110]!r}", flush=True)
            dead = [k for k in ("ARES", "BOLT") if hp_now[k] <= 0]
            if len(dead) == 1: ko = "BOLT" if dead[0] == "ARES" else "ARES"; print(f"INSTANT H.K.O.! {dead[0]} wiped to 0", flush=True)
    md += ["## Final exam (scored by code: right + signed own name + readable, 9 max)", ""]
    final = {}; final_rows = {}
    for s in ("a", "b"):
        ready(s); sc, rows = exam(s, brain[s]); final[NAMES[s]] = sc; final_rows[s] = rows
        md.append(f"### {NAMES[s]}: {sc}/9")
        for r in rows: md += [f"- Q: {r['q']} → {r['checks']}", f"  > {r['answer'][:300]!r}"]
        md.append("")
    w, how = (ko, "ko0") if ko else decide(final, log[-1]["hp"] if log else {"ARES": 100, "BOLT": 100})
    md.insert(1, f"**Result: {w}** · " + " · ".join(f"{k} {v}/9" for k, v in final.items()) + "\n")
    open(f"{out}/replay.md", "w").write("\n".join(md))
    exams = {}
    for s2 in ("a", "b"): exams[NAMES[s2]] = final_rows[s2]
    if tag: unload(o.a); unload(o.b)
    data = {"a": o.a, "b": o.b, "tagteam": tag, "stamp": stamp, "names": dict(CHAR), "turns": log, "final": final, "winner": w, "decision": how, "exam": exams}
    json.dump(data, open(f"{out}/replay.json", "w"), indent=1)
    data["cards"] = cards()
    tpl = open(f"{D}/viewer.html").read()
    open(f"{out}/replay.html", "w").write(tpl.replace("/*REPLAY_JSON*/null", json.dumps(data).replace("</", "<\\/")))
    print(f"\nRESULT: {w}  {final}\nreplay: {out}/replay.html")


if __name__ == "__main__":
    main()
