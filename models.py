"""Модель контакта и правила ввода, независимые от интерфейса."""
from dataclasses import asdict, dataclass, field
from datetime import datetime
import re
from uuid import uuid4


def normalize_phone(value: str) -> str:
    digits = ''.join(c for c in value if c in '0123456789')
    if len(digits) == 11 and digits.startswith('8'):
        digits = '7' + digits[1:]
    return digits


class Validator:
    @staticmethod
    def validate(name, phone, email='', category='Без категории', notes=''):
        values = [name, phone, email, category, notes]
        if not all(isinstance(x, str) for x in values):
            raise ValueError('Поля контакта должны быть строками')
        name, phone, email, category, notes = [x.strip() for x in values]
        if not name:
            raise ValueError('Имя обязательно для заполнения')
        if len(normalize_phone(phone)) < 5:
            raise ValueError('Телефон должен содержать не менее 5 цифр')
        if email and not re.fullmatch(r'[^\s@]+@[^\s@.]+(?:\.[^\s@.]+)+', email):
            raise ValueError('Некорректный адрес email')
        return dict(name=name, phone=phone, email=email,
                    category=category or 'Без категории', notes=notes)


@dataclass(frozen=True)
class Contact:
    name: str
    phone: str
    email: str = ''
    category: str = 'Без категории'
    notes: str = ''
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec='seconds'))
    id: str = field(default_factory=lambda: str(uuid4()))

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise ValueError('Контакт должен быть объектом JSON')
        values = Validator.validate(data.get('name', ''), data.get('phone', ''),
                                    data.get('email', ''), data.get('category', 'Без категории'),
                                    data.get('notes', ''))
        meta = {}
        for key in ('id', 'created_at'):
            if key in data:
                if not isinstance(data[key], str) or not data[key].strip():
                    raise ValueError(f'Некорректное поле {key}')
                meta[key] = data[key]
        return cls(**values, **meta)
