CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    role VARCHAR(20) NOT NULL DEFAULT 'EMPLOYEE',
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_users_role
        CHECK (role IN ('EMPLOYEE', 'ADMIN')),

    CONSTRAINT chk_users_status
        CHECK (status IN ('ACTIVE', 'INACTIVE'))
);

CREATE TABLE offices (
    office_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    address VARCHAR(500) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',

    CONSTRAINT chk_offices_status
        CHECK (status IN ('ACTIVE', 'INACTIVE'))
);

CREATE TABLE rooms (
    room_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    office_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    floor INTEGER NOT NULL,
    capacity INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    photo_url VARCHAR(1000),

    CONSTRAINT fk_rooms_office
        FOREIGN KEY (office_id)
        REFERENCES offices(office_id),

    CONSTRAINT uq_rooms_office_name
        UNIQUE (office_id, name),

    CONSTRAINT chk_rooms_capacity
        CHECK (capacity > 0),

    CONSTRAINT chk_rooms_status
        CHECK (status IN ('ACTIVE', 'INACTIVE'))
);

CREATE TABLE equipment (
    equipment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE
);

CREATE TABLE room_equipment (
    room_id UUID NOT NULL,
    equipment_id UUID NOT NULL,

    PRIMARY KEY (room_id, equipment_id),

    CONSTRAINT fk_room_equipment_room
        FOREIGN KEY (room_id)
        REFERENCES rooms(room_id),

    CONSTRAINT fk_room_equipment_equipment
        FOREIGN KEY (equipment_id)
        REFERENCES equipment(equipment_id)
);

CREATE TABLE bookings (
    booking_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    room_id UUID NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    cancelled_at TIMESTAMPTZ,
    cancelled_by UUID,

    CONSTRAINT fk_bookings_user
        FOREIGN KEY (user_id)
        REFERENCES users(user_id),

    CONSTRAINT fk_bookings_room
        FOREIGN KEY (room_id)
        REFERENCES rooms(room_id),

    CONSTRAINT fk_bookings_cancelled_by
        FOREIGN KEY (cancelled_by)
        REFERENCES users(user_id),

    CONSTRAINT chk_bookings_status
        CHECK (status IN ('ACTIVE', 'CANCELLED', 'COMPLETED')),

    CONSTRAINT chk_bookings_time_order
        CHECK (end_time > start_time),

    CONSTRAINT chk_bookings_min_duration
        CHECK (end_time - start_time >= INTERVAL '15 minutes'),

    CONSTRAINT chk_bookings_max_duration
        CHECK (end_time - start_time <= INTERVAL '4 hours')
);

ALTER TABLE bookings
ADD CONSTRAINT no_overlapping_active_bookings
EXCLUDE USING gist (
    room_id WITH =,
    tstzrange(start_time, end_time, '[)') WITH &&
)
WHERE (status = 'ACTIVE');

CREATE TABLE audit_log (
    audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_user_id UUID NOT NULL,
    booking_id UUID,
    action VARCHAR(100) NOT NULL,
    details JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_audit_actor
        FOREIGN KEY (actor_user_id)
        REFERENCES users(user_id),

    CONSTRAINT fk_audit_booking
        FOREIGN KEY (booking_id)
        REFERENCES bookings(booking_id)
);

CREATE TABLE outbox_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_type VARCHAR(100) NOT NULL,
    aggregate_id UUID NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    retry_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMPTZ,

    CONSTRAINT chk_outbox_status
        CHECK (status IN ('PENDING', 'PUBLISHED', 'FAILED')),

    CONSTRAINT chk_outbox_retry_count
        CHECK (retry_count >= 0)
);