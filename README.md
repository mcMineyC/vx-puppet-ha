# Veracross Grades for Home Assistant

Custom integration that pulls your kid's (or your own) Veracross grades into
Home Assistant. Built on [`vx_puppet`](https://github.com/mcMineyC/vx_puppet) —
a Go library that drives [lightpanda](https://lightpanda.io) (a tiny headless
browser) to log into Veracross and scrape grades, no OAuth needed.

## Install via HACS

1. HACS → Integrations → ⋮ → Custom repositories.
2. Add this repo's URL, category **Integration**.
3. Install "Veracross Grades", restart Home Assistant.
4. Settings → Devices & Services → Add Integration → **Veracross Grades**.
5. Enter:
   - **School ID** — the `<school>` part of `accounts.veracross.com/<school>`
   - **Username** — your Veracross login / student ID
   - **Password**

   Setup does one real login to validate it. First run also downloads
   lightpanda (~15-30s), so give it a minute or two.

## Entities

- `binary_sensor` **Updating** — on while a fetch is in progress.
- `button` **Refresh All Grades** — the *one* master trigger; pulls every
  class in a single login/scrape and updates all sensors at once.
- `sensor.<class name>` — one per class, created dynamically the first time
  it shows up in a fetch. State is the grade string (e.g. `"97%"`).
  Attributes: `class`, `grade_letter`, `grade`, `new_updates`.

No background polling by default — press the button, or call
`button.press` on it from an automation, whenever you want fresh numbers.
It also runs once automatically on HA startup.

## Automations

**Action `veracross.refresh_grades`** fetches and *waits* for the result
(unlike `button.press`, which an automation stops waiting on after ~10s).
With `response_variable` it returns:

```yaml
grades:   [{class, grade, grade_raw, grade_letter, new_updates, entity_id}, ...]
changed:  [ same fields + old_grade, old_grade_raw, old_grade_letter, old_new_updates ]
```

**Events** fired after every fetch:

- `veracross_grade_changed`: one per class whose grade, letter or
  `new_updates` changed (same fields as `changed` above).
- `veracross_grades_updated`: `{grades, changed}` after each successful fetch.
- `veracross_fetch_failed`: `{error}`.

The last grades are saved, so sensors keep their values across restarts and
changes are detected relative to the previous fetch.

Notify on any grade change:

```yaml
triggers:
  - trigger: event
    event_type: veracross_grade_changed
actions:
  - action: notify.notify
    data:
      title: "{{ trigger.event.data.class }}"
      message: >
        {{ trigger.event.data.old_grade_raw }} → {{ trigger.event.data.grade_raw }}
        ({{ trigger.event.data.grade_letter }})
```

Fetch on a schedule and send a summary:

```yaml
actions:
  - action: veracross.refresh_grades
    response_variable: vx
  - action: notify.notify
    data:
      message: >
        {% for g in vx.grades %}{{ g.class }}: {{ g.grade_raw }}
        {% endfor %}
```

## How it works

`vx_puppet` (the linked Go library) is compiled into a small CLI —
[`tools/vx_ha_cli`](tools/vx_ha_cli) — that always prints one JSON line to
stdout (`{"ok":true,"grades":[...]}` or `{"ok":false,"error":"..."}`).
The Python integration ([`custom_components/veracross`](custom_components/veracross))
shells out to a prebuilt static binary via `asyncio`'s executor and parses
that line. Static `linux/amd64` and `linux/arm64` binaries are committed in
`custom_components/veracross/bin/` (that's what actually ships to HACS
installs — Home Assistant containers can't build Go on the fly).

Updating the vendored binaries when `vx_puppet` gets a new release:

```bash
./scripts/build_binaries.sh   # requires Go 1.26+, rebuilds against vx_puppet@latest
git add custom_components/veracross/bin
git commit -m "bump vx_puppet"
```

Bump `version` in `custom_components/veracross/manifest.json` to match, tag
(`vX.Y.Z`), and cut a GitHub release — HACS tracks releases by tag.

## Caveats

- Password is passed as a CLI arg to the subprocess, so it's visible in
  `/proc/<pid>/cmdline` on the host while a fetch runs. Fine for a home
  container; not for a shared multi-tenant box.
- Each fetch spins up a fresh headless browser instance — expect 10-60s per
  run depending on Veracross/lightpanda.
- lightpanda itself gets downloaded to `<config>/veracross_lightpanda/` on
  first use and cached there. Its Linux builds are glibc-linked, but the HA
  container is Alpine (musl), so the CLI embeds a minimal glibc runtime
  (see [`tools/vx_ha_cli/glibc`](tools/vx_ha_cli/glibc)), unpacks it next to
  lightpanda, and launches lightpanda through that loader.

## License

MIT — see [LICENSE](LICENSE).
