import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from manager import ContactManager, fix_keyboard_layout
from models import normalize_phone


class ManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.m = ContactManager(self.path)

    def add(self, **kwargs):
        values = dict(name='Деканат', phone='+7 (900) 123-45-67', email='dean@example.com', category='Учеба')
        values.update(kwargs)
        return self.m.add_contact(**values)

    def test_empty_start(self):
        self.assertEqual(self.m.contacts, [])

    def test_add_reload_unicode(self):
        c = self.add(notes='Кабинет 205')
        self.assertEqual(ContactManager(self.path).contacts, [c])

    def test_empty_name(self):
        with self.assertRaises(ValueError): self.add(name='  ')

    def test_short_phone(self):
        with self.assertRaises(ValueError): self.add(phone='12-34')

    def test_invalid_email(self):
        with self.assertRaises(ValueError): self.add(email='test@com')

    def test_optional_email_and_default_category(self):
        self.assertEqual(self.add(email='', category='').category, 'Без категории')

    def test_duplicate_formats(self):
        self.add()
        with self.assertRaises(ValueError): self.add(name='ДЕКАНАТ', phone='8 900 123 45 67')

    def test_same_name_different_number(self):
        self.add()
        self.add(phone='12345')
        self.assertEqual(len(self.m.contacts), 2)

    def test_phone_normalization(self):
        self.assertEqual(normalize_phone('8 (900) 123-45-67'), '79001234567')

    def test_edit_preserves_metadata(self):
        c = self.add()
        u = self.m.edit_contact(c.id, name='Учебный отдел', notes='Этаж 2')
        self.assertEqual((u.id, u.created_at), (c.id, c.created_at))
        self.assertEqual(ContactManager(self.path).contacts[0].notes, 'Этаж 2')

    def test_edit_rejects_metadata(self):
        c = self.add()
        with self.assertRaises(ValueError): self.m.edit_contact(c.id, created_at='changed')

    def test_edit_rejects_duplicate(self):
        self.add()
        c = self.add(name='Другой', phone='12345')
        with self.assertRaises(ValueError): self.m.edit_contact(c.id, name='Деканат', phone='89001234567')

    def test_delete(self):
        c = self.add()
        self.m.delete_contact(c.id)
        self.assertEqual(ContactManager(self.path).contacts, [])

    def test_delete_all_backup(self):
        self.add()
        self.m.delete_all()
        backups = list((self.path / 'backups').glob('contacts-*.json'))
        self.assertTrue(any(len(json.loads(p.read_text(encoding='utf-8'))) == 1 for p in backups))

    def test_missing_contact(self):
        with self.assertRaises(ValueError): self.m.delete_contact('missing')

    def test_exact_search(self):
        c = self.add()
        self.assertEqual(self.m.fuzzy_search('Деканат')[0], (c, 1.0))

    def test_wrong_layout_ru(self):
        c = self.add()
        self.assertEqual(self.m.fuzzy_search('Ltrfyfn')[0], (c, 1.0))

    def test_wrong_layout_en(self):
        c = self.add(name='John Smith')
        self.assertEqual(self.m.fuzzy_search('Ощрт')[0], (c, 1.0))

    def test_layout_examples(self):
        self.assertEqual(fix_keyboard_layout('Ltrfyfn'), 'деканат')
        self.assertEqual(fix_keyboard_layout('Rjynfrn'), 'контакт')

    def test_typo(self):
        c = self.add()
        self.assertEqual(self.m.fuzzy_search('Диканат')[0][0], c)

    def test_phone_fragment(self):
        c = self.add()
        self.assertEqual(self.m.fuzzy_search('1234567')[0][0], c)

    def test_email_search(self):
        c = self.add()
        self.assertEqual(self.m.fuzzy_search('dean@')[0][0], c)

    def test_rank_and_irrelevant_query(self):
        c = self.add()
        self.add(name='Декан', phone='12345')
        self.assertEqual(self.m.fuzzy_search('Деканат')[0][0], c)
        self.assertEqual(self.m.fuzzy_search('щщщщщщщщщщщщщщщщщщщщщ'), [])

    def test_empty_search(self):
        c = self.add()
        self.assertEqual(self.m.fuzzy_search('  '), [(c, 1.0)])

    def test_history_limit_persistence(self):
        for i in range(12): self.m.fuzzy_search(f'query{i}')
        self.m.fuzzy_search('query10')
        self.assertEqual(len(self.m.search_history), 10)
        self.assertEqual(self.m.search_history[0], 'query10')
        self.assertEqual(ContactManager(self.path).search_history, self.m.search_history)

    def test_export_import(self):
        self.add()
        export = self.path / 'export.json'
        self.m.export_contacts(export)
        self.assertEqual(self.m.import_contacts(export), (0, 1))
        other = ContactManager(self.path / 'other')
        self.assertEqual(other.import_contacts(export), (1, 0))

    def test_import_internal_duplicates(self):
        c = self.add()
        export = self.path / 'export.json'
        export.write_text(json.dumps([c.to_dict(), c.to_dict()]), encoding='utf-8')
        other = ContactManager(self.path / 'other')
        self.assertEqual(other.import_contacts(export), (1, 1))

    def test_import_invalid_atomic(self):
        self.add()
        export = self.path / 'bad.json'
        export.write_text(json.dumps([dict(name='Новый', phone='12345'), dict(name='')]), encoding='utf-8')
        before = self.m.path.read_bytes()
        with self.assertRaises(ValueError): self.m.import_contacts(export)
        self.assertEqual(self.m.path.read_bytes(), before)
        self.assertEqual(len(self.m.contacts), 1)

    def test_corrupt_json_quarantine(self):
        self.m.path.write_text('{bad', encoding='utf-8')
        m = ContactManager(self.path)
        self.assertTrue(m.warning)
        backups = list((self.path / 'backups').glob('corrupt-*.json'))
        self.assertEqual(backups[0].read_text(encoding='utf-8'), '{bad')
        self.assertEqual(m.contacts, [])

    def test_invalid_schema_quarantine(self):
        self.m.path.write_text('{"not_contacts": 5}', encoding='utf-8')
        self.assertTrue(ContactManager(self.path).warning)

    def test_save_failure_rolls_back(self):
        c = self.add()
        before = self.m.path.read_bytes()
        with patch('manager.os.replace', side_effect=OSError('disk full')):
            with self.assertRaises(OSError): self.m.edit_contact(c.id, name='Изменен')
        self.assertEqual(self.m.contacts, [c])
        self.assertEqual(self.m.path.read_bytes(), before)
        self.assertFalse(list(self.path.glob('*.tmp')))

    def test_export_protects_database(self):
        self.add()
        with self.assertRaises(ValueError): self.m.export_contacts(self.m.path)

    def test_import_id_collision(self):
        c = self.add()
        data = c.to_dict()
        data['name'] = 'Другой контакт'
        export = self.path / 'import.json'
        export.write_text(json.dumps([data]), encoding='utf-8')
        self.assertEqual(self.m.import_contacts(export), (1, 0))
        self.assertNotEqual(self.m.contacts[0].id, self.m.contacts[1].id)

    def test_statistics(self):
        self.add()
        self.assertEqual(self.m.statistics(), {'Учеба': 1})


if __name__ == '__main__':
    unittest.main(verbosity=2)
