from db import initialize_db, connect_to_db
from ops import (
    add_mouse,
    manage_mouse,
    batch_apply,
)
from arts import draw_mouse, YELLOW, RESET

VERSION = '26.1.0'


def update_menu():
    """第二层: 更新 -> 新建 / 更新现有."""
    while True:
        print('\n-- Update --')
        print('(1) Add new mice')
        print('(2) Update existing mice')
        print('(b) Back')
        cmd = input('> ').strip().lower()
        if cmd in ('b', 'q'):
            return
        if cmd == '1':
            action = picking_mode('add')
            if action == 'single':
                add_mouse()
            else:
                batch_apply(action='create')
        elif cmd == '2':
            action = picking_mode('update')
            if action == 'single':
                mouse_id = input('mouse id to update: ').strip()
                manage_mouse(mouse_id)
            else:
                # 批量更新覆盖所有字段(含 status). 处死=sacrificed, 寄出=sent out.
                batch_apply(action='update')
        else:
            print(f'{YELLOW}Unknown option.{RESET}')


def picking_mode(what):
    """第三层: 单一 / 批量."""
    while True:
        print(f'-- {what} mode --')
        print('(s) Single')
        print('(b) Batch')
        cmd = input('> ').strip().lower()
        if cmd in ('s', 'single'):
            return 'single'
        if cmd in ('b', 'batch'):
            return 'batch'


def main_menu():
    """第一层: 更新 / 退出. 查询请用 DB Browser for SQLite 打开 micecolony.db."""
    while True:
        print(f'\n=== Mouse Colony Manager v{VERSION} ===')
        print('(1) Update')
        print('(q) Quit')
        cmd = input('> ').strip()
        low = cmd.lower()
        if low == 'q':
            draw_mouse()
            print('Have a great day!')
            break
        elif low in ('1', 'u', 'update'):
            update_menu()
        else:
            # 兼容: 直接输入 mouse id 仍进入 manage_mouse (保留原始大小写)
            mouse_id = cmd
            conn, cursor = connect_to_db()
            cursor.execute('SELECT 1 FROM mice WHERE mouse_id = ?', (mouse_id,))
            exists = cursor.fetchone() is not None
            conn.close()
            if exists:
                manage_mouse(mouse_id)
            else:
                print(f"{YELLOW}Mouse '{mouse_id}' not found.{RESET}")
                create = input('Do you want to add it? (y/n): ').strip().lower()
                if create == 'y':
                    if add_mouse(preset_id=mouse_id):
                        manage_mouse(mouse_id)


if __name__ == '__main__':
    draw_mouse()
    initialize_db()
    main_menu()