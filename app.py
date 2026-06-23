import os

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from datetime import datetime, timezone
from dotenv import load_dotenv
from database import initialize_schema, reset_all_data
from models import Product, Module, TestCase, Project, STATUS_VALUES

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True
api_cache_state = {
    'version': 0,
    'last_cleared_at': None,
}

initialize_schema()

# ==================== Web Routes ====================

def _find_product_tree(product_id):
    for product in TestCase.list_hierarchy():
        if product['id'] == product_id:
            return product
    return None

@app.route('/')
def home():
    return redirect(url_for('testcases'))

@app.route('/testcases')
def testcases():
    query = request.args.get('q', '').strip()
    products = Product.all()
    if query:
        lowered_query = query.lower()
        products = [product for product in products if lowered_query in product['name'].lower()]
    return render_template('product_versions.html', products=products, query=query)


@app.route('/testcases/<int:product_id>')
def product_detail(product_id):
    product = _find_product_tree(product_id)
    if not product:
        flash('找不到指定的 Product/Version', 'error')
        return redirect(url_for('testcases'))
    case_count = sum(len(module['cases']) for module in product['modules'])
    return render_template(
        'product_detail.html',
        product=product,
        modules=product['modules'],
        case_count=case_count,
        priorities=['Low', 'Medium', 'High'],
    )

@app.route('/testcases/new', methods=['GET', 'POST'])
def new_testcase():
    flash('請從 Product/Version 頁面進入 Module & TestCase 頁面新增 TestCase', 'info')
    return redirect(url_for('testcases'))

    if False:
        product_name = request.form.get('product_name', '').strip()
        module_name = request.form.get('module_name', '').strip()
        case_title = request.form.get('case_title', '').strip()
        preconditions = request.form.get('preconditions', '').strip()
        steps = request.form.get('steps', '').strip()
        expected_result = request.form.get('expected_result', '').strip()
        remark = request.form.get('remark', '').strip()
        priority = request.form.get('priority', 'Medium')
        if not (product_name and module_name and case_title):
            flash('Product、Module 與 Case 標題為必填', 'error')
        else:
            try:
                product_id = Product.get_or_create(product_name)
                module_id = Module.get_or_create(product_id, module_name)
                TestCase.create(module_id, case_title, preconditions, steps, expected_result, remark, priority)
                flash('TestCase 已建立', 'success')
                return redirect(url_for('testcases'))
            except Exception as error:
                app.logger.exception('Failed to create testcase')
                flash(f'TestCase 建立失敗：{error}', 'error')
    products = Product.all()
    return render_template('testcase_form.html', products=products, priorities=['Low', 'Medium', 'High'])

@app.route('/testcases/case/<int:case_id>')
def preview_testcase(case_id):
    case = TestCase.get(case_id)
    if not case:
        flash('找不到指定的 TestCase', 'error')
        return redirect(url_for('testcases'))
    return render_template('testcase_preview.html', case=case)

@app.route('/testcases/<int:case_id>/edit', methods=['GET', 'POST'])
def edit_testcase(case_id):
    case = TestCase.get(case_id)
    if not case:
        flash('找不到指定的 TestCase', 'error')
        return redirect(url_for('testcases'))
    if request.method == 'POST':
        module_id = request.form.get('module_id', '').strip()
        case_title = request.form.get('case_title', '').strip()
        preconditions = request.form.get('preconditions', '').strip()
        steps = request.form.get('steps', '').strip()
        expected_result = request.form.get('expected_result', '').strip()
        remark = request.form.get('remark', '').strip()
        priority = request.form.get('priority', 'Medium')
        if not (module_id and case_title):
            flash('Module 與 Case 標題為必填', 'error')
        else:
            try:
                TestCase.update(case_id, int(module_id), case_title, preconditions, steps, expected_result, remark, priority)
                flash('TestCase 已更新', 'success')
                return redirect(url_for('preview_testcase', case_id=case_id))
            except Exception as error:
                app.logger.exception('Failed to update testcase')
                flash(f'TestCase 更新失敗：{error}', 'error')
    product = Product.get(case['product_id'])
    modules = Module.by_product(case['product_id'])
    return render_template('testcase_form.html', case=case, product=product, modules=modules, priorities=['Low', 'Medium', 'High'])

@app.route('/testcases/<int:case_id>/delete', methods=['POST'])
def delete_testcase(case_id):
    TestCase.delete(case_id)
    flash('TestCase 已刪除', 'success')
    return redirect(url_for('testcases'))

@app.route('/testruns')
def testruns():
    all_projects = Project.all()
    grouped_projects = []
    groups_by_month = {}
    uncategorized_projects = []
    for project in all_projects:
        created_at = project.get('created_at') or ''
        month_key = created_at[:7] if len(created_at) >= 7 else ''
        if month_key:
            if month_key not in groups_by_month:
                groups_by_month[month_key] = []
                grouped_projects.append({'label': month_key, 'projects': groups_by_month[month_key]})
            groups_by_month[month_key].append(project)
        else:
            uncategorized_projects.append(project)
    if uncategorized_projects:
        grouped_projects.append({'label': '未分類', 'projects': uncategorized_projects})
    testcase_hierarchy = TestCase.list_hierarchy()
    return render_template(
        'projects.html',
        projects=all_projects,
        grouped_projects=grouped_projects,
        testcase_hierarchy=testcase_hierarchy,
    )

@app.route('/testruns/new', methods=['POST'])
def new_testrun():
    project_name = request.form.get('project_name', '').strip()
    description = request.form.get('description', '').strip()
    test_case_ids = request.form.getlist('test_case_ids')
    if not project_name:
        flash('專案名稱為必填', 'error')
    else:
        Project.create(project_name, description, [int(id_) for id_ in test_case_ids])
        flash('TestRun 已建立', 'success')
    return redirect(url_for('testruns'))

@app.route('/testruns/<int:project_id>')
def testrun_detail(project_id):
    project = Project.get(project_id)
    if not project:
        flash('找不到指定 TestRun', 'error')
        return redirect(url_for('testruns'))
    return render_template('project_detail.html', project=project, statuses=STATUS_VALUES)

@app.route('/testruns/<int:project_id>/report')
def testrun_report(project_id):
    project = Project.get(project_id)
    if not project:
        flash('找不到指定 TestRun', 'error')
        return redirect(url_for('testruns'))
    return render_template('testrun_report.html', project=project)

@app.route('/testruns/<int:project_id>/status/<int:test_case_id>', methods=['POST'])
def update_testrun_status(project_id, test_case_id):
    status = request.form.get('status')
    Project.update_status(project_id, test_case_id, status)
    flash('TestCase 狀態已更新', 'success')
    return redirect(url_for('testrun_detail', project_id=project_id))

# ==================== REST API Endpoints ====================

def clear_api_cache():
    api_cache_state['version'] += 1
    api_cache_state['last_cleared_at'] = datetime.now(timezone.utc).isoformat()
    return {
        'message': 'Cache cleared successfully',
        'data': api_cache_state,
    }
@app.route('/api', methods=['GET'])
def api_index():
    return render_template('api_docs.html', spec_url=url_for('api_spec', v=api_cache_state['version']))


@app.route('/api/index', methods=['GET'])
def api_index_json():
    return jsonify({
        'name': 'TestCase Management API',
        'version': '1.0.0',
        'spec_url': url_for('api_spec', _external=True, v=api_cache_state['version']),
        'endpoints': {
            'products': url_for('api_list_products', _external=True),
            'modules': url_for('api_get_module', module_id=1, _external=True).rsplit('/', 1)[0],
            'testcases': url_for('api_list_testcases', _external=True),
            'testRun': url_for('api_list_testruns', _external=True),
            'cache_clear': url_for('api_clear_cache', _external=True),
            'admin_reset': url_for('api_reset_all_data', _external=True),
        }
    })


@app.route('/api/spec', methods=['GET'])
def api_spec():
    return send_from_directory(app.root_path, 'openspec.yaml', mimetype='application/yaml')


@app.route('/api/cache/clear', methods=['POST'])
def api_clear_cache():
    payload = clear_api_cache()
    return jsonify(payload), 200

# Products API
@app.route('/api/products', methods=['GET'])
def api_list_products():
    try:
        products = Product.all()
        return jsonify(products)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/products', methods=['POST'])
def api_create_product():
    try:
        data = request.get_json()
        if not data or not data.get('name'):
            return jsonify({'error': 'name is required'}), 400
        product_id = Product.create(data['name'])
        product = Product.get(product_id)
        return jsonify(product), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/products/<int:product_id>', methods=['GET'])
def api_get_product(product_id):
    try:
        product = Product.get(product_id)
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        return jsonify(product)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/products/<int:product_id>', methods=['PUT'])
def api_update_product(product_id):
    try:
        data = request.get_json()
        if not data or not data.get('name'):
            return jsonify({'error': 'name is required'}), 400
        Product.update(product_id, data['name'])
        product = Product.get(product_id)
        return jsonify(product)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/products/<int:product_id>', methods=['DELETE'])
def api_delete_product(product_id):
    try:
        Product.delete(product_id)
        return '', 204
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Modules API
@app.route('/api/products/<int:product_id>/modules', methods=['GET'])
def api_list_modules(product_id):
    try:
        modules = Module.by_product(product_id)
        return jsonify(modules)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/products/<int:product_id>/modules', methods=['POST'])
def api_create_module(product_id):
    try:
        data = request.get_json()
        if not data or not data.get('name'):
            return jsonify({'error': 'name is required'}), 400
        module_id = Module.get_or_create(product_id, data['name'])
        module = Module.get(module_id)
        return jsonify(module), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/modules/<int:module_id>', methods=['GET'])
def api_get_module(module_id):
    try:
        module = Module.get(module_id)
        if not module:
            return jsonify({'error': 'Module not found'}), 404
        return jsonify(module)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/modules/<int:module_id>', methods=['PUT'])
def api_update_module(module_id):
    try:
        data = request.get_json()
        if not data or not data.get('name'):
            return jsonify({'error': 'name is required'}), 400
        Module.update(module_id, data['name'])
        module = Module.get(module_id)
        return jsonify(module)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/modules/<int:module_id>', methods=['DELETE'])
def api_delete_module(module_id):
    try:
        if not Module.delete(module_id):
            return jsonify({'error': 'Module not found'}), 404
        return jsonify({'message': 'Module deleted successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# TestCases API
@app.route('/api/testcases', methods=['GET'])
def api_list_testcases():
    try:
        query = request.args.get('q', '').strip()
        cases = TestCase.all(query=query or None)
        return jsonify({
            'message': 'TestCases retrieved successfully',
            'count': len(cases),
            'query': query,
            'data': cases,
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/testcases/hierarchy', methods=['GET'])
def api_list_testcase_hierarchy():
    try:
        return jsonify({
            'message': 'TestCase hierarchy retrieved successfully',
            'data': TestCase.list_hierarchy(),
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/testcases', methods=['POST'])
def api_create_testcase():
    try:
        data = request.get_json()
        if not data or not data.get('module_id') or not data.get('case_title'):
            return jsonify({'error': 'module_id and case_title are required'}), 400
        case_id = TestCase.create(
            data['module_id'],
            data['case_title'],
            data.get('preconditions', ''),
            data.get('steps', ''),
            data.get('expected_result', ''),
            data.get('remark', ''),
            data.get('priority', 'Medium')
        )
        created_case = TestCase.get(case_id)
        return jsonify({
            'message': 'TestCase created successfully',
            'data': created_case,
        }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/testcases/<int:case_id>', methods=['GET'])
def api_get_testcase(case_id):
    try:
        case = TestCase.get(case_id)
        if not case:
            return jsonify({'error': 'TestCase not found'}), 404
        return jsonify({
            'message': 'TestCase retrieved successfully',
            'data': case,
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/testcases/<int:case_id>', methods=['PUT'])
def api_update_testcase(case_id):
    try:
        data = request.get_json()
        if not data or not data.get('module_id') or not data.get('case_title'):
            return jsonify({'error': 'module_id and case_title are required'}), 400
        TestCase.update(
            case_id,
            data['module_id'],
            data['case_title'],
            data.get('preconditions', ''),
            data.get('steps', ''),
            data.get('expected_result', ''),
            data.get('remark', ''),
            data.get('priority', 'Medium')
        )
        case = TestCase.get(case_id)
        return jsonify({
            'message': 'TestCase updated successfully',
            'data': case,
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/testcases/<int:case_id>', methods=['DELETE'])
def api_delete_testcase(case_id):
    try:
        TestCase.delete(case_id)
        return jsonify({'message': 'TestCase deleted successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# TestRun API
@app.route('/api/testruns', methods=['GET'])
def api_list_testruns():
    try:
        projects = Project.all()
        return jsonify(projects)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/testruns', methods=['POST'])
def api_create_testrun():
    try:
        data = request.get_json()
        if not data or not data.get('name'):
            return jsonify({'error': 'name is required'}), 400
        project_id = Project.create(
            data['name'],
            data.get('description', ''),
            data.get('test_case_ids', [])
        )
        return jsonify(Project.get(project_id)), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/testruns/<int:project_id>', methods=['GET'])
def api_get_testrun(project_id):
    try:
        project = Project.get(project_id)
        if not project:
            return jsonify({'error': 'TestRun not found'}), 404
        return jsonify(project)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/testruns/<int:project_id>', methods=['PUT'])
def api_update_testrun(project_id):
    try:
        data = request.get_json()
        if not data or not data.get('name'):
            return jsonify({'error': 'name is required'}), 400
        Project.update(project_id, data['name'], data.get('description', ''))
        project = Project.get(project_id)
        return jsonify(project)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/testruns/<int:project_id>', methods=['DELETE'])
def api_delete_testrun(project_id):
    try:
        Project.delete(project_id)
        return '', 204
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/testruns/<int:project_id>/testcases/<int:test_case_id>/status', methods=['PUT'])
def api_update_testrun_testcase_status(project_id, test_case_id):
    try:
        data = request.get_json()
        if not data or not data.get('status'):
            return jsonify({'error': 'status is required'}), 400
        status = data['status']
        if status not in STATUS_VALUES:
            return jsonify({'error': f'Invalid status. Must be one of: {STATUS_VALUES}'}), 400
        Project.update_status(project_id, test_case_id, status)
        # Return the updated project test case
        project = Project.get(project_id)
        for case in project.get('cases', []):
            if case['case_id'] == test_case_id:
                return jsonify(case)
        return jsonify({'error': 'TestCase not found in project'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Database Reset API
@app.route('/api/admin/reset', methods=['POST'])
def api_reset_all_data():
    """
    重置所有資料與 ID 序列。
    警告：此操作不可逆轉！
    用於開發環境或從 GitHub 下載後重新開始。
    """
    try:
        result = reset_all_data()
        return jsonify({
            'status': 'success',
            'message': result['message'],
            'warning': '所有資料已清空，ID 序列已重置，系統已重新初始化'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'重置失敗：{str(e)}'
        }), 500

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
