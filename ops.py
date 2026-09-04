import sqlite3
from db import connect_to_db
from format_validation import validate_date
from arts import GREEN, RED, RESET, YELLOW
from datetime import date, datetime, timedelta

# 批量新建&批量更新共用的字段表. status 只在更新时接收, 新建时固定 alive.
_FIELD_PROMPTS = {
    'gender':    'gender(m/f/not checked)',
    'dob':       'dob(YYYY-MM-DD)',
    'location':  'location',
    'genotype':  'genotype',
    'strain':    'strain',
    'father_id': 'father id',
    'mother_id': 'mother id',
    'status':    "status(alive/sacrificed/died due to accident/sent out/missing)",
    'notes':     'notes',
}
# 空值有语义的枚举字段: 空 -> 'not checked', 而非 NULL
_ENUM_FIELDS = ('gender',)
# 合法性别值
_VALID_GENDERS = ('m', 'f', 'not checked')
# 合法状态值; 批量更新 status 时在校验用
_VALID_STATUS = ('alive', 'sacrificed', 'died due to accident', 'sent out',
                 'missing')
# event_type 命名与单条 update_* 完全一致 (father/mother 带空格)
_EVENT_KEY = {
    'gender': 'gender', 'dob': 'dob', 'location': 'location',
    'genotype': 'genotype', 'strain': 'strain',
    'father_id': 'father id', 'mother_id': 'mother id',
    'status': 'status', 'notes': 'notes',
}
# 这些字段事件值的缺口: notes/multi_checks 在单条里不写事件, 批量也保持一致
_NO_EVENT = ('notes', 'multi_checks')
# 录入过程中的快捷命令 (类似 git 的暂存/放弃):
#   !c = cancel 取消整个操作, 不写入任何内容
#   !r = redo   重新输入当前字段
_CMD_CANCEL = '!c'
_CMD_REDO = '!r'

class UserAbort(Exception):
    """用户主动取消当前操作 (相当于 git 放弃提交, 不写入任何内容)."""

def add_mouse(preset_id=None):
    return batch_apply(action='create', single=True, preset_id=preset_id)

# --- update functions group ---
def update_multi_checks(mouse_id=None):
    if mouse_id is None:
        mouse_id = input('mouse ID: ')
    
    conn, cursor = connect_to_db()
    cursor.execute('SELECT multi_checks FROM mice WHERE mouse_id = ?', (mouse_id, ))
    row = cursor.fetchone()
    if not row:
        print(f'{RED}Mouse not found.{RESET}')
        conn.close()
        return
    current = row['multi_checks'] or ''
    print(f'Current multi-checks: {current}')

    new_value = input('New multi-checks (press Enter to keep, type "-" to '
                      'clear, "!c" to cancel): ').strip()

    if new_value == _CMD_CANCEL:
        conn.close()
        print(f'{YELLOW}Cancelled, nothing changed.{RESET}')
        return
    if new_value == '':
        conn.close()
        print(f'{YELLOW}No change made.{RESET}')
        return
    elif new_value == '-':
        new_value = None
        print(f'{YELLOW}Clearing multi-checks...{RESET}')
    else:
        pass
    
    cursor.execute('UPDATE mice SET multi_checks = ? WHERE mouse_id = ?', (new_value, mouse_id))
    conn.commit()
    conn.close()
    print(f'{GREEN}Multi-checks updated!{RESET}')

def clear_notes(mouse_id=None):
    """清空 notes(intended to be independent entry, 不影响列向量语义)."""
    if mouse_id is None:
        mouse_id = input('mouse ID: ')
    conn, cursor = connect_to_db()
    cursor.execute('UPDATE mice SET notes = NULL WHERE mouse_id = ?', (mouse_id,))
    if cursor.rowcount == 0:
        print(f'{RED}Mouse not found.{RESET}')
        conn.close()
        return
    conn.commit()
    conn.close()
    print(f'{YELLOW}Notes cleared.{RESET}')

def update_notes(mouse_id=None):
    if mouse_id is None:
        mouse_id = input('mouse ID: ')
    
    conn, cursor = connect_to_db()
    cursor.execute('SELECT notes FROM mice WHERE mouse_id = ?', (mouse_id, ))
    row = cursor.fetchone()
    if not row:
        print(f'{RED}Mouse not found.{RESET}')
        conn.close()
        return
    current = row['notes'] or ''
    conn.close()
    print(f'Current notes: {current}')

    new_value = input('New notes (press Enter to keep, type "c" to clear, '
                      '"!c" to cancel): ').strip()

    if new_value == _CMD_CANCEL:
        print(f'{YELLOW}Cancelled, nothing changed.{RESET}')
        return
    if new_value == '':
        print(f'{YELLOW}No change made.{RESET}')
        return
    elif new_value == 'c':
        clear_notes(mouse_id)
        return
    else:
        conn, cursor = connect_to_db()
        cursor.execute('UPDATE mice SET notes = ? WHERE mouse_id = ?', (new_value, mouse_id))
        conn.commit()
        conn.close()
        print(f'{GREEN}Notes updated!{RESET}')

# --- calculating functions group ---
def calculate_age(dob_str):
    if not dob_str:
        return 'N/A'
    try:
        dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
    except ValueError:
        # 库中可能存在历史脏数据, 展示时不应崩溃
        return 'N/A'
    delta = date.today() - dob
    return f'P{delta.days}'

def calculate_milestones_ahead(dob_str):
    if not dob_str:
        return ''
    try:
        dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
    except ValueError:
        return ''
    today = date.today()
    milestones_ahead = []
    for day in [7, 21, 42]:
        milestone_date = dob + timedelta(days=day)
        if today <= milestone_date:
            milestones_ahead.append(f'P{day}: {milestone_date.strftime("%m/%d")}')
    return '; '.join(milestones_ahead) if milestones_ahead else ''

# manage_mouse 菜单选项 -> 要更新的字段
_MANAGE_FIELD_OPTIONS = {
    '1': 'gender', '2': 'dob', '3': 'location', '4': 'genotype',
    '5': 'strain', '6': 'father_id', '7': 'mother_id', '8': 'status',
}

def manage_mouse(mouse_id):
    while True:
        conn, cursor = connect_to_db()
        cursor.execute('SELECT dob FROM mice WHERE mouse_id = ?', (mouse_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            print(f'{RED}Mouse {mouse_id} not found.{RESET}')
            return

        age_str = calculate_age(row['dob'])
        milestones_ahead = calculate_milestones_ahead(row['dob'])
        print(f'\n--- Managing mouse: {RED}{mouse_id}{RESET} | age: {age_str} | milestones ahead: {milestones_ahead} ---')

        print('1. update gender')
        print('2. update dob')
        print('3. update location')
        print('4. update genotype')
        print('5. update strain')
        print('6. update father id')
        print('7. update mother id')
        print('8. update status')
        print('9. update multi-checks')
        print('10. edit/clear notes')
        print('11. back to main menu')

        choice = input('Choose: ').strip()
        if choice in _MANAGE_FIELD_OPTIONS:       # 只更新所选字段
            batch_apply(action='update', single=True, target_id=mouse_id,
                        fields=[_MANAGE_FIELD_OPTIONS[choice]])
        elif choice == '9':
            update_multi_checks(mouse_id)          # 保留特殊语义
        elif choice == '10':
            update_notes(mouse_id)
        elif choice == '11':
            break
        else:
            print(f'{RED}Invalid choice{RESET}')

# ================= batch group =================
def _split_col(raw):
    """逗号分隔字符串 -> 列表; 空输入返回空列表."""
    return [x.strip() for x in raw.split(',')] if raw and raw.strip() else []

def _prompt_single_field(field, prompt):
    """单条模式读一个字段: 空输入=跳过该字段; 校验失败/!r 重新输入, !c 取消."""
    while True:
        raw = input(f'{prompt} (empty to skip; !c cancel, !r redo): ').strip()
        if raw == _CMD_CANCEL:
            raise UserAbort()
        if raw == _CMD_REDO:
            continue
        try:
            return _validate_col(field, [raw] if raw else [])
        except ValueError as e:
            print(f'{RED}{e}, please re-enter (!c cancel, !r redo).{RESET}')

def _read_batch_field(field, prompt):
    """批量模式读一个字段的逗号列表: 校验失败/!r 重新输入, !c 取消整个操作."""
    while True:
        raw = input(f'{prompt} '
                    '(comma list, empty=skip; short -> pad last; '
                    '!c cancel, !r redo): ').strip()
        if raw == _CMD_CANCEL:
            raise UserAbort()
        if raw == _CMD_REDO:
            continue
        try:
            return _validate_col(field, _split_col(raw))
        except ValueError as e:
            print(f'{RED}{e}, please re-enter (!c cancel, !r redo).{RESET}')

def _validate_col(field, vals):               
    for v in vals:
        if field == 'dob' and v and not validate_date(v, 'Date of birth'):
            raise ValueError(f"Bad dob '{v}'")
        if field == 'status' and v and v not in _VALID_STATUS:
            raise ValueError(f"Bad status '{v}'")
        if field == 'gender' and v and v not in _VALID_GENDERS:
            raise ValueError(
                f"Bad gender '{v}'. Allowed: m, f, not checked")
    return vals

def _collect_create_rows(single=False, preset_id=None):
    if preset_id:
        ids = [preset_id]
    elif single:
        raw = input('mouse ID (required; !c cancel): ').strip()
        if raw == _CMD_CANCEL:
            raise UserAbort()
        ids = [raw]
    else:
        raw = input('ids (comma separated, REQUIRED; !c cancel): ').strip()
        if raw == _CMD_CANCEL:
            raise UserAbort()
        ids = _split_col(raw)

    if not ids or not ids[0]:
        raise ValueError('No ids provided.')
    n = len(ids)
    rows = [{'mouse_id': ids[i], 'status': 'alive'} for i in range(n)]
    for field, prompt in _FIELD_PROMPTS.items():
        if field == 'status':        # 新建不接收status，固定 alive
            continue
        if single:
            values = _prompt_single_field(field, prompt)
        else:
            values = _read_batch_field(field, prompt)
        if not values:
            continue
        for i in range(n):
            val = values[i] if i < len(values) else values[-1]
            if not val:
                continue
            rows[i][field] = val
    for r in rows:
        r.setdefault('gender', 'not checked')
    return rows


def _preflight_create(rows, conn, cursor):
    """新建前检查: 数据库冲突 + 本批内重复. 任一问题整批中止."""
    ids = [r['mouse_id'] for r in rows]
    placeholders = ','.join('?' for _ in ids)
    cursor.execute(
        f'SELECT mouse_id FROM mice WHERE mouse_id IN ({placeholders})', ids)
    exists = [r['mouse_id'] for r in cursor.fetchall()]
    if exists:
        raise ValueError(f'ID conflict, nothing added: {", ".join(exists)}')
    dup = {x for x in ids if ids.count(x) > 1}
    if dup:
        raise ValueError(f'Duplicate ids in batch: {", ".join(dup)}')


def _insert_rows(rows, conn, cursor):
    """单事务批量写 mice + birth 事件, 与 add_mouse 记录格式一致."""
    for r in rows:
        cursor.execute('''
        INSERT INTO mice (mouse_id, gender, dob, location, genotype,
                          strain, father_id, mother_id, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (r.get('mouse_id'), r.get('gender'), r.get('dob'),
              r.get('location'), r.get('genotype'), r.get('strain'),
              r.get('father_id'), r.get('mother_id'), r.get('status'),
              r.get('notes')))
        cursor.execute('''
        INSERT INTO events (mouse_id, event_type, event_value, event_date)
        VALUES (?, ?, ?, ?)
        ''', (r['mouse_id'], 'birth', 'born', r.get('dob')))


def _collect_update_rows(single=False, target_id=None, fields=None):
    if target_id:
        ids = [target_id]
    elif single:
        raw = input('mouse ID (required; !c cancel): ').strip()
        if raw == _CMD_CANCEL:
            raise UserAbort()
        ids = [raw]
    else:
        raw = input('target ids (comma separated, REQUIRED; !c cancel): ').strip()
        if raw == _CMD_CANCEL:
            raise UserAbort()
        ids = _split_col(raw)
    if not ids or not ids[0]:
        raise ValueError('No ids provided.')

    # fields=None -> 全部字段; 否则只提示指定字段 (如 manage_mouse 单选)
    field_items = _FIELD_PROMPTS.items() if fields is None else [
        (f, _FIELD_PROMPTS[f]) for f in fields if f in _FIELD_PROMPTS]

    active = set()
    field_values = {}
    for field, prompt in field_items:
        values = (_prompt_single_field(field, f'new {prompt}')
                  if single else
                  _read_batch_field(field, f'new {prompt}'))
        if not values or all(v == '' for v in values):
            continue
        field_values[field] = values
        active.add(field)

    if not active:
        raise ValueError('No fields to update.')
    return ids, field_values, active

def _read_event_date():
    """批量更新共用同一个事件日期, 手动输入一次."""
    while True:
        d = input('event date for all (YYYY-MM-DD, !c cancel): ').strip()
        if d == _CMD_CANCEL:
            raise UserAbort()
        if validate_date(d, 'Event date'):
            return d


def _to_update_plans(ids, field_values, active, single=False):
    n = len(ids)
    plans = []
    for i in range(n):
        sets = {}
        for field in active:
            vals = field_values[field]
            if single:
                val = vals[0] if vals else ''
            elif i >= len(vals):
                # 向后填充: 值比 id 少时, 余下小鼠沿用最后一个值 (与新建一致)
                val = vals[-1]
            else:
                val = vals[i]
            if field in _ENUM_FIELDS:
                sets[field] = val if val else 'not checked'
            elif val:
                sets[field] = val
        if sets:
            plans.append((ids[i], sets))
    return plans

# --- git 式提交前审查: 先展示将写入的内容, 确认后才真正写入 ---
def _confirm_apply():
    """commit 前确认: y 提交 / n 放弃 / r 全部重填."""
    while True:
        c = input('Apply? (y)es / (n)o / (r)estart entry: ').strip().lower()
        if c in ('y', 'yes'):
            return 'apply'
        if c in ('n', 'no'):
            return 'cancel'
        if c in ('r', 'restart'):
            return 'restart'
        print(f'{YELLOW}Please enter y / n / r.{RESET}')

def _review_create(rows):
    """展示新建暂存内容, 类似 git status 的 + 新增行."""
    print(f'\n{YELLOW}--- Review: {len(rows)} mouse(es) to add ---{RESET}')
    for r in rows:
        fields = ', '.join(f'{k}={v}' for k, v in r.items()
                           if k != 'mouse_id' and v)
        print(f'+ {r["mouse_id"]}: {fields}')
    return _confirm_apply()

def _review_update(plans, conn, cursor):
    """展示更新暂存内容, 类似 git diff 的 old -> new."""
    print(f'\n{YELLOW}--- Review: {len(plans)} mouse(es) to update ---{RESET}')
    for mid, sets in plans:
        cols = ', '.join(sets.keys())
        cursor.execute(f'SELECT {cols} FROM mice WHERE mouse_id = ?', (mid,))
        row = cursor.fetchone()
        if not row:
            print(f'~ {mid}: NOT FOUND (will be skipped)')
            continue
        changes = ', '.join(f'{f}: {row[f]} -> {v}' for f, v in sets.items())
        print(f'~ {mid}: {changes}')
    return _confirm_apply()

def _update_batch(plans, conn, cursor):
    """
    批量 UPDATE: 单事务, 每只鼠每个被改字段写一条事件.
    返回 (updated, not_found). 对不存在的 id 跳过不报错.
    """
    # 只有实际会发生且涉及写事件的更新才需要输入事件日期
    if plans and any(f not in _NO_EVENT for _, sets in plans for f in sets):
        event_date = _read_event_date()
    else:
        event_date = None

    updated = 0
    not_found = []
    for mid, sets in plans:
        # notes/multi_checks 单条不写事件, 这里也跳过事件(与 update_notes 一致)
        cols = ', '.join(f'{c} = ?' for c in sets)
        vals = list(sets.values())
        cursor.execute(
            f'UPDATE mice SET {cols} WHERE mouse_id = ?', vals + [mid])
        if cursor.rowcount == 0:
            not_found.append(mid)
            continue
        updated += 1
        for field, newval in sets.items():
            if field in _NO_EVENT or event_date is None:
                continue
            cursor.execute('''
            INSERT INTO events (mouse_id, event_type, event_value, event_date)
            VALUES (?, ?, ?, ?)
            ''', (mid, _EVENT_KEY[field], str(newval), event_date))
    return updated, not_found


def batch_apply(action='create', single=False, preset_id=None, target_id=None,
                fields=None):
    """
    git 式流程: 收集(暂存) -> 审查(review/diff) -> 确认 -> 单事务写入(commit).
    录入中 !c 取消整个操作; 审查时 n 放弃 / r 全部重填.
    """
    conn, cursor = connect_to_db()
    ok = False
    try:
        if action == 'create':
            while True:
                rows = _collect_create_rows(single=single, preset_id=preset_id)
                _preflight_create(rows, conn, cursor)
                choice = _review_create(rows)
                if choice == 'apply':
                    break
                if choice == 'restart':
                    continue
                print(f'{YELLOW}Cancelled, nothing added.{RESET}')
                return False
            _insert_rows(rows, conn, cursor)
            conn.commit()
            print(f'{GREEN}Batch added {len(rows)} mice successfully!{RESET}')
            for r in rows:
                print(f'- {r["mouse_id"]} '
                      f'{r.get("gender", "not checked")} dob={r.get("dob", "-")}')
            ok = True

        elif action == 'update':
            while True:
                ids, field_values, active = _collect_update_rows(
                    single=single, target_id=target_id, fields=fields)
                plans = _to_update_plans(
                    ids, field_values, active, single=single)
                if not plans:
                    print(f'{YELLOW}Nothing to update.{RESET}')
                    return False
                choice = _review_update(plans, conn, cursor)
                if choice == 'apply':
                    break
                if choice == 'restart':
                    continue
                print(f'{YELLOW}Cancelled, nothing updated.{RESET}')
                return False
            updated, not_found = _update_batch(plans, conn, cursor)
            conn.commit()
            if not_found:
                print(f'{RED}Not found (skipped): {", ".join(not_found)}{RESET}')
            print(f'{GREEN}Updated {updated} mice in {len(ids)} targets.{RESET}')
            ok = True

        else:
            raise ValueError(f'Unknown action: {action}')

    except UserAbort:
        conn.rollback()
        print(f'{YELLOW}Cancelled, nothing changed.{RESET}')
    except ValueError as e:
        conn.rollback()
        print(f'{RED}{e}{RESET}')
    except Exception as e:
        conn.rollback()
        print(f'{RED}Error: {e}{RESET}')
    finally:
        conn.close()
    return ok
