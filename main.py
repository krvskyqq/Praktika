"""Точка входа GUI и автономной проверки готовой сборки."""
import argparse
from pathlib import Path
import tempfile
from manager import ContactManager, fix_keyboard_layout


def self_test():
    with tempfile.TemporaryDirectory() as tmp:
        manager = ContactManager(tmp)
        c = manager.add_contact('Деканат', '+7 (900) 123-45-67', 'dean@example.com', 'Учеба')
        assert fix_keyboard_layout('Ltrfyfn') == 'деканат'
        assert manager.fuzzy_search('Ltrfyfn')[0][0].id == c.id
        assert manager.fuzzy_search('Деканат')[0][1] == 1.0
        assert manager.fuzzy_search('1234567')[0][0].id == c.id
        assert ContactManager(tmp).contacts[0] == c
        import tkinter as tk
        from gui import ContactManagerGUI
        root = tk.Tk()
        root.withdraw()
        gui = ContactManagerGUI(root, manager)
        root.update()
        assert len(gui.tree.get_children()) == 1
        gui.query.set('Ltrfyfn')
        gui.search()
        assert len(gui.result_tree.get_children()) == 1
        root.destroy()


def main():
    parser = argparse.ArgumentParser(description='Менеджер контактов с нечетким поиском')
    parser.add_argument('--data-dir', type=Path, help='Отдельная папка базы данных')
    parser.add_argument('--self-test', action='store_true', help='Проверить хранение, поиск и запуск GUI во временной папке')
    parser.add_argument('--test-result', type=Path, help='Записать результат самопроверки в файл')
    args = parser.parse_args()
    if args.self_test:
        try:
            self_test()
        except Exception as error:
            if args.test_result:
                args.test_result.write_text(f'FAIL: {error}', encoding='utf-8')
            raise
        if args.test_result:
            args.test_result.write_text('PASS', encoding='utf-8')
        return 0
    from gui import run
    return run(args.data_dir)


if __name__ == '__main__':
    raise SystemExit(main())
