"""Sensor ingestion, GIS and explicitly simulated college demonstrations."""
import math
import os
import secrets
from backend.dispatch import assign_nearest
from fastapi import HTTPException, Request, Header


def number(value, minimum, maximum, name):
    try:
        result = float(value)
        if isinstance(value, bool) or not math.isfinite(result) or not minimum <= result <= maximum:
            raise ValueError()
        return result
    except (ValueError, TypeError):
        raise HTTPException(400, f'Invalid {name}.')


def install_routes(app, db, require_staff, require_admin, ai_detection):
    def demo_enabled():
        return os.getenv('DEMO_MODE', 'false').lower() == 'true'

    def ingest(body, simulated=False):
        device = body.get('deviceId')
        if not isinstance(device, str) or not device.strip() or len(device) > 100:
            raise HTTPException(400, 'A device ID of up to 100 characters is required.')
        lat = number(body.get('latitude'), -90, 90, 'latitude')
        lon = number(body.get('longitude'), -180, 180, 'longitude')
        temperature = number(body.get('temperature'), -60, 150, 'temperature')
        humidity = number(body.get('humidity'), 0, 100, 'humidity')
        smoke = number(body.get('smoke'), 0, 100, 'smoke level')
        alert = temperature >= 55 or smoke >= 60
        with db() as conn:
            reading = conn.execute('INSERT INTO sensor_readings(device_id,latitude,longitude,temperature,humidity,smoke,alert,is_demo) VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *', (device.strip(),lat,lon,temperature,humidity,smoke,alert,simulated)).fetchone()
            if alert:
                # Serialize ingestion per device to avoid alert storms from repeated samples.
                conn.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', (device,))
                recent = conn.execute("SELECT id FROM monitoring_alerts WHERE device_id=%s AND created_at>NOW()-INTERVAL '5 minutes'", (device,)).fetchone()
                if not recent:
                    incident = conn.execute("INSERT INTO fire_reports(title,description,latitude,longitude,severity,is_demo) VALUES(%s,%s,%s,%s,'HIGH',%s) RETURNING id", (('DEMO: ' if simulated else '')+'Sensor threshold alert',f'{device}: temperature {temperature} C; smoke {smoke}/100. Requires officer verification.',lat,lon,simulated)).fetchone()
                    conn.execute("INSERT INTO incident_events(incident_type,incident_id,event_type,status,message) VALUES('fire',%s,'SENSOR_ALERT','REPORTED',%s)", (incident['id'], 'Simulated sensor reading.' if simulated else 'Sensor threshold exceeded.'))
                    conn.execute('INSERT INTO monitoring_alerts(device_id,incident_id) VALUES(%s,%s)', (device,incident['id']))
                    assign_nearest(conn,'fire',incident['id'])
        return {'reading': reading}

    @app.post('/api/sensors/readings', status_code=201)
    def readings(body: dict, x_sensor_key: str | None = Header(default=None)):
        key = os.getenv('SENSOR_WEBHOOK_SECRET', '')
        if not key or not secrets.compare_digest(x_sensor_key or '', key):
            raise HTTPException(401, 'Invalid sensor credentials.')
        return ingest(body)

    @app.get('/api/monitoring')
    def monitoring(request: Request):
        user = require_staff(request)
        with db() as conn:
            sensors = conn.execute('SELECT DISTINCT ON(device_id) * FROM sensor_readings ORDER BY device_id,created_at DESC').fetchall()
            sightings = conn.execute('SELECT * FROM wildlife_sightings ORDER BY created_at DESC LIMIT 100').fetchall()
            zones = conn.execute('SELECT * FROM forest_zones ORDER BY id').fetchall()
        return {'sensors': sensors, 'sightings': sightings, 'zones': zones, 'demoEnabled': demo_enabled() and user['role']=='ADMIN'}

    @app.post('/api/demo/events', status_code=201)
    def simulate(request: Request, body: dict):
        require_admin(require_staff(request))
        if not demo_enabled(): raise HTTPException(403, 'Enable DEMO_MODE in .env to use simulations.')
        lat = number(body.get('latitude'), -90, 90, 'latitude')
        lon = number(body.get('longitude'), -180, 180, 'longitude')
        event = body.get('event')
        if event == 'sensor':
            return ingest({'deviceId':'DEMO-SENSOR-01','latitude':lat,'longitude':lon,'temperature':body.get('temperature',30),'humidity':body.get('humidity',50),'smoke':body.get('smoke',10)}, True)
        if event == 'wildlife':
            species = body.get('species', 'Unidentified animal')
            if not isinstance(species,str) or not species.strip() or len(species)>100: raise HTTPException(400,'Enter a species under 100 characters.')
            with db() as conn:
                row = conn.execute('INSERT INTO wildlife_sightings(species,latitude,longitude,is_demo) VALUES(%s,%s,%s,TRUE) RETURNING *', (species.strip(),lat,lon)).fetchone()
            return {'sighting':row}
        if event not in {'forest_fire','human','illegal_logging'}: raise HTTPException(400,'Unknown demonstration event.')
        secret = os.getenv('AI_WEBHOOK_SECRET')
        if not secret: raise HTTPException(503,'Set AI_WEBHOOK_SECRET to enable the detection demonstration.')
        result = ai_detection({'label':event,'confidence':0.95,'latitude':lat,'longitude':lon,'isDemo':True,'description':'SIMULATED college demonstration event. No camera inference was performed.'}, secret)
        return {**result,'simulated':True}

    @app.get('/api/tourism')
    def tourism():
        with db() as conn:
            routes = conn.execute('SELECT id,name,description,safety_notes,coordinates,is_demo FROM tourism_routes WHERE is_active=TRUE ORDER BY id').fetchall()
        return {'routes':routes,'guidelines':['Use only routes approved by the local forest office.','Follow posted closures and travel with an authorized guide where required.','Keep a safe distance from wildlife; never feed animals.','Do not light fires, litter, or remove plants.','Report smoke or unsafe activity from a safe location.'],'notice':'Demonstration routes are fictional and are not travel directions. Confirm real access and conditions with the forest office.'}

    @app.post('/api/tourism/routes', status_code=201)
    def add_route(request: Request, body: dict):
        require_admin(require_staff(request))
        name = body.get('name'); description = body.get('description',''); safety = body.get('safetyNotes','')
        points = body.get('coordinates')
        if not isinstance(name,str) or not name.strip() or len(name)>180 or not isinstance(description,str) or len(description)>4000 or not isinstance(safety,str) or len(safety)>4000:
            raise HTTPException(400,'Provide a route name and details under 4,000 characters.')
        if not isinstance(points,list) or not 2<=len(points)<=200: raise HTTPException(400,'Provide 2–200 [latitude, longitude] route points.')
        validated=[]
        for point in points:
            if not isinstance(point,list) or len(point)!=2: raise HTTPException(400,'Invalid route point.')
            validated.append([number(point[0],-90,90,'latitude'),number(point[1],-180,180,'longitude')])
        from psycopg.types.json import Jsonb
        with db() as conn:
            row=conn.execute('INSERT INTO tourism_routes(name,description,safety_notes,coordinates,is_demo) VALUES(%s,%s,%s,%s,%s) RETURNING *',(name.strip(),description,safety,Jsonb(validated),demo_enabled())).fetchone()
        return {'route':row}
