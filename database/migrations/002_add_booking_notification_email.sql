ALTER TABLE bookings
ADD COLUMN IF NOT EXISTS notification_email VARCHAR(320);

UPDATE bookings AS b
SET notification_email = u.email
FROM users AS u
WHERE b.user_id = u.user_id
  AND b.notification_email IS NULL;

ALTER TABLE bookings
ALTER COLUMN notification_email SET NOT NULL;
