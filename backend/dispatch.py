"""Transactional nearest-team assignment, shared by every incident source."""
import os
from backend.areas import contains

TABLES={'fire':'fire_reports','conflict':'conflict_reports'}

def can_access(conn,user,item):
    return user['role'] in {'ADMIN','OFFICER'} or is_assigned(conn,user,item)

def is_assigned(conn,user,item):
    if not item.get('assigned_team_id'): return item.get('assigned_to')==user['id']
    return bool(item.get('assigned_team_id') and conn.execute('SELECT 1 FROM response_team_members WHERE team_id=%s AND user_id=%s',(item['assigned_team_id'],user['id'])).fetchone())

def notify_assignment(conn,kind,item):
    recipients=[]
    if item.get('assigned_team_id'):
        recipients=conn.execute("SELECT m.user_id FROM response_team_members m JOIN users u ON u.id=m.user_id WHERE m.team_id=%s AND u.role IN ('OFFICER','RESCUE') AND u.is_active",(item['assigned_team_id'],)).fetchall()
    elif item.get('assigned_to'): recipients=[{'user_id':item['assigned_to']}]
    for person in recipients:
        conn.execute("INSERT INTO notifications(user_id,incident_type,incident_id,title,body,push_enabled,assignment_revision) VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(user_id,incident_type,incident_id,assignment_revision) DO NOTHING",
                     (person['user_id'],kind,item['id'],'New incident assigned','Your team has a new incident. Open it to review the location and respond.',not item.get('is_demo',False),item.get('assignment_revision',0)))

def assign_nearest(conn,kind,incident_id):
    table=TABLES[kind]
    conn.execute('SELECT pg_advisory_xact_lock(36001)')
    item=conn.execute(f'SELECT * FROM {table} WHERE id=%s FOR UPDATE',(incident_id,)).fetchone()
    if not item or item['status'] not in {'REPORTED','VERIFIED'} or item['assigned_to'] is not None or item['latitude'] is None or item['longitude'] is None: return item,None
    max_age=int(os.getenv('TEAM_LOCATION_MAX_AGE_MINUTES','60'))
    team=conn.execute('''SELECT t.id,t.name,t.patrol_area,lead.user_id,lead.lead_name,
      6371*acos(LEAST(1.0,GREATEST(-1.0,cos(radians(%s))*cos(radians(t.latitude))*cos(radians(t.longitude)-radians(%s))+sin(radians(%s))*sin(radians(t.latitude))))) AS distance_km
      FROM response_teams t
      JOIN LATERAL (SELECT m.user_id,u.name AS lead_name FROM response_team_members m JOIN users u ON u.id=m.user_id WHERE m.team_id=t.id AND u.role IN ('OFFICER','RESCUE') AND u.is_active ORDER BY m.user_id LIMIT 1) lead ON TRUE
      WHERE t.is_active AND t.patrol_area IS NOT NULL AND t.status='AVAILABLE' AND t.latitude IS NOT NULL AND t.longitude IS NOT NULL
      AND t.location_updated_at>=NOW()-(%s * INTERVAL '1 minute')
      AND NOT EXISTS(SELECT 1 FROM fire_reports r WHERE (r.assigned_team_id=t.id OR r.assigned_to IN (SELECT user_id FROM response_team_members WHERE team_id=t.id)) AND r.status NOT IN ('RESOLVED','CLOSED'))
      AND NOT EXISTS(SELECT 1 FROM conflict_reports r WHERE (r.assigned_team_id=t.id OR r.assigned_to IN (SELECT user_id FROM response_team_members WHERE team_id=t.id)) AND r.status NOT IN ('RESOLVED','CLOSED'))
      ORDER BY distance_km,t.id''',(item['latitude'],item['longitude'],item['latitude'],max_age)).fetchall()
    team=next((candidate for candidate in team if contains(candidate['patrol_area'],item['latitude'],item['longitude'])),None)
    if not team: return item,None
    item=conn.execute(f"UPDATE {table} SET assigned_team_id=%s,assigned_to=%s,status='ASSIGNED',assignment_revision=assignment_revision+1,updated_at=NOW() WHERE id=%s RETURNING *",(team['id'],team['user_id'],incident_id)).fetchone()
    conn.execute("INSERT INTO incident_events(incident_type,incident_id,event_type,status,message) VALUES(%s,%s,'AUTO_TEAM_ASSIGNED','ASSIGNED',%s)",(kind,incident_id,f"{team['name']} assigned automatically ({float(team['distance_km']):.2f} km straight-line distance). Report requires verification."))
    notify_assignment(conn,kind,item)
    return item,{'teamId':team['id'],'teamName':team['name'],'lead':team['lead_name'],'distanceKm':float(team['distance_km'])}

def dispatch_waiting(conn):
    # Bound each pass; later passes pick up the remaining queue.
    rows=conn.execute("SELECT id,'fire' AS kind,severity,created_at FROM fire_reports WHERE status IN ('REPORTED','VERIFIED') AND assigned_to IS NULL UNION ALL SELECT id,'conflict' AS kind,severity,created_at FROM conflict_reports WHERE status IN ('REPORTED','VERIFIED') AND assigned_to IS NULL ORDER BY created_at LIMIT 100").fetchall()
    priority={'CRITICAL':0,'HIGH':1,'MEDIUM':2,'LOW':3}
    for row in sorted(rows,key=lambda r:(priority.get(r['severity'],4),r['created_at'])): assign_nearest(conn,row['kind'],row['id'])
