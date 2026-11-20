CREATE TABLE IF NOT EXISTS users (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'CITIZEN' CHECK (role IN ('ADMIN','OFFICER','RESCUE','TOURISM','CITIZEN','TOURIST')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS fire_reports (
  id BIGSERIAL PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  latitude NUMERIC(9,6), longitude NUMERIC(9,6),
  severity TEXT NOT NULL DEFAULT 'MEDIUM' CHECK (severity IN ('LOW','MEDIUM','HIGH','CRITICAL')),
  status TEXT NOT NULL DEFAULT 'REPORTED',
  image_url TEXT,
  cloudinary_public_id TEXT,
  reported_by BIGINT REFERENCES users(id) ON DELETE SET NULL,
  is_demo BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS conflict_reports (
  id BIGSERIAL PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  latitude NUMERIC(9,6), longitude NUMERIC(9,6),
  severity TEXT NOT NULL DEFAULT 'MEDIUM' CHECK (severity IN ('LOW','MEDIUM','HIGH','CRITICAL')),
  status TEXT NOT NULL DEFAULT 'REPORTED',
  image_url TEXT,
  cloudinary_public_id TEXT,
  reported_by BIGINT REFERENCES users(id) ON DELETE SET NULL,
  animal_type TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE fire_reports ADD COLUMN IF NOT EXISTS assigned_to BIGINT REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE fire_reports ADD COLUMN IF NOT EXISTS verified_by BIGINT REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE fire_reports ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE conflict_reports ADD COLUMN IF NOT EXISTS assigned_to BIGINT REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE conflict_reports ADD COLUMN IF NOT EXISTS verified_by BIGINT REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE conflict_reports ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE conflict_reports ADD COLUMN IF NOT EXISTS animal_type TEXT NOT NULL DEFAULT '';
CREATE TABLE IF NOT EXISTS incident_events (
  id BIGSERIAL PRIMARY KEY,
  incident_type TEXT NOT NULL CHECK (incident_type IN ('fire','conflict')),
  incident_id BIGINT NOT NULL,
  actor_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
  event_type TEXT NOT NULL,
  status TEXT,
  message TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS animals (
  id BIGSERIAL PRIMARY KEY, animal_id TEXT NOT NULL UNIQUE, species TEXT NOT NULL,
  health_status TEXT NOT NULL DEFAULT 'HEALTHY', image_url TEXT, cloudinary_public_id TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS rescue_cases (
  id BIGSERIAL PRIMARY KEY, animal_id BIGINT REFERENCES animals(id) ON DELETE SET NULL,
  status TEXT NOT NULL DEFAULT 'OPEN', location TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS patrols (
  id BIGSERIAL PRIMARY KEY, zone TEXT NOT NULL, officer_name TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'ASSIGNED', scheduled_for TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  notes TEXT NOT NULL DEFAULT '', created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS plantations (
  id BIGSERIAL PRIMARY KEY, name TEXT NOT NULL, location TEXT NOT NULL, species TEXT NOT NULL DEFAULT '',
  trees_planted INTEGER NOT NULL DEFAULT 0 CHECK (trees_planted >= 0), image_url TEXT, cloudinary_public_id TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS destinations (
  id BIGSERIAL PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
  entry_fee NUMERIC(10,2) NOT NULL DEFAULT 0, image_url TEXT, cloudinary_public_id TEXT,
  is_active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS bookings (
  id BIGSERIAL PRIMARY KEY, destination_id BIGINT REFERENCES destinations(id) ON DELETE SET NULL,
  visitor_name TEXT NOT NULL, visit_date DATE NOT NULL, time_slot TEXT NOT NULL DEFAULT '',
  visitor_count INTEGER NOT NULL DEFAULT 1 CHECK (visitor_count > 0), status TEXT NOT NULL DEFAULT 'CONFIRMED',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS fire_reports_created_idx ON fire_reports(created_at DESC);
CREATE INDEX IF NOT EXISTS conflict_reports_created_idx ON conflict_reports(created_at DESC);
CREATE INDEX IF NOT EXISTS fire_reports_status_idx ON fire_reports(status, created_at DESC);
CREATE INDEX IF NOT EXISTS conflict_reports_status_idx ON conflict_reports(status, created_at DESC);
CREATE INDEX IF NOT EXISTS incident_events_lookup_idx ON incident_events(incident_type, incident_id, created_at DESC);

-- Five fixed response teams. Team members are existing OFFICER/RESCUE user accounts.
CREATE TABLE IF NOT EXISTS response_teams (
  id SMALLINT PRIMARY KEY CHECK (id BETWEEN 1 AND 5),
  name TEXT NOT NULL UNIQUE,
  latitude NUMERIC(9,6), longitude NUMERIC(9,6),
  status TEXT NOT NULL DEFAULT 'AVAILABLE' CHECK (status IN ('AVAILABLE','BUSY','OFFLINE')),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
INSERT INTO response_teams(id,name) VALUES
  (1,'Team 1'),(2,'Team 2'),(3,'Team 3'),(4,'Team 4'),(5,'Team 5')
ON CONFLICT (id) DO NOTHING;
CREATE TABLE IF NOT EXISTS response_team_members (
  team_id SMALLINT NOT NULL REFERENCES response_teams(id) ON DELETE CASCADE,
  user_id BIGINT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
  joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY(team_id,user_id)
);
ALTER TABLE fire_reports ADD COLUMN IF NOT EXISTS assigned_team_id SMALLINT REFERENCES response_teams(id);
ALTER TABLE conflict_reports ADD COLUMN IF NOT EXISTS assigned_team_id SMALLINT REFERENCES response_teams(id);
CREATE INDEX IF NOT EXISTS response_team_members_team_idx ON response_team_members(team_id);

-- Synopsis monitoring and eco-tourism modules.
ALTER TABLE conflict_reports ADD COLUMN IF NOT EXISTS is_demo BOOLEAN NOT NULL DEFAULT FALSE;
CREATE TABLE IF NOT EXISTS sensor_readings (
 id BIGSERIAL PRIMARY KEY, device_id TEXT NOT NULL, latitude DOUBLE PRECISION NOT NULL, longitude DOUBLE PRECISION NOT NULL,
 temperature DOUBLE PRECISION NOT NULL, humidity DOUBLE PRECISION NOT NULL, smoke DOUBLE PRECISION NOT NULL,
 alert BOOLEAN NOT NULL, is_demo BOOLEAN NOT NULL DEFAULT FALSE, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS sensor_device_time ON sensor_readings(device_id,created_at DESC);
CREATE TABLE IF NOT EXISTS monitoring_alerts (
 id BIGSERIAL PRIMARY KEY, device_id TEXT NOT NULL, incident_id BIGINT REFERENCES fire_reports(id), created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS wildlife_sightings (
 id BIGSERIAL PRIMARY KEY, species TEXT NOT NULL, latitude DOUBLE PRECISION NOT NULL, longitude DOUBLE PRECISION NOT NULL,
 is_demo BOOLEAN NOT NULL DEFAULT FALSE, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS forest_zones (
 id BIGSERIAL PRIMARY KEY, name TEXT NOT NULL UNIQUE, kind TEXT NOT NULL, coordinates JSONB NOT NULL, is_demo BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS tourism_routes (
 id BIGSERIAL PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', safety_notes TEXT NOT NULL DEFAULT '',
 coordinates JSONB NOT NULL, is_active BOOLEAN NOT NULL DEFAULT TRUE, is_demo BOOLEAN NOT NULL DEFAULT FALSE
);


-- A separate revocable login for each browser tab; only a hash is stored here.
CREATE TABLE IF NOT EXISTS auth_sessions (
 token_hash TEXT PRIMARY KEY,
 user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '12 hours'
);
CREATE INDEX IF NOT EXISTS auth_sessions_expiry_idx ON auth_sessions(expires_at);


CREATE TABLE IF NOT EXISTS report_images (
 id TEXT PRIMARY KEY,
 uploaded_by BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 data BYTEA NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


ALTER TABLE response_teams ADD COLUMN IF NOT EXISTS location_updated_at TIMESTAMPTZ;
CREATE TABLE IF NOT EXISTS notifications (
 id BIGSERIAL PRIMARY KEY,
 user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 incident_type TEXT NOT NULL CHECK(incident_type IN ('fire','conflict')),
 incident_id BIGINT NOT NULL,
 title TEXT NOT NULL,body TEXT NOT NULL,
 push_enabled BOOLEAN NOT NULL DEFAULT TRUE,
 read_at TIMESTAMPTZ,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 UNIQUE(user_id,incident_type,incident_id)
);
CREATE TABLE IF NOT EXISTS push_devices (
 id BIGSERIAL PRIMARY KEY,user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 token TEXT NOT NULL UNIQUE,session_hash TEXT NOT NULL REFERENCES auth_sessions(token_hash) ON DELETE CASCADE,
 enabled BOOLEAN NOT NULL DEFAULT TRUE,updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS push_deliveries (
 id BIGSERIAL PRIMARY KEY,notification_id BIGINT NOT NULL REFERENCES notifications(id) ON DELETE CASCADE,
 device_id BIGINT NOT NULL REFERENCES push_devices(id) ON DELETE CASCADE,
 status TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING','SENDING','RETRY','SENT','FAILED','CANCELLED')),
 attempts INTEGER NOT NULL DEFAULT 0,next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 lease_until TIMESTAMPTZ,sent_at TIMESTAMPTZ,last_error TEXT,provider_message_id TEXT,
 UNIQUE(notification_id,device_id)
);
CREATE INDEX IF NOT EXISTS notifications_user_idx ON notifications(user_id,created_at DESC);
CREATE INDEX IF NOT EXISTS deliveries_pending_idx ON push_deliveries(status,next_attempt_at);
