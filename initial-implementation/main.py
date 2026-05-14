import os
import boto3
from botocore.config import Config
from dotenv import load_dotenv
from nicegui import ui, app
from controllers import SubmissionController, EvaluationManager, Reviewer
from database import get_db_connection

load_dotenv()

# Serve locally uploaded files (create folder if it doesn't exist yet)
os.makedirs('uploads', exist_ok=True)
app.add_static_files('/uploads', 'uploads')

def get_file_url(file_path):
    """Return a usable download URL for both local and R2 files."""
    if file_path.startswith('uploads/') or file_path.startswith('uploads\\'):
        return '/' + file_path.replace('\\', '/')
    # R2 object key — generate a 1-hour pre-signed URL
    try:
        s3 = boto3.client(
            's3',
            endpoint_url=os.getenv('R2_ENDPOINT_URL'),
            aws_access_key_id=os.getenv('R2_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('R2_SECRET_ACCESS_KEY'),
            region_name='auto',
            config=Config(signature_version='s3v4')
        )
        return s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': os.getenv('R2_BUCKET_NAME'), 'Key': file_path},
            ExpiresIn=3600
        )
    except Exception:
        return file_path

# App Layout
ui.query('body').style('background-color: #f8f9fa;')

def get_reviewer_options():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, name FROM reviewers')
    reviewers = {str(row['id']): row['name'] for row in cursor.fetchall()}
    conn.close()
    return reviewers

def researcher_tab():
    with ui.card().classes('w-full max-w-2xl mx-auto p-8 shadow-lg mt-10'):
        ui.label('Submit Research for Peer Review').classes('text-2xl font-bold mb-4 text-primary')
        
        title = ui.input('Research Title').classes('w-full mb-4')
        author = ui.input('Author Name').classes('w-full mb-4')
        email = ui.input('Contact Email').classes('w-full mb-4')
        
        file_data = {'bytes': None, 'name': None}
        
        async def handle_upload(e):
            file_data['bytes'] = await e.file.read()
            file_data['name'] = e.file.name
            ui.notify(f'File {e.file.name} uploaded successfully')

        ui.upload(on_upload=handle_upload, label='Upload Research Document (PDF/DOCX)').classes('w-full mb-6')
        
        async def submit():
            data = {
                'title': title.value,
                'author': author.value,
                'email': email.value,
                'file_bytes': file_data['bytes'],
                'file_name': file_data['name']
            }
            success, msg = SubmissionController().submit(data)
            if success:
                ui.notify(msg, type='positive')
                title.value = author.value = email.value = ''
            else:
                ui.notify(msg, type='negative')

        ui.button('Submit for Review', on_click=submit).classes('w-full py-2 text-lg')

def reviewer_tab():
    with ui.column().classes('w-full max-w-4xl mx-auto p-8'):
        ui.label('Reviewer Dashboard').classes('text-2xl font-bold mb-4 text-primary')
        
        reviewers = get_reviewer_options()
        current_reviewer_id = ui.select(reviewers, label='Select Your Name').classes('w-64 mb-8')
        
        assignments_container = ui.column().classes('w-full')

        def load_assignments():
            assignments_container.clear()
            if not current_reviewer_id.value:
                return
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT s.id, s.title, s.author, s.file_path, r.score 
                FROM submissions s
                JOIN reviews r ON s.id = r.submission_id
                WHERE r.reviewer_id = ?
            ''', (current_reviewer_id.value,))
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                with assignments_container:
                    ui.label('No assignments found.').classes('italic text-gray-500')
                return

            for row in rows:
                with assignments_container:
                    with ui.card().classes('w-full mb-4 p-4'):
                        with ui.row().classes('w-full justify-between items-center'):
                            with ui.column():
                                ui.label(row['title']).classes('text-lg font-semibold')
                                ui.label(f"Author: {row['author']}").classes('text-sm text-gray-600')
                            
                            with ui.row().classes('items-center gap-4'):
                                ui.link('Download File', get_file_url(row['file_path'])).classes('text-blue-500 underline')
                                
                                if row['score'] is not None:
                                    ui.label(f"Score: {row['score']}/10").classes('font-bold text-green-600')
                                else:
                                    score_input = ui.number(label='Score (1-10)', min=1, max=10).classes('w-24')
                                    def submit_score(sid=row['id'], sinput=score_input):
                                        if sinput.value is None:
                                            ui.notify('Please enter a score')
                                            return

                                        reviewer = Reviewer(int(current_reviewer_id.value))
                                        reviewer.submit_score(
                                            sid, int(sinput.value), EvaluationManager()
                                        )

                                        ui.notify('Score submitted!')
                                        load_assignments()

                                    ui.button('Submit', on_click=submit_score).classes('bg-green-500 text-white')

        current_reviewer_id.on_value_change(load_assignments)

def admin_tab():
    with ui.column().classes('w-full p-8'):
        ui.label('System Administration & Overview').classes('text-2xl font-bold mb-4 text-primary')
        
        def refresh_table():
            table_container.clear()
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT id, title, author, email, status FROM submissions')
            rows = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            columns = [
                {'name': 'id', 'label': 'ID', 'field': 'id', 'required': True, 'align': 'left'},
                {'name': 'title', 'label': 'Title', 'field': 'title', 'align': 'left'},
                {'name': 'author', 'label': 'Author', 'field': 'author', 'align': 'left'},
                {'name': 'email', 'label': 'Email', 'field': 'email', 'align': 'left'},
                {'name': 'status', 'label': 'Status', 'field': 'status', 'align': 'center'},
            ]
            with table_container:
                ui.table(columns=columns, rows=rows, row_key='id').classes('w-full')

        ui.button('Refresh Overview', on_click=refresh_table).classes('mb-4')
        table_container = ui.column().classes('w-full')
        refresh_table()

# Main Tabs
with ui.tabs().classes('w-full bg-white shadow-md') as tabs:
    t1 = ui.tab('RESEARCHER')
    t2 = ui.tab('REVIEWER')
    t3 = ui.tab('ADMIN')

with ui.tab_panels(tabs, value=t1).classes('w-full bg-transparent'):
    with ui.tab_panel(t1):
        researcher_tab()
    with ui.tab_panel(t2):
        reviewer_tab()
    with ui.tab_panel(t3):
        admin_tab()

import os as _os
ui.run(title='Peer Review System', port=int(_os.getenv('PORT', 8080)), host='0.0.0.0')