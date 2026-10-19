"""Capture the real Tkinter application in an isolated Linux display for the report."""
from pathlib import Path
import sys
import tempfile
import time

from PIL import ImageGrab
import tkinter as tk

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from manager import ContactManager
from gui import ContactManagerGUI

OUT = ROOT / 'docs' / 'screenshots'
OUT.mkdir(parents=True, exist_ok=True)


def capture(root, name):
    root.update()
    time.sleep(.25)
    x, y = root.winfo_rootx(), root.winfo_rooty()
    ImageGrab.grab(bbox=(x-3, y-27, x+root.winfo_width()+3, y+root.winfo_height()+3)).save(OUT / name)


def dismiss_message(root, name):
    capture(root, name)
    try:
        root.tk.call('destroy', '.__tk__messagebox')
    except tk.TclError:
        pass


with tempfile.TemporaryDirectory(prefix='contact-report-') as tmp:
    m = ContactManager(Path(tmp) / 'demo')
    m.import_contacts(ROOT / 'examples' / 'demo.json')
    root = tk.Tk()
    app = ContactManagerGUI(root, m)
    root.geometry('1060x700+140+75')
    root.update()
    time.sleep(.6)
    capture(root, '01-contact-list.png')

    app.new_contact()
    values = dict(name='Учебный отдел', phone='+7 (900) 000-00-04', email='study@example.com',
                  category='Учеба', notes='Кабинет 205, прием с 10 до 16')
    for key, value in values.items():
        app.fields[key].set(value)
    capture(root, '02-add-form.png')
    app.add_contact()
    capture(root, '03-added-contact.png')

    app.new_contact()
    app.fields['phone'].set('89001234567')
    root.after(550, lambda: dismiss_message(root, '04-empty-name.png'))
    app.add_contact()
    app.fields['name'].set('Тестовый контакт')
    app.fields['email'].set('test@com')
    root.after(550, lambda: dismiss_message(root, '05-invalid-email.png'))
    app.add_contact()

    app.notebook.select(app.search_tab)
    app.query.set('Диканат')
    app.search()
    capture(root, '06-typo-search.png')
    app.query.set('Ltrfyfn')
    app.search()
    capture(root, '07-layout-search.png')

    app.notebook.select(app.list_tab)
    first = next(c for c in m.contacts if c.name == 'Деканат')
    app.tree.selection_set(first.id)
    app.edit_contact()
    root.update()
    capture(root, '08-edit-contact.png')
    for child in root.winfo_children():
        if isinstance(child, tk.Toplevel):
            child.destroy()
    root.destroy()

    damaged = Path(tmp) / 'damaged'
    damaged.mkdir()
    (damaged / 'contacts.json').write_text('{broken JSON', encoding='utf-8')
    root = tk.Tk()
    app = ContactManagerGUI(root, ContactManager(damaged))
    root.geometry('1060x700+140+75')
    root.after(900, lambda: dismiss_message(root, '09-corrupt-json.png'))
    root.after(1500, root.destroy)
    root.mainloop()

assert len(list(OUT.glob('*.png'))) == 9
print('Captured 9 real application screenshots')

