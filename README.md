# Meeting Room Booking System

Portfolio project for designing and implementing an internal meeting room booking system.

The system allows employees to find available meeting rooms, create and manage bookings, while administrators can manage rooms, offices and bookings.

## Project Goal

Design a reliable internal web service that provides a single meeting room booking process and prevents conflicting reservations.

## Key Features

- Search available rooms by office, date and time
- Filter rooms by capacity and equipment
- Create meeting room bookings
- Modify existing bookings
- Cancel bookings
- View current and past bookings
- Prevent overlapping reservations
- Email notifications for booking events
- Administrative management of offices and rooms
- Basic booking and room utilization analytics

## Business Rules

- Minimum booking duration: 15 minutes
- Maximum booking duration: 4 hours
- Booking time step: 15 minutes
- Bookings can be created up to 30 days in advance
- Employees can modify or cancel a booking no later than 30 minutes before it starts
- Overlapping bookings for the same room are not allowed
- Administrators can manage bookings without the 30-minute restriction
- Email delivery failure does not affect the booking itself

## Project Artifacts

### BPMN

- Create Booking Process
- Modify Booking Process
- Cancel Booking Process

Source files are located in `docs/bpmn`.

### UML

- Use Case Diagram
- Create Booking Sequence Diagram
- Modify Booking Sequence Diagram
- Cancel Booking Sequence Diagram

PlantUML source files are located in `docs/uml`.

### Data Model

The project contains an ERD describing the main entities and their relationships.

PlantUML source: `docs/uml/ERD.puml`.

## Planned Technology Stack

- PostgreSQL
- FastAPI
- Python
- RabbitMQ
- OpenAPI / Swagger
- Postman
- PlantUML
- Camunda Modeler
- Git / GitHub

## Project Status

System analysis and design artifacts are completed.

Next stages include database implementation, API design, backend development and asynchronous email notifications.