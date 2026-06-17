---
type: plan
id: "2026-06-17-github-action-auto-update"
title: "GitHub Actions Auto-Update Implementation Plan"
date: "2026-06-17T14:53:24+00:00"
author: "John Cowie Del Corral"
producer: create-plan
status: draft
work_item_id: ""
parent: ""
reviewer: ""
tags: []
revision: "0c2878458e9f909befcd4d9b93855ea3add02b1e"
repository: "world-cup-2026-sweepstake"
last_updated: "2026-06-17T14:53:24+00:00"
last_updated_by: "John Cowie Del Corral"
schema_version: 1
---

# GitHub Actions Auto-Update Implementation Plan

## Overview

Set up a GitHub Actions workflow that runs every 2 hours, fetches the latest
win probabilities from Opta, regenerates `index.html`, and commits + pushes
the result back to `main`. This keeps the GitHub Pages site up to date
automatically without any manual intervention.

## Current State Analysis

- `fetch_probabilities.py opta` — fetches from Opta Supercomputer, saves a
  timestamped JSON to `opta/probabilities_<TIMESTAMP>.json`
- `render_league_table.py opta` — reads the latest JSON from `opta/`,
  regenerates the HTML, writes to **`league_table.html`** (line 429 of the
  script) — **this is now wrong** since we renamed the output file to `index.html`
- `opta/` directory already exists with 11 historical snapshots committed
- No `.github/` directory exists yet
- No `requirements.txt` needed — the scripts use only stdlib

## Desired End State

Every 2 hours, the action:
1. Fetches fresh probabilities from Opta
2. Regenerates `index.html` with the latest data + full history chart
3. Commits `opta/probabilities_<TIMESTAMP>.json` and `index.html` to `main`
4. The GitHub Pages site at `https://johncowie.github.io/world-cup-2026-sweepstake/`
   reflects the update within ~1 minute of the commit

### Verification:
- Trigger the workflow manually via `workflow_dispatch` and confirm a new
  commit appears on `main` with updated `index.html` and a new `opta/` JSON file

## What We're NOT Doing

- Not fetching from DTAI (action only targets `opta`)
- Not setting up any caching of pip dependencies (no pip deps)
- Not sending notifications on failure (can be added later)
- Not deduplicating if Opta data hasn't changed (a commit happens regardless)

## Key Discoveries

- `render_league_table.py:429` writes to `"league_table.html"` — must be updated
  to write to `"index.html"` to match the renamed output file
- `opta/` snapshots are tracked in git (not gitignored) — the action can
  simply `git add opta/ index.html`
- Python stdlib only — no `pip install` step needed
- The `GITHUB_TOKEN` secret is automatically available in Actions and can push
  to the same repo when `contents: write` permission is granted

---

## Phase 1: Fix render_league_table.py output filename

### Overview

The script currently writes to `league_table.html`. Now that we've renamed
the file to `index.html` for GitHub Pages, the script must be updated to match.

### Changes Required:

**File**: `render_league_table.py`  
**Line**: 429  
**Change**: `"league_table.html"` → `"index.html"`

```python
# Before:
    with open("league_table.html", "w") as f:
# After:
    with open("index.html", "w") as f:
```

Also update the print statement on line 432:
```python
# Before:
    print(f"\nLeague table written to league_table.html\n")
# After:
    print(f"\nLeague table written to index.html\n")
```

### Success Criteria:

#### Automated Verification:
- [ ] Running `python3 render_league_table.py opta` produces/updates `index.html`
- [ ] No `league_table.html` file is created

#### Manual Verification:
- [ ] `index.html` content looks correct when opened in a browser

---

## Phase 2: Create the GitHub Actions workflow

### Overview

Create `.github/workflows/update.yml` — a scheduled workflow that runs every
2 hours, fetches Opta probabilities, regenerates the page, and commits back.

### Changes Required:

**File**: `.github/workflows/update.yml` (new file)

```yaml
name: Update sweepstake

on:
  schedule:
    - cron: '0 */2 * * *'
  workflow_dispatch:

permissions:
  contents: write

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Fetch latest probabilities
        run: python3 fetch_probabilities.py opta

      - name: Regenerate index.html
        run: python3 render_league_table.py opta

      - name: Commit and push
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add opta/ index.html
          git diff --cached --quiet && echo "No changes to commit" && exit 0
          git commit -m "Update sweepstake $(date -u '+%Y-%m-%d %H:%M UTC')"
          git push
```

Key design decisions:
- `workflow_dispatch` allows manual triggering for testing
- `permissions: contents: write` grants the token push access
- `git diff --cached --quiet && exit 0` skips the commit if nothing changed
  (guards against Opta returning identical data)
- No pip install step — scripts use stdlib only

### Success Criteria:

#### Automated Verification:
- [ ] Workflow file is valid YAML: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/update.yml'))"`
- [ ] Workflow appears in GitHub Actions UI after push

#### Manual Verification:
- [ ] Trigger via "Run workflow" button in GitHub Actions UI
- [ ] Action completes successfully (green tick)
- [ ] New commit appears on `main` with message `Update sweepstake <date>`
- [ ] `index.html` on GitHub Pages reflects updated timestamp
- [ ] New file appears in `opta/` directory

---

## Testing Strategy

### Manual Testing Steps:
1. After pushing both changes, go to the repo's **Actions** tab on GitHub
2. Select **Update sweepstake** workflow
3. Click **Run workflow** → **Run workflow**
4. Monitor the run — all steps should be green
5. Check that a new commit appears on `main` with the expected message
6. Visit `https://johncowie.github.io/world-cup-2026-sweepstake/` and confirm
   the "updated" timestamp in the header has changed

## References

- GitHub Actions schedule syntax: https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows#schedule
- `actions/checkout@v4`, `actions/setup-python@v5` are the current stable major versions
