---
name: ha-dev
description: Drive the Dayline test Home Assistant instance — deploy from the repos, restart, check why the card is not loading, read the feed or the logs. Use for any "push this to the test server", "restart HA", "why isn't the card showing", or "what does the sensor say" request.
---

# Working against the test Home Assistant

Everything goes through `tools/ha-dev.py`, which reads `HA_URL` and `HA_TOKEN`
from `.ha-env` at the repo root. Run it from the repo root with `python3` (not
the venv — it only needs the stdlib plus `websockets`, which is on the system
Python).

## The commands

```bash
python3 tools/ha-dev.py doctor      # start here for anything broken
python3 tools/ha-dev.py deploy      # HACS pull both repos, restart, then doctor
python3 tools/ha-dev.py update card # HACS pull one repo, no restart
python3 tools/ha-dev.py restart     # restart, wait for RUNNING
python3 tools/ha-dev.py resources   # what the dashboard will try to import
python3 tools/ha-dev.py feed        # the sensor's finished output
python3 tools/ha-dev.py logs --all  # warnings and errors
python3 tools/ha-dev.py repos       # installed vs available, per repository
```

## Deploying a change

Push to GitHub **first** — HACS pulls from there, not from the working tree, so
an unpushed commit deploys the previous one and looks like the fix did nothing.

```bash
git push origin main && python3 tools/ha-dev.py deploy
```

A card-only change also needs the bundle published to the card repository:

```bash
npm run build && npm run stage-card
git -C ../Dayline-card commit -am "..." && git -C ../Dayline-card push
python3 tools/ha-dev.py update card && python3 tools/ha-dev.py restart
```

## Things that will otherwise cost an afternoon

- **`deploy` is slow and that is correct.** A HACS download takes one to two
  minutes and a restart another minute. Do not add a timeout under five minutes,
  and do not poll the API to decide the restart finished — it keeps answering
  for a moment after the request, so "it responded" means the *old* process.
  `ha-dev.py` waits for the API to go away and come back RUNNING.
- **Two repositories, two HACS entries.** `bitmux/Dayline` is the Integration
  (the feed). `bitmux/Dayline-card` is the Dashboard (the card). HACS keys a
  custom repository by `owner/repo` and gives it one category, so one repository
  cannot be both — adding the same repo under a second category silently does
  nothing.
- **HACS registers the card's Lovelace resource itself.** Never write to
  `hass.data["lovelace"].resources` from the integration. There is no public API
  for it, and doing it produced a card that loaded, then stopped loading, for
  reasons that were not in this repository. If a resource is missing, the fix is
  in how HACS installed the Dashboard repository.
- **The feed sensor is named after the config entry's title.** An entry called
  "Dayline" gives `sensor.dayline`. Never hardcode the entity id — find the
  sensor by its shape, a `sensor.*` carrying an `entries` list, which is what
  `ha-dev.py feed` does.
- **A resource row is just a string.** It stays exactly as convincing after the
  file behind it stops existing, which is why `doctor` fetches the URL rather
  than trusting the list.

## When the card does not render

`doctor` checks the chain in the order it breaks. If it is all green and the
browser still says "Custom element doesn't exist", the problem is the browser's
cached copy, not the server — hard-refresh (Ctrl/Cmd-Shift-R). To confirm from
here rather than guessing, the asset URL is unauthenticated, so it can be
fetched and `import()`ed directly in a browser against the instance's origin.
