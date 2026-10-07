# browser-fingerprint-lab

Utilities for inspecting and testing browser fingerprint surfaces in
Chromium-based browsers. Built for privacy research and anti-fingerprinting
testing.

## Contents

- `probe/fingerprint-probe.html` — a single-page probe that collects common
  fingerprint surfaces and reports them as JSON:
  - Canvas 2D fingerprint (FNV-1a hash of the data URL + pixel sample)
  - WebGL vendor/renderer (`WEBGL_debug_renderer_info`) and a render hash
  - `OfflineAudioContext` audio fingerprint
  - Font availability probe
  - Hardware & environment: CPU cores, device memory, screen, DPR,
    languages, timezone

  The result is exposed via `document.title` with an `FPR|` prefix so
  headless harnesses can scrape it from `--dump-dom` output.

- `probe/cdp-title-probe.js` — Node.js helper that drives a Chrome DevTools
  Protocol target: finds or creates a page, navigates it, waits for the probe
  result in `document.title`, and prints the JSON.

- `tools/seed-sweep.py` — harness that runs a fingerprint-seeded headless
  Chromium across many seeds in parallel, stores one JSON record per seed,
  and prints a summary of distinct values.

## Requirements

- Node.js >= 22 (uses the built-in `WebSocket` global)
- Python 3.9+ (for the sweep harness)
- A Chromium binary supporting `--fingerprint=<seed>` (e.g. an
  anti-fingerprinting patched build). Running the probe against a regular
  browser also works — fields will simply reflect real values.

## Usage

Serve the probe locally (the CDP flow needs http, not `file://`):

```
python -m http.server 8799
```

Run headless Chromium against it:

```
chrome --headless=new --fingerprint=12345 --virtual-time-budget=4000 \
  --dump-dom http://127.0.0.1:8799/probe/fingerprint-probe.html
```

or drive a live instance over CDP:

```
chrome --remote-debugging-port=9222 about:blank
node probe/cdp-title-probe.js 9222 http://127.0.0.1:8799/probe/fingerprint-probe.html
```

Sweep seeds:

```
python tools/seed-sweep.py --chrome "C:\path\to\chrome.exe" --count 100 --out results.jsonl
```

## Legal

For research and testing on systems you own or are authorized to test.

## License

[MIT](LICENSE)
