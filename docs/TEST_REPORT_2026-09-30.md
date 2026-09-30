# Meeting Room Booking System — Full Test Report

Date: 2026-09-30
Environment: local FastAPI + PostgreSQL + RabbitMQ, Demo Auth
Frontend: Chromium in-app browser, desktop and 375×812 mobile viewport

## Executive summary

- Automated API/business-rule checks: **50**
- Passed after notification-email implementation: **50**
- Failed after remediation: **0**
- UI scenarios: passed on desktop and mobile, no browser console errors
- Temporary QA data: removed by exact test UUIDs
- PostgreSQL transactional outbox: verified
- Email delivery end-to-end: topology fixed and RabbitMQ reachable; SMTP delivery remains environment-dependent

The core booking workflow, authorization, conflict prevention and administrative CRUD are operational. All reproducible API failures found during this test cycle were fixed and the full 50-test suite passed on rerun.

## Remediation result

The defects below were discovered during the initial run and fixed in the same test cycle:

- availability search now validates reversed/past/out-of-range intervals with the booking time rules;
- Admin booking `status`, `office_id` and `date` filters are applied server-side;
- RabbitMQ exchange, queue bindings and DLQ are declared consistently by publisher and worker;
- static OpenAPI was regenerated from the FastAPI runtime schema;
- “Ближайшие бронирования” now contains only future ACTIVE bookings and is sorted chronologically.

Final regression result: **50/50 passed**.

Additional notification-email regression coverage:

- visitor-selected email is normalized and stored with the booking;
- invalid email is rejected with `422`;
- `BookingCreated`, `BookingUpdated` and `BookingCancelled` events carry the intended recipient;
- changing the notification email updates the booking and subsequent events;
- existing bookings are safely backfilled from the owner email.

## Defects discovered and fixed

### MRBS-TEST-001 — Availability search accepts a reversed interval

Severity: High
Endpoint: `GET /api/v1/rooms/available`

Status: Fixed and covered by regression test.

Request with `end_time < start_time` returns `200 OK` instead of `400` with an invalid-time error. This can show rooms as available for an impossible interval. The booking creation endpoint correctly rejects invalid intervals, so database integrity is protected, but the search contract and UX are inconsistent.

Expected: `400 INVALID_BOOKING_TIME`
Actual: `200 OK`

### MRBS-TEST-002 — Admin booking filters are ignored by the API

Severity: Medium
Endpoint: `GET /api/v1/admin/bookings?status=CANCELLED`

Status: Fixed; `status`, `office_id` and `date` are now applied server-side.

The endpoint returns bookings of every status. The static OpenAPI specification advertises `status`, `office_id` and `date` filters, but the implementation does not accept or apply them. The current frontend performs only client-side status/search filtering after downloading the entire booking list.

Expected: every returned item has `status=CANCELLED`
Actual: unfiltered list returned

### MRBS-TEST-003 — Notification topology is incomplete in code

Severity: High

Status: Fixed with the versioned `email.notifications.v2` queue, three routing-key bindings and `email.notifications.v2.dlq`. RabbitMQ topology declaration was executed successfully. Real SMTP delivery still requires a configured SMTP sandbox/service.

RabbitMQ is reachable on port 5672, and booking/outbox atomicity is working. However:

- the publisher declares `booking.events` and publishes routing keys;
- the email worker declares `email.notifications`;
- no `queue_bind` connects that queue to the exchange;
- no dead-letter exchange/queue arguments are declared;
- no retry/backoff implementation is present;
- local SMTP is unavailable on the tested environment.

Unless RabbitMQ topology is provisioned externally, published events will not reach the email worker. The README currently describes Email Worker/DLQ as implemented more strongly than the repository code demonstrates.

### MRBS-TEST-004 — Static OpenAPI is behind the runtime API

Severity: Medium

Status: Fixed; the static specification was regenerated from FastAPI runtime OpenAPI. Route drift after regeneration: none.

Runtime routes missing from `docs/api/openapi.yaml`:

- `/health`
- `/bookings/me`
- `/admin/users`
- `/admin/equipment/{equipment_id}`
- `/admin/rooms/{room_id}/equipment`

Additional contract drift:

- static analytics contract requires `date_from/date_to`, runtime does not;
- static admin booking filters are documented but not implemented;
- several static response wrappers differ from actual array responses.

### MRBS-TEST-005 — “Upcoming bookings” table can contain past ACTIVE records

Severity: Low/Medium

Status: Fixed in the dashboard query; only future ACTIVE bookings are displayed and they are ordered chronologically.

The dashboard table filters by `status == ACTIVE` but not by `start_time >= now`. Past seed records that remain ACTIVE are displayed in the “Ближайшие бронирования” table and included in the active status chart. A lifecycle job or query-time time filter is needed for consistent analytics.

## Passed business-rule checks

- minimum duration of 15 minutes;
- maximum duration of 4 hours;
- 15-minute time step;
- timezone is required;
- booking cannot start in the past;
- booking cannot cross a calendar day;
- booking cannot be created more than 30 days ahead;
- overlapping ACTIVE booking is rejected with `409 ROOM_ALREADY_BOOKED`;
- adjacent bookings are allowed;
- concurrent overlapping requests produce exactly one `201` and one `409`;
- rejected modification leaves the original booking unchanged;
- busy room is excluded from availability;
- employee can create, modify and cancel an own booking;
- repeated cancellation is rejected;
- employee cannot view, modify or cancel another employee’s booking;
- employee modification/cancellation under 30 minutes is rejected;
- administrator may cancel under 30 minutes;
- inactive room rejects new bookings;
- inactive office rejects new bookings;
- cancelled bookings remain in history;
- unknown room and booking return `404`;
- booking and `BookingCreated` outbox event are committed together;
- administrative mutations create audit records.

The “exactly 30 minutes before start is allowed” boundary was confirmed by code inspection (`< 30 minutes`, not `<=`). A deterministic clock-injected automated test is still recommended.

## Passed functional checks

### Employee

- Demo Auth employee login;
- office, capacity and equipment search filters;
- room equipment rendering;
- booking creation form;
- booking modification form;
- cancellation confirmation;
- upcoming/history tabs and empty state;
- custom date picker limited to today + 30 days;
- 96 selectable daily time slots in 15-minute increments.

### Administrator

- Demo Auth administrator login;
- employee access to admin API denied;
- all-bookings view includes owner, room and office;
- office creation/update/status management;
- room creation/update/status management;
- equipment creation and room assignment;
- analytics counters returned;
- audit log entries written.

### UI and responsive behavior

- landing page and both role entries;
- desktop employee/admin navigation;
- mobile layout at 375×812;
- mobile sidebar opening and closing;
- search form and room cards;
- date/time picker fits mobile viewport;
- admin statistics and management tables;
- loading, empty, error and confirmation components are present;
- no browser console warnings or errors during tested flows.

## Environment and cleanup

- PostgreSQL: available and used by all integration scenarios.
- RabbitMQ port 5672: available.
- Local SMTP port 1025: unavailable.
- Test offices, rooms, equipment, room-equipment links, bookings, outbox events and related audit records were removed using their exact generated identifiers.
- Verification after cleanup found zero `QA Office`, `QA Room` or `QA Equipment` records.

## Remaining recommendations

1. Verify real email delivery with a safe SMTP sandbox configured for the environment.
2. Add retry/backoff before DLQ if required beyond the current direct dead-letter behavior.
3. Introduce automatic `COMPLETED` lifecycle handling for past ACTIVE bookings.
4. Add a committed automated integration suite with an isolated test database and injectable clock.
