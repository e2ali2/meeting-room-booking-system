# Edge Cases and Concurrency

## 1. Concurrent booking of the same room

### Scenario
Two employees attempt to book the same room for overlapping time intervals at approximately the same time.

### Expected behavior
Only one booking can be created successfully.

- First successfully committed request → `201 Created`
- Conflicting request → `409 Conflict`
- Error code → `ROOM_ALREADY_BOOKED`

The backend checks room availability before creating a booking.

Additionally, PostgreSQL enforces the `no_overlapping_active_bookings` exclusion constraint. This protects data integrity even if two concurrent requests both pass the initial availability check.

---

## 2. Adjacent bookings

Bookings whose boundaries only touch do not overlap.

Example:

- Booking A: 14:00–15:00
- Booking B: 15:00–16:00

Both bookings are allowed.

Booking intervals use `[start_time, end_time)` semantics.

---

## 3. Duplicate client request

### Scenario
A user clicks the booking button twice or repeats a request because the response from the first request was not received.

### Current protection
The database prevents creation of overlapping ACTIVE bookings for the same room.

A duplicate request may therefore receive:

`409 ROOM_ALREADY_BOOKED`

### Target solution
Support an `Idempotency-Key` for booking creation.

Repeated requests with the same key should be recognized as the same operation instead of creating another booking attempt.

---

## 4. Concurrent modification / Lost Update

### Scenario
The same booking is opened in two browser tabs.

The booking is modified and saved in the first tab. The second tab still contains an older version of the booking and attempts to save another change.

### Risk
The second request may overwrite newer data.

### Target solution
Use optimistic locking.

Example:

- Client reads booking with `version = 3`
- Another request updates it to `version = 4`
- Client attempts an update using `version = 3`
- Backend rejects the stale update with `409 Conflict`

The client must reload the current booking before attempting another update.

---

## 5. Modification to an unavailable room or time

If the target room or time interval is no longer available, the modification must fail.

The original booking remains unchanged.

Response:

`409 ROOM_ALREADY_BOOKED`

---

## 6. Cancellation and modification time boundary

An employee may modify or cancel an own booking only when at least 30 minutes remain before its start.

- Exactly 30 minutes before start → allowed
- Less than 30 minutes → rejected
- Administrator → not restricted by this rule

Possible errors:

- `BOOKING_MODIFICATION_TOO_LATE`
- `BOOKING_CANCELLATION_TOO_LATE`

---

## 7. Inactive room or office

New bookings cannot be created if:

- the room is INACTIVE;
- the office containing the room is INACTIVE.

Existing and historical bookings are retained.

---

## 8. Database failure before COMMIT

Booking creation and creation of the corresponding Outbox Event are performed in one database transaction.

If PostgreSQL fails before a successful COMMIT:

- Booking → not created
- Outbox Event → not created
- API → server error

The transaction is rolled back.

---

## 9. Backend failure after COMMIT

### Scenario
PostgreSQL successfully commits the Booking and Outbox Event, but the backend fails before the client receives `201 Created`.

### Result
The booking remains stored because the transaction has already been committed.

The client may incorrectly assume that the operation failed and repeat the request.

API idempotency is the target protection against this case.

---

## 10. RabbitMQ unavailable

RabbitMQ availability must not determine whether a booking can be created.

The backend stores:

- Booking
- Outbox Event with status `PENDING`

in the same PostgreSQL transaction.

If RabbitMQ is unavailable:

- Booking remains valid
- API may still return `201 Created`
- Outbox Event remains `PENDING`

After RabbitMQ becomes available, the Outbox Publisher can publish the pending event.

---

## 11. Email service unavailable

Failure to send an email does not cancel or roll back a booking.

Target notification flow:

1. Email Worker receives the event.
2. Email delivery fails.
3. The system retries delivery using retry/backoff.
4. After the retry limit is exceeded, the message is moved to a Dead Letter Queue.

The booking remains valid throughout this process.

### Prototype limitation
The current prototype demonstrates DLQ behavior but does not yet implement a full delayed retry/backoff mechanism.

---

## 12. Duplicate RabbitMQ delivery

RabbitMQ may redeliver an event when a consumer processes a message but fails before the broker receives an ACK.

Example:

1. Worker receives `BookingCreated`.
2. Email is sent.
3. Worker fails before ACK.
4. RabbitMQ delivers the event again.

This can result in duplicate email notifications.

### Target solution
Use `event_id` for consumer-side deduplication.

A persistent processed-events store can be used to determine whether an event has already been processed.

Absolute exactly-once delivery of an external email is not guaranteed because email delivery and the application's database transaction are separate operations.

---

## 13. Notification event consistency

A booking and its Outbox Event must be created atomically.

Valid states:

- Booking + Outbox Event committed
- Neither committed

The system should avoid the inconsistent state:

- Booking committed
- Notification event missing

This is the purpose of the Transactional Outbox pattern.

---

## 14. Booking time edge cases

The backend validates the following rules:

- booking cannot start in the past;
- minimum duration is 15 minutes;
- maximum duration is 4 hours;
- start and end times use a 15-minute step;
- booking cannot cross a calendar-day boundary;
- booking cannot be created more than 30 calendar days in advance.

---

## 15. Authorization edge cases

An employee may modify or cancel only his own bookings.

Changing a `booking_id` in an API request must not allow access to another employee's protected operations.

Administrators may manage bookings according to the administrator role permissions.

Authorization must be enforced by the backend rather than only by the frontend.

---

## Current Prototype vs Target Solution

The current prototype already implements:

- database-level protection against overlapping ACTIVE bookings;
- booking validation;
- employee modification/cancellation restrictions;
- Transactional Outbox;
- RabbitMQ event delivery;
- email notifications;
- DLQ routing;
- persistence of PENDING events while RabbitMQ is unavailable.

Target improvements include:

- API `Idempotency-Key`;
- optimistic locking for concurrent updates;
- persistent consumer deduplication using `event_id`;
- retry with backoff before DLQ;
- production corporate authentication.
