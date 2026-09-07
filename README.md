<div align="center">

# Agent Gauge

**Your coding agent's limits, on a floating desktop widget.**

Watches **Claude Code** or **Codex**, one at a time, switched from the menu.

**English** · [Português](README.pt-BR.md)

[![CI](https://github.com/lucasmaziero/agent-gauge/actions/workflows/ci.yml/badge.svg)](https://github.com/lucasmaziero/agent-gauge/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/lucasmaziero/agent-gauge)](https://github.com/lucasmaziero/agent-gauge/releases/latest)
[![Python](https://img.shields.io/badge/python-3.11+-3776ab)](https://www.python.org)
[![Platform](https://img.shields.io/badge/platform-Windows%20%C2%B7%20macOS%20%C2%B7%20Linux-6e7681)](#installation)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

<img src="docs/shot-widget.png" width="440" alt="Floating widget showing 37% of the 5-hour window">

<a href="https://lucasmaziero.github.io/agent-gauge/"><b>lucasmaziero.github.io/agent-gauge</b></a>

</div>

---

## How it works

Both agents meter the same two things: a rolling **five-hour** window and a **weekly** one, at
18000 and 604800 seconds exactly, each reported as a percentage with a reset time. That is the
whole gauge, and it is why one widget can wear either without redrawing anything.

Where they differ is in what a reading costs.

**Claude Code.** Anthropic publishes no usage endpoint for subscription accounts. Utilization rides
along in the `anthropic-ratelimit-unified-*` headers of any response, so the widget sends the
smallest request that exists - a `POST /v1/messages` with `max_tokens: 1` - purely to read them:

| Header | Becomes |
| --- | --- |
| `unified-5h-utilization` | percentage of the 5-hour window |
| `unified-7d-utilization` | percentage of the 7-day window |
| `unified-5h-reset` / `unified-7d-reset` | clock and countdown for each reset |
| `unified-status` / `representative-claim` | status chip, and which window binds |

**Codex.** There is a usage endpoint, so a reading costs nothing at all: no request against your
quota, no token spent. `backend-api/wham/usage` returns `primary_window` and `secondary_window`
with the same percentages and resets, plus the plan name.

One thing it does not return is Anthropic's `representative-claim`, the server's own answer to
which window binds first. So the panel simply does not say, for Codex, until `limit_reached_type`
reports that one has actually been hit. Which window binds is a claim about the future, and two
percentages cannot support one.

That endpoint is the one caveat worth stating plainly: it belongs to the ChatGPT web backend and is
not a published API. It has no contract and no deprecation policy, so the day its shape changes
this half stops working. Every field is read defensively, and a reply that does not carry the two
windows is reported as a failed reading rather than guessed at - a gauge confidently showing zero
would be worse than one admitting it does not know.

Two things follow from the app running on the **same machine** as the agent:

- **Nothing to configure.** The token comes from wherever the agent itself put it, re-read every
  cycle: `~/.claude/.credentials.json` on Windows and Linux and the login keychain on macOS for
  Claude Code, `~/.codex/auth.json` for Codex. When the agent refreshes it, the widget follows.
- **Real token counts, where they exist.** The percentages are all either API carries. Claude Code
  writes transcripts under `~/.claude/projects/**/*.jsonl` and those absolute numbers are read
  straight off the disk. Codex keeps its history in SQLite with no usage totals in it, so that line
  of the panel is empty rather than wrong.

Nothing is refreshed on your behalf. Both agents rotate their own tokens while they run, and both
carry a refresh token this could spend - but refresh tokens are commonly single-use with rotation,
so spending one could leave the agent holding an invalid token and log you out of it. That is a
disproportionate way to lose a gauge reading.

## Installation

Every download is on the [releases page][releases], each with a SHA-256 beside it. All three builds
are unsigned, so each OS objects in its own way; the notes below say how to get past it.

Whichever you pick, the agent you want to watch has to have been signed in on the machine. Without
it the widget says so and offers the setup page for that agent rather than a number.

[releases]: https://github.com/lucasmaziero/agent-gauge/releases/latest

### Windows

`AgentGauge-<version>.exe`, double-clicked. The install is **per user**, into
`%LOCALAPPDATA%\Programs\Agent Gauge`. No admin, no UAC prompt. The wizard offers a desktop
shortcut and starting with Windows, both optional. It uninstalls from **Installed apps** like any
program, asking first whether to remove your preferences too.

Unsigned, so SmartScreen warns about an "unknown publisher" on the first download.

### macOS

`AgentGauge-<version>-arm64.dmg` for Apple Silicon, `-x86_64` for Intel. Open it and drag the app
to Applications. It has no Dock icon by design (`LSUIElement`): the menu bar and the floating widget
are the whole interface.

The bundle is signed ad-hoc rather than with a Developer ID, so Gatekeeper refuses it on the first
launch. Right-click the app and choose **Open**, which offers the override a double-click does not,
or:

```bash
xattr -dr com.apple.quarantine "/Applications/Agent Gauge.app"
```

The first poll opens a keychain prompt, because on macOS the token lives there rather than in a
file. Choose **Always Allow** and it is never asked again.

### Linux

`AgentGauge-<version>.AppImage`, marked executable and run:

```bash
chmod +x AgentGauge-*.AppImage
./AgentGauge-*.AppImage
```

Two desktop caveats worth knowing before filing a bug:

- **GNOME ships no system tray.** The icon appears only with an AppIndicator extension installed.
  Without one the app notices and keeps the floating widget on screen, since its right-click menu
  carries the same commands.
- **Wayland forbids a window from placing itself**, so a saved position cannot be restored. Where an
  X server is reachable the app asks for XWayland and the position works normally; setting
  `QT_QPA_PLATFORM` yourself always wins.

### From source

Works on all three, and is the only route on an architecture without a build.

```bash
uv sync
uv run agent-gauge       # ./run.sh detaches it from the terminal
```

```powershell
uv sync
uv run agent-gauge       # or .\run.bat, which starts it without a console window
```

## Usage

<img src="docs/shot-panel-en.png" width="380" align="right" alt="Expanded panel">

**Widget.** No number appears twice: the ring answers *how much of the 5-hour window is spent*, the
`5h` row answers *how long until it resets* (with the reset clock on the right), and the `7d` row
covers the week.

A second ring orbits the gauge, gray over a track, counting down to the next fetch, and it turns
into a green spinner while the fetch runs. The gray is deliberate: at high usage the gauge goes
amber or red, and a concentric ring in the same color family melts into it.

The right column has three floors: the mascot on top, the **refresh** button in the middle, the menu
at the bottom. Drag the rest of the card to move it (the position is saved), click to open the
panel, or right-click anywhere for the menu.

**Panel.** The 5-hour window is what bites first, so it gets a card with the big number and an
eighteen-segment meter; the 7-day window is supporting information and sits directly on the surface
with a continuous bar. Below a hairline come the metadata: status chip (`OK` / `WARNING` /
`BLOCKED`), real token counts for the window, open incidents from `status.claude.com`, and the
timestamp of the last fetch.

The mascot in the header goes gray on a fetch error or an open incident, the same signal the
widget's badge gives.

**With no token** there is nothing to timestamp, so the footer carries the way out instead: a link
to the setup page of whichever agent is being watched. It names the actual dead end - **Get Claude
Code** or **Get Codex** when that agent's directory is not on the machine at all, **How to sign in**
when it is there but carries no usable token. Every message on that path names the agent too, and
none of them names a command: `claude` is not what a Codex user types.

That directory - `~/.claude` or `~/.codex` - is the test rather than a binary on PATH, because the
desktop apps and the IDE extensions write it without ever installing a CLI, and a PATH check would
tell an active user they had never installed anything. Nothing is installed for you: piping an
install script into a shell on someone's behalf is not a thing a usage widget should do.

**Switching agents.** One at a time, from **Watching** in the menu. The panel header names the
one in view and wears its mark - Claude Code's or Codex's own - because the ring and the rows look
identical either way, and a mark over the wrong numbers would be the one thing this must not get
wrong. Switching drops the snapshot, the alert state and the burn-rate history: a rate mixing two
agents' windows would be a fiction. The app's own mark is neither of theirs; it is the gauge.

**Tray.** The icon is the ring with the number inside, drawn one size at a time so the shell never
has to shrink it, including the in-between sizes display scaling asks for (25px at 125%). The
tooltip carries both windows.

**Alerts.** A widget is a display, and a display only works if you look at it. Once per five-hour
window, when the number first crosses the threshold, the app says so through the system's own
notifications - and it says the thing worth acting on: not that you are at 80%, but that at this
rate you hit 100% in forty minutes. Set the threshold in the menu, or turn it off there.

**About.** A small card with the version, the author, the licence and the repository, plus a
**Check for updates** button. That check runs only when you press it: there is no background poll
and no auto-update. It reads the latest tag from GitHub, and if it is ahead of the running build it
becomes a link to the download page - which names the file for each platform, where the release page
is eight files and leaves you to work out which two are yours. Downloading and installing stays
yours either way.

A check that fails is never worded as one that passed, and the ways of failing are not worded as
each other: a dead network, a GitHub rate limit, an HTTP status and an unreadable answer each say
so, and each is written to `errors.log`. They all used to read "could not reach GitHub" - which for
the rate limit is a wrong answer rather than a vague one, since sixty requests an hour is counted
per IP and an office can exhaust it without this machine making a call.

<br clear="right">

<div align="center"><img src="docs/tray.png" width="260" alt="Tray icon at 6%, 47%, 83% and 100%"></div>

### Menu

| Item | What it does |
| --- | --- |
| Refresh now | Forces a cycle outside the interval |
| Open panel | Same as clicking the widget |
| Show widget | Leaves only the tray icon |
| Compact mode | Shrinks the widget to the ring |
| Lock position | Ignores dragging |
| Interval | 30 s to 15 min, 2 min by default; a floor, not a fixed cadence |
| Watching | Claude Code or Codex; switching clears what belonged to the other |
| Alert at | Notify once per window at this percent, 80% by default; Off turns it off |
| Language | Automatic, Português, English |
| Start with *&lt;your OS&gt;* | Named after the system it is running on; one mechanism each, see below |
| Check for updates | Asks GitHub for the latest tag, once, when you click it |
| About | Version, author, licence, and the same update check |

Autostart and preferences are the only things that differ per platform. `history.json` and
`errors.log` sit beside `settings.json` in the same directory, holding the burn-rate samples and
the record of failed cycles:

| | Autostart | Preferences |
| --- | --- | --- |
| Windows | `HKCU\...\CurrentVersion\Run` | `%APPDATA%\AgentGauge\settings.json` |
| macOS | `~/Library/LaunchAgents/com.lucasmaziero.agent-gauge.plist` | `~/Library/Application Support/AgentGauge/settings.json` |
| Linux | `~/.config/autostart/agent-gauge.desktop` | `$XDG_CONFIG_HOME/agent-gauge/settings.json` |

All three are per user: none needs admin, and none writes outside your home directory.

### Language

The interface ships in English and Portuguese. It follows the system language by default; the
**Language** menu offers Automatic, Português and English, and the choice is saved. Switching
applies immediately, with no restart.

It is not only labels: the weekday (`Fri` / `sex`), the decimal mark (`6.0M` / `6,0M`) and the
plural of sessions follow the language too. Translating labels while the numbers stay in one locale
reads half converted, which is worse than not translating at all.

Strings live in `src/agent_gauge/i18n.py`, one dictionary per language. Adding a language means
copying the English dictionary, translating the values and registering it in `LANGUAGES`; a test
keeps the keys and the `{format}` fields in step across every language.

## Layout

```
src/agent_gauge/   application code    tests/       test suite
installer/          packaging           tools/       icon and preview generators
```

| Module | Role |
| --- | --- |
| `paths.py` | Where each OS keeps the credentials, transcripts and preferences |
| `credentials.py` | Reads Claude Code's OAuth token, from a file or the macOS keychain |
| `autostart.py` | Start with the session: Run key, LaunchAgent or .desktop entry |
| `providers/` | One `Provider` per agent: credentials, fetch, incidents, token totals |
| `signin.py` | Tells the two no-token dead ends apart and opens the setup page |
| `diag.py` | A bounded log of failed cycles, written only when one fails |
| `net.py` | The one TLS context every HTTPS call uses, verified by the OS |
| `release.py` | Reads the latest published tag and compares it with this build |
| `about.py` | Version, author and the update check, as a card |
| `api.py` | Usage and incidents; `parse()` split out so the contract tests without a network |
| `tokens.py` | Sums the window's tokens from local transcripts |
| `poller.py` | Collection thread, history, burn rate and projection |
| `theme.py` | Palette, 4pt spacing scale and formatters |
| `paint.py` | Drawing primitives: ring, meter, chip, shadow, icons |
| `brand.py` | The app's own gauge mark, plus one mascot per agent, embedded as strings |
| `i18n.py` | Interface strings, one dictionary per language |
| `widget.py` | The floating bar |
| `panel.py` | The expanded panel |
| `app.py` | Tray, menu and wiring |

## Development

```powershell
uv sync                                           # creates the .venv with the dev group
uv run pytest                                     # 268 tests, no network, no windows
uv run ruff check .                               # lint (rules in pyproject.toml)
uv run python tools/preview.py docs/preview.png   # offline render of both surfaces
$env:AGENT_GAUGE_DEBUG=1; uv run agent-gauge    # prints every cycle to the console
```

The render tests use `QT_QPA_PLATFORM=offscreen` (see `tests/conftest.py`) and check that every
painting path runs without raising, across the states the UI actually reaches: no data, live, error,
collecting and compact.

In that mode Qt swaps the real font database for a stub whose fallback runs about 1.8x wider than
Segoe UI. Two consequences:

- tests that measure text geometry are gated on the font (the `real_fonts` fixture) and skip
  themselves when headless. To run the whole suite against the real thing:

  ```powershell
  $env:QT_QPA_PLATFORM = "windows"; uv run pytest     # Windows
  ```

  ```bash
  QT_QPA_PLATFORM=cocoa uv run pytest                 # macOS
  QT_QPA_PLATFORM=xcb uv run pytest                   # Linux
  ```

- `tools/preview.py` deliberately does **not** use offscreen: in that mode every glyph is a box.

That gate is stricter than "did we get a font". The geometry constants in `widget.py` were derived
from one family's metrics, and `paint.MEASURED` records which families have since been checked.

```powershell
uv run python tools/measure_font.py                     # whatever the app resolved
uv run python tools/measure_font.py "Noto Sans"         # an installed family
uv run python tools/measure_font.py path\to\Inter.ttf    # a file, nothing installed
```

It runs the same twelve checks the tests do and prints the numbers. A font file is loaded into that
process only, through `QFontDatabase`, so measuring a face does not mean installing it. The same
switch is available at runtime: `AGENT_GAUGE_FONT` pins a family, for a desktop whose default
measures badly.

What that turned up:

| Family | Result |
| --- | --- |
| Segoe UI Variable Display | all twelve fit; the face the design was drawn against |
| Noto Sans | all twelve fit |
| Ubuntu | all twelve fit |
| Cantarell | `56min` overruns its row by 0.1px and is elided to fit |
| Inter | two rows overrun; the widest ran nearly 2px past |

Two changes came out of it. The gauge number now **sizes itself**: it starts at the point size the
design uses and steps down until it clears the stroke, so it shrinks a point instead of crossing the
ring. On Segoe UI nothing moves, because nothing had to. And the Linux entry in `paint.CANDIDATES`
is gone: it led with Inter, which no desktop ships and which measures worst of the lot, so it was
overriding the user's own configured font with a poorer fit. Linux now uses what the desktop is set
to, which is what `QFontDatabase` was already reporting.

Rows still elide rather than collide when a face runs wide, which is the correct answer to text that
genuinely does not fit - but it is a truncation, so a family only joins `MEASURED` when nothing
truncates. macOS remains unmeasured: SF Pro is not distributed in a form this can load.

The platform layer itself is testable from anywhere: `paths`, `autostart` and the macOS keychain
branch of `credentials` read module-level flags that the tests pin, so `test_paths.py` and
`test_autostart.py` exercise the macOS and Linux code paths on a Windows machine and vice versa.
Only the Windows registry backend is left to a machine that has a registry.

## Building

Each platform builds its own artifact, on itself. There is no cross-compilation here: PyInstaller
freezes the interpreter and the Qt libraries of the machine it runs on.

```powershell
.\installer\build.ps1                  # icon -> PyInstaller -> Inno Setup
.\installer\build.ps1 -SkipInstaller   # only the portable folder in build\dist
.\installer\build.ps1 -Clean           # wipes build\ first, caches included
```

```bash
./installer/build.sh                   # icon -> PyInstaller -> .dmg or .AppImage
./installer/build.sh --skip-package    # only the portable folder in build/dist
./installer/build.sh --clean           # wipes build/ first, caches included
```

| Platform | Needs | Produces |
| --- | --- | --- |
| Windows | Inno Setup (`winget install JRSoftware.InnoSetup`) | `build/AgentGauge-<version>.exe`, ~21 MB from 70 MB installed |
| macOS | Xcode command line tools, for `iconutil`, `codesign` and `hdiutil` | `build/AgentGauge-<version>-<arch>.dmg` |
| Linux | `appimagetool`, downloaded on first run | `build/AgentGauge-<version>.AppImage` |

Every run leaves **exactly one** artifact in `build/`, the one just built: keeping old versions side
by side is how the wrong file gets shipped.

| File | Role |
| --- | --- |
| `installer/build.ps1` | Windows: the three steps, version read from `pyproject.toml` |
| `installer/build.sh` | macOS and Linux: the same three steps, plus signing and packaging |
| `installer/agent-gauge.spec` | PyInstaller, shared: onedir, no console, per-OS icon and metadata |
| `installer/agent-gauge.iss` | Inno Setup: per-user install, shortcuts, autostart, uninstaller |
| `installer/entry.py` | Frozen entry point (`__main__.py` uses a relative import) |
| `tools/gen_icon.py` | `.ico`, `.iconset` or a hicolor tree, chosen by the output path |
| `tools/measure_font.py` | Runs the layout's geometry checks against any font |

Packaging decisions:

- **onedir, not onefile.** `--onefile` unpacks the whole Qt runtime into a temp folder on every
  launch, a second or two for an app that lives in the tray and starts with the session.
- **`opengl32sw.dll` left out.** That is 20 MB of Mesa's software OpenGL, a fifth of the bundle, and
  this interface is painted by Qt's raster engine alone.
- **`QtDBus` is excluded everywhere except Linux**, where it is not optional: a tray icon on a modern
  Linux desktop *is* a D-Bus StatusNotifierItem, and dropping the module leaves the app trayless.
- **The `.ico` is assembled by hand, the `.icns` is not.** Importing Pillow into a PySide6 process
  loads a second libpng/zlib and Qt's PNG encoder dies with an access violation, so the ICO container
  is written directly - 40 lines, and no DLL clash. For macOS the generator emits an `.iconset`
  directory and lets Apple's `iconutil` build the container: a hand-rolled one that macOS quietly
  refuses is the worse trade.
- **Ad-hoc signing on macOS is not cosmetic.** An unsigned arm64 binary is killed on launch, so
  `build.sh` always signs; `CODESIGN_ID` swaps in a real Developer ID where there is one.
- **The AppImage is built on the oldest supported Ubuntu image**, because it inherits the glibc of
  the machine that built it and a newer one would refuse to start on older distributions.

## Implementation notes

Things that cost time and that the code alone does not explain:

- **`QGraphicsDropShadowEffect` on a translucent window freezes the content** after the first frame
  on Windows; the widget painted `--` forever. The shadow is drawn by hand in `paint.shadow()` and
  each window reserves a transparent margin for it.
- **The receiver of the poller's signals must be a `QObject`.** Connected to a plain Python object
  the connection becomes direct, and painting happens on the collection thread.
- **Clicking the widget while the panel is open arrives in two parts.** The `Qt.Popup` closes itself
  on the outside click and the widget receives that same click next; without a guard the panel
  closed and reopened in one gesture. `Panel.just_closed()` swallows the second event for 250 ms.
- **HTTPS trust goes through the operating system, not OpenSSL's own store.** Windows keeps a small
  set of root certificates on disk and fetches the rest on demand through CryptoAPI, which is why a
  browser opens a site that Python, verifying with OpenSSL, rejects as "unable to get local issuer
  certificate". That is not hypothetical: it was reported from a machine where the gauge read
  Anthropic fine, the browser opened `api.github.com` fine, and the update check inside the same app
  could not. `net.context()` hands verification to the OS, so the answer matches what everything
  else on that machine believes, including a corporate proxy's own CA - and every HTTPS call in the
  app goes through it. Before, one of five passed a context and four did not, which is why the
  difference stayed invisible for so long. Where the OS layer is unavailable the older verifier
  still runs - refusing to connect would be worse - but that fallback writes a line to `errors.log`,
  because a fix that quietly turns itself off is indistinguishable from no fix at all.
- **A failure that happens at 3am used to leave nothing behind.** The message sat on screen until
  the next cycle overwrote it, so by the time anyone looked the app had recovered and the evidence
  was gone. `errors.log` now keeps the last two hundred failed cycles with the context that tells
  them apart: the HTTP status, how long since the last good cycle, when Claude Code last rewrote the
  credentials, and whether the token was actually past its expiry. Successes are not logged, so the
  file staying empty is itself the signal. Neither token is written to it, and a test reads the
  whole file back to prove it.

  A run of the same failure collapses into one line carrying the newest values, a `repeat=` count
  and a `since=` start. That is not a nicety: the first outage this caught repeated every two
  minutes for four hours, wrote 130 identical lines, and pushed the beginning of that very outage
  out of the file.
- **One dropped packet used to look like breakage.** There was no retry, so a connection that
  failed for a second painted the widget red until the next cycle - fifteen minutes of it at the
  longest interval. The probe is now tried twice. An HTTP answer is not retried: 429 carries the
  rate-limit headers this request exists to read, and repeating it would double the cost of being
  rate limited.
- **An expired token is a resting state, not a fault.** Claude Code's access token lives eight
  hours and is only renewed while Claude Code is running, so a night away ends with no usable token
  - measured, not assumed: three consecutive cycles of 8.00 h each. Painting that red made the
  widget cry wolf about its own normal condition, so it now waits in grey and says so. Red is kept
  for the things that are actually wrong. The request is not sent either: `expiresAt` is the
  timestamp Claude Code refreshes against, so it would only come back 401.
- **Recovery no longer waits for the next cycle.** While the token is expired the only thing that
  can change the answer is Claude Code rewriting the credentials, so that file's timestamp is
  watched instead of the clock. Using Claude Code brings the widget back in about five seconds
  rather than up to a full interval, and a `stat` costs nothing.
- **What it will not do is refresh the token itself.** The refresh token is right there and it
  would work. Refresh tokens are commonly single-use with rotation, so a widget that spent one
  could leave Claude Code holding an invalid token and log you out of it - a disproportionate way
  to lose a gauge reading.
- **The burn rate used to die for hours after every window reset.** The sample deque was bounded
  by count, not by time, so the readings from the previous window stayed in it; `burn_rate()` saw
  the percentage fall, took that for a reset, and returned zero until they aged out - up to six
  hours. Samples are now dropped once they predate the current window, which is also what makes the
  baseline safe to keep on disk between runs.
- **Text is measured, never placed at a fixed offset.** `56min` is half again as wide as `2h13` and
  used to run into the clock column. Digits use `tnum` (`QFont.setFeature`), otherwise `1` is
  narrower than the other digits and the countdown jitters every second.

And four that only appear once the app leaves Windows:

- **macOS hides `Qt.Tool` windows whenever the application is deactivated.** For a widget whose
  entire job is to stay visible while you work in something else, that means it is never on screen.
  `WA_MacAlwaysShowToolWindow` undoes it, and is a no-op on the other two.
- **Wayland gives a window no say in its own position.** `move()` is silently ignored, so the saved
  position - most of the point of a floating widget - cannot be restored. There is no fix inside the
  protocol; `app.prefer_x11()` asks for XWayland when an X server is reachable, and steps aside if
  the user set `QT_QPA_PLATFORM` themselves.
- **The tray icon is drawn on a surface this app does not paint.** Near-white digits vanish on a
  light taskbar, menu bar or panel, so the ink follows the system theme. On Windows that means
  reading `SystemUsesLightTheme` from the registry rather than Qt's `colorScheme()`: Qt reports the
  *app* theme, and a light-apps/dark-taskbar setup would come back inverted.
- **On macOS the token is not in a file.** Claude Code puts it in the login keychain, so
  `credentials.py` shells out to `security find-generic-password` and keeps the file as a fallback.
  Every way that call can come up empty - not signed in, access denied, no binary at all - falls
  through to the file and produces a single error for both.

## Cost

Each cycle is a POST worth one output token, the smallest request the API accepts. At two minutes
that would be roughly 700 a day, but the interval is a floor rather than a cadence: after three
readings that do not move, the wait stretches up to four times it, so an idle machine settles near
175. Anything that moves the number, any error, and the refresh button all put it straight back.
Raise the interval in the menu if it still bothers you.

## License

MIT. See [LICENSE](LICENSE).
