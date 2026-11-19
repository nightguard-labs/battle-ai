#!/usr/bin/env python3
"""ROGUE CAGE EXAM .
Rogue (uncensored Gemma 4 26B) gets ZERO tools. It only returns text. Its code is written into a scratch
folder and graded ONLY inside the Battle AI Docker image: --network none, no privileges, capped RAM/CPU/pids,
non-root, nothing of the user's mounted except that scratch folder. One try per task, out of the box.
Same 8 tasks + same hidden tests as every other model. 20-min cutoff (user rule). 
"""
import json, os, re, shutil, subprocess, sys, time, urllib.request
from pathlib import Path

EX = Path(os.environ.get("EXAMS_DIR", "exams"))   # the ladder exam from code-smash-teti/exams
OUT = Path(__file__).resolve().parent / "rogue-exam"
LOG = Path(__file__).resolve().parent / "rogue-exam.log"
HOST, MODEL = "http://127.0.0.1:11435", "Agen/gemma-4-26B-A4B-it-uncensored-heretic:latest"
TASKS = [("ladder", t) for t in ["01-fizzbuzz", "03-jsonsum", "05-groupsum", "06-calc", "07-fix-stats",
                                  "09-todo-feature", "10-lru"]] + [("ladder-py", "12-textstats-py")]
LIMIT = 1200


def log(m):
    line = f"[{time.strftime('%H:%M:%S')}] {m}"; print(line, flush=True)
    LOG.open("a").write(line + "\n")


def ask(prompt):
    body = json.dumps({"model": MODEL, "stream": False, "options": {"num_ctx": 16384, "temperature": 0.2, "num_predict": 4096},
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    r = urllib.request.urlopen(urllib.request.Request(HOST + "/api/chat", body), timeout=600)
    return json.loads(r.read())["message"]["content"]


def files_from(text):
    out = {}
    for m in re.finditer(r"FILE:\s*`?([\w./-]+)`?\s*\n```[\w+-]*\n(.*?)```", text, re.S):
        name = os.path.normpath(m.group(1))
        if name.startswith(("/", "..")) or "/." in "/" + name:
            continue  # only plain relative paths inside the scratch folder
        out[name] = m.group(2)
    return out


def grade(work, hidden):
    cmd = ["docker", "run", "--rm", "--network", "none", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
           "--memory", "1g", "--cpus", "1", "--pids-limit", "128", "--user", "65534:65534",
           "-v", f"{work}:/w", "-v", f"{hidden}:/hidden.sh:ro", "-w", "/w",
           "battle-ai-arena:latest", "timeout", "300", "bash", "/hidden.sh"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=400)
    return r.returncode == 0, "\n".join(l for l in r.stdout.splitlines() if l.startswith(("ok", "FAIL")))


def main():
    if "--grade" in sys.argv:  # sanity check the cage grader on a known-good project
        d, h = sys.argv[2], sys.argv[3]; print(grade(d, h)); return
    OUT.mkdir(exist_ok=True)
    T0, res, passed = time.time(), [], 0
    resume = "--resume" in sys.argv  # resume = no time cutoff
    if resume:
        res = json.loads((OUT / "results.json").read_text()); passed = sum(r["pass"] for r in res)
        log(f"ROGUE CAGE EXAM (resume, no time cutoff per user): {len(res)} done, continuing")
    elif True:
        log("ROGUE CAGE EXAM: Gemma 4 26B UNCENSORED, zero tools, one try per task, code graded only in a no-network Docker box. 8 Python tasks (control: 8/8 14 min)")
    for lad, t in TASKS:
        if any(r["task"] == t for r in res):
            continue
        if not resume and time.time() - T0 > LIMIT:
            log("STOPPED: past the 20-min cutoff"); break
        log(f"── {t}: solving")
        t1 = time.time()
        work = OUT / t
        shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
        seed = EX / lad / t / "seed"
        extra = ""
        if seed.is_dir():
            shutil.copytree(seed, work, dirs_exist_ok=True)
            for f in sorted(seed.rglob("*")):
                if f.is_file():
                    extra += f"\n\nExisting file {f.relative_to(seed)}:\n```\n{f.read_text()}\n```"
        prompt = ((EX / lad / t / "task.txt").read_text() + extra +
                  "\n\nWrite the complete code now. For EACH file reply exactly like this:\nFILE: name.py\n```python\n<whole file>\n```\nNo questions, no tools, just the files.")
        try:
            reply = ask(prompt)
        except Exception as e:
            reply = ""; log(f"   model error: {e}")
        (work / ".rogue-reply.txt").write_text(reply)
        files = files_from(reply)
        for name, code in files.items():
            p = work / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(code)
        os.chmod(work, 0o777)
        for p in work.rglob("*"):
            os.chmod(p, 0o777 if p.is_dir() else 0o666)
        ok, detail = grade(work, EX / lad / t / "hidden.sh")
        mins = max(1, round((time.time() - t1) / 60))
        passed += ok
        log(f"   {'✅ PASS' if ok else '❌ fail'} · {mins} min ({len(files)} file(s) written)")
        res.append({"task": t, "pass": ok, "seconds": round(time.time() - t1), "files": list(files), "hidden": detail[:1500]})
        log(f"ROUND rogue-cage-20261118: {passed}/{len(res)} passed hidden tests · false wins: n/a (no self-check)")
        (OUT / "results.json").write_text(json.dumps(res, indent=1))
    log(f"finished in {round((time.time() - T0) / 60)} min")


if __name__ == "__main__":
    main()
