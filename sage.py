#!/usr/bin/env python3
# shell-sage — terminal agent. plain english -> shell command.
# runtime: local python CLI. aws: bedrock (converse). no cloudformation.
# flow: ask -> model proposes cmd + 1-line why -> you confirm -> run.
import json
import os
import re
import subprocess
import sys
import configparser
from pathlib import Path

CFG = Path.home() / ".shell-sage.ini"
DEFAULT_MODEL = "anthropic.claude-3-5-haiku-20241022-v1:0"
DEFAULT_REGION = "us-west-2"

# ---- ascii ---------------------------------------------------------------
BANNER = r"""
   _____ _  _ ___ _    _     ___  _   ___ ___
  / __  | || | __| |  | |   / __|/_\ / __| __|
  \__ \ | __ | _|| |__| |__ \__ \ _ \ (_ | _|
  |___/_|_||_|___|____|____||___/_/ \_\___|___|
  plain english -> shell. you approve. it runs.
"""

C = {
    "dim": "\033[2m", "b": "\033[1m", "r": "\033[0m",
    "cy": "\033[36m", "gr": "\033[32m", "ye": "\033[33m", "rd": "\033[31m",
}
def paint(s, c):
    if not sys.stdout.isatty():
        return s
    return f"{C[c]}{s}{C['r']}"

# ---- danger scan (local guard, before any run) ---------------------------
DANGER = [
    r"\brm\s+-rf?\s+/\S*", r"\bmkfs\b", r"\bdd\s+if=", r":\(\)\s*\{",
    r"\bshutdown\b", r"\breboot\b", r">\s*/dev/sd", r"\bchmod\s+-R\s+777\s+/",
    r"\bgit\s+push\s+.*--force", r"\bDROP\s+TABLE\b",
]
def is_dangerous(cmd):
    return [p for p in DANGER if re.search(p, cmd, re.IGNORECASE)]

# ---- config / first run --------------------------------------------------
def load_cfg():
    cp = configparser.ConfigParser()
    if CFG.exists():
        cp.read(CFG)
    if "sage" not in cp:
        cp["sage"] = {}
    return cp

def save_cfg(cp):
    with open(CFG, "w") as f:
        cp.write(f)
    try:
        os.chmod(CFG, 0o600)
    except OSError:
        pass

def first_run():
    print(paint(BANNER, "cy"))
    print("first run. let's wire you to bedrock. 3 answers.\n")
    cp = load_cfg()
    region = input(f"  aws region [{DEFAULT_REGION}]: ").strip() or DEFAULT_REGION
    model = input(f"  model id [{DEFAULT_MODEL}]: ").strip() or DEFAULT_MODEL
    profile = input("  aws profile [default/env creds -> leave blank]: ").strip()
    cp["sage"]["region"] = region
    cp["sage"]["model"] = model
    cp["sage"]["profile"] = profile
    save_cfg(cp)
    print(paint(f"\n  wrote {CFG} (chmod 600). you're set.\n", "gr"))
    return cp

# ---- bedrock -------------------------------------------------------------
SYS = (
    "You are shell-sage, a terminal assistant. Given a user's plain-English "
    "request and their OS, reply with STRICT JSON only: "
    '{"cmd": "<single shell command>", "why": "<one short sentence>"}. '
    "No markdown, no code fences, no extra text. Prefer safe, non-destructive, "
    "widely-available commands. If the request is unsafe or impossible, set cmd "
    'to "" and explain in why.'
)
def ask_model(cp, prompt):
    try:
        import boto3
    except ImportError:
        die("boto3 not installed. run: pip install boto3")
    region = cp["sage"].get("region", DEFAULT_REGION)
    model = cp["sage"].get("model", DEFAULT_MODEL)
    profile = cp["sage"].get("profile", "").strip()
    session = boto3.Session(profile_name=profile) if profile else boto3.Session()
    brt = session.client("bedrock-runtime", region_name=region)
    osname = f"{sys.platform} ({os.name})"
    try:
        resp = brt.converse(
            modelId=model,
            system=[{"text": SYS}],
            messages=[{"role": "user", "content": [
                {"text": f"OS: {osname}\nRequest: {prompt}"}]}],
            inferenceConfig={"maxTokens": 300, "temperature": 0.2},
        )
    except Exception as e:  # friendly error, not a stack trace
        msg = str(e)
        if "AccessDenied" in msg or "could not be found" in msg:
            die(f"bedrock refused model '{model}' in {region}.\n"
                f"  -> enable model access in the Bedrock console (that region),\n"
                f"     or edit {CFG} to a model/region you have.")
        if "credential" in msg.lower() or "token" in msg.lower():
            die("no aws credentials. run 'aws configure' or 'aws sso login',\n"
                "  then retry. (set a profile via first-run if needed.)")
        die(f"bedrock call failed: {msg}")
    text = "".join(b.get("text", "") for b in resp["output"]["message"]["content"])
    return parse(text)

def parse(text):
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            d = json.loads(m.group(0))
            return d.get("cmd", "").strip(), d.get("why", "").strip()
        except json.JSONDecodeError:
            pass
    return "", f"(could not parse model reply: {text[:120]})"

def die(msg):
    print(paint("\n  ✗ " + msg, "rd"), file=sys.stderr)
    sys.exit(1)

# ---- repl ----------------------------------------------------------------
def run_once(cp, prompt):
    cmd, why = ask_model(cp, prompt)
    if not cmd:
        print(paint(f"  sage: {why or 'no command.'}", "ye"))
        return
    print()
    print(paint("  $ " + cmd, "b"))
    print(paint("    " + (why or "—"), "dim"))
    hits = is_dangerous(cmd)
    if hits:
        print(paint("  ⚠ looks destructive. refusing to auto-run.", "rd"))
        print(paint(f"    matched: {hits[0]}", "dim"))
    ans = input(paint("  run it? [y/N] ", "ye")).strip().lower()
    if ans != "y":
        print(paint("    skipped.\n", "dim"))
        return
    if hits:
        ans2 = input(paint("  really run a destructive command? type RUN: ", "rd")).strip()
        if ans2 != "RUN":
            print(paint("    aborted.\n", "dim"))
            return
    try:
        subprocess.run(cmd, shell=True)
    except KeyboardInterrupt:
        print(paint("\n    interrupted.", "dim"))
    print()

def repl(cp):
    print(paint(BANNER, "cy"))
    print(paint("  ask in english. 'exit' to quit.\n", "dim"))
    while True:
        try:
            prompt = input(paint("sage> ", "gr")).strip()
        except (EOFError, KeyboardInterrupt):
            print(paint("\n  bye.", "dim"))
            return
        if not prompt:
            continue
        if prompt in ("exit", "quit", ":q"):
            print(paint("  bye.", "dim"))
            return
        run_once(cp, prompt)

def main():
    if not CFG.exists():
        cp = first_run()
    else:
        cp = load_cfg()
    args = sys.argv[1:]
    if args:
        run_once(cp, " ".join(args))
    else:
        repl(cp)

if __name__ == "__main__":
    main()
