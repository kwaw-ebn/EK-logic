import csv
import io
import json
import math
import zipfile
import pandas as pd
from fastapi import HTTPException
from .config import MAX_COLUMNS, MAX_ROWS


def read_frame(raw: bytes, filename: str, sheet: str | None = None):
    ext = filename.rsplit('.', 1)[-1].lower()
    sheets = []
    try:
        if ext == 'xlsx':
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                entries = archive.infolist()
                if len(entries) > 2000 or sum(x.file_size for x in entries) > 50 * 1024 * 1024:
                    raise ValueError('Expanded workbook too large')
                if any('vbaproject' in x.filename.lower() for x in entries):
                    raise ValueError('Macros are not accepted')
            book = pd.ExcelFile(io.BytesIO(raw), engine='openpyxl')
            sheets = book.sheet_names
            if sheet and sheet not in sheets:
                raise ValueError('Worksheet not found')
            selected = sheet or sheets[0]
            frame = pd.read_excel(book, sheet_name=selected, nrows=MAX_ROWS + 1)
        elif ext == 'csv':
            selected = None
            frame = pd.read_csv(io.BytesIO(raw), nrows=MAX_ROWS + 1, encoding='utf-8-sig')
        else:
            raise ValueError('Only CSV and XLSX files are supported')
        if frame.empty or len(frame) > MAX_ROWS or len(frame.columns) > MAX_COLUMNS:
            raise ValueError(f'Use 1–{MAX_ROWS:,} rows and at most {MAX_COLUMNS} columns')
        frame.columns = [str(c) for c in frame.columns]
        if len(set(frame.columns)) != len(frame.columns):
            raise ValueError('Column names must be unique')
        return frame, sheets, selected
    except HTTPException:
        raise
    except Exception as exc:
        # Do not return parser details or filesystem paths.
        message = str(exc) if isinstance(exc, ValueError) and str(exc).startswith(('Only ', 'Use ', 'Worksheet ', 'Expanded ', 'Macros ', 'Column ')) else 'Unable to parse file; check its format and encoding'
        raise HTTPException(422, message) from exc


def clean_json(value):
    return json.loads(pd.DataFrame(value).to_json(orient='records', date_format='iso'))


def profile_frame(frame, sheets, selected):
    columns = []
    for name in frame.columns:
        col = frame[name]
        kind = 'number' if pd.api.types.is_numeric_dtype(col) else 'text'
        if kind == 'text' and len(col.dropna()) and ('date' in name.lower() or 'month' in name.lower()):
            parsed = pd.to_datetime(col.dropna(), errors='coerce')
            if parsed.notna().mean() > .9:
                kind = 'date'
        role = 'measure' if kind == 'number' else ('date' if kind == 'date' else 'dimension')
        stats = {}
        if kind == 'number':
            values = col.replace([float('inf'), float('-inf')], float('nan')).dropna()
            stats = {k: float(v) for k, v in values.agg(['min', 'max', 'mean', 'median']).items() if pd.notna(v)}
        columns.append({'name': name, 'type': kind, 'suggested_role': role,
                        'missing': int(col.isna().sum()), 'unique': int(col.nunique()), 'stats': stats})
    return {'rows': len(frame), 'columns': columns, 'duplicate_rows': int(frame.duplicated().sum()),
            'missing_cells': int(frame.isna().sum().sum()), 'sheets': sheets, 'selected_sheet': selected,
            'preview': clean_json(frame.head(20)),
            'limitations': ['Types and semantic roles are inferred; confirm them before analysis.',
                           'No data is automatically removed or imputed. Numeric text may need cleaning.']}


def aggregate(frame, dimension, measure, operation):
    if dimension not in frame.columns or (operation != 'count' and measure not in frame.columns):
        raise HTTPException(422, 'Choose existing columns')
    if operation not in {'sum', 'mean', 'count', 'min', 'max'}:
        raise HTTPException(422, 'Unsupported aggregation')
    copy = frame.copy()
    copy[dimension] = copy[dimension].fillna('(Missing)').astype(str)
    if operation == 'count':
        grouped = copy.groupby(dimension, sort=True).size()
    else:
        original = copy[measure]
        values = pd.to_numeric(original, errors='coerce').replace([float('inf'), float('-inf')], float('nan'))
        if values[original.notna()].isna().any():
            raise HTTPException(422, 'Measure contains non-numeric values; clean the source file first')
        copy[measure] = values
        if operation == 'sum':
            grouped = copy.groupby(dimension, sort=True)[measure].sum(min_count=1)
        else:
            grouped = copy.groupby(dimension, sort=True)[measure].agg(operation)
    # Exact export matches this visible aggregate; never silently truncate.
    if len(grouped) > 500:
        raise HTTPException(422, 'More than 500 groups; choose a lower-cardinality dimension')
    points = [{'label': str(label), 'value': float(value) if pd.notna(value) and math.isfinite(value) else None}
              for label, value in grouped.items()]
    return {'dimension': dimension, 'measure': measure, 'operation': operation,
            'points': points, 'source_rows': len(frame), 'groups': len(points),
            'limitations': ['Missing dimension values appear as (Missing).',
                           'Aggregation describes observed data and does not establish causes.']}


def safe_cell(value):
    if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')):
        return "'" + value
    return value


def report_bytes(result, name, source, fmt):
    rows = [[safe_cell(p['label']), p['value']] for p in result['points']]
    headers = [safe_cell(result['dimension']), safe_cell(f"{result['operation']}({result['measure'] or 'rows'})")]
    if fmt == 'csv':
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerows(rows)
        return output.getvalue().encode('utf-8-sig'), 'text/csv'
    if fmt == 'xlsx':
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            pd.DataFrame(rows, columns=headers).to_excel(writer, sheet_name='Analysis', index=False)
            pd.DataFrame({'Field': ['Analysis', 'Source', 'Source rows', 'Limitations'],
                          'Value': [safe_cell(name), safe_cell(source), result['source_rows'], ' '.join(result['limitations'])]}).to_excel(writer, sheet_name='Metadata', index=False)
        return output.getvalue(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    if fmt == 'pdf':
        from html import escape
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, TableStyle
        output = io.BytesIO()
        styles = getSampleStyleSheet()
        table = LongTable([[Paragraph(escape(str(x)), styles['BodyText']) for x in row]
                           for row in [headers] + rows], colWidths=[300, 160], repeatRows=1)
        table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#dbeafe')),
                                   ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('BOTTOMPADDING', (0, 0), (-1, -1), 8)]))
        story = [Paragraph(escape(name), styles['Title']),
                 Paragraph(escape(f'Source: {source} • Rows: {result["source_rows"]}'), styles['BodyText']), Spacer(1, 16), table,
                 Spacer(1, 16), Paragraph(escape(' '.join(result['limitations'])), styles['BodyText'])]
        SimpleDocTemplate(output).build(story)
        return output.getvalue(), 'application/pdf'
    raise HTTPException(422, 'Choose csv, xlsx or pdf')
