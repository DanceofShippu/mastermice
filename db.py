import os
import sqlite3

# 数据库固定放在脚本所在目录, 避免从其他 cwd 运行时悄悄新建一个空库
_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'micecolony.db')

def connect_to_db():
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    return conn, cursor
# 'db' is short for 'datebase'.

def initialize_db():
    conn, cursor = connect_to_db()
    
    # create mice table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS mice (
        mouse_id TEXT PRIMARY KEY,
        gender TEXT,
        dob TEXT,
        location TEXT,
        genotype TEXT,
        strain TEXT,
        father_id TEXT,
        mother_id TEXT,
        status TEXT,
        multi_checks TEXT,
        notes TEXT
    )
    ''')

    # create events table
    # cursor.execute() cannot create two tables at the same time.
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS events (
        mouse_id TEXT,
        event_type TEXT,
        event_value TEXT,
        event_date TEXT
    )
    ''')

    conn.commit()
    conn.close()
    print('Database has been initialized! ')