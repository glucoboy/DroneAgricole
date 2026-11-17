"""Tests d'infrastructure hors FreeCAD ; archives XML synthétiques uniquement."""
from pathlib import Path
import argparse
import tempfile
import unittest
import zipfile
from workspace_guard import dependencies, stage, verify_sources, select_backend, probe_python


def archive(path, link=''):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, 'w') as out:
        out.writestr('Document.xml', f'<Document><XLink file="{link}"/></Document>')


class WorkspaceTests(unittest.TestCase):
    def test_dependency_copy_and_source_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'source'
            archive(root / 'assembly/main.FCStd', '../parts/part.FCStd')
            archive(root / 'parts/part.FCStd')
            receipt = stage(root, 'assembly/main.FCStd', Path(temporary) / 'experiment', parameters={'radius': 22})
            self.assertEqual(2, verify_sources(receipt)['files_checked'])
            self.assertTrue((Path(receipt['copy_root']) / 'parts/part.FCStd').exists())
            self.assertEqual(receipt['parameters']['radius'], 22)
            (root / 'parts/part.FCStd').write_bytes(b'changed')
            with self.assertRaises(RuntimeError):
                verify_sources(receipt)

    def test_escape_and_absolute_link_blocked(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'source'
            for link in ('../../outside.FCStd', 'C:/original/part.FCStd'):
                archive(root / 'main.FCStd', link)
                with self.assertRaises(ValueError):
                    dependencies(root, ['main.FCStd'])

    def test_existing_or_nested_target_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'source'
            archive(root / 'main.FCStd')
            with self.assertRaises(ValueError):
                stage(root, 'main.FCStd', root / 'nested')
            existing = Path(temporary) / 'exists'
            existing.mkdir()
            with self.assertRaises(ValueError):
                stage(root, 'main.FCStd', existing)

    def test_missing_dependency_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive(Path(temporary) / 'main.FCStd', 'missing.FCStd')
            with self.assertRaises(ValueError):
                dependencies(temporary, ['main.FCStd'])

    def test_receipt_never_overwrites_copied_dependency(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'source'
            archive(root / 'main.FCStd')
            (root / 'experiment.json').write_text('{}', encoding='utf-8')
            target = Path(temporary) / 'copy'
            with self.assertRaises(ValueError):
                stage(root, 'main.FCStd', target, extras=['experiment.json'])
            self.assertFalse(target.exists())

    def test_mcp_unavailable_never_means_geometry_passed(self):
        self.assertIsNone(select_backend(False, {})['backend'])
        result = select_backend(False, {'verified': True})
        self.assertEqual(result['backend'], 'freecad_python')
        self.assertFalse(result['geometry_executed'])
        self.assertTrue(result['requires_cables_probe'])
        self.assertFalse(probe_python('not-a-real-freecad-executable')['verified'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--temp-root', type=Path, default=Path('.runtime/electromechanical-integration/workspace-tests'))
    args, remaining = parser.parse_known_args()
    args.temp_root.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(args.temp_root.resolve())
    unittest.main(argv=[__file__, *remaining])
