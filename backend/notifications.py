"""Per-member inbox and an at-least-once FCM outbox with leases and retries."""
import json
import logging
import os
import threading
from fastapi import HTTPException, Request
from backend.dispatch import TABLES,is_assigned,dispatch_waiting

log=logging.getLogger('vanrakshak.push')

def firebase_app():
    import firebase_admin
    from firebase_admin import credentials
    try: return firebase_admin.get_app()
    except ValueError:
        config=os.getenv('FIREBASE_SERVICE_ACCOUNT_JSON')
        path=os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if not config and not path: return None
        credential=credentials.Certificate(json.loads(config) if config else path)
        return firebase_admin.initialize_app(credential,options={'httpTimeout':15})

def send_push(token,notification):
    from firebase_admin import messaging
    app=firebase_app()
    if not app: raise RuntimeError('Firebase credentials are not configured')
    message=messaging.Message(token=token,notification=messaging.Notification(title='VanRakshak: new assignment',body='Open the guard app to review your team’s incident.'),data={'notificationId':str(notification['id']),'incidentType':notification['incident_type'],'incidentId':str(notification['incident_id'])},android=messaging.AndroidConfig(priority='high',ttl=3600,notification=messaging.AndroidNotification(channel_id='incident_alerts',tag=f"incident-{notification['incident_type']}-{notification['incident_id']}")))
    return messaging.send(message,app=app)

def process_delivery(db,sender=send_push):
    with db() as conn:
        conn.execute('''INSERT INTO push_deliveries(notification_id,device_id)
          SELECT n.id,d.id FROM notifications n JOIN push_devices d ON d.user_id=n.user_id
          JOIN auth_sessions s ON s.token_hash=d.session_hash AND s.expires_at>NOW()
          WHERE n.push_enabled=TRUE AND n.created_at>NOW()-INTERVAL '24 hours' AND d.enabled=TRUE
          ON CONFLICT(notification_id,device_id) DO NOTHING''')
        job=conn.execute("SELECT * FROM push_deliveries WHERE (status IN ('PENDING','RETRY') AND next_attempt_at<=NOW()) OR (status='SENDING' AND lease_until<NOW()) ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1").fetchone()
        if not job:return False
        device=conn.execute('SELECT d.*,s.expires_at>NOW() AS active_session FROM push_devices d LEFT JOIN auth_sessions s ON s.token_hash=d.session_hash WHERE d.id=%s',(job['device_id'],)).fetchone()
        notification=conn.execute('SELECT * FROM notifications WHERE id=%s',(job['notification_id'],)).fetchone()
        user=conn.execute('SELECT id,role,is_active FROM users WHERE id=%s',(notification['user_id'],)).fetchone() if notification else None
        item=conn.execute(f"SELECT * FROM {TABLES[notification['incident_type']]} WHERE id=%s",(notification['incident_id'],)).fetchone() if notification else None
        if not device or not device['enabled'] or not device['active_session'] or not user or not user['is_active'] or user['role'] not in {'OFFICER','RESCUE'} or not item or notification['assignment_revision']!=item['assignment_revision'] or item['status'] in {'RESOLVED','CLOSED'} or device['user_id'] != user['id'] or not is_assigned(conn,user,item):
            conn.execute("UPDATE push_deliveries SET status='CANCELLED',last_error='No current assignment or signed-in device' WHERE id=%s",(job['id'],));return True
        conn.execute("UPDATE push_deliveries SET status='SENDING',attempts=attempts+1,lease_until=NOW()+INTERVAL '2 minutes' WHERE id=%s",(job['id'],))
    try:
        receipt=sender(device['token'],notification)
        with db() as conn:conn.execute("UPDATE push_deliveries SET status='SENT',sent_at=NOW(),provider_message_id=%s,last_error=NULL WHERE id=%s",(receipt,job['id']))
    except Exception as exc:
        # Never log device tokens or service-account values.
        invalid=type(exc).__name__=='UnregisteredError'
        attempts=job['attempts']+1
        with db() as conn:
            if invalid: conn.execute('UPDATE push_devices SET enabled=FALSE WHERE id=%s',(device['id'],))
            conn.execute("UPDATE push_deliveries SET status=%s,last_error=%s,next_attempt_at=NOW()+(%s * INTERVAL '1 second') WHERE id=%s",('FAILED' if invalid or attempts>=8 else 'RETRY',type(exc).__name__,min(300,2**attempts*5),job['id']))
    return True

def worker_loop(db,stop):
    while not stop.is_set():
        try:
            with db() as conn: dispatch_waiting(conn)
            if os.getenv('PUSH_ENABLED','false').lower()=='true' and firebase_app():
                for _ in range(25):
                    if stop.is_set() or not process_delivery(db): break
        except Exception as exc: log.warning('Dispatch/notification worker retry: %s',type(exc).__name__)
        stop.wait(10)

def install_routes(app,db,require_user,require_staff,require_admin,token_hash):
    @app.get('/api/notifications')
    def inbox(request:Request):
        user=require_staff(request)
        with db() as conn: rows=conn.execute('SELECT id,incident_type,incident_id,title,body,read_at,created_at FROM notifications WHERE user_id=%s ORDER BY created_at DESC LIMIT 100',(user['id'],)).fetchall()
        return {'items':rows}

    @app.patch('/api/notifications/{notification_id}/read')
    def mark_read(notification_id:int,request:Request):
        user=require_staff(request)
        with db() as conn:row=conn.execute('UPDATE notifications SET read_at=NOW() WHERE id=%s AND user_id=%s RETURNING id',(notification_id,user['id'])).fetchone()
        if not row:raise HTTPException(404,'Notification not found.')
        return {'ok':True}

    @app.post('/api/push/devices')
    def register_device(request:Request,body:dict):
        user=require_staff(request)
        if user['role'] not in {'OFFICER','RESCUE'}:raise HTTPException(403,'Use a forest guard account in the guard app.')
        token=body.get('token')
        if not isinstance(token,str) or not 20<=len(token)<=4096:raise HTTPException(400,'A valid Android notification token is required.')
        with db() as conn:row=conn.execute('INSERT INTO push_devices(user_id,token,session_hash) VALUES(%s,%s,%s) ON CONFLICT(token) DO UPDATE SET user_id=EXCLUDED.user_id,session_hash=EXCLUDED.session_hash,enabled=TRUE,updated_at=NOW() RETURNING id',(user['id'],token,token_hash(request))).fetchone()
        return {'deviceId':row['id']}

    @app.delete('/api/push/devices/{device_id}')
    def unregister_device(device_id:int,request:Request):
        user=require_user(request)
        with db() as conn:conn.execute('DELETE FROM push_devices WHERE id=%s AND user_id=%s',(device_id,user['id']))
        return {'ok':True}

    @app.get('/api/admin/dispatch-status')
    def dispatch_status(request:Request):
        require_admin(require_staff(request))
        with db() as conn:
            counts=conn.execute('SELECT status,COUNT(*)::int AS count FROM push_deliveries GROUP BY status').fetchall()
            devices=conn.execute('SELECT COUNT(*)::int AS count FROM push_devices d JOIN auth_sessions s ON s.token_hash=d.session_hash WHERE d.enabled AND s.expires_at>NOW()').fetchone()['count']
        return {'pushEnabled':os.getenv('PUSH_ENABLED','false').lower()=='true','firebaseConfigured':bool(os.getenv('FIREBASE_SERVICE_ACCOUNT_JSON') or os.getenv('GOOGLE_APPLICATION_CREDENTIALS')),'registeredDevices':devices,'deliveries':counts,'locationMaxAgeMinutes':int(os.getenv('TEAM_LOCATION_MAX_AGE_MINUTES','60'))}
