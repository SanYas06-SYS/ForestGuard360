from pathlib import Path
from dotenv import load_dotenv
import os, bcrypt, psycopg
ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT/'.env')
url=os.getenv('DATABASE_URL'); email=(os.getenv('ADMIN_EMAIL') or '').strip().lower(); password=os.getenv('ADMIN_PASSWORD'); name=os.getenv('ADMIN_NAME','Forest Administrator')
if not url or not email or not password or len(password)<12: raise SystemExit('Set DATABASE_URL, ADMIN_EMAIL and ADMIN_PASSWORD (at least 12 characters) in .env.')
if os.getenv('PGSSL','false').lower()=='true' and 'sslmode=' not in url: url += ('&' if '?' in url else '?')+'sslmode=require'
hash=bcrypt.hashpw(password.encode(),bcrypt.gensalt(rounds=12)).decode()
with psycopg.connect(url) as conn:
    conn.execute('SET LOCAL search_path TO public')
    conn.execute("INSERT INTO users(name,email,password_hash,role) VALUES(%s,%s,%s,'ADMIN') ON CONFLICT(email) DO UPDATE SET name=EXCLUDED.name,password_hash=EXCLUDED.password_hash,role='ADMIN'",(name,email,hash))
print(f'Administrator account is ready for {email}.')
