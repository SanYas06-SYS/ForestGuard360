"""Idempotent demo setup; preserves existing accounts and operational records."""
import os
from pathlib import Path
import bcrypt
import psycopg
from dotenv import load_dotenv, set_key

ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT/'.env')
url=os.environ['DATABASE_URL']
with psycopg.connect(url) as conn:
    conn.execute('SET LOCAL search_path TO public')
    conn.execute((ROOT/'backend/schema.sql').read_text(encoding='utf-8-sig'))
    email=os.getenv('ADMIN_EMAIL','').strip().lower()
    password=os.getenv('ADMIN_PASSWORD','')
    if not email or len(password)<12 or len(password.encode())>72:
        raise SystemExit('Set ADMIN_EMAIL and ADMIN_PASSWORD (12 characters minimum, 72 bytes maximum).')
    conn.execute("INSERT INTO users(name,email,password_hash,role) VALUES(%s,%s,%s,'ADMIN') ON CONFLICT(email) DO NOTHING",(os.getenv('ADMIN_NAME','Forest Administrator'),email,bcrypt.hashpw(password.encode(),bcrypt.gensalt()).decode()))
    conn.execute("INSERT INTO forest_zones(name,kind,coordinates,is_demo) VALUES('DEMO restricted conservation zone','RESTRICTED','[[16.70,74.30],[16.70,74.32],[16.72,74.32],[16.72,74.30]]',TRUE) ON CONFLICT(name) DO NOTHING")
    conn.execute("INSERT INTO tourism_routes(name,description,safety_notes,coordinates,is_demo) SELECT 'DEMO nature trail','Fictional route for the college presentation.','Not an approved visitor route. Do not use for navigation.','[[16.68,74.28],[16.69,74.29],[16.70,74.29]]',TRUE WHERE NOT EXISTS(SELECT 1 FROM tourism_routes WHERE name='DEMO nature trail')")
set_key(str(ROOT/'.env'),'DEMO_MODE','true')
print('Demo schema and route are ready. Sign in using ADMIN_EMAIL and ADMIN_PASSWORD from .env.')
