"""ForestGuard 360 REST API - Python/FastAPI implementation."""
from __future__ import annotations
import os, re, time, math, logging, secrets, hashlib
from pathlib import Path
from contextlib import contextmanager, asynccontextmanager
import threading
from backend.dispatch import assign_nearest, notify_assignment, can_access, dispatch_waiting
from backend.notifications import worker_loop
from psycopg import sql
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
import bcrypt

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')
logging.basicConfig(level=logging.INFO)
log = logging.getLogger('forestguard')
DATABASE_URL = os.getenv('DATABASE_URL', '')
if not DATABASE_URL:
    log.warning('DATABASE_URL is not configured; database routes will not work until .env is set.')
_pool: Optional[ConnectionPool] = None
if DATABASE_URL:
    conninfo = DATABASE_URL
    if os.getenv('PGSSL', 'false').lower() == 'true' and 'sslmode=' not in conninfo:
        conninfo += ('&' if '?' in conninfo else '?') + 'sslmode=require'
    _pool = ConnectionPool(conninfo=conninfo, min_size=1, max_size=10, check=ConnectionPool.check_connection, kwargs={'row_factory': dict_row}, open=True)

@asynccontextmanager
async def lifespan(app):
    stop=threading.Event()
    worker=None
    if os.getenv('ENABLE_DISPATCH_WORKER','true').lower()=='true' and os.getenv('NODE_ENV')!='test':
        worker=threading.Thread(target=worker_loop,args=(db,stop),daemon=True,name='dispatch-worker')
        worker.start()
    yield
    stop.set()
    if worker: worker.join(timeout=20)
    if _pool and DB_SCHEMA == 'public': _pool.close()

app = FastAPI(title='VanRakshak 360 API', version='3.0.0',lifespan=lifespan)

FIRE = 'fire_reports'; CONFLICT = 'conflict_reports'
INCIDENT_TABLES = {'fire': FIRE, 'conflict': CONFLICT}
STAFF_ROLES = {'ADMIN', 'OFFICER', 'RESCUE'}
STATUSES = {'REPORTED','VERIFIED','ASSIGNED','RESPONDING','RESOLVED','CLOSED'}
TRANSITIONS = {'REPORTED': {'VERIFIED','ASSIGNED','CLOSED'}, 'VERIFIED': {'ASSIGNED','CLOSED'}, 'ASSIGNED': {'RESPONDING','VERIFIED','CLOSED'}, 'RESPONDING': {'ASSIGNED','RESOLVED','CLOSED'}, 'RESOLVED': {'RESPONDING','CLOSED'}, 'CLOSED': set()}
INCIDENT_UNION = """SELECT id,'fire'::text AS type,title,description,latitude,longitude,severity,status,image_url,cloudinary_public_id,reported_by,assigned_to,verified_by,created_at,updated_at,assigned_team_id FROM fire_reports UNION ALL SELECT id,'conflict'::text AS type,title,description,latitude,longitude,severity,status,image_url,cloudinary_public_id,reported_by,assigned_to,verified_by,created_at,updated_at,assigned_team_id FROM conflict_reports"""

class DBUnavailable(Exception): pass

DB_SCHEMA = 'public'
@contextmanager
def db():
    if _pool is None: raise HTTPException(503, 'Database is not configured. Set DATABASE_URL in .env.')
    with _pool.connection() as conn:
        conn.execute(sql.SQL('SET LOCAL search_path TO {}').format(sql.Identifier(DB_SCHEMA)))
        yield conn

def one(cur): return cur.fetchone()
def session_user(row): return {'id': row['id'], 'name': row['name'], 'email': row['email'], 'role': row['role']}
def token_hash(request: Request):
    authorization = request.headers.get('authorization', '')
    if not authorization.startswith('Bearer '): return None
    token = authorization[7:]
    if not 32 <= len(token) <= 128: return None
    return hashlib.sha256(token.encode()).hexdigest()

def current_user(request: Request):
    digest = token_hash(request)
    if not digest: return None
    with db() as conn:
        row = conn.execute('SELECT u.id,u.name,u.email,u.role FROM auth_sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=%s AND s.expires_at>NOW() AND u.is_active', (digest,)).fetchone()
    return session_user(row) if row else None

def issue_session(request: Request, row):
    token = secrets.token_urlsafe(32)
    digest = hashlib.sha256(token.encode()).hexdigest()
    with db() as conn:
        previous = token_hash(request)
        if previous: conn.execute('DELETE FROM auth_sessions WHERE token_hash=%s', (previous,))
        conn.execute('DELETE FROM auth_sessions WHERE expires_at<=NOW()')
        conn.execute('INSERT INTO auth_sessions(token_hash,user_id) VALUES(%s,%s)', (digest,row['id']))
    return {'user':session_user(row),'token':token}

@app.middleware('http')
async def private_responses(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    return response
def require_user(request: Request):
    user = current_user(request)
    if not user: raise HTTPException(401, 'Sign in required')
    return user
def require_staff(request: Request):
    user = require_user(request)
    if user['role'] not in STAFF_ROLES: raise HTTPException(403, 'Response staff access required.')
    return user
def require_admin(user):
    if user['role'] != 'ADMIN': raise HTTPException(403, 'Administrator access required.')
def as_float(value):
    try:
        if value is None or value == '': return None
        number = float(value)
        return number if math.isfinite(number) and not isinstance(value, bool) else None
    except (TypeError, ValueError): return None
def validate_coordinates(lat, lon):
    if (lat is None) != (lon is None): return False
    if lat is not None and (as_float(lat) is None or not -90 <= float(lat) <= 90): return False
    if lon is not None and (as_float(lon) is None or not -180 <= float(lon) <= 180): return False
    return True

@app.get('/api/health')
def health():
    with db() as conn: conn.execute('SELECT 1')
    return {'status':'ok','database':'connected'}

@app.get('/api/auth/session')
def auth_session(request: Request): return {'user': current_user(request)}

@app.post('/api/auth/register', status_code=201)
def register(request: Request, body: dict):
    name, email, password = body.get('name'), body.get('email'), body.get('password')
    if not isinstance(name,str) or not name.strip() or len(name)>120 or not isinstance(email,str) or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email.strip()) or not isinstance(password,str) or len(password)<8 or len(password.encode())>72:
        raise HTTPException(400, 'Enter your name, a valid email, and a password with at least 8 characters.')
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()
    try:
        with db() as conn:
            row = one(conn.execute('INSERT INTO users(name,email,password_hash,role) VALUES(%s,%s,%s,%s) RETURNING id,name,email,role', (name.strip(),email.strip().lower(),hashed,'CITIZEN')))
    except Exception as e:
        if getattr(e, 'sqlstate', None) == '23505': raise HTTPException(409, 'An account with that email already exists.')
        raise
    return issue_session(request, row)

@app.post('/api/auth/login')
def login(request: Request, body: dict):
    email = str(body.get('email') or '').strip().lower(); password = body.get('password')
    with db() as conn: row = one(conn.execute('SELECT id,name,email,password_hash,role FROM users WHERE email=%s AND is_active', (email,)))
    if not row or not isinstance(password,str) or len(password.encode())>72 or not bcrypt.checkpw(password.encode(), row['password_hash'].encode()): raise HTTPException(401, 'Email or password is incorrect.')
    return issue_session(request, row)

@app.post('/api/auth/logout', status_code=204)
def logout(request: Request):
    digest = token_hash(request)
    if digest:
        with db() as conn: conn.execute('DELETE FROM auth_sessions WHERE token_hash=%s', (digest,))
    response = Response(status_code=204)
    response.delete_cookie('connect.sid')
    return response

@app.get('/api/admin/overview')
def overview(request: Request):
    user=require_staff(request); scoped=user['role']=='RESCUE'; where='WHERE ((assigned_team_id IS NULL AND assigned_to=%s) OR assigned_team_id IN (SELECT team_id FROM response_team_members WHERE user_id=%s))' if scoped else ''; vals=(user['id'],user['id']) if scoped else ()
    with db() as conn:
        stats=one(conn.execute(f"WITH incidents AS ({INCIDENT_UNION}) SELECT COUNT(*) FILTER(WHERE status NOT IN ('RESOLVED','CLOSED'))::int AS open,COUNT(*) FILTER(WHERE status IN ('REPORTED','VERIFIED') AND assigned_to IS NULL)::int AS unassigned,COUNT(*) FILTER(WHERE status IN ('ASSIGNED','RESPONDING'))::int AS active_response,COUNT(*) FILTER(WHERE severity='CRITICAL' AND status NOT IN ('RESOLVED','CLOSED'))::int AS critical,COUNT(*) FILTER(WHERE status='RESOLVED' AND updated_at>=NOW()-INTERVAL '7 days')::int AS resolved_week FROM incidents {where}", vals))
        recent=conn.execute(f"WITH incidents AS ({INCIDENT_UNION}) SELECT i.id::text||':'||i.type AS key,i.id,i.type,i.title,i.description,i.latitude,i.longitude,i.severity,i.status,i.image_url,i.reported_by,i.assigned_to,i.assigned_team_id,i.created_at,i.updated_at,reporter.name AS reporter_name,assignee.name AS assignee_name,t.name AS assigned_team_name FROM incidents i LEFT JOIN users reporter ON reporter.id=i.reported_by LEFT JOIN users assignee ON assignee.id=i.assigned_to LEFT JOIN response_teams t ON t.id=i.assigned_team_id {'WHERE ((i.assigned_team_id IS NULL AND i.assigned_to=%s) OR i.assigned_team_id IN (SELECT team_id FROM response_team_members WHERE user_id=%s))' if scoped else ''} ORDER BY i.created_at DESC LIMIT 8", vals).fetchall()
        severities=conn.execute(f"WITH incidents AS ({INCIDENT_UNION}) SELECT severity,COUNT(*)::int AS total FROM incidents WHERE type='fire' GROUP BY severity").fetchall()
    return {'user':user,'stats':stats,'recent':recent,'fires_by_severity':severities}

@app.get('/api/staff')
def staff_list(request: Request):
    require_staff(request)
    with db() as conn: rows=conn.execute("SELECT id,name,role FROM users WHERE is_active AND role IN ('ADMIN','OFFICER','RESCUE') ORDER BY name").fetchall()
    return {'staff':rows}

@app.post('/api/staff', status_code=201)
def staff_create(request: Request, body: dict):
    user=require_staff(request); require_admin(user)
    name=str(body.get('name') or '').strip(); email=str(body.get('email') or '').strip().lower(); password=body.get('password'); role=body.get('role')
    if not name or len(name)>120 or not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$',email) or not isinstance(password,str) or len(password)<12 or len(password.encode())>72 or role not in {'OFFICER','RESCUE'}: raise HTTPException(400,'Enter a name, valid email, 12-character password, and response role.')
    hashed=bcrypt.hashpw(password.encode(),bcrypt.gensalt(rounds=12)).decode()
    try:
        with db() as conn: row=one(conn.execute('INSERT INTO users(name,email,password_hash,role) VALUES(%s,%s,%s,%s) RETURNING id,name,role',(name,email,hashed,role)))
    except Exception as e:
        if getattr(e,'sqlstate',None)=='23505': raise HTTPException(409,'An account with that email already exists.')
        raise
    return {'staff':row}

from backend.teams import install_team_routes
install_team_routes(app,db,require_staff,require_admin)

@app.post('/api/ai/detections', status_code=201)
def ai_detection(body: dict, x_ai_key: str | None = Header(default=None)):
    secret=os.getenv('AI_WEBHOOK_SECRET')
    if not secret or not secrets.compare_digest(x_ai_key or '', secret): raise HTTPException(401,'Invalid AI service credentials.')
    label=body.get('label'); conf=as_float(body.get('confidence')); lat=as_float(body.get('latitude')); lon=as_float(body.get('longitude'))
    allowed={'forest_fire','smoke','illegal_logging','tree_cutting','wildlife','human'}
    if label not in allowed or conf is None or conf<float(os.getenv('AI_DETECTION_MIN_CONFIDENCE','0.5')) or conf>1 or lat is None or lon is None or not validate_coordinates(lat,lon): raise HTTPException(400,'Detection label, confidence, and GPS coordinates are required.')
    is_fire=label in {'forest_fire','smoke'}; table=FIRE if is_fire else CONFLICT; typ='fire' if is_fire else 'conflict'; severity='HIGH' if conf>=.85 else 'MEDIUM'; title='AI detected: '+label.replace('_',' ')
    with db() as conn:
        with conn.transaction():
            conn.execute('SELECT pg_advisory_xact_lock(36001)')
            demo=body.get('isDemo') is True
            row=one(conn.execute(f"INSERT INTO {table}(title,description,latitude,longitude,severity,is_demo,image_url) VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING *",(('DEMO: ' if demo else '')+title,str(body.get('description') or ''),lat,lon,severity,demo,body.get('imageUrl'))))
            conn.execute('INSERT INTO incident_events(incident_type,incident_id,event_type,status,message) VALUES(%s,%s,%s,%s,%s)',(typ,row['id'],'AI_DETECTED','REPORTED',f'Detection {label} ({round(conf*100)}% confidence); officer verification required.'))
            row,assignment=assign_nearest(conn,typ,row['id'])
    return {'incident':row,'assignment':assignment}

@app.get('/api/incidents')
def incident_list(request: Request, type: str | None=None, status: str | None=None, q: str | None=None):
    user=require_staff(request); filters=[]; vals=[]
    if type in {'fire','conflict'}: filters.append('i.type=%s'); vals.append(type)
    if status in STATUSES: filters.append('i.status=%s'); vals.append(status)
    if q and q.strip(): filters.append('(title ILIKE %s OR description ILIKE %s)'); vals.extend([f'%{q.strip()[:100]}%',f'%{q.strip()[:100]}%'])
    if user['role']=='RESCUE': filters.append('((assigned_team_id IS NULL AND assigned_to=%s) OR assigned_team_id IN (SELECT team_id FROM response_team_members WHERE user_id=%s))'); vals.extend([user['id'],user['id']])
    where=('WHERE '+' AND '.join(filters)) if filters else ''
    sql=f"WITH incidents AS ({INCIDENT_UNION}) SELECT i.id::text||':'||i.type AS key,i.id,i.type,i.title,i.description,i.latitude,i.longitude,i.severity,i.status,i.image_url,i.reported_by,i.assigned_to,i.created_at,i.updated_at,reporter.name AS reporter_name,assignee.name AS assignee_name,t.name AS assigned_team_name FROM incidents i LEFT JOIN users reporter ON reporter.id=i.reported_by LEFT JOIN users assignee ON assignee.id=i.assigned_to LEFT JOIN response_teams t ON t.id=i.assigned_team_id {where} ORDER BY CASE WHEN i.severity='CRITICAL' THEN 0 WHEN i.severity='HIGH' THEN 1 WHEN i.severity='MEDIUM' THEN 2 ELSE 3 END,i.created_at DESC LIMIT 150"
    with db() as conn: rows=conn.execute(sql,vals).fetchall()
    return {'items':rows}

@app.get('/api/incidents/{kind}/{incident_id}')
def incident_detail(kind: str, incident_id: str, request: Request):
    user=require_staff(request); table=INCIDENT_TABLES.get(kind)
    if not table or not incident_id.isdigit(): raise HTTPException(404,'Incident not found.')
    with db() as conn:
        item=one(conn.execute(f'SELECT i.*,r.name AS reporter_name,a.name AS assignee_name,t.name AS assigned_team_name FROM {table} i LEFT JOIN users r ON r.id=i.reported_by LEFT JOIN users a ON a.id=i.assigned_to LEFT JOIN response_teams t ON t.id=i.assigned_team_id WHERE i.id=%s',(int(incident_id),)))
        if not item: raise HTTPException(404,'Incident not found.')
        if user['role']=='RESCUE' and not can_access(conn,user,item): raise HTTPException(403,'This incident is assigned to another team.')
        events=conn.execute('SELECT e.id,e.event_type,e.status,e.message,e.created_at,u.name AS actor_name FROM incident_events e LEFT JOIN users u ON u.id=e.actor_id WHERE e.incident_type=%s AND e.incident_id=%s ORDER BY e.created_at DESC',(kind,int(incident_id))).fetchall()
    item['type'] = kind
    return {'incident':item,'events':events}

@app.patch('/api/incidents/{kind}/{incident_id}')
def incident_update(kind: str, incident_id: str, request: Request, body: dict):
    user=require_staff(request); table=INCIDENT_TABLES.get(kind)
    if not table or not incident_id.isdigit(): raise HTTPException(404,'Incident not found.')
    from backend.teams import team_busy
    status=body.get('status'); message=str(body.get('message') or '').strip()[:1000]
    if 'assignedTo' in body:raise HTTPException(400,'Select a response team, not an individual member.')
    if status is not None and (not isinstance(status,str) or status not in STATUSES):raise HTTPException(400,'Invalid incident status.')
    changing_team='assignedTeamId' in body
    team_id=body.get('assignedTeamId')
    if changing_team and team_id is not None and (isinstance(team_id,bool) or not isinstance(team_id,int) or team_id<1):raise HTTPException(400,'Choose a valid team.')
    with db() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(36001)')
        item=one(conn.execute(f'SELECT * FROM {table} WHERE id=%s FOR UPDATE',(int(incident_id),)))
        if not item:raise HTTPException(404,'Incident not found.')
        if user['role']=='RESCUE' and not can_access(conn,user,item):raise HTTPException(403,'This incident is assigned to another team.')
        if changing_team and user['role'] not in {'ADMIN','OFFICER'}:raise HTTPException(403,'Only administrators and officers can assign teams.')
        next_team=team_id if changing_team else item['assigned_team_id']
        reassigned=changing_team and (next_team!=item['assigned_team_id'] or (next_team is None and item['assigned_to'] is not None))
        lead=item['assigned_to'];team_name='';team=None
        if next_team and (reassigned or (status in {'ASSIGNED','RESPONDING'} and item['status'] not in {'ASSIGNED','RESPONDING'})):
            team=conn.execute('SELECT * FROM response_teams WHERE id=%s AND is_active FOR UPDATE',(next_team,)).fetchone()
            if not team:raise HTTPException(400,'Choose an existing team.')
            if team['status']!='AVAILABLE' or team_busy(conn,next_team,kind,int(incident_id)):raise HTTPException(409,'This team is unavailable or already responding to another case.')
            person=conn.execute("SELECT u.id FROM response_team_members m JOIN users u ON u.id=m.user_id WHERE m.team_id=%s AND u.is_active AND u.role IN ('OFFICER','RESCUE') ORDER BY u.id LIMIT 1",(next_team,)).fetchone()
            if not person:raise HTTPException(400,'Add members to this team before assigning it.')
            lead=person['id'];team_name=team['name']
        if changing_team and next_team is None:lead=None
        next_status=status or item['status']
        if reassigned and next_team and next_status in {'REPORTED','VERIFIED'}:next_status='ASSIGNED'
        if next_status!=item['status'] and next_status not in TRANSITIONS.get(item['status'],set()):raise HTTPException(409,'This status transition is not allowed.')
        if next_status in {'ASSIGNED','RESPONDING'} and not lead:raise HTTPException(400,'Assign a team before starting a response, or return the case to Verified when unassigning.')
        if reassigned and item['status'] in {'RESOLVED','CLOSED'}:raise HTTPException(409,'Reopen the case before changing its team.')
        if not status and not message and not changing_team:raise HTTPException(400,'Choose a status, team, or add an update.')
        updated=conn.execute(f"UPDATE {table} SET status=%s,assigned_to=%s,assigned_team_id=%s,assignment_revision=assignment_revision+%s,verified_by=CASE WHEN %s='VERIFIED' THEN %s ELSE verified_by END,updated_at=NOW() WHERE id=%s RETURNING *",(next_status,lead,next_team,1 if reassigned else 0,next_status,user['id'],int(incident_id))).fetchone()
        if reassigned:
            conn.execute('INSERT INTO incident_events(incident_type,incident_id,actor_id,event_type,status,message) VALUES(%s,%s,%s,%s,%s,%s)',(kind,int(incident_id),user['id'],'TEAM_ASSIGNED',next_status,f'Assigned to {team_name}. All current members notified.' if next_team else 'Team assignment removed.'))
            if next_team:notify_assignment(conn,kind,updated)
        if next_status!=item['status'] or message:
            conn.execute('INSERT INTO incident_events(incident_type,incident_id,actor_id,event_type,status,message) VALUES(%s,%s,%s,%s,%s,%s)',(kind,int(incident_id),user['id'],'STATUS' if next_status!=item['status'] else 'UPDATE',next_status,message or f'Status changed to {next_status}.'))
    return {'incident':updated}


@app.post('/api/cloudinary/signature')
def cloudinary_signature(request: Request):
    require_user(request)
    cloud=os.getenv('CLOUDINARY_CLOUD_NAME'); key=os.getenv('CLOUDINARY_API_KEY'); secret=os.getenv('CLOUDINARY_API_SECRET')
    if not cloud or not key or not secret: raise HTTPException(503,'Cloudinary is not configured. Add its credentials to .env.')
    try:
        import cloudinary, cloudinary.utils
        cloudinary.config(cloud_name=cloud,api_key=key,api_secret=secret,secure=True)
        folder='forestguard/reports'; timestamp=int(time.time()); signature=cloudinary.utils.api_sign_request({'folder':folder,'timestamp':timestamp},secret)
    except ImportError: raise HTTPException(503,'Install the Cloudinary Python package to enable image uploads.')
    return {'cloudName':cloud,'apiKey':key,'folder':folder,'timestamp':timestamp,'signature':signature}

def create_report(path: str, request: Request, body: dict):
    user=require_user(request); title=body.get('title'); description=body.get('description',''); lat=body.get('latitude'); lon=body.get('longitude'); severity=body.get('severity','MEDIUM'); animal=body.get('animalType',''); image_url=body.get('imageUrl'); public_id=body.get('cloudinaryPublicId')
    if not isinstance(title,str) or not title.strip() or len(title.strip())>180 or not isinstance(description,str) or len(description)>4000 or severity not in {'LOW','MEDIUM','HIGH','CRITICAL'}: raise HTTPException(400,'Enter a short title, details under 4,000 characters, and a valid severity.')
    if not validate_coordinates(lat,lon): raise HTTPException(400,'Enter valid map coordinates.')
    if path=='conflicts' and (not isinstance(animal,str) or len(animal)>100): raise HTTPException(400,'Enter an animal type under 100 characters.')
    if isinstance(image_url,str) and image_url.startswith('/api/report-images/'):
        identifier=image_url.removeprefix('/api/report-images/')
        if not re.fullmatch('[a-f0-9]{32}',identifier): raise HTTPException(400,'Attach a photo uploaded through this report form.')
        with db() as conn: uploaded=conn.execute('SELECT id FROM report_images WHERE id=%s AND uploaded_by=%s',(identifier,user['id'])).fetchone()
        if not uploaded: raise HTTPException(400,'Attach a photo uploaded from your account.')
        public_id=None
    elif image_url:
        from urllib.parse import urlparse
        if not isinstance(image_url,str) or urlparse(image_url).scheme != 'https' or urlparse(image_url).hostname!='res.cloudinary.com' or not isinstance(public_id,str) or len(public_id)>255: raise HTTPException(400,'Attach an image uploaded to the ForestGuard Cloudinary folder.')
    table=FIRE if path=='fires' else CONFLICT; typ='fire' if path=='fires' else 'conflict'
    with db() as conn:
        with conn.transaction():
            if path=='conflicts': row=one(conn.execute(f'INSERT INTO {table}(title,description,latitude,longitude,severity,image_url,cloudinary_public_id,reported_by,animal_type) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *',(title.strip(),description,lat,lon,severity,image_url,public_id,user['id'],animal.strip())))
            else: row=one(conn.execute(f'INSERT INTO {table}(title,description,latitude,longitude,severity,image_url,cloudinary_public_id,reported_by) VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *',(title.strip(),description,lat,lon,severity,image_url,public_id,user['id'])))
            conn.execute('INSERT INTO incident_events(incident_type,incident_id,actor_id,event_type,status,message) VALUES(%s,%s,%s,%s,%s,%s)',(typ,row['id'],user['id'],'REPORTED','REPORTED','Report submitted.'))
            row,assignment=assign_nearest(conn,typ,row['id'])
    return {'item':row,'assignment':assignment}

@app.post('/api/fires',status_code=201)
def create_fire(request: Request, body: dict): return create_report('fires',request,body)
@app.post('/api/conflicts',status_code=201)
def create_conflict(request: Request, body: dict): return create_report('conflicts',request,body)

@app.get('/api/my-reports')
def my_reports(request: Request):
    user=require_user(request)
    with db() as conn: rows=conn.execute(f"WITH incidents AS ({INCIDENT_UNION}) SELECT i.id::text||':'||i.type AS key,i.id,i.type,i.title,i.description,i.latitude,i.longitude,i.severity,i.status,i.image_url,i.assigned_to,i.created_at,i.updated_at,assignee.name AS assignee_name,t.name AS assigned_team_name FROM incidents i LEFT JOIN users assignee ON assignee.id=i.assigned_to LEFT JOIN response_teams t ON t.id=i.assigned_team_id WHERE i.reported_by=%s ORDER BY i.created_at DESC LIMIT 100",(user['id'],)).fetchall()
    return {'items':rows}

from backend.notifications import install_routes as install_notification_routes
install_notification_routes(app,db,require_user,require_staff,require_admin,token_hash)

from backend.uploads import install_upload_routes
install_upload_routes(app, db, require_user)

from backend.monitoring import install_routes
install_routes(app, db, require_staff, require_admin, ai_detection)

# Serve the compiled React app and static resources from the same origin.
static_root=ROOT/'static'
if (static_root/'core').exists(): app.mount('/static',StaticFiles(directory=str(static_root)),name='static')
frontend_root=static_root/'frontend'
if (frontend_root/'assets').exists(): app.mount('/assets',StaticFiles(directory=str(frontend_root/'assets')),name='assets')
@app.get('/{full_path:path}')
def frontend_fallback(full_path: str):
    if full_path.startswith('api/'): raise HTTPException(404,'API route not found.')
    index=frontend_root/'index.html'
    if index.exists(): return FileResponse(index)
    raise HTTPException(404,'Frontend build not found. Run npm run build.')

@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    message = exc.detail if isinstance(exc.detail, str) else 'Request failed.'
    return JSONResponse(status_code=exc.status_code, content={'error': message}, headers=exc.headers)

@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={'error': 'Invalid request data.'})

@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception):
    log.exception('Unhandled API error: %s',exc)
    return JSONResponse(status_code=500,content={'error':'The server could not complete that request.'})
