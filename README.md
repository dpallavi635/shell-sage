```
   _____ _  _ ___ _    _     ___  _   ___ ___
  / __  | || | __| |  | |   / __|/_\ / __| __|
  \__ \ | __ | _|| |__| |__ \__ \ _ \ (_ | _|
  |___/_|_||_|___|____|____||___/_/ \_\___|___|
  plain english -> shell. you approve. it runs.
```

# shell-sage

terminal agent. you type what you want in english; it proposes ONE shell
command + a one-line why, then waits for your `y`. destructive patterns are
caught locally and need a second `RUN` confirm. nothing executes without you.

```
you ──"undo my last git commit"──▶ sage.py
                                     │
                                     ├─ bedrock.converse  (haiku)
                                     │     ▲ aws, pay-per-call
                                     ▼
                             $ git reset --soft HEAD~1
                             keeps your changes, drops the commit
                             run it? [y/N] _
```

## what / who
- a dev who half-remembers a command and wants it right, fast.
- not a chat bot. one request -> one vetted command -> your call.

## stack
| piece      | choice                        | why                     |
|------------|-------------------------------|-------------------------|
| runtime    | single-file python CLI        | no server, no deploy    |
| brain      | amazon bedrock (`converse`)   | pay-per-call, no infra  |
| model      | claude 3.5 haiku (default)    | cheap, fast, good enough|
| ui         | colored terminal REPL         | zero deps beyond boto3  |
| infra      | none. no cloudformation.      | runs on your machine    |

## run — step by step

**Step 1 — python 3.9+**
```
python --version
```

**Step 2 — install the one dep**
```
pip install -r requirements.txt
```

**Step 3 — aws creds (bedrock needs them)**
```
aws configure            # or: aws sso login --profile <name>
```
you also need **Bedrock model access** enabled for your model+region
(Bedrock console -> Model access -> enable Claude 3.5 Haiku).

**Step 4 — first run (one-time wizard)**
```
python sage.py
```
answers 3 prompts (region / model id / optional profile), writes
`~/.shell-sage.ini` (chmod 600). defaults: `us-west-2`,
`anthropic.claude-3-5-haiku-20241022-v1:0`.

**Step 5 — use it**
```
python sage.py                       # interactive REPL
python sage.py "find big files here" # one-shot
```
type `exit` to leave the REPL.

## safety
- every command is shown + explained BEFORE anything runs.
- default answer is **No** (bare enter skips).
- local regex guard blocks `rm -rf /`, `mkfs`, `dd if=`, fork-bombs,
  `chmod -R 777 /`, `git push --force`, `DROP TABLE`, … those demand a typed
  `RUN`.

## cost / cleanup
- cost = per bedrock call only. no always-on resources, nothing to tear down.
- to remove: `pip uninstall boto3` (if unwanted) + `del ~/.shell-sage.ini`.

## files
```
shell-sage/
├── sage.py            # the whole agent
├── requirements.txt   # boto3
└── README.md
```
