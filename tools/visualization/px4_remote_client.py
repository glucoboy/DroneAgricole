#!/usr/bin/env python3
"""Client subprocess du dashboard vers le runner PX4 SITL interne."""

from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


TERMINAL = {"completed", "failed", "cancelled"}
stop_requested = False


def request_json(url: str, method: str = "GET", payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=5.0) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8")).get("error")
        except Exception:
            detail = None
        raise RuntimeError(detail or f"Runner PX4 HTTP {exc.code}") from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError(f"Runner PX4 inaccessible : {exc}") from exc


def _signal_stop(_signum: int, _frame: object) -> None:
    global stop_requested
    stop_requested = True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--mode", choices=("square", "failsafe"), required=True)
    parser.add_argument("--result-directory", required=True)
    parser.add_argument("--takeoff-altitude-m", type=float, required=True)
    parser.add_argument("--leg-m", type=float, required=True)
    parser.add_argument("--warmup-s", type=float, required=True)
    parser.add_argument("--hover-s", type=float, required=True)
    parser.add_argument("--stage-timeout-s", type=float, required=True)
    args = parser.parse_args()
    signal.signal(signal.SIGINT, _signal_stop)
    signal.signal(signal.SIGTERM, _signal_stop)
    root = args.url.rstrip("/")
    payload = {
        "run_id": args.run_id,
        "mode": args.mode,
        "result_directory": args.result_directory,
        "parameters": {
            "takeoff_altitude_m": args.takeoff_altitude_m,
            "leg_m": args.leg_m,
            "warmup_s": args.warmup_s,
            "hover_s": args.hover_s,
            "stage_timeout_s": args.stage_timeout_s,
        },
    }
    try:
        status = request_json(f"{root}/api/run/start", "POST", payload)
        print(f"PX4_RUNNER_STARTED={args.run_id}", flush=True)
        log_count = 0
        stop_sent = False
        while status.get("state") not in TERMINAL:
            if stop_requested and not stop_sent:
                status = request_json(f"{root}/api/run/stop", "POST", {})
                stop_sent = True
            else:
                time.sleep(0.5)
                status = request_json(f"{root}/api/run/status")
            logs = status.get("logs") or []
            if len(logs) < log_count:
                log_count = 0
            for line in logs[log_count:]:
                print(line, flush=True)
            log_count = len(logs)
        print(f"PX4_RUNNER_STATE={status.get('state')}", flush=True)
        if stop_sent or status.get("state") == "cancelled":
            return 130
        return 0 if status.get("state") == "completed" else 1
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
