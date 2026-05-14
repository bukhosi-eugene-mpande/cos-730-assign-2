import sqlite3
import os
import boto3
from botocore.config import Config
from dotenv import load_dotenv

load_dotenv()

DB_NAME = 'app.db'

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        author TEXT NOT NULL,
        email TEXT NOT NULL,
        file_path TEXT NOT NULL,
        status TEXT DEFAULT 'Pending'
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS reviewers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        submission_id INTEGER NOT NULL,
        reviewer_id INTEGER NOT NULL,
        score INTEGER,
        FOREIGN KEY (submission_id) REFERENCES submissions (id),
        FOREIGN KEY (reviewer_id) REFERENCES reviewers (id)
    )
    ''')
    
    # Seed reviewers if empty
    cursor.execute('SELECT COUNT(*) FROM reviewers')
    if cursor.fetchone()[0] == 0:
        reviewers = [('Alice',), ('Bob',), ('Charlie',), ('David',)]
        cursor.executemany('INSERT INTO reviewers (name) VALUES (?)', reviewers)
    
    conn.commit()
    conn.close()

class Database:
    def save_submission(self, title, author, email, file_path):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO submissions (title, author, email, file_path) VALUES (?, ?, ?, ?)',
            (title, author, email, file_path)
        )
        submission_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return submission_id

    def fetch_reviewers(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM reviewers')
        reviewers = [row['id'] for row in cursor.fetchall()]
        conn.close()
        return reviewers

    def save_review_assignment(self, submission_id, reviewer_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO reviews (submission_id, reviewer_id) VALUES (?, ?)',
            (submission_id, reviewer_id)
        )
        conn.commit()
        conn.close()

    def save_score(self, submission_id, reviewer_id, score):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE reviews SET score = ? WHERE submission_id = ? AND reviewer_id = ?',
            (score, submission_id, reviewer_id)
        )
        conn.commit()
        conn.close()

    def get_scores(self, submission_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT score FROM reviews WHERE submission_id = ?', (submission_id,))
        scores = [row['score'] for row in cursor.fetchall()]
        conn.close()
        return scores

    def get_submission(self, submission_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT email, title FROM submissions WHERE id = ?', (submission_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def update_status(self, submission_id, status):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE submissions SET status = ? WHERE id = ?', (status, submission_id))
        conn.commit()
        conn.close()


def upload_to_r2(file_bytes, file_name):
    """Uploads file to Cloudflare R2 and returns the object key."""
    account_id = os.getenv('R2_ACCOUNT_ID')
    access_key = os.getenv('R2_ACCESS_KEY_ID')
    secret_key = os.getenv('R2_SECRET_ACCESS_KEY')
    bucket_name = os.getenv('R2_BUCKET_NAME')
    endpoint_url = os.getenv('R2_ENDPOINT_URL')

    if not all([account_id, access_key, secret_key, bucket_name, endpoint_url]):
        # Fallback for local testing if no R2 creds
        print("Warning: R2 credentials missing. Saving locally to 'uploads/' instead.")
        os.makedirs('uploads', exist_ok=True)
        local_path = os.path.join('uploads', file_name)
        with open(local_path, 'wb') as f:
            f.write(file_bytes)
        return local_path

    s3 = boto3.client(
        's3',
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name='auto',
        config=Config(signature_version='s3v4')
    )
    
    try:
        s3.put_object(Bucket=bucket_name, Key=file_name, Body=file_bytes)
        return file_name
    except Exception as e:
        print(f"Error uploading to R2: {e}")
        return None

if __name__ == '__main__':
    init_db()
    print("Database initialized.")
