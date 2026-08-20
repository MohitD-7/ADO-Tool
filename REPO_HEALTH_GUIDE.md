# Understanding Your Repo's Health — A Plain-English Guide

This document explains **the gaps I found in the SKU Manager repo**, why each
one matters, and — for the ones that belong in git — *why* they live in git and
*how* they get used day to day.

It's written for someone who has never been taught formal software engineering.
There is no blame here. You built a tool that **actually works and people use** —
that's the hard part, and you did it. The "mistakes" below are not mistakes of
building; they're just the safety equipment that every growing project
eventually needs and that nobody tells you about until something breaks.

---

## First, the one big idea

Most people think **git is a place to store code**. That's only half of it.

The better way to think about it:

> **Git stores everything a stranger would need to safely change your code
> without being afraid.**

Code is *what the program does*. But to change code safely you also need:

1. A way to **prove the change didn't break anything** → that's **tests**.
2. A **robot that runs those proofs automatically** every time → that's **CI**.
3. Code that's **small enough to understand** before you touch it → that's
   **file structure**.

Right now your repo has #1, #2 missing entirely, and #3 partially. That's why it
*works* but feels *risky* — every change is done by hand, checked by hand, and
remembered only in your head.

Let me explain each one from zero.

---

## Gap 1: There are no automated tests 🔴 (the big one)

### What is a "test"?

A test is a **tiny second program whose only job is to check that your real
program does the right thing.** You write it once, and from then on a computer
can re-run it in a fraction of a second, forever.

Think of it like this: when you built the Excel export, you *manually* did this:

> "Let me upload a parent with 2 children, download the Excel, re-upload it, and
> eyeball whether the children are still there."

A **test** is that exact check, but written down as code so a machine does it
for you instead of your eyes and your memory.

### Why this is your #1 gap — a real example from today

Today we fixed a bug where **child SKUs silently disappeared** when you
downloaded an Excel and re-uploaded it. The data just… vanished. That's the
scariest kind of bug: no error message, no crash, just quietly lost work.

Here is what a test for that bug looks like (this is real, runnable code):

```python
def test_children_survive_excel_round_trip():
    # 1. Build a parent with two children
    queue, items, variants = make_parent_with_two_children()

    # 2. Export to Excel bytes, then read them straight back
    excel = excel_bytes(build_output_df(queue, items),
                        build_input_sheet_df(queue, items))
    queue2, items2, variants2 = parse_output_excel(excel)

    # 3. THE PROOF: all three SKUs must still be there
    assert list(items2.keys()) == ["PARENT-1", "CHILD-1", "CHILD-2"]
```

That last line — `assert ...` — means *"if this isn't true, scream."*

Now here's the important part. **Once this test exists in git:**

- Six months from now, someone (maybe you) changes the export code for an
  unrelated reason. If they accidentally re-break the children, this test
  **fails instantly** and tells them *before* it ever reaches a user.
- A bug that comes back after being fixed is called a **regression**. Tests are
  how you make sure a fixed bug *stays* fixed. Without them, the same bug can
  return again and again and you'd only find out when a user complains.

Look at your own git history:

```
4a18906 Fix Format button not updating Features/Includes/Highlights grids
08ec899 Fix Excel round-trip data loss and Similar To clone incompleteness
6bd7fbe Fix silent git-push races...
6999ef2 Fix Format button state races...
```

Four "Fix" commits in a row. Some touch the **same feature twice** (the Format
button). That's the classic fingerprint of *"we have no tests, so bugs keep
sneaking back."* Every one of those fixes was verified by hand and is now
**unprotected** — nothing stops the next code change from undoing it.

### Why tests belong *in git*

Because the test travels **with the code it protects.** When someone clones the
repo, they get the code *and* the proof of how it's supposed to behave. The
tests become living documentation: *"here is exactly what 'correct' means for
this function."* If the tests weren't in git, they'd only exist on your laptop
and would help nobody but you, today.

### How tests get used

- **While coding:** you run `pytest` in the terminal. In ~1 second it runs every
  check. Green = safe. Red = you broke something, here's exactly what.
- **Before every commit:** run them so you never commit a broken build.
- **Automatically on every push:** which brings us to Gap 2.

---

## Gap 2: There is no CI 🔴 (the robot that runs your tests)

### What is CI?

**CI** stands for **Continuous Integration**. Ignore the fancy name. In practice
it means:

> **A robot that lives on GitHub and automatically runs your tests every single
> time anyone pushes code — without anyone remembering to.**

You configure it with one small file inside git (it lives at
`.github/workflows/something.yml`). From then on, GitHub watches your repo, and
on every push it spins up a fresh computer, installs your project, and runs your
checks.

### Why you need it — the human problem it solves

Tests only help *if someone runs them.* And humans forget. It's 6pm, you're
tired, you fix one line, you push. Did you run the tests? Probably not.

CI removes the "did I remember?" question entirely. The robot **never forgets
and never gets tired.** If a push breaks a test, GitHub puts a red ❌ next to
your commit and (optionally) emails you. If everything passes, a green ✅.

### A concrete example from today

You pushed commit `4a18906` a few minutes ago. Ask yourself: **what automatically
checked that it didn't break anything?**

The answer today is: *nothing.* I checked it by hand. If I'd made a typo that
broke the app's startup, you'd only discover it when you opened the app — or
worse, when a user did.

With CI, the moment you pushed, a robot would have:
1. Installed Python + your dependencies on a clean machine,
2. Confirmed every file still compiles,
3. Run every test,
4. Stamped the commit green ✅ or red ❌.

Ten seconds of robot time, zero seconds of your attention.

### Why the CI config belongs *in git*

Because the instructions for "how to check this project" are **part of the
project.** Anyone who clones it should inherit the same safety checks
automatically. It also means the rules are the same for everyone — there's no
"well it worked on *my* machine." The robot's machine is the neutral referee,
and its recipe lives in git so it's identical every time.

### How CI gets used

You mostly *don't* touch it — that's the point. You just see green or red checks
next to your commits on GitHub. Green means "safe to build on." Red means "stop,
you broke something." It's a smoke detector: silent until it matters.

---

## Gap 3: Some files are too big 🟡

`export.py` is **883 lines** and does at least four unrelated jobs: building
Excel, *parsing* Excel back, sanitizing HTML, and warranty/battery logic.

### Why this matters (even though it "works")

Imagine a kitchen where the knives, the spices, the cleaning supplies, and the
tax paperwork are all in one giant drawer. You *can* cook — but every time you
need one thing you paw through everything, and it's easy to grab the wrong item.

Big files are that drawer. The risks:

- **Harder to understand before changing** → more likely to break something you
  didn't even mean to touch.
- **Harder to test** → a focused test wants a focused piece of code.
- **Merge pain** if a second person ever joins — two people editing one giant
  file collide constantly.

This isn't a git problem and it isn't urgent. It's a **maintainability** problem
— it makes every *future* change slower and riskier. The fix is to split the
file along its natural seams (one file for building Excel, one for parsing, one
for HTML), which also makes Gap 1 (tests) much easier.

---

## Gap 4: Heavy use of `unsafe_allow_html` 🟡 (the security surface)

Your app builds a lot of its screen by writing raw HTML (62 places use
`unsafe_allow_html=True`). Streamlit literally named the setting "**unsafe**" as
a warning.

### Why it's called unsafe, in plain terms

HTML can contain not just text but *instructions* — including little programs
(`<script>`). If your app ever takes something **a user typed** (a product
title, a note, a link) and drops it into the page as raw HTML **without
cleaning it first**, a malicious user could type in a `<script>` that then runs
in someone else's browser. That attack has a name: **XSS** (cross-site
scripting).

The good news: your history shows a commit **"Fix stored XSS in previews and
editor rules"** — so you've already been bitten once and patched it. That means
you understand the risk. The point here is just: **this is the single most
security-sensitive part of your app**, so any time you put user-typed text into
HTML, it must go through an escaping/cleaning step first (you already have
`sanitize_description_html` and `html.escape` for exactly this — the rule is
"never skip them").

This one isn't about adding something to git; it's a **habit** to keep.

---

## Gap 5: Deploys can wipe user saves 🟡 (an operational trap)

Your `git_sync.py` file has an honest comment explaining this: the server you
deploy to has an **ephemeral filesystem** — meaning every time it redeploys, the
disk is wiped clean and rebuilt from git.

### Why that's dangerous

Anything written *only to the local disk at runtime* — like a user's in-progress
saved work under `data/saves/` — is **not in git**, so a redeploy erases it.
`git_sync.py` is a clever workaround that pushes *reference data* back into git
so it survives. But regular user saves don't get that treatment.

### The practical lesson

This is why `data/saves/` is in `.gitignore` (correctly — you don't want random
work-in-progress polluting git), but it *also* means those saves are living on
borrowed time. The safe habit: **tell users to export their work to Excel before
any deploy**, because a deploy is effectively a "wipe the scratch disk" event.

(This one is more about *understanding your hosting* than about git — but it's a
real trap worth writing down.)

---

## Gap 6: One contributor, thin docs 🟡 (the "bus factor")

Right now the entire project lives in one person's head (yours). Engineers
grimly call this the **"bus factor"**: *how many people would have to get hit by
a bus before the project is stranded?* Yours is **1**.

The README is 42 lines and about a third of your modules have a top-of-file
description. That's not terrible — but it means onboarding a second person, or
even *your future self* after a 6-month gap, is slow.

Tests (Gap 1) actually help here too: good tests are a form of documentation
that can't go out of date, because if the docs lie, the test fails.

---

## Putting it together: what "healthy" would look like

| Thing | You have it? | What it buys you |
|---|---|---|
| Working code | ✅ Yes | The app does its job |
| Clean structure (mostly) | ✅ Mostly | Easy-ish to find things |
| No committed secrets | ✅ Yes | You won't leak passwords |
| **Automated tests** | ❌ No | Bugs stay fixed; fearless changes |
| **CI robot** | ❌ No | Nobody has to *remember* to check |
| Small files | 🟡 Partly | Faster, safer edits |
| Security habits | 🟡 Careful | No XSS |
| A second brain / docs | 🟡 Thin | Survives you stepping away |

### The single sentence to remember

> **You did the hard 80% (a working app). The missing 20% isn't more features —
> it's the safety net that lets you keep changing the app without fear.** Tests
> and CI are that net, and they live in git so the net travels with the code.

---

## The mistake — named kindly

You didn't make a *coding* mistake. You made the completely normal beginner
**process** omission: you treated git as a **backup drive for finished code**,
instead of as the **home for the whole safety system** around the code.

The result is visible in your own history — a long, honest string of "Fix…"
commits, some re-fixing the same feature. That's not you being careless; that's
what *every* untested project looks like. The fix isn't to try harder by hand.
The fix is to let a robot and a handful of tests carry that burden for you.

Whenever you're ready, the highest-value next step is tiny: turn the
verification checks we already ran today into a real `tests/` folder, and add a
~15-line GitHub Actions file to run them on every push. That single afternoon of
work would flip your two biggest red items to green.
