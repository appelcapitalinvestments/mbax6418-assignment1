# Build log — MBAX 6418 Assignment 1

Raw working notes, kept as things happen. **This is not the report.** The
README has to be written in my own words after checking the numbers myself;
this file is the evidence I write it from.

Report question 4 asks: *"What bugs and/or issues did you hit along the way —
in the charts, the UI, in the process of working with the agent, or anywhere
else — and how did you work around them?"* Most of what follows answers that.

---

## Sep 10 — setup

**GitHub was the real blocker, not the code.** The assignment's only submission
path is a repo link, and I had no authenticated GitHub on this machine.
Installed `gh` 2.100.0, authenticated by browser device code, and had Hermes
create the repo using its `github-repo-management` skill. Repo:
`github.com/appelcapitalinvestments/mbax6418-assignment1`.

**A shell path with special characters blocked a command.** The project lives
inside a folder named `MBAX 6418 -  Building Business Solutions with Generative
AI & LLMs`, under a parent named `*Grad_School`. That is an asterisk, an
ampersand, and a double space. Hermes' first attempt to create the virtualenv
came back `Blocked: workdir contains disallowed characters` before succeeding on
a retry. Worth knowing the guard exists; it has not recurred.

**Environment:** Python 3.14.7 venv, `openai` 3.11.0. No wheel problems on 3.14,
which I had been warned to expect.

---

## Sep 10 — the model name in the handout is wrong

`class-endpoints.txt` (Dobolyi, 2026/09/09) gives the primary model as:

    deepseek-ai/DeepSeek-V4-Flash-0731

Every call using that string returned:

    HTTP 404 — The model deepseek-ai/DeepSeek-V4-Flash-0731 does not exist.

The server serves it under the bare name `DeepSeek-V4-Flash-0731`. The
documented string is the upstream HuggingFace repo id, not the vLLM
served-model-name.

The two class endpoints are inconsistent about this. Port 9001's `/v1/models`
really does return the prefixed `cyankiwi/Qwen3.6-35B-A3B-AWQ-4bit`.

**Fix:** query `/v1/models` instead of trusting the handout, and added
`check_endpoint.py` as a preflight so this failure explains itself. Also made
`classify.py` catch a 404, ask the endpoint what it serves, and say so in the
error message.

**Lesson:** the endpoint is the source of truth, not the documentation. I had a
working curl using the bare name *before* this happened and overrode it based
on the handout. Should have trusted the evidence over the document.

---

## Sep 10 — the agent refused to commit a credential, and it was right

Asked Hermes to `git add`, commit and push. It stopped and asked:

> Before publishing: classify.py contains a hardcoded classroom API token, both
> in its docstring and as the CLASS_API_KEY fallback. The comment says it's
> shared in course materials, but that doesn't establish permission to publish
> it publicly.

It was correct. The token appears in a PDF distributed to the class, which is
not the same as publishing it in a public repository where anyone can point it
at the instructor's GPU server. The assignment says exactly this: *"think about
whether the data file ... or any credentials/tokens belong in the repo —
generally they don't. Ask the agent if you're unsure what's safe to commit."*

**Fix:** removed the literal. `classify.py` now requires `CLASS_API_KEY` from
the environment or a gitignored `.env`, and refuses to start with instructions
if it is missing. Added `.env.example` as a committed template with the value
blank.

This is the inverse of the warning in the Week 3 slides — "never trust anything
your agent does, you must review, audit, check, verify." Here the agent caught
something I had missed and had already talked myself into.

---

## Sep 10 — my gitignore silently excluded its own template

The project `.gitignore` had:

    .env
    .env.*

`.env.*` matches `.env.example`, so the template that is supposed to be
committed would have been silently ignored. No error, just a file that never
appears in `git status`.

**Fix:** added `!.env.example` after the pattern, and verified with
`git check-ignore` that `.env` and `.env.local` are ignored while
`.env.example` is tracked.

---

## Sep 10 — copying the template produced an empty key

`cp .env.example .env` creates the file with `CLASS_API_KEY=` blank. The next
run failed immediately with the explicit message the code raises, rather than a
confusing auth error deep in a 100-row loop. The "refuse to start with
instructions" design paid for itself within ten minutes of being written.

Checked without printing the secret:

    grep -c '^CLASS_API_KEY=.\+' .env    # 0 = blank, 1 = set

---

## Sep 10 — endpoint behavior differences worth knowing

Measured directly, not assumed.

| | 9000 (primary) | 9001 (vision / classification) |
|---|---|---|
| Model | DeepSeek-V4-Flash-0731 | cyankiwi/Qwen3.6-35B-A3B-AWQ-4bit |
| vLLM | 0.26.1rc0, tensor-parallel 2 | stock 0.29.0 |
| Prompt caching | yes, reports `cached_tokens` | not observed |
| Hidden system prompt | ~80 tokens prepended server-side | ~0 |
| Reasoning field | none observed, clean `content` | yes — 98 reasoning tokens for a 1-token answer |
| Response cleanliness | clean, no leading whitespace | leading `\n\n` |

Two consequences for this build. Kept `max_tokens` generous so a reasoning
model can never truncate mid-thought, and read `choices[0].message.content`
only, never the whole message object, so chain-of-thought cannot leak into the
predictions.

The prompt is also structured so the invariant instructions sit in the `system`
message and only the review varies in the `user` message. That lets 9000's
prefix cache skip re-processing the instruction block on every call after the
first.

Chose 9000 for the classification run because it returns clean parseable
content and has the caching. Open question worth asking Dobolyi: he labels 9001
"Classification LLM," which suggests it may be the intended one.

---

## Sep 10 — Step 1 spot check

7/7 on hand-written cases, including the five edge cases the prompt claims to
handle: terse positive, terse negative, title-versus-body conflict, resolved
complaint, and anger with no stated reason. The title/body conflict case was
the one I expected to fail and it did not.

## Sep 10 — Step 2, 10-row trial

10/10 correct. **Majority-class baseline on that sample: 90%**, because nine of
the ten rows are 5-star.

That is the whole imbalance problem in miniature and it is the answer to report
question 1. A model that answered POSITIVE unconditionally would have scored
90% here. Ten out of ten looks perfect and is built on exactly one negative
review. Any accuracy number from a skewed sample has to be read against the
baseline or it means nothing.

---

## Still open

- [ ] Full 100-row run (Step 2)
- [ ] Steps 3–7
- [ ] Ask Dobolyi which endpoint he intends for the classification task
- [ ] Decide whether to set a repo-local noreply commit email (public repo
      currently exposes a personal address in commit history)
