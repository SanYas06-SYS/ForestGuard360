from pathlib import Path
from dotenv import load_dotenv
import os
import psycopg
ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT/'.env')
url=os.getenv('DATABASE_URL')
if not url: raise SystemExit('Set DATABASE_URL in .env before running database setup.')
if os.getenv('PGSSL','false').lower()=='true' and 'sslmode=' not in url: url += ('&' if '?' in url else '?')+'sslmode=require'
schema=(ROOT/'backend'/'schema.sql').read_text(encoding='utf-8')
with psycopg.connect(url) as conn:
    conn.execute('SET LOCAL search_path TO public')
    conn.execute(schema)
print('ForestGuard PostgreSQL tables are ready.')
