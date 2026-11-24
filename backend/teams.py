"""Admin team management and guard location updates."""
import math
from fastapi import HTTPException, Request
from psycopg.types.json import Jsonb
from backend.areas import validate_area
from backend.dispatch import TABLES, notify_assignment

def lock(conn):conn.execute('SELECT pg_advisory_xact_lock(36001)')

def team_busy(conn,team_id,exclude_kind='',exclude_id=0):
    for kind,table in TABLES.items():
        if conn.execute(f"SELECT 1 FROM {table} WHERE status NOT IN ('RESOLVED','CLOSED') AND (assigned_team_id=%s OR (assigned_team_id IS NULL AND assigned_to IN (SELECT user_id FROM response_team_members WHERE team_id=%s))) AND NOT (%s=%s AND id=%s) LIMIT 1",(team_id,team_id,kind,exclude_kind,exclude_id)).fetchone():return True
    return False

def remove_member(conn,team_id,user_id):
    member=conn.execute('SELECT 1 FROM response_team_members WHERE team_id=%s AND user_id=%s',(team_id,user_id)).fetchone()
    if not member:raise HTTPException(404,'Team member not found.')
    other=conn.execute('SELECT m.user_id FROM response_team_members m JOIN users u ON u.id=m.user_id WHERE m.team_id=%s AND m.user_id<>%s AND u.is_active ORDER BY m.user_id LIMIT 1',(team_id,user_id)).fetchone()
    if not other and team_busy(conn,team_id):raise HTTPException(409,'Reassign or finish active cases before removing the last team member.')
    conn.execute('DELETE FROM response_team_members WHERE team_id=%s AND user_id=%s',(team_id,user_id))
    for table in TABLES.values():
        conn.execute(f'UPDATE {table} SET assigned_to=%s WHERE assigned_team_id=%s AND assigned_to=%s',(other['user_id'] if other else None,team_id,user_id))

def coordinates(body):
    try:
        lat=body['latitude'];lon=body['longitude']
        if isinstance(lat,bool) or isinstance(lon,bool):raise ValueError()
        lat=float(lat);lon=float(lon)
        if not math.isfinite(lat) or not math.isfinite(lon) or not -90<=lat<=90 or not -180<=lon<=180:raise ValueError()
        return lat,lon
    except (KeyError,ValueError,TypeError):raise HTTPException(400,'Choose a valid location on the map.')

def install_team_routes(app,db,require_staff,require_admin):
    def admin(request):require_admin(require_staff(request))

    @app.get('/api/response-teams')
    def teams(request:Request):
        require_staff(request)
        with db() as conn:
            rows=conn.execute("SELECT t.*,COUNT(u.id)::int AS member_count,COALESCE(json_agg(json_build_object('id',u.id,'name',u.name,'role',u.role)) FILTER(WHERE u.id IS NOT NULL),'[]') AS members FROM response_teams t LEFT JOIN response_team_members m ON m.team_id=t.id LEFT JOIN users u ON u.id=m.user_id AND u.is_active WHERE t.is_active GROUP BY t.id ORDER BY t.id").fetchall()
            for row in rows:row['has_active_case']=team_busy(conn,row['id'])
        return {'teams':rows}

    @app.post('/api/response-teams',status_code=201)
    def create_team(request:Request,body:dict):
        admin(request);name=body.get('name')
        if not isinstance(name,str) or not 1<=len(name.strip())<=120:raise HTTPException(400,'Enter a team name under 120 characters.')
        with db() as conn:
            lock(conn)
            if conn.execute('SELECT 1 FROM response_teams WHERE lower(name)=lower(%s)',(name.strip(),)).fetchone():raise HTTPException(409,'That team name is already used. Choose a different name.')
            next_id=conn.execute('SELECT COALESCE(MAX(id),0)+1 AS id FROM response_teams').fetchone()['id']
            if next_id>32767:raise HTTPException(409,'Team capacity reached.')
            row=conn.execute("INSERT INTO response_teams(id,name,status) VALUES(%s,%s,'OFFLINE') RETURNING *",(next_id,name.strip())).fetchone()
        return {'team':row}

    @app.patch('/api/response-teams/{team_id}')
    def update_team(team_id:int,request:Request,body:dict):
        admin(request)
        if not any(k in body for k in ('name','status','latitude','longitude','patrolArea')):raise HTTPException(400,'Choose a team change to save.')
        with db() as conn:
            lock(conn)
            team=conn.execute('SELECT * FROM response_teams WHERE id=%s AND is_active FOR UPDATE',(team_id,)).fetchone()
            if not team:raise HTTPException(404,'Team not found.')
            if 'name' in body:
                name=body['name']
                if not isinstance(name,str) or not 1<=len(name.strip())<=120:raise HTTPException(400,'Enter a team name under 120 characters.')
                if conn.execute('SELECT 1 FROM response_teams WHERE lower(name)=lower(%s) AND id<>%s',(name.strip(),team_id)).fetchone():raise HTTPException(409,'That team name is already used.')
                team['name']=name.strip()
            if 'status' in body:
                if body['status'] not in {'AVAILABLE','BUSY','OFFLINE'}:raise HTTPException(400,'Choose a valid team availability.')
                team['status']=body['status']
            located='latitude' in body or 'longitude' in body
            if located:team['latitude'],team['longitude']=coordinates(body)
            if 'patrolArea' in body:
                try:team['patrol_area']=validate_area(body['patrolArea']) if body['patrolArea'] is not None else None
                except ValueError as e:raise HTTPException(400,str(e))
            row=conn.execute('UPDATE response_teams SET name=%s,status=%s,latitude=%s,longitude=%s,patrol_area=%s,location_updated_at=CASE WHEN %s THEN NOW() ELSE location_updated_at END,updated_at=NOW() WHERE id=%s RETURNING *',(team['name'],team['status'],team['latitude'],team['longitude'],Jsonb(team['patrol_area']) if team['patrol_area'] else None,located,team_id)).fetchone()
        return {'team':row}

    @app.delete('/api/response-teams/{team_id}')
    def delete_team(team_id:int,request:Request):
        admin(request)
        with db() as conn:
            lock(conn)
            if not conn.execute('SELECT 1 FROM response_teams WHERE id=%s AND is_active',(team_id,)).fetchone():raise HTTPException(404,'Team not found.')
            if team_busy(conn,team_id):raise HTTPException(409,'Reassign or finish active cases before deleting this team.')
            conn.execute("UPDATE response_teams SET is_active=FALSE,status='OFFLINE',updated_at=NOW() WHERE id=%s",(team_id,))
            conn.execute('DELETE FROM response_team_members WHERE team_id=%s',(team_id,))
        return {'ok':True}

    @app.post('/api/response-teams/{team_id}/members',status_code=201)
    def add_member(team_id:int,request:Request,body:dict):
        admin(request);uid=body.get('userId')
        if isinstance(uid,bool) or not isinstance(uid,int):raise HTTPException(400,'Choose a staff member.')
        with db() as conn:
            lock(conn)
            if not conn.execute('SELECT 1 FROM response_teams WHERE id=%s AND is_active',(team_id,)).fetchone():raise HTTPException(404,'Team not found.')
            if not conn.execute("SELECT 1 FROM users WHERE id=%s AND is_active AND role IN ('OFFICER','RESCUE')",(uid,)).fetchone():raise HTTPException(400,'Choose an active guard or officer account.')
            if conn.execute('SELECT 1 FROM response_team_members WHERE user_id=%s',(uid,)).fetchone():raise HTTPException(409,'Remove this member from their current team before adding them here.')
            conn.execute('INSERT INTO response_team_members(team_id,user_id) VALUES(%s,%s)',(team_id,uid))
            for kind,table in TABLES.items():
                for item in conn.execute(f"SELECT * FROM {table} WHERE assigned_team_id=%s AND status NOT IN ('RESOLVED','CLOSED')",(team_id,)).fetchall():notify_assignment(conn,kind,item)
        return {'ok':True}

    @app.delete('/api/response-teams/{team_id}/members/{user_id}')
    def delete_member(team_id:int,user_id:int,request:Request):
        admin(request)
        with db() as conn:lock(conn);remove_member(conn,team_id,user_id)
        return {'ok':True}

    @app.delete('/api/staff/{user_id}')
    def delete_staff(user_id:int,request:Request):
        admin(request)
        with db() as conn:
            lock(conn)
            if not conn.execute("SELECT 1 FROM users WHERE id=%s AND is_active AND role IN ('OFFICER','RESCUE')",(user_id,)).fetchone():raise HTTPException(404,'Guard or officer account not found.')
            for table in TABLES.values():
                if conn.execute(f"SELECT 1 FROM {table} WHERE assigned_to=%s AND assigned_team_id IS NULL AND status NOT IN ('RESOLVED','CLOSED')",(user_id,)).fetchone():raise HTTPException(409,'Reassign this account’s active case to a team first.')
            membership=conn.execute('SELECT team_id FROM response_team_members WHERE user_id=%s',(user_id,)).fetchone()
            if membership:remove_member(conn,membership['team_id'],user_id)
            conn.execute('UPDATE users SET is_active=FALSE WHERE id=%s',(user_id,))
            conn.execute('DELETE FROM auth_sessions WHERE user_id=%s',(user_id,))
        return {'ok':True}

    @app.get('/api/my-team')
    def my_team(request:Request):
        user=require_staff(request)
        with db() as conn:team=conn.execute('SELECT t.* FROM response_teams t JOIN response_team_members m ON m.team_id=t.id WHERE m.user_id=%s AND t.is_active',(user['id'],)).fetchone()
        return {'team':team}

    @app.patch('/api/my-team/location')
    def update_location(request:Request,body:dict):
        user=require_staff(request);lat,lon=coordinates(body)
        with db() as conn:
            lock(conn)
            team=conn.execute('UPDATE response_teams t SET latitude=%s,longitude=%s,location_updated_at=NOW(),updated_at=NOW() FROM response_team_members m WHERE m.team_id=t.id AND m.user_id=%s AND t.is_active RETURNING t.*',(lat,lon,user['id'])).fetchone()
            if not team:raise HTTPException(403,'Ask an administrator to add you to a team first.')
        return {'team':team}
