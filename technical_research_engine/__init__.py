"""Interface Python du moteur natif de recherche technique L1."""

import json
import os
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile

from electromechanical_engine.contracts import decode

__all__ = ["ResearchEngine", "ResearchEngineError", "export_json"]


class ResearchEngineError(RuntimeError):
    """Échec du moteur avec le code de sortie et sa réponse structurée."""

    def __init__(self, returncode, response):
        self.returncode = returncode
        self.response = response
        super().__init__(response.get("message") or response.get("reason")
                         or response.get("error") or str(response))


class ResearchEngine:
    """Client du processus natif pour une racine et un registre locaux."""

    def __init__(self, root, store, executable, catalog=None):
        self.root = Path(root)
        self.store = Path(store)
        self.executable = os.fspath(executable)
        self.catalog = None if catalog is None else Path(catalog)

    def _execute(self, action, *options, use_root=True):
        command = [self.executable, action, "--store", str(self.store)]
        if use_root:
            command.extend(("--root", str(self.root)))
        command.extend(options)
        try:
            process = subprocess.run(command, capture_output=True, check=False)
        except OSError as exc:
            raise ResearchEngineError(1, {"error": str(exc)}) from exc
        try:
            response = decode("réponse du moteur L1", process.stdout)
        except ValueError as exc:
            raise ResearchEngineError(1, {
                "error": f"Réponse JSON L1 invalide (code natif {process.returncode})"
            }) from exc
        if process.returncode:
            raise ResearchEngineError(process.returncode, response)
        return response

    def submit_issue(self, issue_id, *, online=False, refresh=False):
        """Cherche par identifiant et enregistre le rapport, y compris UNKNOWN."""
        if self.catalog is None:
            raise ValueError("Un catalogue est requis pour soumettre une question.")
        options = ["--catalog", str(self.catalog), "--issue", issue_id]
        if online:
            options.append("--online")
        if refresh:
            options.append("--refresh")
        return self._execute("submit", *options)

    def get_issue(self, issue_id):
        """Relit le rapport courant. Le code 3 indique une absence ou une péremption."""
        return self._execute("get", "--issue", issue_id)

    def list_reports(self):
        return self._execute("list", "--view", "reports")

    def list_evidence(self):
        return self._execute("list", "--view", "evidence")

    def list_unknowns(self):
        return self._execute("list", "--view", "unknowns")

    def invalidate_issue(self, issue_id):
        """Invalide l'entrée afin que la prochaine soumission rejoue la recherche."""
        return self._execute("invalidate", "--issue", issue_id, use_root=False)


def export_json(result, path):
    """Publie un JSON UTF-8 dans un fichier neuf du répertoire choisi."""
    path = Path(path)
    payload = json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
        # Sous Windows, rename refuse un nom occupé. Sur POSIX, link fournit
        # la même garantie tout en publiant le fichier déjà complet.
        if os.name == "nt":
            temporary.rename(path)
        else:
            os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
