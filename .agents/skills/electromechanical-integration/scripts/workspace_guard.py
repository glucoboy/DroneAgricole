"""Infrastructure de copie FreeCAD et empreintes, sans logique de routage."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def inside(root, path):
    root, path = Path(root).resolve(), Path(path).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f'Chemin hors racine : {path}')
    return path


def relative_file(root, name):
    if Path(name).is_absolute() or PureWindowsPath(name).is_absolute():
        raise ValueError(f'Chemin relatif requis : {name}')
    path = inside(root, Path(root) / name)
    if not path.is_file():
        raise ValueError(f'Dépendance absente : {path}')
    # Les jonctions/symlinks pourraient conserver une destination originale.
    for part in (Path(root) / name).absolute().parents:
        if part == Path(root).absolute():
            break
        if part.is_symlink() or getattr(part, 'is_junction', lambda: False)():
            raise ValueError(f'Lien filesystem interdit : {part}')
    if (Path(root) / name).is_symlink():
        raise ValueError(f'Lien filesystem interdit : {name}')
    return path


def dependencies(root, entrypoints):
    """Fermer les XLink natifs, sans charger ni exécuter les documents."""
    pending = [relative_file(root, p) for p in entrypoints]
    found = set()
    while pending:
        path = pending.pop()
        if path in found:
            continue
        found.add(path)
        if path.suffix.lower() != '.fcstd':
            continue
        with zipfile.ZipFile(path) as archive:
            document = ET.fromstring(archive.read('Document.xml'))
        for element in document.iter():
            if not element.tag.startswith('XLink'):
                continue
            filename = element.get('file', '')
            if not filename:
                continue
            if Path(filename).is_absolute() or PureWindowsPath(filename).is_absolute():
                raise ValueError(f'XLink absolu à remapper explicitement sur copie : {filename}')
            name = os.path.relpath(path.parent / filename.replace('\\', '/'), root)
            pending.append(relative_file(root, name))
    return sorted(found)


def stage(root, entry, target, extras=(), parameters=None):
    root, target = Path(root).resolve(), Path(target).resolve()
    if target == root or target.is_relative_to(root) or root.is_relative_to(target):
        raise ValueError('Source et destination doivent être disjointes.')
    if target.exists():
        raise ValueError('La destination doit être nouvelle ; aucun écrasement.')
    files = dependencies(root, [entry, *extras])
    if root / 'experiment.json' in files:
        raise ValueError('experiment.json à la racine est réservé au reçu ; choisir une autre racine source.')
    hashes = {str(p.relative_to(root)).replace('\\', '/'): sha256(p) for p in files}
    target.mkdir(parents=True)
    for source in files:
        destination = target / source.relative_to(root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        if sha256(destination) != hashes[str(source.relative_to(root)).replace('\\', '/')]:
            raise RuntimeError('Copie incohérente ; ne pas ouvrir cet essai.')
    receipt = {'schema_version': 1, 'source_root': str(root), 'copy_root': str(target),
               'entry': entry, 'inputs_sha256': hashes, 'parameters': parameters or {},
               'closure': 'native_XLink_plus_explicit_extras',
               'limitations': ['Les fichiers lus par macros/proxies doivent être ajoutés explicitement.',
                               'Vérifier les liens résolus dans FreeCAD avant toute reconstruction.']}
    (target / 'experiment.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    verify_sources(receipt)
    return receipt


def verify_sources(receipt):
    root = Path(receipt['source_root'])
    changed = [name for name, digest in receipt['inputs_sha256'].items()
               if not inside(root, root / name).is_file() or sha256(root / name) != digest]
    if changed:
        raise RuntimeError(f'Sources modifiées ou manquantes : {changed}')
    return {'sources_unchanged': True, 'files_checked': len(receipt['inputs_sha256'])}


def probe_python(executable, timeout=30):
    code = ('import json,FreeCAD as A,Part; s=Part.makeBox(1,2,3); '
            'print(json.dumps({"freecad":A.Version(),"shape_valid":s.isValid(),'
            '"volume":s.Volume,"solids":len(s.Solids)}))')
    try:
        run = subprocess.run([str(executable), '-c', code], capture_output=True,
                             text=True, timeout=timeout, check=False)
        records = [json.loads(line) for line in run.stdout.splitlines() if line.startswith('{')]
        result = records[-1] if records else {}
        ok = run.returncode == 0 and result.get('shape_valid') is True and result.get('solids') == 1 and abs(result.get('volume', 0)-6) < 1e-8
        return {'verified': ok, 'executable': str(executable), 'returncode': run.returncode,
                'result': result, 'stderr': run.stderr[-3000:], 'scope': 'Part_only_no_Cables_GUI'}
    except (OSError, subprocess.TimeoutExpired, ValueError) as error:
        return {'verified': False, 'executable': str(executable), 'error': str(error)}


def select_backend(mcp_available, python_probe):
    if mcp_available is True:
        return {'backend': 'mcp', 'geometry_executed': False}
    if python_probe.get('verified') is True:
        return {'backend': 'freecad_python', 'geometry_executed': False,
                'requires_cables_probe': True}
    return {'backend': None, 'geometry_executed': False, 'reason': 'no_verified_backend'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    copy = commands.add_parser('stage')
    copy.add_argument('--root', required=True)
    copy.add_argument('--entry', required=True)
    copy.add_argument('--target', required=True)
    copy.add_argument('--extra', action='append', default=[])
    copy.add_argument('--parameters', help='Fichier JSON des paramètres effectifs')
    verify = commands.add_parser('verify')
    verify.add_argument('receipt')
    probe = commands.add_parser('probe-python')
    probe.add_argument('executable')
    args = parser.parse_args()
    if args.command == 'stage':
        parameters = json.loads(Path(args.parameters).read_text(encoding='utf-8')) if args.parameters else {}
        result = stage(args.root, args.entry, args.target, args.extra, parameters)
    elif args.command == 'verify':
        result = verify_sources(json.loads(Path(args.receipt).read_text(encoding='utf-8')))
    else:
        result = probe_python(args.executable)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get('verified', True) else 2


if __name__ == '__main__':
    raise SystemExit(main())
