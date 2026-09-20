# UniOptiSchedule

An explainable university timetable optimizer that combines teacher preferences, room capacity, class requirements, and conflict-free scheduling.

## Features

- Conflict-free scheduling for teachers, sections, and rooms
- Teacher unavailable slots and preferred slots
- Room capacity validation
- Workload and preference satisfaction scores
- Section-, teacher-, and room-wise timetable views
- CSV upload support
- Beautiful Excel quality report with teacher satisfaction and room utilization
- Teacher-wise landscape A4 PDF matching the supplied timetable style
- Repair-friendly optimization model using OR-Tools CP-SAT

## Quick start

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

The sample data is loaded automatically. Replace the CSV files in `data/` or upload your own files from the sidebar.

## Input files

Required columns are shown in the sample CSV files:

- `teachers.csv`: teacher_id, teacher_name, unavailable_slots, preferred_slots
- `sections.csv`: section_id, program, semester, size
- `rooms.csv`: room_id, capacity, room_type
- `courses.csv`: course_id, course_name, section_id, teacher_id, periods_per_week, room_type

Slots use the format `Monday|08:00-09:00`. Multiple slots are separated by semicolons.

## Project structure

```text
app.py              Streamlit dashboard
scheduler.py        CP-SAT optimization and validation engine
data/               Sample university data
requirements.txt    Python dependencies
```

## Important design decision

This is an optimization system rather than a black-box prediction model. Hard constraints are never intentionally violated, while soft constraints are scored and optimized. This makes the generated timetable explainable to the university administration.

## Production roadmap

1. Add PostgreSQL and role-based login.
2. Add faculty preference submission and HOD approval.
3. Add timetable version history and audit logs.
4. Add incremental repair when a teacher, room, or course changes.
5. Deploy privately on the university server.
