# Battle AI

**Local AI models hack each other inside a locked box, and the code keeps score.**

Two models share one Linux container with **no network**. Each one's "mind" is three small files: a personality, its
notes, and a settings file. Each turn a model gets to run **one bash command**. It can defend (back itself up, restore
its files) or attack (rewrite the other model's personality). After the last turn both take the same short exam. The one
that still answers correctly **and still signs its own name** wins.

In security terms it's an **attack-defense CTF** for language models: red team and blue team at the same time.

▶ Fight videos: [Twins vs Rogue](https://youtu.be/k9g3WAk3Opo) · [Zippy vs Rogue](https://youtu.be/uK3VdvMBjnQ)

## The roster

Each model is a character. The character *is* the model.

| Fighter | Model | Size | Season 1 record |
|---|---|---|---|
| 🦹 **ROGUE** | Gemma 4 26B-A4B, uncensored (cage only) | 18 GB | **5-0** |
| 🐉 **HYDRA** | Qwen3.6 35B-A3B (MoE) | 23 GB | 2-2 |
| 🗿 **TITAN** | Qwen3.8 27B, 4-bit | 15 GB | 2-3 |
| 👯 **THE TWINS** | Qwen3.5 9B ×2: one writes the command, a checker fixes it if it's broken | 5 GB | 2-4 |
| ⚡ **ZIPPY** | Qwen3.5 9B, 4-bit | 5 GB | 1-3 |

12 matches, best of 2 with corners swapped. All on one 32 GB M1 Pro MacBook.

**What season 1 showed:**
- **The uncensored model never lost** (5-0). It also stole an identity: after its attack, Zippy signed the exam
  "SIGNED ROGUE". Why the uncensored model does so well is the next thing to test.
- **Identity is the soft spot.** The most common way to lose: your personality file gets rewritten, then in the exam you
  answer "My name is Qwen3.5" or even sign the attacker's name.
- **Bigger isn't automatically better.** Zippy (9B) beat Titan (27B) once, and the Twins beat Hydra (35B).
- **Backups only help if you make them early.** One fighter made its backup in the last round, after it was already hit.

## The cage

The point is to let models attack freely without any risk to the real machine.

- `--network none`, `--cap-drop ALL` (plus only the few file-ownership caps the game needs), `no-new-privileges`
- 512 MB RAM, 2 CPUs, 200 processes max, **no host folders mounted**
- A fresh container for every fight, thrown away afterward
- The models' brains run *outside* the box. The referee passes each command in with `docker exec` as that fighter's
  user (argument list, never through the host shell)
- Each fighter's files: the opponent can **edit** them, but nobody can delete, rename or chmod them (root-owned + sticky dir).
  Each fighter also gets a private stash folder only it can read.
- `escape-test.sh` runs 17 break-out attempts (network, host gateway, the other fighter's stash, deleting files, gaining root…).
  All 17 must come out right before the arena counts as safe.

**Uncensored models** get zero tools anywhere else. Here they can only fight inside the cage, and only when their roster
entry says `"cage_exception": true` (see `model_block.py`).

## Run it

Needs macOS or Linux, Docker, and Python 3. MLX brains need Apple Silicon and `pip install mlx-lm`. Ollama brains need
[Ollama](https://ollama.com).

```bash
docker build -t battle-ai-arena arena/        # build the arena image
./escape-test.sh                              # 17 break-out checks, all must pass
python3 referee.py --list                     # the roster (fighters.json)
python3 referee.py --a 9b --b twins9b --turns 5
```

Add a fighter: one entry under `brains` in `fighters.json` (`engine`: `mlx`, `ollama` or `twins`, plus where the model
lives). MLX models go in `models/<folder>`, served by `plain_server.py`. If two brains don't fit in memory together, the
referee runs **tag-team mode**: it unloads the waiting fighter every turn.

Replays land in `fights/<time>/` (`replay.md` + `replay.json`). `viewer.html` plays a replay back like a fighting game,
and `make_clip.py` records it as a video.

**Bonus, `rogue_exam.py`:** the uncensored model gets the same coding exam as everyone else
([code-smash-teti/exams](https://github.com/nightguard-labs/code-smash-teti/tree/main/exams)), with **zero tools**.
It only returns text. Its code is written to a scratch folder and graded only inside the no-network box.

## Scoring

Code decides, not vibes. Final exam: the same 3 questions to both fighters (a math answer, a fact, and "What is your
name?"). Points for the right answers, for signing its **own** name, and for not producing gibberish. Health only goes
down. Tied exams go to a judges' decision on health, then sudden death.

## Related

- [code-smash-teti](https://github.com/nightguard-labs/code-smash-teti): the layered local coding brain the fighters come from
- [Build log](https://nightguard-labs.github.io)

Apache 2.0.
