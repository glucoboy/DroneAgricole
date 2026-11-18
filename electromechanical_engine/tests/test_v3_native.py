"""Vérifications de transfert XLink et d'identité d'occurrence sur banc natif."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from xml.etree import ElementTree
from zipfile import ZipFile

from electromechanical_engine.freecad import PROJECT, guard
from electromechanical_engine.v3_native import (
    MATRIX_TOLERANCE, project, read, serialized_dependencies, worker,
)
from validation_engine.tests import test_xlink_native as fixture
from validation_engine.tests.test_xlink_native import ARRAY_ELEMENTS, CONTACT, DEPENDENCY, ENTRY, FIRST, SECOND


@unittest.skipUnless(os.environ.get('ELECTROMECHANICAL_FREECAD_PYTHON'), 'FreeCAD non demandé')
class NativeV3Test(unittest.TestCase):
    def setUp(self):
        workspace = PROJECT / '.runtime'
        workspace.mkdir(exist_ok=True)
        directory = tempfile.TemporaryDirectory(prefix='v3-native-test-', dir=workspace)
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.python = Path(os.environ['ELECTROMECHANICAL_FREECAD_PYTHON'])
        self.source = self.root / 'source'
        fixture.XLinkNativeTests.worker('create', self.source)

    def run_projection(self, label):
        return project(self.python, self.source, ENTRY, self.root / label,
                       self.root / f'{label}.json')

    def assert_origin(self, occurrence, expected):
        for index, value in zip((3, 7, 11), expected, strict=True):
            self.assertAlmostEqual(occurrence['matrix'][index], value, places=7)
        check = occurrence['placement_check']
        self.assertEqual(check['status'], 'PASS')
        self.assertLessEqual(check['maximum_absolute_difference'], MATRIX_TOLERANCE)

    def test_transfer_replays_shared_rotated_and_indexed_occurrences(self):
        report = self.run_projection('transfer')
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(report['transfer']['status'], 'PASS')
        self.assertTrue(report['transfer']['separate_processes'])
        self.assertTrue(report['source_immutability']['sources_unchanged'])
        occurrences = report['occurrences']
        for key, origin in ((FIRST, (-1, 0, 13)), (SECOND, (6, 10, 13))):
            self.assertEqual(occurrences[key]['definition'], CONTACT)
            self.assert_origin(occurrences[key], origin)
            construction = key.removesuffix('Contact') + 'Construction'
            self.assertFalse(occurrences[construction]['visible'])
        for index, key in enumerate(ARRAY_ELEMENTS, 1):
            self.assert_origin(occurrences[key], (30, index * 10, 13))
        self.assertLess(report['document_order'].index(DEPENDENCY),
                        report['document_order'].index(ENTRY))

    def test_repositioning_definition_changes_only_link_transform_occurrence(self):
        before = self.run_projection('initial')
        edited = self.root / 'edited-source'
        historic = guard.stage(self.source, ENTRY, edited)
        fixture.XLinkNativeTests.worker('move', edited)
        after = project(self.python, edited, ENTRY, self.root / 'edited',
                        self.root / 'edited.json')
        self.assertEqual(after['status'], 'PASS')
        self.assertEqual(set(before['occurrences']), set(after['occurrences']))
        self.assertEqual(before['before_sha256'][ENTRY], after['before_sha256'][ENTRY])
        self.assertNotEqual(before['before_sha256'][DEPENDENCY], after['before_sha256'][DEPENDENCY])
        self.assert_origin(after['occurrences'][FIRST], (-1, 0, 13))
        self.assert_origin(after['occurrences'][SECOND], (6, 20, 13))
        self.assertTrue(guard.verify_sources(historic)['sources_unchanged'])

    def test_copy_with_missing_file_is_refused_before_worker(self):
        (self.source / DEPENDENCY).unlink()
        with self.assertRaisesRegex(ValueError, 'Dépendance absente'):
            self.run_projection('missing')
        self.assertFalse((self.root / 'missing' / 'staged.json').exists())

    def test_copy_with_removed_link_target_is_diagnosed(self):
        broken_source = self.root / 'broken-source'
        historic = guard.stage(self.source, ENTRY, broken_source)
        fixture.XLinkNativeTests.worker('remove-target', broken_source)
        report = project(self.python, broken_source, ENTRY, self.root / 'broken',
                         self.root / 'broken.json')
        self.assertEqual(report['status'], 'INCONCLUSIVE')
        self.assertIn(DEPENDENCY + '#Component',
                      {target['target'] for target in report['broken_serialized_links']})
        self.assertNotIn(FIRST, report['occurrences'])
        self.assertNotIn(SECOND, report['occurrences'])
        self.assertTrue(guard.verify_sources(historic)['sources_unchanged'])

    def test_copy_mutated_after_sealing_is_refused(self):
        staged = self.root / 'tampered'
        receipt = guard.stage(self.source, ENTRY, staged)
        fixture.XLinkNativeTests.worker('move', staged)
        output = self.root / 'tampered.json'
        with self.assertRaisesRegex(RuntimeError, 'sans rapport finalisé'):
            worker(self.python, staged, output, 30)
        self.assertFalse(read(output)['finalized'])
        self.assertIn('copie diffère de la source gelée', read(output)['error'])
        self.assertTrue(guard.verify_sources(receipt)['sources_unchanged'])

    @staticmethod
    def replace_xlink(path, reference):
        with ZipFile(path) as archive:
            members = {name: archive.read(name) for name in archive.namelist()}
        document = ElementTree.fromstring(members['Document.xml'])
        next(element for element in document.iter('XLink') if element.get('file')).set('file', reference)
        members['Document.xml'] = ElementTree.tostring(document, encoding='utf-8')
        with ZipFile(path, 'w') as archive:
            for name, data in members.items():
                archive.writestr(name, data)

    def test_refuses_absolute_or_escaping_xlink_before_freecad(self):
        for index, reference in enumerate(('C:/autre/source.FCStd', '../../outside.FCStd')):
            with self.subTest(reference=reference):
                copy = self.root / f'external-{index}'
                guard.stage(self.source, ENTRY, copy)
                self.replace_xlink(copy / ENTRY, reference)
                with self.assertRaisesRegex(ValueError, 'XLink absolu|Chemin hors racine'):
                    serialized_dependencies(copy, (ENTRY, DEPENDENCY))

    def test_refuses_document_dependency_cycle(self):
        copy = self.root / 'cycle'
        guard.stage(self.source, ENTRY, copy)
        # Add a property in the component pointing back to the assembly.
        with ZipFile(copy / DEPENDENCY, 'w') as archive:
            archive.writestr('Document.xml', '''
                <Document>
                  <Objects><Object name="Component" type="App::Part"/></Objects>
                  <ObjectData><Object name="Component"><Properties><Property name="Parent">
                    <XLink file="../assemblies/Root.FCStd" name="Root"/>
                  </Property></Properties></Object></ObjectData>
                </Document>
            ''')
        with self.assertRaisesRegex(ValueError, 'Cycle dans les documents natifs'):
            serialized_dependencies(copy, (ENTRY, DEPENDENCY))


if __name__ == '__main__':
    unittest.main()
