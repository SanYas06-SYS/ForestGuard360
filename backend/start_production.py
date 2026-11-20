"""Apply idempotent schema changes, create an initial admin, then serve HTTP."""
import os
import runpy
import bcrypt
import psycopg

def main():
    runpy.run_module('backend.setup_db', run_name='__main__')
    url=os.environ['DATABASE_URL']
    if os.getenv('PGSSL','false').lower()=='true' and 'sslmode=' not in url:
        url+=('&' if '?' in url else '?')+'sslmode=require'
    email=os.getenv('ADMIN_EMAIL','').strip().lower()
    password=os.getenv('ADMIN_PASSWORD','')
    if not email or not 12<=len(password.encode())<=72:
        raise SystemExit('Configure ADMIN_EMAIL and ADMIN_PASSWORD (12–72 bytes).')
    with psycopg.connect(url) as conn:
        conn.execute("INSERT INTO users(name,email,password_hash,role) VALUES(%s,%s,%s,'ADMIN') ON CONFLICT(email) DO NOTHING",(os.getenv('ADMIN_NAME','Forest Administrator'),email,bcrypt.hashpw(password.encode(),bcrypt.gensalt()).decode()))
    import uvicorn
    uvicorn.run('backend.app:app',host='0.0.0.0',port=int(os.getenv('PORT','10000')),workers=1)

if __name__=='__main__': main()
