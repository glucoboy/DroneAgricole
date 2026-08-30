#!/usr/bin/env python3
"""Runner HTTP interne, limité aux deux essais PX4 SITL approuvés."""

from __future__ import annotations

import argparse
import asyncio
from collections import deque
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
from typing import Any, Mapping

from aiohttp import web

from software.visualization.px4_runner_contract import Px4RunnerError, validate_start_payload


class Px4RunManager:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.resolve()
        self.process: asyncio.subprocess.Process | None = None
        self.log_task: asyncio.Task[None] | None = None
        self.watch_task: asyncio.Task[None] | None = None
        self.logs: deque[str] = deque(maxlen=120)
        self.current: dict[str, Any] = {"state": "idle", "message": "Runner PX4 SITL prêt."}
        self.stop_requested = False

    def status(self) -> dict[str, Any]:
        return {**self.current, "logs": list(self.logs)[-20:]}

    async def start(self, payload: Any) -> dict[str, Any]:
        if self.process is not None and self.process.returncode is None:
            raise RuntimeError("Un essai PX4 est déjà actif.")
        request = validate_start_payload(payload, self.workspace)
        parameters = request["parameters"]
        command = [
            "ros2", "run", "drone_agricole_px4_bridge", "offboard_test", "--ros-args",
            "-p", "execute:=true",
            "-p", f"mission_mode:={request['mode']}",
            "-p", f"takeoff_altitude_m:={parameters['takeoff_altitude_m']}",
            "-p", f"leg_m:={parameters['leg_m']}",
            "-p", f"warmup_s:={parameters['warmup_s']}",
            "-p", f"hover_s:={parameters['hover_s']}",
            "-p", f"stage_timeout_s:={parameters['stage_timeout_s']}",
            "-p", f"result_directory:={request['result_directory']}",
        ]
        environment = os.environ.copy()
        if environment.get("DRONE_AGRICOLE_SITL") != "1":
            raise RuntimeError("Le verrou d'environnement SITL n'est pas actif.")
        self.logs.clear()
        self.stop_requested = False
        self.current = {
            "state": "starting",
            "run_id": request["run_id"],
            "mode": request["mode"],
            "parameters": parameters,
            "result_directory": request["result_directory"],
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": None,
            "exit_code": None,
            "message": "Démarrage du scénario PX4 SITL…",
        }
        try:
            self.process = await asyncio.create_subprocess_exec(
                *command,
                cwd=self.workspace,
                env=environment,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                start_new_session=True,
            )
        except Exception:
            self.current.update(state="failed", message="Le processus PX4 n'a pas démarré.")
            raise
        self.current.update(state="running", message="Scénario PX4 SITL en cours.")
        self.log_task = asyncio.create_task(self._consume_logs(self.process))
        self.watch_task = asyncio.create_task(self._watch(self.process))
        return self.status()

    async def _consume_logs(self, process: asyncio.subprocess.Process) -> None:
        if process.stdout is None:
            return
        async for raw_line in process.stdout:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if line:
                self.logs.append(line)

    async def _watch(self, process: asyncio.subprocess.Process) -> None:
        exit_code = await process.wait()
        if self.log_task is not None:
            await self.log_task
        result_path = self.workspace / self.current["result_directory"] / "result.json"
        result = None
        if result_path.is_file():
            try:
                result = json.loads(result_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                self.logs.append("Le fichier result.json est illisible.")
        if self.stop_requested:
            state, message = "cancelled", "Essai PX4 arrêté ; l'atterrissage de sécurité a été demandé."
        elif exit_code == 0 and isinstance(result, Mapping) and result.get("success") is True:
            state, message = "completed", "Essai PX4 SITL terminé avec succès."
        else:
            state, message = "failed", f"Essai PX4 en échec avec le code {exit_code}."
        self.current.update(
            state=state,
            message=message,
            finished_at=datetime.now(timezone.utc).isoformat(),
            exit_code=exit_code,
            result=result,
        )
        if self.process is process:
            self.process = None

    async def stop(self) -> dict[str, Any]:
        process = self.process
        if process is None or process.returncode is not None:
            raise RuntimeError("Aucun essai PX4 n'est actif.")
        self.stop_requested = True
        self.current.update(state="stopping", message="Arrêt sûr PX4 en cours…")
        try:
            os.killpg(process.pid, signal.SIGINT)
        except ProcessLookupError:
            pass
        try:
            await asyncio.wait_for(asyncio.shield(process.wait()), timeout=20.0)
        except asyncio.TimeoutError:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        if self.watch_task is not None:
            await asyncio.gather(self.watch_task, return_exceptions=True)
        return self.status()


def create_application(manager: Px4RunManager) -> web.Application:
    application = web.Application()

    async def health(_request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "sitl_locked": os.environ.get("DRONE_AGRICOLE_SITL") == "1", "run": manager.status()})

    async def status(_request: web.Request) -> web.Response:
        return web.json_response(manager.status())

    async def start(request: web.Request) -> web.Response:
        try:
            payload = await request.json()
            response = await manager.start(payload)
        except (json.JSONDecodeError, Px4RunnerError) as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except RuntimeError as exc:
            return web.json_response({"error": str(exc)}, status=409)
        return web.json_response(response, status=202)

    async def stop(_request: web.Request) -> web.Response:
        try:
            response = await manager.stop()
        except RuntimeError as exc:
            return web.json_response({"error": str(exc)}, status=409)
        return web.json_response(response)

    async def cleanup(_application: web.Application) -> None:
        if manager.process is not None and manager.process.returncode is None:
            await manager.stop()

    application.router.add_get("/api/health", health)
    application.router.add_get("/api/run/status", status)
    application.router.add_post("/api/run/start", start)
    application.router.add_post("/api/run/stop", stop)
    application.on_cleanup.append(cleanup)
    return application


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8091)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    args = parser.parse_args()
    manager = Px4RunManager(args.workspace)
    web.run_app(create_application(manager), host=args.host, port=args.port, print=None)


if __name__ == "__main__":
    main()
