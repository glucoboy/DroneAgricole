"""Launch FreeCAD in dedicated processes and keep source assemblies isolated."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
from uuid import uuid4
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile


PROJECT = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = PROJECT / '.agents/skills/electromechanical-integration/scripts'
BUILDER = PROJECT / 'hardware/mecanique/cartographe/verification/cable_workbench_prototype.py'


def load_helper(path):
    """Import a specific repository helper without changing global search paths."""
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = load_helper(SKILL_SCRIPTS / 'workspace_guard.py')


class FreeCADError(RuntimeError):
    """No validated native observation could be finalized."""


class FreeCADAdapter:
    def __init__(self, python: str | Path, timeout: int = 60):
        self.python = Path(python).resolve()
        self.timeout = timeout
        self._probe = None

    def probe(self):
        """Verify FreeCAD/Part independently before any CAD work."""
        if self._probe is None:
            self._probe = guard.probe_python(self.python, min(self.timeout, 30))
        return dict(self._probe)

    def _run(self, target, action, entry, **parameters):
        probe = self.probe()
        if not probe['verified']:
            raise FreeCADError(f'FreeCAD Python unavailable: {probe}')
        request = target / f'{action}-{uuid4().hex}.request.json'
        response = request.with_suffix('.result.json')
        trace = request.with_suffix('.stderr.log')
        request.write_text(json.dumps(dict(action=action, entry=entry, **parameters), allow_nan=False), encoding='utf-8')
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen', PYTHONUTF8='1', PYTHONPATH=str(PROJECT))
        try:
            with trace.open('wb') as diagnostics:
                execution = subprocess.run(
                    [str(self.python), '-B', '-m', 'electromechanical_engine.freecad_worker',
                     str(request), str(response)], cwd=target, env=env, stdout=subprocess.DEVNULL,
                    stderr=diagnostics, timeout=self.timeout, check=False,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                )
        except subprocess.TimeoutExpired as exc:
            raise FreeCADError(f'FreeCAD {action} timed out after {self.timeout}s: '
                               f'{trace.read_text(encoding="utf-8", errors="replace")[-3000:]}') from exc
        except OSError as exc:
            raise FreeCADError(f'FreeCAD {action} did not start: {exc}') from exc
        try:
            result = json.loads(response.read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise FreeCADError(f'FreeCAD {action} did not finalize its report (code {execution.returncode}): '
                               f'{trace.read_text(encoding="utf-8", errors="replace")[-2000:]}') from exc
        if execution.returncode or result.get('finalized') is not True:
            raise FreeCADError(f'FreeCAD {action} failed: {result.get("error") or trace}')
        return result

    def _roundtrip(self, target, action, entry, **parameters):
        entry = guard.inside(target, target / entry).relative_to(target).as_posix()
        before_save = self._native_hashes(target, entry) if action == 'roundtrip' else None
        saved = self._run(target, action, entry, **parameters)
        if before_save is not None and not saved['recompute_ok']:
            if saved['save_performed']:
                raise FreeCADError('An invalid native inventory was unexpectedly saved.')
            self._verify_native_observation(target, entry, saved, before_save)
            return {**saved, 'reopened': False}
        saved_hashes = self._native_hashes(target, entry)
        if before_save is not None and (
                before_save.keys() != saved_hashes.keys()
                or any(saved_hashes[name] != digest for name, digest in before_save.items() if name != entry)):
            raise FreeCADError('Saving the entry changed a native dependency or its closure.')
        inspected = self._run(target, 'inspect', entry, **parameters)
        self._verify_native_observation(target, entry, inspected, saved_hashes)
        if (not saved['save_performed'] or saved['worker_id'] == inspected['worker_id']
                or saved_hashes[entry] != saved['native_sha256']):
            raise FreeCADError('Independent reopening did not inspect the saved file.')
        inspected.update(reopened=True, save_performed=True,
                         saved_process=saved['pid'], saved_worker_id=saved['worker_id'],
                         saved_recomputed_features=saved['recomputed_features'])
        return inspected

    @staticmethod
    def _native_hashes(target, entry):
        try:
            paths = guard.dependencies(target, [entry])
            return {path.relative_to(target).as_posix(): guard.sha256(path) for path in paths}
        except (BadZipFile, ParseError, ValueError, KeyError, OSError) as exc:
            raise FreeCADError(f'Invalid native dependency closure: {exc}') from exc

    def _verify_native_observation(self, target, entry, observed, hashes):
        if self._native_hashes(target, entry) != hashes or observed['native_sha256'] != hashes[entry]:
            raise FreeCADError('Candidate or dependency changed during independent inspection.')
        if {document['file'] for document in observed['documents']} != hashes.keys():
            raise FreeCADError('FreeCAD did not open exactly the expected native dependency closure.')
        observed['native_inputs_sha256'] = hashes

    def extract(self, source_root, entry, target, extra=()):
        """Stage the native XLink closure, then save and reopen only the copy."""
        target = Path(target).resolve()
        try:
            receipt = guard.stage(source_root, Path(entry).as_posix(), target, extra)
        except (RuntimeError, BadZipFile, ParseError) as exc:
            raise FreeCADError(f'Native isolation failed: {exc}') from exc
        try:
            inspected = self._roundtrip(target, 'roundtrip', receipt['entry'])
        finally:
            try:
                verified = guard.verify_sources(receipt)
            except (RuntimeError, OSError, ValueError) as exc:
                raise FreeCADError(f'Source integrity failure: {exc}') from exc
        return {**inspected, **verified, 'source_receipt': receipt}

    def build(self, plan, target):
        """Build WireFlex/ArchCable candidates over declared reference geometry."""
        target = Path(target).resolve()
        target.mkdir(parents=True, exist_ok=False)
        return self._roundtrip(target, 'build', 'candidate.FCStd', plan=plan)

    def inspect(self, candidate, specification):
        """Measure a saved candidate in a new process without saving it."""
        candidate = Path(candidate).resolve()
        if candidate.is_dir():
            candidate /= 'candidate.FCStd'
        hashes = self._native_hashes(candidate.parent, candidate.name)
        try:
            result = self._run(candidate.parent, 'inspect', candidate.name, plan=specification)
        finally:
            if self._native_hashes(candidate.parent, candidate.name) != hashes:
                raise FreeCADError('Candidate or dependency changed during independent inspection.')
        self._verify_native_observation(candidate.parent, candidate.name, result, hashes)
        return {**result, 'reopened': True}
