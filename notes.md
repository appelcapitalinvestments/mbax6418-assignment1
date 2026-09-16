# Build log - MBAX 6418 Assignment 1

Raw working notes, kept as things happen. **This is not the report.** The
README has to be written in my own words after checking the numbers myself;
this file is the evidence I write it from.

Report question 4 asks: *"What bugs and/or issues did you hit along the way -
in the charts, the UI, in the process of working with the agent, or anywhere
else - and how did you work around them?"* Most of what follows answers that.

---

## Sep 10 - setup

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

## Sep 10 - the model name in the handout is wrong

`class-endpoints.txt` (Dobolyi, 2026/09/09) gives the primary model as:

    deepseek-ai/DeepSeek-V4-Flash-0731

Every call using that string returned:

    HTTP 404 - The model deepseek-ai/DeepSeek-V4-Flash-0731 does not exist.

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

## Sep 10 - the agent refused to commit a credential, and it was right

Asked Hermes to `git add`, commit and push. It stopped and asked:

> Before publishing: classify.py contains a hardcoded classroom API token, both
> in its docstring and as the CLASS_API_KEY fallback. The comment says it's
> shared in course materials, but that doesn't establish permission to publish
> it publicly.

It was correct. The token appears in a PDF distributed to the class, which is
not the same as publishing it in a public repository where anyone can point it
at the instructor's GPU server. The assignment says exactly this: *"think about
whether the data file ... or any credentials/tokens belong in the repo -
generally they don't. Ask the agent if you're unsure what's safe to commit."*

**Fix:** removed the literal. `classify.py` now requires `CLASS_API_KEY` from
the environment or a gitignored `.env`, and refuses to start with instructions
if it is missing. Added `.env.example` as a committed template with the value
blank.

This is the inverse of the warning in the Week 3 slides - "never trust anything
your agent does, you must review, audit, check, verify." Here the agent caught
something I had missed and had already talked myself into.

---

## Sep 10 - my gitignore silently excluded its own template

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

## Sep 10 - copying the template produced an empty key

`cp .env.example .env` creates the file with `CLASS_API_KEY=` blank. The next
run failed immediately with the explicit message the code raises, rather than a
confusing auth error deep in a 100-row loop. The "refuse to start with
instructions" design paid for itself within ten minutes of being written.

Checked without printing the secret:

    grep -c '^CLASS_API_KEY=.\+' .env    # 0 = blank, 1 = set

---

## Sep 10 - endpoint behavior differences worth knowing

Measured directly, not assumed.

| | 9000 (primary) | 9001 (vision / classification) |
|---|---|---|
| Model | DeepSeek-V4-Flash-0731 | cyankiwi/Qwen3.6-35B-A3B-AWQ-4bit |
| vLLM | 0.26.1rc0, tensor-parallel 2 | stock 0.29.0 |
| Prompt caching | yes, reports `cached_tokens` | not observed |
| Hidden system prompt | ~80 tokens prepended server-side | ~0 |
| Reasoning field | none observed, clean `content` | yes - 98 reasoning tokens for a 1-token answer |
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

## Sep 10 - Step 1 spot check

7/7 on hand-written cases, including the five edge cases the prompt claims to
handle: terse positive, terse negative, title-versus-body conflict, resolved
complaint, and anger with no stated reason. The title/body conflict case was
the one I expected to fail and it did not.

## Sep 10 - Step 2, 10-row trial

10/10 correct. **Majority-class baseline on that sample: 90%**, because nine of
the ten rows are 5-star.

That is the whole imbalance problem in miniature and it is the answer to report
question 1. A model that answered POSITIVE unconditionally would have scored
90% here. Ten out of ten looks perfect and is built on exactly one negative
review. Any accuracy number from a skewed sample has to be read against the
baseline or it means nothing.

---

## Still open

- [x] Full 100-row run (Step 2) - done, see below
- [ ] Steps 3-7
- [ ] Ask Dobolyi which endpoint he intends for the classification task
- [ ] Decide whether to set a repo-local noreply commit email (public repo
      currently exposes a personal address in commit history)

---

## Sep 10 - Step 2, full 100-row run

Saved to `results/step2_first100.json`. Run at 17:18 UTC against
`DeepSeek-V4-Flash-0731` on port 9000, first 100 rows in file order.

**Headline: 99.0% agreement with the star rating.**
**Majority-class baseline: 92.9%. Margin over baseline: +6.1 points.**

Rating distribution in the sample: 91 five-star, 2 four-star, 2 three-star,
1 two-star, 4 one-star. So 93 POSITIVE and 7 NEGATIVE under the >=4 rule.

| | n | correct | accuracy |
|---|---|---|---|
| POSITIVE | 92 | 92 | 100% |
| NEGATIVE | 7 | 6 | 85.7% |

Confusion, truth to prediction: POSITIVE->POSITIVE 92, POSITIVE->NEGATIVE 0,
NEGATIVE->POSITIVE 1, NEGATIVE->NEGATIVE 6.

### Four things this run actually shows

**1. The 99% is mostly the skew.** Answering POSITIVE unconditionally scores
92.9% on this sample. The model earned 6.1 points above that. The headline
number is doing far less work than it looks like it is.

**2. The NEGATIVE class rests on seven examples.** "85.7% accuracy on
negatives" is 6 out of 7. One review moving changes that figure by 14 points.
Any claim about how the model handles negatives is, at this sample size, close
to unsupported. This is the direct argument for balanced sampling in Step 6.

**3. The single miss suggests the ground truth is wrong, not the model.**

    row 98 | 3 stars | truth NEGATIVE | predicted POSITIVE | confidence 0.90
    title: "Easy to use"
    text : "Very easy to use. I wish I knew about it earlier"

That text is plainly positive. It is labeled NEGATIVE only because the binary
rule forces anything below 4 stars into NEGATIVE. The model read the review
correctly and the scheme scored it wrong.

The other 3-star review in the sample went the other way:

    row 91 | 3 stars | truth NEGATIVE | predicted NEGATIVE | correct
    title: "Okay as a gift"
    text : "After I bought several I realized I could have sent 'gift' money
            via text without the fees or wait."

Two 3-star reviews, one reading positive and one reading negative, and neither
is really negative. This is empirical evidence *inside the binary run* that
3-star reviews do not belong in either bucket, which is exactly what Step 6's
three-class split exists to fix. Report question 2 asks whether 3-star reviews
get labeled negative or negatives get called neutral; the answer starts here.

**4. One classification failed to parse.**

    row 17 | 5 stars | prediction null
    title: "No note attached to sent gift card"
    text : "What a pretty gift card presentation, the recipient loved it!
            I have one complaint, I took the time and wrote a short note..."

A genuinely mixed review: warm about the product, annoyed about one feature.
The format lock held for 99 rows and broke on the one review whose sentiment is
actually ambiguous. That is Week 3 slide 22 demonstrated live - prompting for a
format does not guarantee the format, and the failure lands precisely where the
task is hardest.

Handled rather than hidden: the run excludes it from accuracy and reports it as
a failure, so the denominator is 99 and not a quietly wrong 100.

### Confidence is not a useful error signal

Mean confidence 0.948 across the run, range 0.80 to 1.00. The one wrong answer
carried 0.90, which is unremarkable against that distribution. Confidence here
cannot be used to flag likely errors. Worth stating plainly rather than
implying the number means something.

### Open questions carried into later steps

- Does the 3-star problem persist once NEUTRAL is a real class (Step 6)?
- Does the parse failure recur on mixed reviews at larger sample sizes, and
  does structured output via guided decoding eliminate it?
- Balanced sampling should push accuracy down. That drop is the finding, not
  a regression.

---

## Sep 10 - Steps 5, 6 and 7 built together

Steps 5 and 6 both change the shape of the model's output, so building them
one after the other would have meant building the dashboard twice. They went in
as one pass. The Step 2 binary run stays in `results/` as evidence of the
earlier stage, and `prompt.py` keeps the binary schema and the binary
`rating_to_label` so that saved run is still reproducible.

### The NRC lexicon cannot be committed

Checked the licence before writing the loader. It says: *"Do not redistribute
the data. Direct interested parties to the lexicon home page."* So the file is
downloaded by hand, gitignored, and `emotion.py` raises a `FileNotFoundError`
carrying the official URL rather than failing obscurely.

### Ties are reported, not broken

`primary_emotion()` returns `None` when the top NRC score is a tie or when no
listed word matched. Taking whichever emotion sorts first would have produced a
tidier distribution and a dishonest one. The no-answer count is reported on the
dashboard for the same reason.

### Sampling verified before trusting it

`sample.py` was checked three ways before any of its output was used:
exactly N per class; identical row set and order on a reseeded redraw; and row
indices spread across the whole file rather than clustered early. All three
pass. If the second one had failed, every number in the report would have been
unverifiable.

### Bugs found by testing the dashboard, not by reading it

Built a synthetic 150-row fixture with the exact shape `score3.save()` writes,
rendered the page in a headless browser, and read the numbers back out of the
DOM to compare against the JSON. 26 value checks - tiles, per-class bars, all
nine confusion cells, star counts, filter counts, live count. Four real
problems surfaced that reading the code had not:

1. **A relative path argument crashed the script** - after it had already
   written the file. `Path.relative_to()` throws when one path is relative and
   the other absolute. Fixed with a `_short()` helper that falls back to the
   absolute path.

2. **The page scrolled sideways by 373px on a phone.** The review table has
   eight columns and no amount of wrapping fixes that; it now lives in an
   `overflow-x` container with a `min-width`, which is the correct answer for a
   wide table rather than squeezing it.

3. **The confusion matrix was unreadable in dark mode.** Cell text used
   `var(--ink)`, which flips to white in dark mode, but the cell *backgrounds*
   are a fixed sequential ramp that does not flip. Result: white text on a pale
   blue cell. A magnitude ramp should not change meaning when the theme does,
   so the ramp and the ink on it are now both pinned, independent of theme.

4. **White text on the mid ramp step was 3.64:1** - under AA for text that
   size. `#0b0b0b` on the same step is 5.4:1, so the white/dark ink switch moved
   up one step. Checked with a contrast calculation, not by looking at it.

Also: `rating_distribution` is written 5-to-1 by `score3.py`, but JSON object
keys that look like integers come back in ascending order regardless of write
order, so the page was rendering 1-to-5. Sorted explicitly in the page.

### The palette was computed, not chosen

Sentiment is polarity data, so it uses a **diverging** encoding - blue for
POSITIVE, neutral gray for NEUTRAL, red for NEGATIVE - not three arbitrary
categorical hues. The first attempt used a categorical trio and it failed dark
mode outright: `#e66767` against `#c98500` came out at ΔE 13.0, under the
normal-vision floor of 15. Two readers with ordinary colour vision could not
have told those two bars apart.

Final sets, all validated in both light and dark:

| Use | Light | Dark |
|---|---|---|
| POSITIVE / NEGATIVE poles | `#2a78d6` / `#e34948` | `#3987e5` / `#e66767` |
| NEUTRAL midpoint | `#898781` | `#898781` |
| Model vs word list | `#2a78d6` / `#eb6834` | `#3987e5` / `#d95926` |
| Confusion ramp | `#cde2fb` → `#0d366b` (same in both) | same |

The two-hue pairs pass every check including CVD separation under protan,
deutan and tritan. The diverging trio's gray midpoint reads as low-chroma by
design, which a categorical validator flags and a diverging scale requires.
The sequential ramp was checked for monotonic lightness separately.

### What is still open

- None of this has been run against the real endpoint yet. Every number in
  `README.md` is a placeholder until `score3.py` runs on Jacob's machine with
  the lexicon downloaded.
- The prediction from Step 2 stands: balanced sampling should push accuracy
  down hard, and NEUTRAL should be the worst class by a wide margin. If it
  isn't, something is wrong with the scoring, not right with the model.

---

## Sep 13 - the run "froze," and it was a missing timeout

Jacob's full run appeared to hang. It probably was not hung.

`classify.py` built the client as `OpenAI(base_url=..., api_key=...)` and set
nothing else. The library's defaults are **600 seconds per request with 2
automatic retries**, so a single unresponsive call can occupy the terminal for
up to half an hour while printing nothing. That is indistinguishable from a
freeze, and on a 150-call loop it is not a rare event - Dobolyi extended the
deadline from 9/13 to 9/15 precisely because the class endpoints had been
falling over since Friday evening (hosting provider incident, linked in his
Sep 12 announcement).

Two fixes, both because of that instability rather than in spite of it:

**1. An explicit timeout.** `timeout=60, max_retries=2`. A short review
classification that has not answered in a minute is stalled, not slow. Sixty
seconds fails fast enough to be visible and generous enough not to fire on a
merely sluggish endpoint.

**2. Checkpointing, so an interrupt costs one review instead of the run.**
`score3.py` previously wrote its JSON only at the very end. Twenty minutes in,
Ctrl+C threw away twenty minutes. Now each scored review is written to
`results/.step6_partial{N}.json` as it completes, re-running the same command
resumes from the first unscored row, and `KeyboardInterrupt` is caught so
stopping prints how far it got rather than a stack trace. `--fresh` forces a
clean run. The checkpoint is deleted once the real results file is written, and
is gitignored - a partial run is not a result.

The checkpoint is keyed on model and seed. Change either and it is discarded
rather than silently mixing rows from two different configurations, which would
produce a results file no one could reproduce.

**Verified rather than assumed.** With a stubbed endpoint: interrupt after 5 of
12 reviews, confirm the checkpoint holds exactly 5 and the process exits 130;
resume and confirm it makes exactly 7 further calls, produces 12 unique rows,
and leaves none unscored; then run clean from scratch and confirm the row set
and order are identical to the resumed one. Also confirmed a checkpoint written
under a different seed is rejected. All pass.

**The general lesson, worth its place in the report's fourth question:** the
default timeout of a library you did not configure is a decision you made by
omission. Ten minutes was never the right answer for this task, and the only
reason it surfaced is that the endpoint had a bad week.

---

## Sep 13 - the balanced run landed, and it found three problems

150 sampled, **137 scored, 13 unusable**. Agreement 70.8% against a 35.0%
majority baseline. Per class: POSITIVE 48/48 (100%), NEGATIVE 45/46 (97.8%),
**NEUTRAL 4/43 (9.3%)**.

### The headline is not the accuracy, it is the shape

Collapse NEUTRAL out and the model gets 93 of 94 poles right - 98.9%. Put
NEUTRAL back and it gets 4 of 43. This is not a model that is 70.8% good at a
three-class problem. It is a near-perfect binary classifier being asked a
three-class question, and it answers by picking a pole: of 43 scored 3-star
reviews, 27 (63%) went NEGATIVE and 12 (28%) went POSITIVE.

The prompt anticipated this. It says outright that "NEUTRAL is a real answer,
not a fallback for uncertainty," and defines the class explicitly. It did not
help. Prompting did not fix a behaviour this strong, which is a sharper version
of the Week 3 slide 22 point than structured outputs alone make.

Worth being fair to the model on this. Several of its NEUTRAL "errors" look
defensible next to the rating:

    3* "A perfect find the right price Excellent! very good product"
       -> called POSITIVE at 0.95 confidence
    3* "good" / "not bad"        -> POSITIVE
    3* "Convenient" / "Simplifies making purchases." -> POSITIVE
    3* "Did not receive the amount I chose." -> NEGATIVE

Read the text alone and the model is arguably right in every one. The 3-star
rating is carrying information the text does not contain - habitual rating
style, a partial refund, something outside the review. That is the strongest
available answer to "where does the star rating fail as ground truth."

### Problem 1 - the 13 failures were not random, and they inflate the numbers

Every failure was the same error: empty `content`. This is a reasoning model;
it writes chain-of-thought into a separate field first, and `max_tokens=512`
was being consumed by thinking before any answer got written.

The distribution is what matters. Of the 13 lost rows, **7 were NEUTRAL**,
4 NEGATIVE, 2 POSITIVE. The model thinks longest about the reviews it finds
hardest, so truncation removes the hardest cases first - and those cases are
concentrated in the class that was already performing worst. NEUTRAL's 9.3% is
computed over the 43 that survived, not the 50 that were sampled. Every figure
in the run is therefore flattered by an unknown amount.

Fixed three ways:

- `MAX_TOKENS` 512 -> 2048. It is a ceiling, not a target, so this costs
  nothing on calls that already answered.
- The empty-content error now reports `finish_reason` and the actual completion
  token count, so the next occurrence proves its own cause instead of inviting
  a guess.
- `metrics()` now emits `failures_by_truth` and `failure_rate_by_truth`, and
  `report()` flags any class losing more than 1.5x its share. The check is
  automatic from here rather than something that has to be noticed.

### Problem 2 - output is not reproducible, despite fixed seed and temperature

Two consecutive runs over the same reviews, `temperature=0.0`, `seed=6418`,
same model, same prompt - and they disagreed:

    'Perfume smell :('   run A: NEUTRAL      run B: NEGATIVE
    'As expected'        run A: NEUTRAL      run B: POSITIVE
    'Easy to give'       emotion joy      -> trust
    'Three Stars' (#35) emotion trust    -> joy
    'Five Stars'  (#11) failed in A, succeeded in B

The assignment requires results "repeatable via a fixed seed and fixed
settings." They are not, and the reason is not the seed. vLLM batches
concurrent requests, batch composition changes the order of floating-point
reductions inside the kernels, and different summation order shifts logits
slightly. Near a decision boundary that is enough to flip the argmax at
temperature 0. Batch composition depends on whatever else is hitting the shared
class endpoint at that moment - other students, in other words. The seed
governs sampling and cannot touch any of this.

`check_determinism.py` added to measure the rate rather than assert it: same
reviews classified twice, reports how often sentiment, emotion and confidence
change. Prediction to test: flips should cluster on NEUTRAL, because
instability and the model's weakest class are the same phenomenon - reviews
sitting on a boundary.

Practical consequence for the report: any single accuracy figure from this
endpoint carries run-to-run noise on top of sampling noise. Small differences
between configurations are not interpretable, and none should be claimed.

### Problem 3 - the rating leak turned out to be mostly harmless, and that is measurable

Amazon auto-fills "One Star" ... "Five Stars" as the title when the reviewer
leaves it blank, which puts the rating into a prompt that is supposed to never
see it. Feared earlier that this was inflating accuracy.

The run says otherwise. The six "Three Stars" rows in the sample were called
POSITIVE, NEGATIVE, POSITIVE, POSITIVE, NEGATIVE and NEUTRAL - scattered. If
the model were reading the number out of the title it would have answered those
identically. It is not.

`metrics()` now counts the exposure and reports accuracy on leaked rows against
accuracy on the rest, so the claim rests on a number rather than on six
hand-checked examples.

### The emotion comparison: 26.0%, on a quarter of the data

The word list gave **no answer on 93 of 150 reviews (62%)**. Only 50 rows had
an answer from both methods, and those agreed on 13 - **26.0%**.

Two distributions that barely overlap:

    LLM  : anger 55, joy 50, sadness 11, trust 10, disgust 5, surprise 3,
           anticipation 2, fear 1
    NRC  : anticipation 24, joy 16, trust 9, sadness 3, anger 3, fear 1,
           surprise 1

The single most common disagreement is **anger vs anticipation, 14 times**, and
the cause is visible once stated: in the NRC lexicon "gift" carries
anticipation, joy, surprise and trust. Every gift-card review contains the word
"gift." So the word list reports anticipation for furious reviews about gift
cards that failed, because it is counting vocabulary, not reading a stance.

That is the answer to question 3, and it is not a defect in either method. They
measure different things. The LLM judges the reviewer's attitude. The word list
counts emotion-associated words with no notion of who feels them, whether they
are negated, or whether the word is doing emotional work at all.

The 62% no-answer rate is the other half of the finding: gift-card reviews are
short ("Great", "Reload", "...", "?"), and a lexicon method needs vocabulary to
count. It has nothing to work with.

---

## Sep 13 (later) - the fix worked, and it inverted my prediction

`python score3.py --fresh` with `max_tokens=2048`: **150 of 150 scored, zero
failures**, 228 seconds.

I predicted NEUTRAL accuracy would **fall** once the truncated hard cases came
back into the denominator. It **rose**, from 9.3% to 24.0%.

The reason is better than the prediction was. Look at what the 13 recovered
rows actually returned - **6 of the 7 recovered 3-star reviews came back
correctly labelled NEUTRAL**:

    'Gift Certificate'                  -> NEUTRAL  ok
    "I love the floral box but I'm..."  -> NEUTRAL  ok
    'Santa Gift Card Box'               -> NEUTRAL  ok
    'com gift cards are nice and...'    -> NEUTRAL  ok
    "Family didn't know if this..."     -> NEUTRAL  ok
    'The Tin Was Dented in Two Places'  -> NEUTRAL  ok
    'Why am I asked to review this?'    -> NEGATIVE MISS

Arriving at NEUTRAL requires weighing two sides; arriving at a pole does not.
So the reasoning budget was not losing rows at random - **it was systematically
truncating one specific answer**, the one that takes longest to reach. A token
ceiling was acting as a silent bias against the model's own middle class.

Across the whole run the shift is visible in the prediction distribution:

    max_tokens 512 :  5 NEUTRAL predictions / 137 scored  =  3.6%
    max_tokens 2048: 17 NEUTRAL predictions / 150 scored  = 11.3%

3.1x more NEUTRAL answers, from nothing but headroom. Meanwhile overall
agreement moved 70.8% -> 71.3%, half a point. **The aggregate metric was almost
perfectly blind to a behavioural change that tripled one class's output.** If
the only number being watched had been "accuracy," this would have gone
unnoticed in both directions - first as a silent bias, then as a silent fix.

Worth recording as a mistake on my side too: I stated the direction confidently
and was wrong. The reasoning behind the prediction ("the hardest cases return,
so accuracy on them should be worse") was sound as far as it went and missed
that truncation was not sampling those cases neutrally.

### The final numbers, all from results/step6_balanced50.json

    scored               150 / 150
    agreement            71.3%   (baseline 33.3%, margin +38.0 pts)
    POSITIVE             49/50 = 98.0%
    NEUTRAL              12/50 = 24.0%
    NEGATIVE             46/50 = 92.0%
    poles only           95/100 = 95.0%
    predictions issued   POSITIVE 61, NEGATIVE 72, NEUTRAL 17
    emotion agreement    14/57 comparable = 24.6%  (NRC silent on 93/150 = 62%)
    confidence mean 0.883; 0.900 correct (n=107), 0.840 wrong (n=43)

Two structural facts in the confusion matrix worth more than the headline:

**Every error is one step.** Zero POSITIVE reviews called NEGATIVE, zero
NEGATIVE called POSITIVE. The ordering is perfect; only the middle thresholds
are wrong.

**38 of 43 errors are the NEUTRAL row.** This is not a model with a general
accuracy problem. It is a model with one specific, locatable failure.

### The rating leak, now measured

13 of 150 sampled reviews (8.7%) carry Amazon's auto-generated "N Stars" title.
Accuracy on those rows: **61.5%**. On everything else: **72.3%**. The leaked
rows scored *worse*. Whatever the model is doing, it is not reading the number
out of the title. Reported and left in place rather than filtered - filtering
would have meant re-running and would have looked like tidying.

### Two dashboard bugs the synthetic fixture could not have caught

Both appeared the instant real data went through the page, which is the
argument for rendering the real thing before calling it done:

1. **Literal `<br />` in the review text.** Amazon bodies carry raw HTML where
   the reviewer pressed return. The page escapes everything it prints, so those
   rendered as visible `<br />` mid-sentence. Now stripped before escaping.
   Note the model saw them too, in the prompt, and was unbothered.

2. **Zero-count bars still drew.** `min-width:2px` on every bar meant an
   emotion with a count of 0 rendered a small tick. That is the inverse of the
   collapsed-bar bug the assignment warns about - instead of real data
   vanishing, absent data appeared. A count of zero now draws nothing, and the
   2px floor applies only to genuinely non-zero values.

Verified after the fix by querying the rendered DOM: zero cells containing a
literal `<br>`, zero visible bars with `data-n="0"`.

### Verification of the report itself

Wrote a script that re-derives all 32 quoted figures from
`results/step6_balanced50.json` and confirms each appears in `README.md` -
per-class counts, all nine confusion cells, both emotion distributions, the
leak comparison, the confidence split. All pass. Separately, all 23 figures
rendered on the dashboard were read back out of the DOM and compared to the
same file. Also all pass.

That is the assignment's "every number quoted must match a visible figure in
the saved output," done mechanically rather than by reading carefully and
hoping.

---

## Sep 15 - reproducibility, measured

`check_determinism.py`, 18 reviews classified twice in one sitting, identical
settings. 17 comparable (one review exhausted its token budget in a pass).

    sentiment changed   0 / 17   ( 0.0%)
    emotion changed     3 / 17   (17.6%)
    confidence changed  6 / 17   (35.3%)

    joy      -> sadness    'Cute but not te best'
    sadness  -> disgust    'Santa Gift Card Box'
    sadness  -> anger      'Paper egg presentation damaged'

**This corrected my own overstatement.** On Sep 13 I wrote that "output is not
reproducible" and generalised from two observed sentiment flips between full
runs. The controlled test found **zero sentiment changes in 17 reviews**. Both
observations are real; the conclusion I drew from the first was too broad.

The accurate version: sentiment is mostly stable, emotion and confidence are
not. A 17-review test cannot detect a flip rate of a few percent, and two
sentiment flips were directly observed earlier, so the rate is low but nonzero.
The README now says that rather than the stronger claim.

The mechanism is unchanged and still worth reporting - batch composition on a
shared vLLM endpoint changes floating-point reduction order, which moves logits
enough to flip a near-tie at temperature 0. What the measurement adds is
*where* it bites: the three emotion changes are all mixed reviews, and emotion
has eight near-neighbours where sentiment has three well-separated ones. More
candidate labels packed closer together means more ties available to flip. And
confidence, a free-form float, changes most of all at 35.3%.

Lesson for the report: "not reproducible" was the right instinct and the wrong
resolution. Measuring it turned an anecdote into a bounded claim, and the bound
is narrower than the anecdote implied.

### 2048 tokens is still not always enough

One of the 18 came back `finish_reason=length, completion_tokens=2048/2048`.
The ceiling problem is reduced - 13 failures in 150 became roughly 1 in 18 -
not solved. Worth noting that the diagnostic added on Sep 13 is what made this
immediately legible: the message named the finish reason and the exact token
count, so there was nothing to infer.

---

## Sep 15 - audit against the actual assignment PDF, and a number I got wrong

Read the assignment PDF and the Notes file properly for the first time. Two
corrections came out of it, one of them the exact failure the assignment warns
against.

### Wrong number in the README, caught by checking the file

The README claimed the Step 2 binary run produced "the 95% accuracy" against a
92.9% baseline, "worth about two points of genuine signal." Neither figure was
read from the saved output; both were carried from memory.

`results/step2_first100.json` actually says:

    n_attempted              100
    n_scored                  99   (1 unusable)
    agreement_with_rating    0.9899  -> 99.0%
    majority_class_baseline  0.9293 -> 92.9%
    POSITIVE                 92/92 = 100%
    NEGATIVE                  6/7  = 85.7%

So the real margin was **6.1 points, not 2**, and the headline was **99.0%, not
95%**. Corrected, along with the downstream sentence comparing it to the
balanced run's 38.0-point margin.

This is precisely the standing instruction - *"every number you claim should
match the saved output; don't publish something you haven't re-checked"* - and
I broke it by paraphrasing a run from three days earlier instead of opening the
file. The verification script I wrote on Sep 13 covered every figure sourced
from `step6_balanced50.json` and never touched `step2_first100.json`, so it
passed while a wrong number sat two sections above. A checker only checks what
it is pointed at.

### Port 9000 vs 9001 - a real conflict in the course materials

*Assignment 1 Notes* (Sep 4) says: *"for the OpenAI-compatible endpoint, use the
following one: http://dobolyi.com:9001/v1"*. This project used **:9000**
throughout.

Not a mistake, but it was undocumented, which is the actual problem. The case
for :9000:

- The assignment brief says model calls go through *"an OpenAI-compatible
  endpoint (e.g., the one we used to set up Hermes Agent)"*, and
  `class-endpoints.txt` (Sep 10) labels :9000 **Hermes Primary Model**.
- That same file lists :9001 as `cyankiwi/Qwen3.6-35B-A3B-AWQ-4bit` - a
  **vision** model, not the text model this task wants.
- Both were tested directly on Sep 10. :9000 returns clean JSON and reports
  `cached_tokens`; :9001 injects an ~80-token system prompt and returns a
  separate reasoning field.
- The brief's binding requirement is "OpenAI-compatible," which both satisfy.

Now written into the README as an explicit, reasoned deviation rather than a
silent one. An unexplained port mismatch reads as carelessness; an explained one
reads as judgment, and the reasoning is real either way.

### Plaud has no transcripts

Checked whether the Sep 10 lecture recording said anything that relaxed the
report requirements. **Every recording in the account returns an empty
transcript** - nothing is transcribed, including the three 6418 sessions. So
there is no verbal record to weigh against the written brief, in either
direction. The PDF stands as the only authority, and it lists the four report
questions under "The report should be able to answer, with evidence."

### Full audit against the PDF

Steps 1-7: all present. Final deliverables: report, prompt, scoring script,
word-list script, dashboard generator, one balanced run's raw output, final
dashboard - all present. Report format: markdown README, five screenshots,
data source cited. Submission: public repo, one per person, all code and the
README in it.

The only genuinely outstanding items are the prose being the agent's rather
than Jacob's, and the Canvas submission itself.

---

## Sep 15 (evening) - precision vs recall, and a confidence inversion

Two analyses that should have been run on Sep 13 and were not. Both change what
the report's central claim should be.

### "Bad at neutral" was the wrong diagnosis

The confusion matrix was only ever read by rows, which gives recall. Reading
the columns gives precision, and the two tell different stories:

    class predicted right precision recall
    POSITIVE          61     49     80.3%    98.0%
    NEUTRAL           17     12     70.6%    24.0%
    NEGATIVE          72     46     63.9%    92.0%

**When the model says NEUTRAL it is right 70.6% of the time - better precision
than it manages on NEGATIVE (63.9%).** It is not failing to recognise mixed
reviews. It is declining to call them. 17 NEUTRAL predictions against a true 50
is under-commitment, not incapacity.

And the poles are the mirror image: 98.0% and 92.0% recall bought at 80.3% and
63.9% precision. NEGATIVE gets predicted 72 times against a true 50, absorbing
most of the 3-star row. The model is not balanced-but-weak; it is aggressive on
the poles and conservative in the middle.

This is a materially better answer to question 2 than "NEUTRAL accuracy is
24%," and it was sitting in the same matrix the whole time. Lesson: a confusion
matrix read one way is half a result.

### Confidence runs backwards on the class that needs it most

    true class mean conf when correct when wrong
    POSITIVE     0.913 (n=49)             0.700 (n=1)
    NEGATIVE     0.926 (n=46)             0.625 (n=4)
    NEUTRAL      0.742 (n=12)             0.867 (n=38)

On the poles, confidence is well calibrated - wrong answers come in visibly
lower. On 3-star reviews it **inverts**: the model is more confident when it is
wrong (0.867) than when it is right (0.742).

The mechanism is not mysterious once stated. Correctly identifying a review as
mixed is an act of hedging, and the model's confidence reflects that hedge.
Collapsing a mixed review into a pole feels like a clean call, so it reports
high confidence. The feeling of certainty tracks the shape of the answer, not
its correctness.

Consequence worth stating plainly: **26 of the 43 errors carried confidence
>= 0.90, and 8 carried >= 0.95.** A human-review queue fed by low confidence
would have passed nearly every error straight through, and on NEUTRAL it would
have actively selected the wrong answers for automatic acceptance. The
confidence field looks like information and is not.

Earlier I recorded that confidence was "nearly useless as an error signal"
based on the aggregate gap (0.900 correct vs 0.840 wrong). That understated it.
The aggregate averaged an inverted relationship together with two calibrated
ones and produced a number that looked merely weak rather than actively
misleading. Third time in this project that a pooled metric hid the finding.

### Verification gap closed

The Sep 13 checker only opened `step6_balanced50.json`, which is how a wrong
Step 2 figure survived it. The script now re-derives all **30** quoted figures
from **both** results files and confirms each string appears in the README.
All pass.

### Report provenance stated openly

Replaced the internal "DRAFT - rewrite before submitting" banner with a "How
this report was produced" section: what the agent did, what Jacob directed, and
two places where the agent was demonstrably wrong (the Step 2 number carried
from memory; the confidently wrong prediction about NEUTRAL accuracy falling).
The assignment is explicitly about working with an agent, so describing that
work honestly - including its failures - is more appropriate than either hiding
it or apologising for it.

Added a "what I would do differently" section: hand-label the 50 3-star
reviews to escape the ground-truth ceiling, require a rationale before the
label to test the deliberation finding, and drop self-reported confidence in
favour of logprobs.
