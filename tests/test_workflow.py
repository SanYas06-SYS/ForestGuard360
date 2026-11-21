"""Integration checks use a new, disposable schema in the configured PostgreSQL DB."""
import os
import uuid
from contextlib import contextmanager
from pathlib import Path
import pytest
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from dotenv import load_dotenv
from fastapi.testclient import TestClient

ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT/'.env')
os.environ['NODE_ENV']='test'
os.environ['DEMO_MODE']='true'
os.environ['SESSION_SECRET']='integration-test-secret-with-more-than-32-characters'
os.environ['AI_WEBHOOK_SECRET']='integration-test-ai-key'
os.environ['SENSOR_WEBHOOK_SECRET']='integration-test-sensor-key'

class TabClient(TestClient):
    def request(self, method, url, **kwargs):
        response = super().request(method, url, **kwargs)
        if str(url) in {'/api/auth/login','/api/auth/register'} and response.is_success:
            self.headers['Authorization']='Bearer '+response.json()['token']
        return response

@pytest.fixture()
def environment():
    import backend.app as backend
    schema='test_vanrakshak_'+uuid.uuid4().hex
    url=os.environ['DATABASE_URL']
    with psycopg.connect(url) as conn:
        conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        conn.execute(sql.SQL('SET LOCAL search_path TO {}').format(sql.Identifier(schema)))
        conn.execute((ROOT/'backend/schema.sql').read_text(encoding='utf-8-sig'))
    old=backend._pool
    old_schema=backend.DB_SCHEMA
    backend.DB_SCHEMA=schema
    class ScopedPool(ConnectionPool):
        @contextmanager
        def connection(self):
            with super().connection() as conn:
                conn.execute(sql.SQL('SET LOCAL search_path TO {}').format(sql.Identifier(schema)))
                yield conn
    pool=ScopedPool(url,min_size=1,max_size=3,kwargs={'row_factory':dict_row},open=True)
    backend._pool=pool
    client=TabClient(backend.app)
    try: yield client,pool
    finally:
        client.close();pool.close();backend._pool=old;backend.DB_SCHEMA=old_schema
        with psycopg.connect(url) as conn: conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))

def register(client,email='citizen@example.test'):
    response=client.post('/api/auth/register',json={'name':'Test User','email':email,'password':'test-password-123'})
    assert response.status_code==201,response.text
    return response.json()['user']

def admin(client,pool):
    user=register(client,'admin@example.test')
    with pool.connection() as conn: conn.execute("UPDATE users SET role='ADMIN' WHERE id=%s",(user['id'],))
    assert client.post('/api/auth/login',json={'email':user['email'],'password':'test-password-123'}).status_code==200

def test_auth_validation_and_citizen_permissions(environment):
    c,p=environment
    assert c.get('/api/incidents').status_code==401
    assert c.post('/api/auth/register',json={'name':'a','email':'invalid','password':'abcdefgh'}).status_code==400
    assert c.post('/api/auth/register',json={'name':'a','email':'valid@example.test','password':'a'*73}).status_code==400
    register(c)
    assert c.get('/api/incidents').status_code==403
    assert c.post('/api/demo/events',json={}).status_code==403
    assert c.post('/api/fires',json={'title':'fire','latitude':12}).status_code==400
    assert c.post('/api/fires',json={'title':'fire','latitude':'nan','longitude':12}).status_code==400
    assert c.post('/api/fires',json={'title':'fire','imageUrl':123}).status_code==400
    assert c.post('/api/fires',json={'title':'fire','latitude':16.7,'longitude':74.3}).status_code==201
    assert len(c.get('/api/my-reports').json()['items'])==1

def test_dispatch_lifecycle_and_cross_type_booking(environment):
    c,p=environment;admin(c,p)
    staff=c.post('/api/staff',json={'name':'Rescuer','email':'rescue@example.test','password':'rescue-password-123','role':'RESCUE'}).json()['staff']
    assert c.patch('/api/response-teams/1',json={'latitude':16.7,'longitude':74.3,'status':'AVAILABLE'}).status_code==200
    assert c.post('/api/response-teams/1/members',json={'userId':staff['id']}).status_code==201
    def detection(label):
        response=c.post('/api/ai/detections',headers={'x-ai-key':os.environ['AI_WEBHOOK_SECRET']},json={'label':label,'confidence':.95,'latitude':16.7,'longitude':74.3})
        assert response.status_code==201,response.text
        return response.json()
    first=detection('forest_fire');assert first['assignment']['teamId']==1
    second=detection('illegal_logging');assert second['assignment'] is None
    key=first['incident']['id']
    assert c.get(f'/api/incidents/fire/{key}').json()['incident']['type']=='fire'
    assert c.patch(f'/api/incidents/fire/{key}',json={'assignedTo':None}).status_code==400
    assert c.patch(f'/api/incidents/fire/{key}',json={'status':'RESPONDING'}).status_code==200
    assert c.patch(f'/api/incidents/fire/{key}',json={'status':'RESOLVED'}).status_code==200
    third=detection('human');assert third['assignment']['teamId']==1
    assert c.post('/api/auth/login',json={'email':'rescue@example.test','password':'rescue-password-123'}).status_code==200
    assert c.get(f"/api/incidents/conflict/{second['incident']['id']}").status_code==403

def test_monitoring_and_tourism(environment):
    c,p=environment;admin(c,p)
    body={'event':'sensor','latitude':16.7,'longitude':74.3,'temperature':60,'humidity':35,'smoke':70}
    assert c.post('/api/demo/events',json=body).status_code==201
    assert c.post('/api/demo/events',json=body).status_code==201
    assert len(c.get('/api/incidents').json()['items'])==1
    assert c.get('/api/monitoring').json()['sensors'][0]['is_demo']
    assert c.post('/api/demo/events',json={**body,'event':'wildlife','species':'Deer'}).status_code==201
    assert c.get('/api/monitoring').json()['sightings'][0]['species']=='Deer'
    assert c.post('/api/tourism/routes',json={'name':'Demo trail','coordinates':[[16.7,74.3],[16.71,74.31]]}).status_code==201
    assert c.post('/api/tourism/routes',json={'name':'Bad trail','coordinates':[[100,74.3],[16.71,74.31]]}).status_code==400
    c.post('/api/auth/logout')
    assert c.get('/api/tourism').json()['routes'][0]['is_demo']
    assert c.get('/api/monitoring').status_code==401
    assert c.post('/api/sensors/readings',json={}).status_code==401

def test_independent_tab_sessions_and_revocation(environment):
    import backend.app as backend
    first,pool=environment
    admin(first,pool)
    first_token=first.headers['Authorization']
    with TabClient(backend.app) as second:
        # A shared old cookie cannot restore any login.
        second.cookies.set('connect.sid','legacy-browser-session')
        assert second.get('/api/auth/session').json()['user'] is None
        assert second.get('/api/admin/overview').status_code==401
        register(second,'second@example.test')
        assert second.get('/api/auth/session').json()['user']['role']=='CITIZEN'
        assert first.get('/api/auth/session').json()['user']['role']=='ADMIN'
        assert second.get('/api/admin/overview').status_code==403
        assert first.post('/api/auth/logout').status_code==204
        # Reusing the original token after logout is denied by the server.
        assert first.get('/api/admin/overview',headers={'Authorization':first_token}).status_code==401
        assert second.get('/api/auth/session').json()['user']['email']=='second@example.test'
        assert second.post('/api/auth/logout').status_code==204
        assert second.get('/api/my-reports').status_code==401

def test_session_expiry(environment):
    c,pool=environment
    register(c)
    assert c.get('/api/auth/session').json()['user'] is not None
    with pool.connection() as conn: conn.execute("UPDATE auth_sessions SET expires_at=NOW()-INTERVAL '1 second'")
    assert c.get('/api/auth/session').json()['user'] is None
    assert c.get('/api/my-reports').status_code==401

def test_report_photo_upload_and_permissions(environment):
    import io
    from PIL import Image
    import backend.app as backend
    c,pool=environment
    content=io.BytesIO()
    Image.new('RGB',(3000,1500),(20,110,60)).save(content,format='PNG')
    raw=content.getvalue()
    assert c.post('/api/uploads/report-image',files={'image':('photo.png',raw,'image/png')}).status_code==401
    register(c)
    assert c.post('/api/uploads/report-image',files={'image':('fake.png',b'not an image','image/png')}).status_code==400
    assert c.post('/api/uploads/report-image',files={'image':('huge.png',b'x'*(10*1024*1024+1),'image/png')}).status_code==413
    uploaded=c.post('/api/uploads/report-image',files={'image':('photo.png',raw,'image/png')})
    assert uploaded.status_code==201,uploaded.text
    photo=uploaded.json()
    response=c.get(photo['imageUrl'])
    assert response.status_code==200
    assert response.headers['content-type']=='image/jpeg'
    assert response.headers['cache-control']=='no-store'
    assert Image.open(io.BytesIO(response.content)).size==(2400,1200)
    report=c.post('/api/fires',json={'title':'Photo with map point','latitude':0,'longitude':0,**photo})
    assert report.status_code==201,report.text
    assert report.json()['item']['image_url']==photo['imageUrl']
    assert float(report.json()['item']['latitude'])==0
    with TabClient(backend.app) as other:
        register(other,'other@example.test')
        assert other.get(photo['imageUrl']).status_code==403
        assert other.post('/api/fires',json={'title':'Not my photo',**photo}).status_code==400
    admin(c,pool)
    assert c.get(photo['imageUrl']).status_code==200
    c.post('/api/auth/logout')
    assert c.get(photo['imageUrl']).status_code==401


def test_nearest_team_members_and_push_outbox(environment):
    from backend.notifications import process_delivery
    import backend.app as backend
    c,pool=environment;admin(c,pool)
    members=[]
    for n in range(3):
        member=c.post('/api/staff',json={'name':f'Guard {n}','email':f'guard{n}@example.test','password':'guard-password-123','role':'OFFICER' if n==1 else 'RESCUE'}).json()['staff']
        members.append(member)
        assert c.post(f'/api/response-teams/{1 if n<2 else 2}/members',json={'userId':member['id']}).status_code==201
    for team in (1,2):
        assert c.patch(f'/api/response-teams/{team}',json={'latitude':16.7,'longitude':74.3,'status':'AVAILABLE'}).status_code==200
    with pool.connection() as conn:
        conn.execute("UPDATE response_teams SET location_updated_at=NOW()-INTERVAL '2 hours' WHERE id=2")
    report=c.post('/api/fires',json={'title':'Nearest team check','latitude':16.7,'longitude':74.3}).json()
    assert report['assignment']['teamId']==1
    key=report['item']['id']
    assert c.post('/api/auth/login',json={'email':'guard1@example.test','password':'guard-password-123'}).status_code==200
    assert c.get('/api/notifications').json()['items'][0]['incident_id']==key
    assert c.get('/api/my-team').json()['team']['id']==1
    assert c.post('/api/push/devices',json={'token':'test-device-token-for-guard-1'}).status_code==200
    sent=[]
    assert process_delivery(backend.db,lambda token,item:sent.append(item['id']) or 'fake-fcm-receipt')
    assert len(sent)==1
    assert not process_delivery(backend.db,lambda *_:pytest.fail('Duplicate push'))
    with pool.connection() as conn:
        conn.execute("UPDATE push_deliveries SET status='RETRY',next_attempt_at=NOW()")
        conn.execute('DELETE FROM response_team_members WHERE user_id=%s',(members[1]['id'],))
    # Officers have broad viewing rights, but only current assignees get pushes.
    assert process_delivery(backend.db,lambda *_:pytest.fail('Push sent to removed team member'))
    with pool.connection() as conn:
        assert conn.execute('SELECT status FROM push_deliveries').fetchone()['status']=='CANCELLED'
    assert c.post('/api/auth/logout').status_code==204
    with pool.connection() as conn: assert conn.execute('SELECT COUNT(*) AS n FROM push_devices').fetchone()['n']==0
    assert c.post('/api/auth/login',json={'email':'guard0@example.test','password':'guard-password-123'}).status_code==200
    assert c.get(f'/api/incidents/fire/{key}').status_code==200
    assert c.patch('/api/my-team/location',json={'latitude':16.71,'longitude':74.31}).status_code==200
    assert c.patch('/api/my-team/location',json={'latitude':100,'longitude':74}).status_code==400
    assert c.post('/api/fires',json={'title':'Wait for available team','latitude':16.7,'longitude':74.3}).json()['assignment'] is None
