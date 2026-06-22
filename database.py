import os
import sqlite3
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()

# 使用 SQLite（檔案型資料庫，無需服務）
DB_PATH = os.path.join(os.path.dirname(__file__), 'testcase_manager.db')
SQLALCHEMY_DATABASE_URI = f'sqlite:///{DB_PATH}'

engine = create_engine(SQLALCHEMY_DATABASE_URI, echo=False)
Session = sessionmaker(bind=engine)


def get_connection():
    """取得資料庫連線 - 使用原生 SQLite 連線以相容參數格式"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def _ensure_sqlite_columns():
    """補齊舊版 SQLite 資料庫缺少的欄位，避免程式升級後插入失敗。"""
    expected_columns = {
        'test_cases': {
            'preconditions': ('ALTER TABLE test_cases ADD COLUMN preconditions TEXT', None),
            'steps': ('ALTER TABLE test_cases ADD COLUMN steps TEXT', None),
            'expected_result': ('ALTER TABLE test_cases ADD COLUMN expected_result TEXT', None),
            'remark': ('ALTER TABLE test_cases ADD COLUMN remark TEXT', None),
            'priority': ('ALTER TABLE test_cases ADD COLUMN priority VARCHAR(32)', None),
            'created_at': (
                'ALTER TABLE test_cases ADD COLUMN created_at TIMESTAMP',
                "UPDATE test_cases SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL",
            ),
            'updated_at': (
                'ALTER TABLE test_cases ADD COLUMN updated_at TIMESTAMP',
                "UPDATE test_cases SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP) WHERE updated_at IS NULL",
            ),
        },
        'testruns': {
            'description': ('ALTER TABLE testruns ADD COLUMN description TEXT', None),
            'created_at': (
                'ALTER TABLE testruns ADD COLUMN created_at TIMESTAMP',
                "UPDATE testruns SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL",
            ),
        },
        'testrun_test_cases': {
            'status': (
                "ALTER TABLE testrun_test_cases ADD COLUMN status VARCHAR(32) DEFAULT 'Pending'",
                "UPDATE testrun_test_cases SET status = 'Pending' WHERE status IS NULL",
            ),
            'updated_at': (
                'ALTER TABLE testrun_test_cases ADD COLUMN updated_at TIMESTAMP',
                "UPDATE testrun_test_cases SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL",
            ),
        },
    }

    conn = get_connection()
    try:
        for table_name, columns in expected_columns.items():
            existing = {
                row[1]
                for row in conn.execute(f'PRAGMA table_info({table_name})').fetchall()
            }
            for column_name, statements in columns.items():
                alter_sql, backfill_sql = statements
                if column_name not in existing:
                    conn.execute(alter_sql)
                    existing.add(column_name)
                if backfill_sql:
                    conn.execute(backfill_sql)
        conn.commit()
    finally:
        conn.close()


def _rename_legacy_project_tables():
    """將舊的 project 資料表名稱遷移為 TestRun 版，保留既有資料。"""
    conn = get_connection()
    try:
        existing_tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        if 'projects' in existing_tables and 'testruns' not in existing_tables:
            conn.execute('ALTER TABLE projects RENAME TO testruns')
            existing_tables.add('testruns')
        if 'project_test_cases' in existing_tables and 'testrun_test_cases' not in existing_tables:
            conn.execute('ALTER TABLE project_test_cases RENAME TO testrun_test_cases')
        conn.commit()
    finally:
        conn.close()


def initialize_schema():
    """初始化資料庫表結構"""
    create_statements = [
        '''CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(128) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''',
        '''CREATE TABLE IF NOT EXISTS modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            name VARCHAR(128) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
            UNIQUE(product_id, name)
        )''',
        '''CREATE TABLE IF NOT EXISTS test_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_id INTEGER NOT NULL,
            case_title VARCHAR(256) NOT NULL,
            preconditions TEXT,
            steps TEXT,
            expected_result TEXT,
            remark TEXT,
            priority VARCHAR(32),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE CASCADE
        )''',
        '''CREATE TABLE IF NOT EXISTS testruns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(128) NOT NULL UNIQUE,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''',
        '''CREATE TABLE IF NOT EXISTS testrun_test_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            test_case_id INTEGER NOT NULL,
            status VARCHAR(32) DEFAULT 'Pending',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES testruns(id) ON DELETE CASCADE,
            FOREIGN KEY (test_case_id) REFERENCES test_cases(id) ON DELETE CASCADE,
            UNIQUE(project_id, test_case_id)
        )'''
    ]

    try:
        _rename_legacy_project_tables()
        with engine.begin() as conn:
            for sql in create_statements:
                try:
                    conn.execute(text(sql))
                except Exception:
                    continue
        _ensure_sqlite_columns()
    except Exception as error:
        print('Warning: 無法初始化資料庫', error)


def reset_all_data():
    """
    重置所有資料表的數據與 ID 序列。
    用於從 GitHub 下載後重新開始使用。
    """
    conn = get_connection()
    try:
        # 清空所有資料表
        conn.execute('DELETE FROM testrun_test_cases')
        conn.execute('DELETE FROM test_cases')
        conn.execute('DELETE FROM modules')
        conn.execute('DELETE FROM products')
        conn.execute('DELETE FROM testruns')
        
        # 重置 ID 序列
        conn.execute("DELETE FROM sqlite_sequence")
        
        conn.commit()
        return {'status': 'success', 'message': '已重置所有資料與 ID 序列'}
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
