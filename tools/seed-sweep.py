#!/usr/bin/env python3
"""Sweep fingerprint seeds in a fingerprint-seeded headless Chromium build.

Serves the probe/ directory over a local HTTP server, launches
`chrome --headless=new --fingerprint=<seed> --dump-dom` against the probe
page for each seed, scrapes the `FPR|{json}` payload, and stores one record
per seed in a JSONL file. Prints a summary of distinct values at the end.

Usage:
  python seed-sweep.py --chrome /path/to/chrome --count 100 --out results.jsonl
"""
import argparse
import concurrent.futures
import functools
import html
import json
import random
import re
import subprocess
import threading
from collections import Counter
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

FPR_RE = re.compile(r"FPR\|(.*?)</title>", re.S)


def start_server(root, port):
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(root))
    srv = HTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def probe_seed(args, seed):
    url = f"http://127.0.0.1:{args.port}/probe/fingerprint-probe.html"
    cmd = [
        args.chrome, "--headless=new", "--disable-gpu",
        f"--fingerprint={seed}",
        f"--virtual-time-budget={args.virtual_time}",
        "--timeout=20000", "--dump-dom", url,
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=args.timeout).stdout
        m = FPR_RE.search(out)
        if not m:
            return None, "no_output"
        rec = json.loads(html.unescape(m.group(1)))
        rec["seed"] = seed
        return rec, None
    except json.JSONDecodeError:
        return None, "JSONDecodeError"
    except subprocess.TimeoutExpired:
        return None, "timeout"
    except Exception as e:
        return None, type(e).__name__


def main():
    p = argparse.ArgumentParser(description="fingerprint seed sweep harness")
    p.add_argument("--chrome", required=True, help="path to a fingerprint-seeded chromium binary")
    p.add_argument("--count", type=int, default=100, help="number of seeds to test")
    p.add_argument("--start", type=int, default=0, help="sequential seed start (ignored with --random)")
    p.add_argument("--random", action="store_true", help="use random seeds instead of sequential")
    p.add_argument("--max-seed", type=int, default=90000, help="upper bound for random seeds")
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--port", type=int, default=8799, help="local http server port")
    p.add_argument("--virtual-time", type=int, default=4000)
    p.add_argument("--timeout", type=int, default=30, help="per-seed subprocess timeout (seconds)")
    p.add_argument("--out", default="seed_sweep_results.jsonl")
    args = p.parse_args()

    probe_root = Path(__file__).resolve().parent.parent
    start_server(probe_root, args.port)

    if args.random:
        seeds = [random.randrange(args.max_seed) for _ in range(args.count)]
    else:
        seeds = list(range(args.start, args.start + args.count))

    errors = Counter()
    done = 0
    with open(args.out, "w", encoding="utf-8") as fh, \
         concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = [pool.submit(probe_seed, args, s) for s in seeds]
        for fut in concurrent.futures.as_completed(futs):
            rec, err = fut.result()
            done += 1
            if err:
                errors[err] += 1
            else:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            if done % 100 == 0:
                print(f"progress {done}/{len(seeds)}")

    records = [json.loads(line) for line in open(args.out, encoding="utf-8")]
    print("\n== SUMMARY ==")
    print(f"total={len(seeds)} ok={len(records)} errors={sum(errors.values())}")
    if errors:
        print("error kinds:", dict(errors))
    if records:
        for f in records[0]:
            if f == "seed":
                continue
            vals = {str(r.get(f)) for r in records}
            if len(vals) <= 5:
                print(f"{f}: {sorted(vals)}")
        for f in ("canvas", "glHash", "audio"):
            vals = {str(r.get(f)) for r in records if f in r}
            if vals:
                print(f"{f}: {len(vals)} distinct / {len(records)}")
        gpus = Counter(r.get("glRenderer") for r in records)
        if len(gpus) > 1:
            print(f"GPU models: {len(gpus)} distinct")
    print(f"\nresults file: {Path(args.out).resolve()}")


if __name__ == "__main__":
    main()
