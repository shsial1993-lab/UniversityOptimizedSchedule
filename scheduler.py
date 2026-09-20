from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import pandas as pd
from ortools.sat.python import cp_model


@dataclass
class SolveResult:
    schedule: pd.DataFrame
    conflicts: List[str]
    teacher_scores: pd.DataFrame
    objective: int


def slot_list() -> List[str]:
    periods = ["08:00-09:00", "09:00-10:00", "10:00-11:00", "11:00-12:00", "12:00-13:00", "13:00-14:00", "14:00-15:00", "15:00-16:00", "16:00-17:00", "17:00-18:00", "18:00-19:00", "19:00-20:00"]
    return [f"{day}|{period}" for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"] for period in periods]


def _split(value: object) -> set[str]:
    if pd.isna(value) or not str(value).strip():
        return set()
    return {item.strip() for item in str(value).split(";") if item.strip()}


def solve_timetable(teachers: pd.DataFrame, sections: pd.DataFrame, rooms: pd.DataFrame, courses: pd.DataFrame, time_limit: int = 20) -> SolveResult:
    slots = slot_list()
    model = cp_model.CpModel()
    courses = courses.reset_index(drop=True).copy()
    rooms = rooms.reset_index(drop=True).copy()
    variables: Dict[Tuple[int, int, int], cp_model.IntVar] = {}

    unavailable = {str(row.teacher_id): _split(row.unavailable_slots) for row in teachers.itertuples()}
    preferred = {str(row.teacher_id): _split(row.preferred_slots) for row in teachers.itertuples()}
    room_ids = rooms.room_id.astype(str).tolist()

    for ci, course in courses.iterrows():
        valid_slots = [s for s in slots if s not in unavailable.get(str(course.teacher_id), set())]
        for si, slot in enumerate(slots):
            for ri, room in rooms.iterrows():
                if slot in valid_slots and str(room.room_type).lower() in {str(course.room_type).lower(), "both", "any"} and int(room.capacity) >= int(course.enrollment):
                    variables[(ci, si, ri)] = model.NewBoolVar(f"x_{ci}_{si}_{ri}")

    for ci, course in courses.iterrows():
        options = [v for (c, _, _), v in variables.items() if c == ci]
        model.Add(sum(options) == int(course.periods_per_week)) if options else model.AddBoolOr([])

    for si, slot in enumerate(slots):
        for ri in range(len(rooms)):
            model.Add(sum(v for (c, s, r), v in variables.items() if s == si and r == ri) <= 1)
        for teacher_id in courses.teacher_id.astype(str).unique():
            model.Add(sum(v for (c, s, r), v in variables.items() if s == si and str(courses.iloc[c].teacher_id) == teacher_id) <= 1)
        for section_id in courses.section_id.astype(str).unique():
            model.Add(sum(v for (c, s, r), v in variables.items() if s == si and str(courses.iloc[c].section_id) == section_id) <= 1)

    preference_terms = []
    for (ci, si, ri), var in variables.items():
        teacher_id = str(courses.iloc[ci].teacher_id)
        if slots[si] in preferred.get(teacher_id, set()):
            preference_terms.append(var)
    model.Maximize(sum(preference_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return SolveResult(pd.DataFrame(), ["No feasible timetable exists with the current hard constraints."], pd.DataFrame(), 0)

    rows = []
    for (ci, si, ri), var in variables.items():
        if solver.Value(var):
            course = courses.iloc[ci]
            room = rooms.iloc[ri]
            rows.append({"slot": slots[si], "day": slots[si].split("|")[0], "time": slots[si].split("|")[1], "course_id": course.course_id, "course_name": course.course_name, "section_id": course.section_id, "teacher_id": course.teacher_id, "teacher_name": teachers.loc[teachers.teacher_id.astype(str) == str(course.teacher_id), "teacher_name"].iloc[0], "room_id": room.room_id})
    schedule = pd.DataFrame(rows).sort_values(["day", "time", "section_id"]).reset_index(drop=True)

    score_rows = []
    for teacher in teachers.itertuples():
        assigned = schedule[schedule.teacher_id.astype(str) == str(teacher.teacher_id)]
        pref = _split(teacher.preferred_slots)
        matched = sum(slot in pref for slot in assigned.slot) if pref else 0
        score_rows.append({"teacher_id": teacher.teacher_id, "teacher_name": teacher.teacher_name, "assigned_periods": len(assigned), "preferred_periods_matched": matched, "preference_satisfaction_%": round(100 * matched / len(assigned), 1) if len(assigned) else 100.0})
    teacher_scores = pd.DataFrame(score_rows)
    satisfaction = dict(zip(teacher_scores.teacher_id.astype(str), teacher_scores["preference_satisfaction_%"]))
    schedule["teacher_satisfaction_%"] = schedule.teacher_id.astype(str).map(satisfaction).fillna(0)
    return SolveResult(schedule, [], teacher_scores, int(solver.ObjectiveValue()))


def validate_schedule(schedule: pd.DataFrame) -> List[str]:
    if schedule.empty:
        return ["The timetable is empty."]
    errors = []
    for field, label in [("teacher_id", "teacher"), ("section_id", "section"), ("room_id", "room")]:
        dup = schedule[schedule.duplicated(["slot", field], keep=False)]
        if not dup.empty:
            errors.append(f"{label.title()} conflict detected in {len(dup)} allocation rows.")
    return errors
