INSERT INTO users (employee_id, name, email, role, status)
VALUES
('EMP1001', 'Иван Петров', 'ivan.petrov@company.ru', 'EMPLOYEE', 'ACTIVE'),
('EMP1002', 'Анна Смирнова', 'anna.smirnova@company.ru', 'EMPLOYEE', 'ACTIVE'),
('EMP1003', 'Дмитрий Волков', 'dmitry.volkov@company.ru', 'EMPLOYEE', 'ACTIVE'),
('ADM1001', 'Мария Соколова', 'maria.sokolova@company.ru', 'ADMIN', 'ACTIVE');

INSERT INTO offices (name, address, status)
VALUES
('Москва — Центральный офис', 'Москва, Пресненская набережная, 10', 'ACTIVE'),
('Москва — Северный офис', 'Москва, Ленинградское шоссе, 16А', 'ACTIVE');

INSERT INTO rooms (office_id, name, floor, capacity, status)
SELECT office_id, 'Orion', 5, 8, 'ACTIVE'
FROM offices
WHERE name = 'Москва — Центральный офис';

INSERT INTO rooms (office_id, name, floor, capacity, status)
SELECT office_id, 'Vega', 5, 12, 'ACTIVE'
FROM offices
WHERE name = 'Москва — Центральный офис';

INSERT INTO rooms (office_id, name, floor, capacity, status)
SELECT office_id, 'Atlas', 7, 20, 'ACTIVE'
FROM offices
WHERE name = 'Москва — Центральный офис';

INSERT INTO rooms (office_id, name, floor, capacity, status)
SELECT office_id, 'Polaris', 3, 6, 'ACTIVE'
FROM offices
WHERE name = 'Москва — Северный офис';

INSERT INTO equipment (name)
VALUES
('TV'),
('Projector'),
('Videoconference'),
('Whiteboard');

INSERT INTO room_equipment (room_id, equipment_id)
SELECT r.room_id, e.equipment_id
FROM rooms r
CROSS JOIN equipment e
WHERE r.name = 'Orion'
  AND e.name IN ('TV', 'Videoconference', 'Whiteboard');

INSERT INTO room_equipment (room_id, equipment_id)
SELECT r.room_id, e.equipment_id
FROM rooms r
CROSS JOIN equipment e
WHERE r.name = 'Vega'
  AND e.name IN ('TV', 'Projector', 'Whiteboard');

INSERT INTO room_equipment (room_id, equipment_id)
SELECT r.room_id, e.equipment_id
FROM rooms r
CROSS JOIN equipment e
WHERE r.name = 'Atlas'
  AND e.name IN ('TV', 'Projector', 'Videoconference', 'Whiteboard');

INSERT INTO room_equipment (room_id, equipment_id)
SELECT r.room_id, e.equipment_id
FROM rooms r
CROSS JOIN equipment e
WHERE r.name = 'Polaris'
  AND e.name IN ('TV', 'Whiteboard');

INSERT INTO bookings (user_id, room_id, start_time, end_time)
SELECT
    u.user_id,
    r.room_id,
    TIMESTAMPTZ '2026-09-28 10:00:00+03',
    TIMESTAMPTZ '2026-09-28 11:00:00+03'
FROM users u
JOIN rooms r ON r.name = 'Orion'
WHERE u.employee_id = 'EMP1001';

INSERT INTO bookings (user_id, room_id, start_time, end_time)
SELECT
    u.user_id,
    r.room_id,
    TIMESTAMPTZ '2026-09-28 11:00:00+03',
    TIMESTAMPTZ '2026-09-28 12:00:00+03'
FROM users u
JOIN rooms r ON r.name = 'Orion'
WHERE u.employee_id = 'EMP1002';

INSERT INTO bookings (user_id, room_id, start_time, end_time)
SELECT
    u.user_id,
    r.room_id,
    TIMESTAMPTZ '2026-09-28 13:00:00+03',
    TIMESTAMPTZ '2026-09-28 14:30:00+03'
FROM users u
JOIN rooms r ON r.name = 'Vega'
WHERE u.employee_id = 'EMP1003';

INSERT INTO bookings (user_id, room_id, start_time, end_time)
SELECT
    u.user_id,
    r.room_id,
    TIMESTAMPTZ '2026-09-29 09:00:00+03',
    TIMESTAMPTZ '2026-09-29 11:00:00+03'
FROM users u
JOIN rooms r ON r.name = 'Atlas'
WHERE u.employee_id = 'EMP1001';