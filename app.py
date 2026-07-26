import math
import os
import re
from io import BytesIO

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, send_from_directory, abort
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from database import initialize_schema, reset_all_data
from excel_import import ImportValidationError, build_template, import_file, validate_import
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
TAIPEI_TIMEZONE = timezone(timedelta(hours=8))

initialize_schema()

# ==================== Web Routes ====================

def _find_product_tree(product_id):
    for product in TestCase.list_hierarchy():
        if product['id'] == product_id:
            return product
    return None


def _group_testrun_cases(cases):
    grouped = []
    product_map = {}
    for case in cases:
        product_name = case.get('product_name') or 'N/A'
        module_name = case.get('module_name') or 'N/A'
        product = product_map.get(product_name)
        if not product:
            product = {
                'product_name': product_name,
                'modules': [],
                '_module_map': {},
            }
            product_map[product_name] = product
            grouped.append(product)
        module = product['_module_map'].get(module_name)
        if not module:
            module = {
                'module_name': module_name,
                'cases': [],
            }
            product['_module_map'][module_name] = module
            product['modules'].append(module)
        module['cases'].append(case)
    for product in grouped:
        product.pop('_module_map', None)
    return grouped


def _parse_db_datetime(value):
    if value is None or value == '':
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(value / 1000, timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _testrun_local_datetime(created_at):
    value = _parse_db_datetime(created_at)
    return value.astimezone(TAIPEI_TIMEZONE) if value else None


REPORT_STATUS_CONFIG = [
    {'key': 'pending', 'label': 'Pending', 'class_name': 'status-pending', 'color': '#e2e8f0'},
    {'key': 'in_progress', 'label': 'In Progress', 'class_name': 'status-in-progress', 'color': '#fde68a'},
    {'key': 'passed', 'label': 'Passed', 'class_name': 'status-passed', 'color': '#bbf7d0'},
    {'key': 'failed', 'label': 'Failed', 'class_name': 'status-failed', 'color': '#fecaca'},
    {'key': 'blocked', 'label': 'Blocked', 'class_name': 'status-blocked', 'color': '#fed7aa'},
    {'key': 'skipped', 'label': 'Skipped', 'class_name': 'status-skipped', 'color': '#cbd5e1'},
    {'key': 'retest', 'label': 'Retest', 'class_name': 'status-retest', 'color': '#e9d5ff'},
]


def _build_report_status_summary(project):
    total_count = project.get('total_count') or 0
    cursor = 0.0
    statuses = []
    gradient_parts = []
    for status in REPORT_STATUS_CONFIG:
        count = project.get(f"{status['key']}_count") or 0
        degrees = (count / total_count * 360) if total_count else 0
        start = cursor
        end = cursor + degrees
        if count:
            gradient_parts.append(f"{status['color']} {start:.3f}deg {end:.3f}deg")
        cursor = end
        statuses.append({
            **status,
            'count': count,
            'percent': round((count / total_count * 100), 1) if total_count else 0,
        })
    if not gradient_parts:
        gradient_parts.append('#e5e7eb 0deg 360deg')
    return statuses, f"background: conic-gradient({', '.join(gradient_parts)});"


def _safe_report_filename(project):
    name = re.sub(r'[^A-Za-z0-9._-]+', '-', project.get('name') or '').strip('-')
    suffix = f"-{name}" if name else ''
    return f"testrun-report-{project.get('id')}{suffix}.pdf"


def _report_display_date(project, key):
    return project.get(f'{key}_date') or 'N/A'


def _pdf_text(value):
    if value is None or value == '':
        return 'N/A'
    return str(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _pdf_markup_text(value, cjk_font_name):
    text = _pdf_text(value)
    parts = []
    cjk_buffer = []
    for char in text:
        if ord(char) > 127:
            cjk_buffer.append(char)
            continue
        if cjk_buffer:
            parts.append(f'<font name="{cjk_font_name}">{"".join(cjk_buffer)}</font>')
            cjk_buffer = []
        parts.append(char)
    if cjk_buffer:
        parts.append(f'<font name="{cjk_font_name}">{"".join(cjk_buffer)}</font>')
    return ''.join(parts)


def _register_pdf_cjk_font(pdfmetrics, TTFont, UnicodeCIDFont):
    font_candidates = [
        ('NotoSansTC', r'C:\Windows\Fonts\NotoSansTC-VF.ttf', 'ttf'),
        ('MicrosoftJhengHei', r'C:\Windows\Fonts\msjh.ttc', 'ttf'),
        ('STSong-Light', None, 'cid'),
    ]
    for font_name, font_path, font_type in font_candidates:
        try:
            pdfmetrics.getFont(font_name)
            return font_name
        except KeyError:
            pass
        try:
            if font_type == 'ttf' and font_path and os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont(font_name, font_path))
                return font_name
            if font_type == 'cid':
                pdfmetrics.registerFont(UnicodeCIDFont(font_name))
                return font_name
        except Exception:
            continue
    return 'Helvetica'


def _build_report_donut(report_statuses, total_count, font_name):
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.graphics.shapes import Circle, Drawing, String
    from reportlab.lib import colors

    drawing = Drawing(130, 130)
    slice_border_color = colors.HexColor('#f8fafc')
    pie = Pie()
    pie.x = 8
    pie.y = 8
    pie.width = 114
    pie.height = 114
    pie.sideLabels = 0
    pie.simpleLabels = 0
    pie.labels = ['' for _ in report_statuses]
    active_statuses = [status for status in report_statuses if status['count']]
    pie.data = [status['count'] for status in active_statuses] or [1]
    for index, status in enumerate(active_statuses):
        pie.slices[index].fillColor = colors.HexColor(status['color'])
        pie.slices[index].strokeColor = slice_border_color
        pie.slices[index].strokeWidth = 0.45
    if not active_statuses:
        pie.slices[0].fillColor = colors.HexColor('#e5e7eb')
        pie.slices[0].strokeColor = slice_border_color
        pie.slices[0].strokeWidth = 0.45
    drawing.add(pie)
    drawing.add(Circle(65, 65, 34, fillColor=colors.white, strokeColor=colors.white, strokeWidth=1))
    drawing.add(String(65, 72, 'Total', textAnchor='middle', fontName='Helvetica-Bold', fontSize=8, fillColor=colors.HexColor('#64748b')))
    drawing.add(String(65, 52, str(total_count), textAnchor='middle', fontName='Helvetica-Bold', fontSize=19, fillColor=colors.HexColor('#111827')))
    return drawing


def _build_testrun_report_pdf(project):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    font_name = _register_pdf_cjk_font(pdfmetrics, TTFont, UnicodeCIDFont)

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title='TestRun Report',
    )
    content_width = doc.width
    styles = {
        'title': ParagraphStyle('ReportTitle', fontName='Helvetica-Bold', fontSize=20, leading=24, textColor=colors.HexColor('#111827')),
        'meta': ParagraphStyle('ReportMeta', fontName='Helvetica', fontSize=10.5, leading=13, alignment=TA_RIGHT, textColor=colors.HexColor('#475569')),
        'run_name': ParagraphStyle('RunName', fontName='Helvetica-Bold', fontSize=16, leading=21, spaceAfter=4, textColor=colors.HexColor('#111827')),
        'body': ParagraphStyle('ReportBody', fontName='Helvetica-Bold', fontSize=10.2, leading=14, textColor=colors.HexColor('#64748b')),
        'section': ParagraphStyle('ReportSection', fontName='Helvetica-Bold', fontSize=20, leading=24, leftIndent=-3 * mm, spaceAfter=10, textColor=colors.HexColor('#111827')),
        'product': ParagraphStyle('ReportProduct', fontName='Helvetica-Bold', fontSize=12, leading=15, spaceBefore=7, spaceAfter=5, textColor=colors.HexColor('#111827')),
        'module': ParagraphStyle('ReportModule', fontName='Helvetica-Bold', fontSize=10, leading=13, spaceBefore=4, spaceAfter=4, textColor=colors.HexColor('#64748b')),
        'table': ParagraphStyle('ReportTableText', fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=colors.HexColor('#111827')),
        'table_center': ParagraphStyle('ReportTableCenter', fontName='Helvetica-Bold', fontSize=8.8, leading=11.5, alignment=TA_CENTER, textColor=colors.HexColor('#111827')),
        'badge_center': ParagraphStyle('ReportBadgeCenter', fontName='Helvetica-Bold', fontSize=8.6, leading=11, alignment=TA_CENTER, textColor=colors.HexColor('#111827')),
        'head': ParagraphStyle('ReportTableHead', fontName='Helvetica-Bold', fontSize=9.2, leading=12, textColor=colors.HexColor('#475569')),
        'head_center': ParagraphStyle('ReportTableHeadCenter', fontName='Helvetica-Bold', fontSize=9.2, leading=12, alignment=TA_CENTER, textColor=colors.HexColor('#475569')),
    }
    priority_colors = {
        'low': ('#e0f2fe', '#075985'),
        'medium': ('#fef3c7', '#92400e'),
        'high': ('#fee2e2', '#991b1b'),
        'critical': ('#fecaca', '#7f1d1d'),
    }
    status_colors = {
        'pending': ('#e2e8f0', '#334155'),
        'in progress': ('#dbeafe', '#1d4ed8'),
        'passed': ('#dcfce7', '#166534'),
        'failed': ('#fee2e2', '#991b1b'),
        'blocked': ('#ffedd5', '#9a3412'),
        'skipped': ('#f1f5f9', '#475569'),
        'retest': ('#f3e8ff', '#7e22ce'),
    }

    def badge_text(value, palette):
        label = _pdf_markup_text(value, font_name)
        _background, text_color = palette
        return Paragraph(f'<font color="{text_color}">{label}</font>', styles['badge_center'])

    report_statuses, _chart_style = _build_report_status_summary(project)
    grouped_cases = _group_testrun_cases(project.get('cases', []))
    story = []
    meta = f"Created {_report_display_date(project, 'created')} | Release {_report_display_date(project, 'release')}"
    story.append(Table(
        [[Paragraph('TestRun Report', styles['title']), Paragraph(_pdf_text(meta), styles['meta'])]],
        colWidths=[content_width * 0.48, content_width * 0.52],
        style=TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]),
    ))
    story.append(Spacer(1, 7 * mm))
    story.append(Paragraph(_pdf_markup_text(project.get('name'), font_name), styles['run_name']))
    story.append(Paragraph(_pdf_markup_text(project.get('description') or '無描述', font_name), styles['body']))
    story.append(Spacer(1, 7 * mm))

    donut = _build_report_donut(report_statuses, project.get('total_count') or 0, font_name)
    legend_rows = []
    legend_styles = [
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]
    for index, status in enumerate(report_statuses):
        legend_rows.append(['', Paragraph(_pdf_markup_text(status['label'], font_name), styles['table']), Paragraph(str(status['count']), styles['table_center'])])
        legend_styles.extend([
            ('BACKGROUND', (0, index), (0, index), colors.HexColor(status['color'])),
            ('BOX', (0, index), (0, index), 0, colors.HexColor(status['color'])),
        ])
    legend = Table(legend_rows, colWidths=[5 * mm, 36 * mm, 10 * mm], style=TableStyle(legend_styles))
    status_summary_table = Table(
        [[donut, '', legend]],
        colWidths=[58 * mm, 12 * mm, 55 * mm],
        style=TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]),
    )
    status_summary_table.hAlign = 'CENTER'
    story.append(status_summary_table)
    story.append(Spacer(1, 9 * mm))
    story.append(Paragraph('TestCase Results', styles['section']))

    if not grouped_cases:
        story.append(Paragraph('此 TestRun 尚未指定任何 TestCase', styles['body']))
    for product in grouped_cases:
        story.append(Paragraph(_pdf_markup_text(product.get('product_name'), font_name), styles['product']))
        for module in product.get('modules', []):
            story.append(Paragraph(_pdf_markup_text(module.get('module_name'), font_name), styles['module']))
            rows = [[
                Paragraph('Case', styles['head']),
                Paragraph('Priority', styles['head_center']),
                Paragraph('Status', styles['head_center']),
            ]]
            table_styles = [
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f8fafc')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#475569')),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#edf2f7')),
                ('ALIGN', (1, 0), (2, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]
            for case in module.get('cases', []):
                row_index = len(rows)
                priority = case.get('priority') or 'Medium'
                status = case.get('status') or 'Pending'
                priority_palette = priority_colors.get(str(priority).lower(), priority_colors['medium'])
                status_palette = status_colors.get(str(status).lower(), status_colors['pending'])
                rows.append([
                    Paragraph(_pdf_markup_text(case.get('case_title'), font_name), styles['table']),
                    badge_text(priority, priority_palette),
                    badge_text(status, status_palette),
                ])
                table_styles.extend([
                    ('BACKGROUND', (1, row_index), (1, row_index), colors.HexColor(priority_palette[0])),
                    ('BACKGROUND', (2, row_index), (2, row_index), colors.HexColor(status_palette[0])),
                    ('VALIGN', (1, row_index), (2, row_index), 'MIDDLE'),
                ])
            case_table_width = content_width - 6
            case_table = Table(
                rows,
                colWidths=[case_table_width - 55 * mm, 25 * mm, 30 * mm],
                repeatRows=1,
                style=TableStyle(table_styles),
            )
            case_table.hAlign = 'LEFT'
            story.append(Table(
                [[case_table]],
                colWidths=[content_width],
                style=TableStyle([
                    ('LEFTPADDING', (0, 0), (-1, -1), 6),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                    ('TOPPADDING', (0, 0), (-1, -1), 0),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
                ]),
            ))
            story.append(Spacer(1, 5 * mm))

    doc.build(story)
    buffer.seek(0)
    return buffer


def _db_datetime_to_timestamp_ms(value):
    parsed = _parse_db_datetime(value)
    if not parsed:
        return None
    return int(parsed.astimezone(timezone.utc).timestamp() * 1000)


def _timestamp_ms_to_db_datetime(value, field_name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{field_name} must be a Unix timestamp in milliseconds')
    if not math.isfinite(value) or value < 0:
        raise ValueError(f'{field_name} must be a valid Unix timestamp in milliseconds')
    try:
        parsed = datetime.fromtimestamp(value / 1000, timezone.utc)
    except (OverflowError, OSError, ValueError) as error:
        raise ValueError(f'{field_name} must be a valid Unix timestamp in milliseconds') from error
    return parsed.replace(tzinfo=None).strftime('%Y-%m-%d %H:%M:%S')


def _taipei_today():
    return datetime.now(TAIPEI_TIMEZONE).date()


def _release_date_from_db_datetime(value):
    parsed = _parse_db_datetime(value)
    return parsed.astimezone(TAIPEI_TIMEZONE).date() if parsed else None


def _release_date_to_db_datetime(value):
    if not value:
        return None
    try:
        parsed = datetime.strptime(value, '%Y-%m-%d')
    except (TypeError, ValueError) as error:
        raise ValueError('release_date must be a valid date') from error
    local_release = parsed.replace(tzinfo=TAIPEI_TIMEZONE)
    return local_release.astimezone(timezone.utc).replace(tzinfo=None).strftime('%Y-%m-%d %H:%M:%S')


def _validate_release_not_past(release_at):
    release_date = _release_date_from_db_datetime(release_at)
    if release_date and release_date < _taipei_today():
        raise ValueError('Release 不可小於當下日期')


def _serialize_api_timestamps(value):
    if isinstance(value, list):
        return [_serialize_api_timestamps(item) for item in value]
    if isinstance(value, dict):
        serialized = {}
        for key, item in value.items():
            if key.endswith('_at'):
                serialized[key] = _db_datetime_to_timestamp_ms(item)
            else:
                serialized[key] = _serialize_api_timestamps(item)
        return serialized
    return value


@app.route('/')
def home():
    return redirect(url_for('testcases'))

@app.route('/testcases')
def testcases():
    products = Product.all()
    return render_template('product_versions.html', products=products)


@app.route('/testcases/search')
def testcase_search():
    return render_template('testcase_search.html')


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
        priorities=['Low', 'Medium', 'High', 'Critical'],
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
    return render_template('testcase_form.html', products=products, priorities=['Low', 'Medium', 'High', 'Critical'])

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
    return render_template('testcase_form.html', case=case, product=product, modules=modules, priorities=['Low', 'Medium', 'High', 'Critical'])

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
    current_month = datetime.now(TAIPEI_TIMEZONE).strftime('%Y-%m')
    for project in all_projects:
        created_at = project.get('created_at') or ''
        local_created_at = _testrun_local_datetime(created_at)
        local_release_at = _testrun_local_datetime(project.get('release_at') or '')
        month_key = local_created_at.strftime('%Y-%m') if local_created_at else ''
        project['created_date'] = local_created_at.strftime('%Y-%m-%d') if local_created_at else None
        project['release_date'] = local_release_at.strftime('%Y-%m-%d') if local_release_at else None
        if month_key:
            if month_key not in groups_by_month:
                groups_by_month[month_key] = []
                grouped_projects.append({
                    'label': month_key,
                    'projects': groups_by_month[month_key],
                    'is_current': month_key == current_month,
                })
            groups_by_month[month_key].append(project)
        else:
            uncategorized_projects.append(project)
    if current_month not in groups_by_month:
        grouped_projects.insert(0, {
            'label': current_month,
            'projects': [],
            'is_current': True,
        })
    if uncategorized_projects:
        grouped_projects.append({
            'label': '未分類',
            'projects': uncategorized_projects,
            'is_current': False,
        })
    testcase_hierarchy = TestCase.list_hierarchy()
    return render_template(
        'projects.html',
        projects=all_projects,
        grouped_projects=grouped_projects,
        testcase_hierarchy=testcase_hierarchy,
        current_month=current_month,
    )

@app.route('/testruns/new', methods=['POST'])
def new_testrun():
    project_name = request.form.get('project_name', '').strip()
    description = request.form.get('description', '').strip()
    release_date = request.form.get('release_date', '').strip()
    test_case_ids = request.form.getlist('test_case_ids')
    if not project_name:
        flash('專案名稱為必填', 'error')
    else:
        try:
            release_at = _release_date_to_db_datetime(release_date)
            _validate_release_not_past(release_at)
            Project.create(project_name, description, [int(id_) for id_ in test_case_ids], release_at=release_at)
            flash('TestRun 已建立', 'success')
        except ValueError as error:
            flash(str(error), 'error')
    return redirect(url_for('testruns'))

@app.route('/testruns/<int:project_id>')
def testrun_detail(project_id):
    project = Project.get(project_id)
    if not project:
        flash('找不到指定 TestRun', 'error')
        return redirect(url_for('testruns'))
    local_created_at = _testrun_local_datetime(project.get('created_at') or '')
    local_release_at = _testrun_local_datetime(project.get('release_at') or '')
    project['created_date'] = local_created_at.strftime('%Y-%m-%d') if local_created_at else None
    project['release_date'] = local_release_at.strftime('%Y-%m-%d') if local_release_at else None
    return render_template(
        'project_detail.html',
        project=project,
        statuses=STATUS_VALUES,
        grouped_cases=_group_testrun_cases(project.get('cases', [])),
        testcase_hierarchy=TestCase.list_hierarchy(),
        existing_case_ids=[case.get('case_id') for case in project.get('cases', [])],
    )

@app.route('/testruns/<int:project_id>/report')
def testrun_report(project_id):
    project = Project.get(project_id)
    if not project:
        flash('找不到指定 TestRun', 'error')
        return redirect(url_for('testruns'))
    local_created_at = _testrun_local_datetime(project.get('created_at') or '')
    local_release_at = _testrun_local_datetime(project.get('release_at') or '')
    project['created_date'] = local_created_at.strftime('%Y-%m-%d') if local_created_at else None
    project['release_date'] = local_release_at.strftime('%Y-%m-%d') if local_release_at else None
    report_statuses, report_chart_style = _build_report_status_summary(project)
    report_back_url = (
        url_for('testrun_detail', project_id=project_id)
        if request.args.get('source') == 'detail'
        else url_for('testruns')
    )
    return render_template(
        'testrun_report.html',
        project=project,
        grouped_cases=_group_testrun_cases(project.get('cases', [])),
        report_statuses=report_statuses,
        report_chart_style=report_chart_style,
        report_back_url=report_back_url,
    )


@app.route('/testruns/<int:project_id>/report.pdf')
def testrun_report_pdf(project_id):
    project = Project.get(project_id)
    if not project:
        abort(404)
    local_created_at = _testrun_local_datetime(project.get('created_at') or '')
    local_release_at = _testrun_local_datetime(project.get('release_at') or '')
    project['created_date'] = local_created_at.strftime('%Y-%m-%d') if local_created_at else None
    project['release_date'] = local_release_at.strftime('%Y-%m-%d') if local_release_at else None
    try:
        pdf_buffer = _build_testrun_report_pdf(project)
    except ImportError:
        app.logger.exception('reportlab is required to export TestRun report PDF')
        return 'PDF export requires reportlab. Please install dependencies from requirements.txt.', 500
    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        as_attachment=False,
        download_name=_safe_report_filename(project),
    )

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
    return send_from_directory(app.root_path, 'api-spec.yaml', mimetype='application/yaml')


@app.route('/api/cache/clear', methods=['POST'])
def api_clear_cache():
    payload = clear_api_cache()
    return jsonify(payload), 200

# Products API
@app.route('/api/products', methods=['GET'])
def api_list_products():
    try:
        products = Product.all()
        return jsonify(_serialize_api_timestamps(products))
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
        return jsonify(_serialize_api_timestamps(product)), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/products/<int:product_id>', methods=['GET'])
def api_get_product(product_id):
    try:
        product = Product.get(product_id)
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        return jsonify(_serialize_api_timestamps(product))
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
        return jsonify(_serialize_api_timestamps(product))
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
        return jsonify(_serialize_api_timestamps(modules))
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
        return jsonify(_serialize_api_timestamps(module)), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/modules/<int:module_id>', methods=['GET'])
def api_get_module(module_id):
    try:
        module = Module.get(module_id)
        if not module:
            return jsonify({'error': 'Module not found'}), 404
        return jsonify(_serialize_api_timestamps(module))
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
        return jsonify(_serialize_api_timestamps(module))
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
def _import_upload():
    upload = request.files.get('file')
    if not upload or not upload.filename:
        raise ImportValidationError('請選擇要上傳的 .xlsx 檔案。')
    return upload.read(), upload.filename


@app.route('/api/testcases/import/template', methods=['GET'])
def api_download_testcase_import_template():
    return send_file(
        build_template(),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='testcase-import-template.xlsx',
    )


@app.route('/api/testcases/import/preview', methods=['POST'])
def api_preview_testcase_import():
    try:
        file_bytes, filename = _import_upload()
        preview = validate_import(file_bytes, filename)
        return jsonify({
            'message': 'Excel 預覽完成' if preview['valid'] else 'Excel 資料驗證失敗',
            'data': preview,
        }), 200
    except ImportValidationError as error:
        return jsonify({'error': str(error), 'errors': error.errors}), 400
    except Exception as error:
        app.logger.exception('Failed to preview testcase import')
        return jsonify({'error': str(error)}), 500


@app.route('/api/testcases/import', methods=['POST'])
def api_import_testcases():
    try:
        file_bytes, filename = _import_upload()
        confirmed = request.form.get('confirm_new') == 'true'
        result = import_file(file_bytes, filename, confirm_new=confirmed)
        return jsonify({'message': 'TestCase 匯入成功', 'data': result}), 201
    except ImportValidationError as error:
        status = 409 if '請先確認' in str(error) else 400
        return jsonify({'error': str(error), 'errors': error.errors}), status
    except Exception as error:
        app.logger.exception('Failed to import testcases')
        return jsonify({'error': str(error)}), 500


@app.route('/api/testcases', methods=['GET'])
def api_list_testcases():
    try:
        query = request.args.get('q', '').strip()
        page_value = request.args.get('page')
        per_page_value = request.args.get('per_page')
        if page_value is not None or per_page_value is not None:
            try:
                page = int(page_value or '1')
                per_page = int(per_page_value or '20')
            except ValueError:
                return jsonify({'error': 'page and per_page must be integers'}), 400
            if page < 1:
                return jsonify({'error': 'page must be a positive integer'}), 400
            if per_page not in (20, 50, 100):
                return jsonify({'error': 'per_page must be one of 20, 50, 100'}), 400

            cases, total_items = TestCase.search_page(query, page, per_page)
            total_pages = (total_items + per_page - 1) // per_page
            return jsonify({
                'message': 'TestCases retrieved successfully',
                'count': len(cases),
                'query': query,
                'data': _serialize_api_timestamps(cases),
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total_items': total_items,
                    'total_pages': total_pages,
                },
            }), 200

        cases = TestCase.all(query=query or None)
        return jsonify(_serialize_api_timestamps({
            'message': 'TestCases retrieved successfully',
            'count': len(cases),
            'query': query,
            'data': cases,
        })), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/testcases/hierarchy', methods=['GET'])
def api_list_testcase_hierarchy():
    try:
        return jsonify(_serialize_api_timestamps({
            'message': 'TestCase hierarchy retrieved successfully',
            'data': TestCase.list_hierarchy(),
        })), 200
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
            'data': _serialize_api_timestamps(created_case),
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
            'data': _serialize_api_timestamps(case),
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
            'data': _serialize_api_timestamps(case),
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
        return jsonify(_serialize_api_timestamps(projects))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/testruns', methods=['POST'])
def api_create_testrun():
    try:
        data = request.get_json()
        if not data or not data.get('name'):
            return jsonify({'error': 'name is required'}), 400
        try:
            created_at = (
                _timestamp_ms_to_db_datetime(data['created_at'], 'created_at')
                if data.get('created_at') is not None
                else None
            )
            release_at = (
                _timestamp_ms_to_db_datetime(data['release_at'], 'release_at')
                if data.get('release_at') is not None
                else None
            )
            _validate_release_not_past(release_at)
        except ValueError as error:
            return jsonify({'error': str(error)}), 400
        project_id = Project.create(
            data['name'],
            data.get('description', ''),
            data.get('test_case_ids', []),
            created_at=created_at,
            release_at=release_at,
        )
        return jsonify(_serialize_api_timestamps(Project.get(project_id))), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/testruns/<int:project_id>', methods=['GET'])
def api_get_testrun(project_id):
    try:
        project = Project.get(project_id)
        if not project:
            return jsonify({'error': 'TestRun not found'}), 404
        return jsonify(_serialize_api_timestamps(project))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/testruns/<int:project_id>', methods=['PUT'])
def api_update_testrun(project_id):
    try:
        data = request.get_json()
        if not data or not data.get('name'):
            return jsonify({'error': 'name is required'}), 400
        try:
            if 'release_at' in data:
                release_at = (
                    _timestamp_ms_to_db_datetime(data['release_at'], 'release_at')
                    if data['release_at'] is not None
                    else None
                )
                _validate_release_not_past(release_at)
            else:
                current_project = Project.get(project_id)
                if not current_project:
                    return jsonify({'error': 'TestRun not found'}), 404
                release_at = current_project.get('release_at')
        except ValueError as error:
            return jsonify({'error': str(error)}), 400
        Project.update(project_id, data['name'], data.get('description', ''), release_at=release_at)
        project = Project.get(project_id)
        return jsonify(_serialize_api_timestamps(project))
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
                return jsonify(_serialize_api_timestamps(case))
        return jsonify({'error': 'TestCase not found in project'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/testruns/<int:project_id>/testcases', methods=['POST'])
def api_add_testrun_testcases(project_id):
    try:
        data = request.get_json()
        test_case_ids = data.get('test_case_ids') if data else None
        if not isinstance(test_case_ids, list) or not test_case_ids:
            return jsonify({'error': 'test_case_ids is required'}), 400
        try:
            Project.add_test_cases(project_id, test_case_ids)
        except LookupError:
            return jsonify({'error': 'TestRun not found'}), 404
        except ValueError as error:
            return jsonify({'error': str(error)}), 400
        return jsonify(_serialize_api_timestamps(Project.get(project_id)))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/testruns/<int:project_id>/testcases/<int:test_case_id>', methods=['DELETE'])
def api_delete_testrun_testcase(project_id, test_case_id):
    try:
        try:
            Project.remove_test_case(project_id, test_case_id)
        except LookupError:
            return jsonify({'error': 'TestRun not found'}), 404
        except ValueError as error:
            return jsonify({'error': str(error)}), 404
        return jsonify(_serialize_api_timestamps(Project.get(project_id)))
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
