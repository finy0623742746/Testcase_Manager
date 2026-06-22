from database import get_connection, engine
import sqlite3

STATUS_VALUES = ['Pending', 'In Progress', 'Passed', 'Failed']

class Product:
    @staticmethod
    def create(name):
        """建立新 Product，允許重複名稱"""
        conn = get_connection()
        try:
            conn.execute('INSERT INTO products (name) VALUES (?)', (name,))
            cur = conn.execute('SELECT last_insert_rowid()')
            product_id = cur.fetchone()[0]
            return product_id
        finally:
            conn.commit()
            conn.close()

    @staticmethod
    def get_or_create(name):
        """向後相容 - 直接建立新 Product"""
        return Product.create(name)

    @staticmethod
    def all():
        conn = get_connection()
        try:
            cur = conn.execute('SELECT id, name, created_at FROM products ORDER BY name')
            return [dict(id=row[0], name=row[1], created_at=row[2]) for row in cur.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def get(product_id):
        conn = get_connection()
        try:
            cur = conn.execute('SELECT id, name, created_at FROM products WHERE id = ?', (product_id,))
            row = cur.fetchone()
            if not row:
                return None
            return dict(id=row[0], name=row[1], created_at=row[2])
        finally:
            conn.close()

    @staticmethod
    def update(product_id, name):
        conn = get_connection()
        try:
            conn.execute('UPDATE products SET name = ? WHERE id = ?', (name, product_id))
        finally:
            conn.commit()
            conn.close()

    @staticmethod
    def delete(product_id):
        conn = get_connection()
        try:
            conn.execute('DELETE FROM products WHERE id = ?', (product_id,))
        finally:
            conn.commit()
            conn.close()

class Module:
    @staticmethod
    def get_or_create(product_id, name):
        conn = get_connection()
        try:
            cur = conn.execute('SELECT id FROM modules WHERE product_id = ? AND name = ?', (product_id, name))
            row = cur.fetchone()
            if row:
                return row[0]
            conn.execute('INSERT INTO modules (product_id, name) VALUES (?, ?)', (product_id, name))
            cur = conn.execute('SELECT id FROM modules WHERE product_id = ? AND name = ?', (product_id, name))
            return cur.fetchone()[0]
        finally:
            conn.commit()
            conn.close()

    @staticmethod
    def by_product(product_id):
        conn = get_connection()
        try:
            cur = conn.execute('SELECT id, name, created_at FROM modules WHERE product_id = ? ORDER BY name', (product_id,))
            return [dict(id=row[0], name=row[1], created_at=row[2], product_id=product_id) for row in cur.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def get(module_id):
        conn = get_connection()
        try:
            cur = conn.execute('SELECT id, product_id, name, created_at FROM modules WHERE id = ?', (module_id,))
            row = cur.fetchone()
            if not row:
                return None
            return dict(id=row[0], product_id=row[1], name=row[2], created_at=row[3])
        finally:
            conn.close()

    @staticmethod
    def update(module_id, name):
        conn = get_connection()
        try:
            conn.execute('UPDATE modules SET name = ? WHERE id = ?', (name, module_id))
        finally:
            conn.commit()
            conn.close()

    @staticmethod
    def delete(module_id):
        conn = get_connection()
        try:
            cur = conn.execute('DELETE FROM modules WHERE id = ?', (module_id,))
            return cur.rowcount > 0
        finally:
            conn.commit()
            conn.close()

class TestCase:
    @staticmethod
    def create(module_id, case_title, preconditions, steps, expected_result, remark, priority):
        conn = get_connection()
        try:
            cur = conn.execute(
                '''INSERT INTO test_cases (
                    module_id, case_title, preconditions, steps, expected_result, remark, priority, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)''',
                (module_id, case_title, preconditions, steps, expected_result, remark, priority),
            )
            return cur.lastrowid
        finally:
            conn.commit()
            conn.close()

    @staticmethod
    def update(case_id, module_id, case_title, preconditions, steps, expected_result, remark, priority):
        conn = get_connection()
        try:
            conn.execute(
                '''UPDATE test_cases
                   SET module_id = ?, case_title = ?, preconditions = ?, steps = ?, expected_result = ?,
                       remark = ?, priority = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?''',
                (module_id, case_title, preconditions, steps, expected_result, remark, priority, case_id),
            )
        finally:
            conn.commit()
            conn.close()

    @staticmethod
    def delete(case_id):
        conn = get_connection()
        try:
            conn.execute('DELETE FROM test_cases WHERE id = ?', (case_id,))
        finally:
            conn.commit()
            conn.close()

    @staticmethod
    def get(case_id):
        conn = get_connection()
        try:
            cur = conn.execute('''SELECT t.id, t.case_title, t.preconditions, t.steps, t.expected_result, t.remark,
                          t.priority, t.created_at, t.updated_at, m.id, m.name, p.id, p.name
                          FROM test_cases t
                          JOIN modules m ON t.module_id = m.id
                          JOIN products p ON m.product_id = p.id
                          WHERE t.id = ?''', (case_id,))
            row = cur.fetchone()
            if not row:
                return None
            return dict(
                id=row[0], case_title=row[1], preconditions=row[2], steps=row[3], expected_result=row[4],
                remark=row[5], priority=row[6], created_at=row[7], updated_at=row[8], module_id=row[9],
                module_name=row[10], product_id=row[11], product_name=row[12]
            )
        finally:
            conn.close()

    @staticmethod
    def list_hierarchy():
        conn = get_connection()
        try:
            cur = conn.execute('SELECT id, name FROM products ORDER BY name')
            products = [{'id': row[0], 'name': row[1], 'modules': []} for row in cur.fetchall()]
            for product in products:
                cur = conn.execute('SELECT id, name FROM modules WHERE product_id = ? ORDER BY name', (product['id'],))
                modules = [{'id': row[0], 'name': row[1], 'cases': []} for row in cur.fetchall()]
                for module in modules:
                    cur = conn.execute(
                        'SELECT id, case_title, priority, created_at, updated_at FROM test_cases WHERE module_id = ? ORDER BY case_title',
                        (module['id'],),
                    )
                    module['cases'] = [
                        {
                            'id': r[0],
                            'case_title': r[1],
                            'priority': r[2],
                            'created_at': r[3],
                            'updated_at': r[4],
                        }
                        for r in cur.fetchall()
                    ]
                product['modules'] = modules
            return products
        finally:
            conn.close()

    @staticmethod
    def all(query=None):
        """取得所有 TestCase"""
        conn = get_connection()
        try:
            sql = '''SELECT t.id, t.case_title, t.preconditions, t.steps, t.expected_result, t.remark,
                          t.priority, t.created_at, t.updated_at,
                          m.id, m.name, p.id, p.name
                          FROM test_cases t
                          JOIN modules m ON t.module_id = m.id
                          JOIN products p ON m.product_id = p.id
            '''
            params = []
            if query:
                sql += ' WHERE t.case_title LIKE ?'
                params.append(f'%{query}%')
            sql += ' ORDER BY p.name, m.name, t.case_title'
            cur = conn.execute(sql, params)
            return [dict(
                id=row[0], case_title=row[1], preconditions=row[2], steps=row[3], 
                expected_result=row[4], remark=row[5], priority=row[6], created_at=row[7], updated_at=row[8],
                module_id=row[9], module_name=row[10], product_id=row[11], product_name=row[12]
            ) for row in cur.fetchall()]
        finally:
            conn.close()

class Project:
    @staticmethod
    def create(name, description, test_case_ids):
        conn = get_connection()
        try:
            conn.execute('INSERT INTO testruns (name, description) VALUES (?, ?)', (name, description))
            cur = conn.execute('SELECT id FROM testruns WHERE name = ?', (name,))
            project_id = cur.fetchone()[0]
            for tc_id in test_case_ids:
                conn.execute('INSERT INTO testrun_test_cases (project_id, test_case_id) VALUES (?, ?)', (project_id, tc_id))
        finally:
            conn.commit()
            conn.close()

    @staticmethod
    def all():
        conn = get_connection()
        try:
            cur = conn.execute('SELECT id, name, description, created_at FROM testruns ORDER BY created_at DESC')
            return [{'id': row[0], 'name': row[1], 'description': row[2], 'created_at': row[3]} for row in cur.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def get(project_id):
        conn = get_connection()
        try:
            cur = conn.execute('SELECT id, name, description FROM testruns WHERE id = ?', (project_id,))
            project = cur.fetchone()
            if not project:
                return None
            cur = conn.execute('''SELECT ptc.id, t.id, t.case_title, p.name, m.name, ptc.status
                           FROM testrun_test_cases ptc
                           JOIN test_cases t ON ptc.test_case_id = t.id
                           JOIN modules m ON t.module_id = m.id
                           JOIN products p ON m.product_id = p.id
                           WHERE ptc.project_id = ?
                           ORDER BY t.case_title''', (project_id,))
            cases = [{'relation_id': r[0], 'case_id': r[1], 'case_title': r[2], 'product_name': r[3], 'module_name': r[4], 'status': r[5]} for r in cur.fetchall()]
            return {'id': project[0], 'name': project[1], 'description': project[2], 'cases': cases}
        finally:
            conn.close()

    @staticmethod
    def update_status(project_id, test_case_id, status):
        if status not in STATUS_VALUES:
            status = 'Pending'
        conn = get_connection()
        try:
            conn.execute('UPDATE testrun_test_cases SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE project_id = ? AND test_case_id = ?', (status, project_id, test_case_id))
        finally:
            conn.commit()
            conn.close()

    @staticmethod
    def update(project_id, name, description):
        conn = get_connection()
        try:
            conn.execute('UPDATE testruns SET name = ?, description = ? WHERE id = ?', (name, description, project_id))
        finally:
            conn.commit()
            conn.close()

    @staticmethod
    def delete(project_id):
        conn = get_connection()
        try:
            conn.execute('DELETE FROM testruns WHERE id = ?', (project_id,))
        finally:
            conn.commit()
            conn.close()

    @staticmethod
    def all_test_cases():
        conn = get_connection()
        try:
            cur = conn.execute('SELECT id, case_title FROM test_cases ORDER BY case_title')
            return [{'id': row[0], 'case_title': row[1]} for row in cur.fetchall()]
        finally:
            conn.close()
