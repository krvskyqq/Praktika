"""Хранение, CRUD, импорт и ранжированный поиск контактов."""
from collections import Counter
from dataclasses import replace
from datetime import datetime
from difflib import SequenceMatcher
import json
import os
from pathlib import Path
import shutil
import tempfile
from uuid import uuid4
from models import Contact, Validator, normalize_phone

EN = "`qwertyuiop[]asdfghjkl;'zxcvbnm,./"
RU = 'ёйцукенгшщзхъфывапролджэячсмитьбю.'
EN_TO_RU = str.maketrans(EN, RU)
RU_TO_EN = str.maketrans(RU, EN)


def default_data_dir():
    if os.name == 'nt':
        return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'KurovskyContacts'
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'kurovsky-contacts'


def fix_keyboard_layout(text):
    text = text.casefold()
    latin = sum(c in EN[: -1] for c in text)
    cyrillic = sum(c in RU[: -1] for c in text)
    return text.translate(EN_TO_RU if latin >= cyrillic else RU_TO_EN)


def query_variants(text):
    text = text.casefold().strip()
    return {text, text.translate(EN_TO_RU), text.translate(RU_TO_EN)}


class ContactManager:
    def __init__(self, data_dir=None):
        self.data_dir = Path(data_dir) if data_dir is not None else default_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir / 'contacts.json'
        self.history_path = self.data_dir / 'search_history.json'
        self.contacts = []
        self.search_history = []
        self.warning = ''
        self.load_contacts()
        try:
            history = json.loads(self.history_path.read_text(encoding='utf-8'))
            if isinstance(history, list):
                self.search_history = list(dict.fromkeys(x for x in history if isinstance(x, str) and x.strip()))[:10]
        except (OSError, ValueError):
            pass

    @staticmethod
    def _atomic_write(path, data):
        path = Path(path)
        fd, temp = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)

    @staticmethod
    def _key(contact):
        return contact.name.casefold().strip(), normalize_phone(contact.phone)

    @classmethod
    def _decode(cls, data):
        if isinstance(data, dict):
            data = data.get('contacts')
        if not isinstance(data, list):
            raise ValueError('Ожидается список контактов или объект с полем contacts')
        contacts = [Contact.from_dict(row) for row in data]
        return contacts

    def _backup(self, corrupt=False):
        backup_dir = self.data_dir / 'backups'
        backup_dir.mkdir(exist_ok=True)
        label = 'corrupt' if corrupt else 'contacts'
        path = backup_dir / f'{label}-{datetime.now():%Y%m%d-%H%M%S-%f}-{uuid4().hex[:6]}.json'
        shutil.copy2(self.path, path)
        return path

    def load_contacts(self):
        if not self.path.exists():
            return
        # Ошибки доступа не означают повреждение базы и передаются вызывающему коду.
        try:
            raw = self.path.read_text(encoding='utf-8')
            contacts = self._decode(json.loads(raw))
            keys, ids = set(), set()
            for c in contacts:
                if self._key(c) in keys or c.id in ids:
                    raise ValueError('В базе обнаружены повторяющиеся контакты или идентификаторы')
                keys.add(self._key(c))
                ids.add(c.id)
            self.contacts = contacts
        except (ValueError, TypeError) as error:
            backup = self._backup(corrupt=True)
            self.warning = f'База повреждена: {error}. Сохранена копия:\n{backup}\nОткрыта пустая база.'
            self.contacts = []

    def _commit(self, contacts):
        if self.path.exists():
            self._backup()
        self._atomic_write(self.path, [c.to_dict() for c in contacts])
        self.contacts = contacts

    def add_contact(self, name, phone, email='', category='Без категории', notes=''):
        contact = Contact(**Validator.validate(name, phone, email, category, notes))
        if any(self._key(c) == self._key(contact) for c in self.contacts):
            raise ValueError('Контакт с таким именем и телефоном уже существует')
        self._commit(self.contacts + [contact])
        return contact

    def edit_contact(self, contact_id, **values):
        original = self.get_contact(contact_id)
        editable = {k: getattr(original, k) for k in ('name', 'phone', 'email', 'category', 'notes')}
        if not set(values) <= set(editable):
            raise ValueError('Дата создания и идентификатор не редактируются')
        editable.update(values)
        updated = replace(original, **Validator.validate(**editable))
        if any(c.id != contact_id and self._key(c) == self._key(updated) for c in self.contacts):
            raise ValueError('Контакт с таким именем и телефоном уже существует')
        self._commit([updated if c.id == contact_id else c for c in self.contacts])
        return updated

    def get_contact(self, contact_id):
        for c in self.contacts:
            if c.id == contact_id:
                return c
        raise ValueError('Контакт не найден')

    def delete_contact(self, contact_id):
        self.get_contact(contact_id)
        self._commit([c for c in self.contacts if c.id != contact_id])

    def delete_all(self):
        self._commit([])

    def export_contacts(self, path):
        path = Path(path)
        protected = {self.path.resolve(), self.history_path.resolve()}
        if path.resolve() in protected or path.resolve().is_relative_to((self.data_dir / 'backups').resolve()):
            raise ValueError('Выберите файл вне служебной базы и резервных копий')
        self._atomic_write(path, [c.to_dict() for c in self.contacts])

    def import_contacts(self, path):
        # Сначала проверяется весь файл: ошибка одной записи не приводит к частичному импорту.
        incoming = self._decode(json.loads(Path(path).read_text(encoding='utf-8-sig')))
        contacts = list(self.contacts)
        keys = {self._key(c) for c in contacts}
        ids = {c.id for c in contacts}
        added = skipped = 0
        for c in incoming:
            key = self._key(c)
            if key in keys:
                skipped += 1
                continue
            if c.id in ids:
                c = replace(c, id=str(uuid4()))
            contacts.append(c)
            keys.add(key)
            ids.add(c.id)
            added += 1
        if added:
            self._commit(contacts)
        return added, skipped

    def add_to_search_history(self, query):
        query = query.strip()
        if query:
            history = [query] + [q for q in self.search_history if q != query]
            history = history[:10]
            self._atomic_write(self.history_path, history)
            self.search_history = history

    def fuzzy_search(self, query, remember=True):
        query = query.strip()
        if not query:
            return [(c, 1.0) for c in sorted(self.contacts, key=lambda c: c.name.casefold())]
        if remember:
            self.add_to_search_history(query)
        variants = query_variants(query)
        digits = normalize_phone(query)
        results = []
        for c in self.contacts:
            score = 0.0
            name = c.name.casefold()
            for q in variants:
                if q in name:
                    score = max(score, 1.0)
                score = max(score, SequenceMatcher(None, q, name).ratio())
                for token in name.split():
                    score = max(score, SequenceMatcher(None, q, token).ratio() * .95)
                if c.email and q in c.email.casefold():
                    score = max(score, .9)
            phone = normalize_phone(c.phone)
            if digits and len(digits) >= 3:
                if digits == phone:
                    score = 1.0
                elif digits in phone:
                    score = max(score, .6 + .4 * len(digits) / len(phone))
                else:
                    score = max(score, .9 * SequenceMatcher(None, digits, phone).ratio())
            if score >= .3:
                results.append((c, score))
        return sorted(results, key=lambda item: (-item[1], item[0].name.casefold(), item[0].id))

    def statistics(self):
        return dict(Counter(c.category for c in self.contacts))
