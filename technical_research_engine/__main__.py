"""Soumettre et consulter des recherches techniques depuis la ligne de commande."""

import argparse
import json
import sys

from . import ResearchEngine, ResearchEngineError, export_json


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--executable", required=True, help="binaire technical_research_core")
    result.add_argument("--root", required=True, help="racine des sources locales")
    result.add_argument("--store", required=True, help="dossier du registre et du cache")
    result.add_argument("--catalog", help="catalogue JSON des questions et des sources")
    commands = result.add_subparsers(dest="command", required=True)
    submit = commands.add_parser("submit", help="exécuter ou réutiliser une recherche")
    submit.add_argument("issue", help="identifiant d’issue dans le catalogue")
    submit.add_argument("--online", action="store_true", help="autoriser les sources réseau")
    submit.add_argument("--refresh", action="store_true", help="rejouer la recherche")
    get = commands.add_parser("get", help="relire le rapport d’une issue")
    get.add_argument("issue")
    listing = commands.add_parser("list", help="lister les rapports, preuves ou inconnues")
    listing.add_argument("view", choices=("reports", "evidence", "unknowns"))
    invalidate = commands.add_parser("invalidate", help="invalider une recherche du cache")
    invalidate.add_argument("issue")
    for command in (submit, get, listing, invalidate):
        command.add_argument("--output", help="exporter le JSON dans un fichier neuf")
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    engine = ResearchEngine(args.root, args.store, args.executable, args.catalog)
    code = 0
    try:
        if args.command == "submit":
            result = engine.submit_issue(args.issue, online=args.online, refresh=args.refresh)
        elif args.command == "get":
            result = engine.get_issue(args.issue)
        elif args.command == "list":
            list_view = {"reports": engine.list_reports, "evidence": engine.list_evidence,
                         "unknowns": engine.list_unknowns}
            result = list_view[args.view]()
        else:
            result = engine.invalidate_issue(args.issue)
        if args.output:
            export_json(result, args.output)
    except ResearchEngineError as exc:
        result, code = exc.response, exc.returncode
    except (OSError, ValueError) as exc:
        result, code = {"error": str(exc)}, 1
    print(json.dumps(result, ensure_ascii=True, allow_nan=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
