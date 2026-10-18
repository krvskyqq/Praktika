"""Графический интерфейс менеджера контактов."""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from manager import ContactManager


class ContactManagerGUI:
    def __init__(self, root, manager):
        self.root, self.manager = root, manager
        root.title('Менеджер контактов — Е.Е. Куровский')
        root.geometry('1060x700')
        root.minsize(850, 580)
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('Treeview', rowheight=30, font=('Segoe UI', 10))
        style.configure('Treeview.Heading', font=('Segoe UI', 10, 'bold'))
        style.configure('TButton', padding=(10, 7))
        style.configure('TLabel', font=('Segoe UI', 10))
        header = ttk.Frame(root, padding=(18, 14))
        header.pack(fill='x')
        ttk.Label(header, text='Менеджер контактов', font=('Segoe UI', 21, 'bold')).pack(anchor='w')
        ttk.Label(header, text='Учебные и личные контакты · Поиск с учетом опечаток и раскладки').pack(anchor='w', pady=(4, 0))
        bar = ttk.Frame(root, padding=(18, 0, 18, 10))
        bar.pack(fill='x')
        for title, command in [('Добавить', self.new_contact), ('Редактировать', self.edit_contact),
                               ('Удалить', self.delete_contact), ('Импорт JSON', self.import_contacts),
                               ('Экспорт JSON', self.export_contacts), ('Статистика', self.statistics)]:
            ttk.Button(bar, text=title, command=command).pack(side='left', padx=(0, 5))
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True, padx=18)
        self.list_tab = ttk.Frame(self.notebook, padding=12)
        self.search_tab = ttk.Frame(self.notebook, padding=12)
        self.add_tab = ttk.Frame(self.notebook, padding=18)
        for frame, title in [(self.list_tab, 'Все контакты'), (self.search_tab, 'Поиск'), (self.add_tab, 'Новый контакт')]:
            self.notebook.add(frame, text=title)
        filter_bar = ttk.Frame(self.list_tab)
        filter_bar.pack(fill='x', pady=(0, 10))
        ttk.Label(filter_bar, text='Категория:').pack(side='left')
        self.category_filter = tk.StringVar(value='Все категории')
        self.filter_combo = ttk.Combobox(filter_bar, textvariable=self.category_filter, state='readonly', width=26)
        self.filter_combo.pack(side='left', padx=8)
        self.filter_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh())
        self.tree = self.make_tree(self.list_tab)
        query_bar = ttk.Frame(self.search_tab)
        query_bar.pack(fill='x', pady=(0, 10))
        self.query = tk.StringVar()
        self.search_entry = ttk.Combobox(query_bar, textvariable=self.query, width=48)
        self.search_entry.pack(side='left', fill='x', expand=True)
        self.search_entry.bind('<Return>', lambda e: self.search())
        self.search_entry.bind('<<ComboboxSelected>>', lambda e: self.search())
        ttk.Button(query_bar, text='Найти', command=self.search).pack(side='left', padx=8)
        ttk.Button(query_bar, text='Сбросить', command=self.clear_search).pack(side='left')
        ttk.Label(self.search_tab, text='Например: «Деканат», «Ltrfyfn», часть телефона или email. Оценка — сходство строк.').pack(anchor='w', pady=(0, 10))
        self.result_tree = self.make_tree(self.search_tab, scored=True)
        self.fields = self.make_fields(self.add_tab)
        ttk.Button(self.add_tab, text='Сохранить контакт', command=self.add_contact).pack(anchor='w', pady=12)
        ttk.Label(self.add_tab, text='* Обязательные поля. Дубликат определяется по имени и нормализованному телефону.').pack(anchor='w')
        self.status = tk.StringVar()
        ttk.Label(root, textvariable=self.status, padding=(18, 10)).pack(fill='x')
        menu = tk.Menu(root)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label='Импорт JSON', command=self.import_contacts)
        file_menu.add_command(label='Экспорт JSON', command=self.export_contacts)
        file_menu.add_separator()
        file_menu.add_command(label='Удалить все контакты', command=self.delete_all)
        file_menu.add_command(label='Выход', command=root.destroy)
        menu.add_cascade(label='Файл', menu=file_menu)
        menu.add_command(label='О программе', command=self.about)
        root.config(menu=menu)
        root.bind('<Control-n>', lambda e: self.new_contact())
        root.bind('<Control-f>', lambda e: self.focus_search())
        root.bind('<Control-e>', lambda e: self.edit_contact())
        # Delete действует только в таблицах, не при редактировании текста.
        for tree in (self.tree, self.result_tree):
            tree.bind('<Delete>', lambda e: self.delete_contact())
            tree.bind('<Double-1>', lambda e: self.edit_contact())
            tree.bind('<Return>', lambda e: self.edit_contact())
            tree.bind('<Button-3>', self.context_menu)
        root.bind('<Escape>', lambda e: self.clear_search())
        self.refresh()
        if manager.warning:
            root.after(200, lambda: messagebox.showwarning('Восстановление базы', manager.warning, parent=root))

    def make_tree(self, parent, scored=False):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True)
        columns = ['name', 'phone', 'email', 'category'] + (['score'] if scored else [])
        tree = ttk.Treeview(frame, columns=columns, show='headings', selectmode='browse')
        labels = {'name': 'Имя', 'phone': 'Телефон', 'email': 'Email', 'category': 'Категория', 'score': 'Сходство'}
        for col in columns:
            tree.heading(col, text=labels[col], command=lambda c=col: self.sort_tree(tree, c))
            tree.column(col, width=210 if col in ('name', 'email') else 150, minwidth=70)
        if scored:
            tree.column('score', width=90)
        tree.tag_configure('strong', foreground='#146b43')
        tree.tag_configure('partial', foreground='#805700')
        scroll = ttk.Scrollbar(frame, command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        tree.pack(fill='both', expand=True)
        return tree

    @staticmethod
    def sort_tree(tree, column):
        reverse = getattr(tree, '_sort', None) == (column, False)
        def key(iid):
            value = tree.set(iid, column)
            return float(value.rstrip('%')) if column == 'score' else value.casefold()
        for index, iid in enumerate(sorted(tree.get_children(), key=key, reverse=reverse)):
            tree.move(iid, '', index)
        tree._sort = column, reverse

    def make_fields(self, parent, contact=None):
        fields = {}
        for key, label in [('name', 'Имя *'), ('phone', 'Телефон *'), ('email', 'Email'),
                           ('category', 'Категория'), ('notes', 'Заметка')]:
            row = ttk.Frame(parent)
            row.pack(fill='x', pady=5)
            ttk.Label(row, text=label, width=15).pack(side='left')
            var = tk.StringVar(value=getattr(contact, key) if contact else ('Учеба' if key == 'category' else ''))
            if key == 'category':
                widget = ttk.Combobox(row, textvariable=var, values=['Учеба', 'Преподаватели', 'Работа', 'Личное', 'Без категории'])
            else:
                widget = ttk.Entry(row, textvariable=var)
            widget.pack(side='left', fill='x', expand=True)
            fields[key] = var
        return fields

    def guard(self, operation):
        try:
            return operation()
        except (ValueError, OSError, TypeError) as error:
            messagebox.showerror('Не удалось выполнить операцию', str(error), parent=self.root)
            return None

    def refresh(self):
        categories = ['Все категории'] + sorted(self.manager.statistics())
        self.filter_combo['values'] = categories
        if self.category_filter.get() not in categories:
            self.category_filter.set('Все категории')
        self.tree.delete(*self.tree.get_children())
        for c in sorted(self.manager.contacts, key=lambda c: c.name.casefold()):
            if self.category_filter.get() in ('Все категории', c.category):
                self.tree.insert('', 'end', iid=c.id, values=(c.name, c.phone, c.email, c.category))
        self.search(remember=False)
        self.status.set(f'Контактов: {len(self.manager.contacts)}   ·   Данные: {self.manager.path}')

    def new_contact(self):
        self.notebook.select(self.add_tab)

    def focus_search(self):
        self.notebook.select(self.search_tab)
        self.search_entry.focus_set()

    def add_contact(self):
        def run():
            c = self.manager.add_contact(**{k: v.get() for k, v in self.fields.items()})
            for key, var in self.fields.items():
                var.set('Учеба' if key == 'category' else '')
            self.refresh()
            self.notebook.select(self.list_tab)
            self.tree.selection_set(c.id)
            self.tree.see(c.id)
        self.guard(run)

    def selected_id(self):
        tree = self.result_tree if self.notebook.select() == str(self.search_tab) else self.tree
        selection = tree.selection()
        if not selection:
            messagebox.showinfo('Выбор контакта', 'Выберите контакт в таблице', parent=self.root)
            return None
        return selection[0]

    def edit_contact(self):
        contact_id = self.selected_id()
        if not contact_id:
            return
        c = self.manager.get_contact(contact_id)
        dialog = tk.Toplevel(self.root)
        dialog.title('Редактирование контакта')
        dialog.geometry('570x390')
        dialog.transient(self.root)
        dialog.grab_set()
        body = ttk.Frame(dialog, padding=18)
        body.pack(fill='both', expand=True)
        fields = self.make_fields(body, c)
        ttk.Label(body, text=f'Создан: {c.created_at}').pack(anchor='w', pady=8)
        def save():
            def run():
                self.manager.edit_contact(contact_id, **{k: v.get() for k, v in fields.items()})
                dialog.destroy()
                self.refresh()
            self.guard(run)
        ttk.Button(body, text='Сохранить изменения', command=save).pack(anchor='w')
        dialog.bind('<Escape>', lambda e: dialog.destroy())

    def delete_contact(self):
        contact_id = self.selected_id()
        if contact_id and messagebox.askyesno('Удаление', 'Удалить выбранный контакт?', parent=self.root):
            self.guard(lambda: self.manager.delete_contact(contact_id))
            self.refresh()

    def delete_all(self):
        if messagebox.askyesno('Удаление всех контактов', 'Удалить ВСЕ контакты? Предыдущая база останется в резервной копии.', parent=self.root):
            self.guard(self.manager.delete_all)
            self.refresh()

    def search(self, remember=True):
        def run():
            results = self.manager.fuzzy_search(self.query.get(), remember=remember)
            self.result_tree.delete(*self.result_tree.get_children())
            for c, score in results:
                self.result_tree.insert('', 'end', iid=c.id, values=(c.name, c.phone, c.email, c.category, f'{score:.0%}'),
                                        tags=('strong' if score >= .8 else 'partial',))
            self.search_entry['values'] = self.manager.search_history
        self.guard(run)

    def clear_search(self):
        self.query.set('')
        self.search(remember=False)

    def import_contacts(self):
        path = filedialog.askopenfilename(parent=self.root, filetypes=[('Контакты JSON', '*.json')])
        if path:
            result = self.guard(lambda: self.manager.import_contacts(path))
            if result is not None:
                self.refresh()
                messagebox.showinfo('Импорт завершен', f'Добавлено: {result[0]}. Пропущено дубликатов: {result[1]}.', parent=self.root)

    def export_contacts(self):
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension='.json', initialfile='contacts-export.json',
                                          filetypes=[('Контакты JSON', '*.json')], confirmoverwrite=True)
        if path:
            def run():
                self.manager.export_contacts(path)
                messagebox.showinfo('Экспорт завершен', 'Контакты сохранены в выбранный файл', parent=self.root)
            self.guard(run)

    def statistics(self):
        messagebox.showinfo('Статистика', f'Всего контактов: {len(self.manager.contacts)}\n\n' +
                            '\n'.join(f'{k}: {v}' for k, v in sorted(self.manager.statistics().items())), parent=self.root)

    def about(self):
        messagebox.showinfo('О программе', 'Менеджер контактов с нечетким поиском\nВерсия 1.0.0\nКуровский Евгений Евгеньевич\nPython · Tkinter · JSON\n\nCtrl+N — новый контакт\nCtrl+F — поиск\nCtrl+E — редактирование\nDelete — удаление в таблице\nEscape — сброс поиска', parent=self.root)

    def context_menu(self, event):
        tree = event.widget
        iid = tree.identify_row(event.y)
        if iid:
            tree.selection_set(iid)
            menu = tk.Menu(self.root, tearoff=False)
            menu.add_command(label='Редактировать', command=self.edit_contact)
            menu.add_command(label='Удалить', command=self.delete_contact)
            menu.tk_popup(event.x_root, event.y_root)


def run(data_dir=None):
    root = tk.Tk()
    try:
        manager = ContactManager(data_dir)
    except (ValueError, OSError) as error:
        root.withdraw()
        messagebox.showerror('Ошибка открытия базы', str(error), parent=root)
        root.destroy()
        return 1
    ContactManagerGUI(root, manager)
    root.mainloop()
    return 0
