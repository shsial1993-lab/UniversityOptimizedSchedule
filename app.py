import io
from pathlib import Path

import pandas as pd
import streamlit as st
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from scheduler import solve_timetable, validate_schedule
from pdf_report import build_teacher_pdf

st.set_page_config(page_title="UniOptiSchedule", page_icon="🗓️", layout="wide")
st.title("🗓️ UniOptiSchedule")
st.caption("Faculty-aware, explainable university timetable optimization")

DATA = Path(__file__).parent / "data"


def load_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA / name)


def upload_or_sample(name: str) -> pd.DataFrame:
    uploaded = st.sidebar.file_uploader(f"Upload {name}", type=["csv", "xlsx"], key=name)
    if uploaded is None:
        return load_csv(name + ".csv")
    return pd.read_excel(uploaded) if uploaded.name.endswith("xlsx") else pd.read_csv(uploaded)


def create_beautiful_report(schedule: pd.DataFrame, teacher_scores: pd.DataFrame, rooms: pd.DataFrame) -> bytes:
    """Create a polished multi-sheet Excel quality report."""
    output = io.BytesIO()
    navy = "17365D"
    green = "E2F0D9"
    orange = "FCE4D6"
    thin_gray = Side(style="thin", color="D9E1F2")
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary = pd.DataFrame({
            "Metric": ["Generated timetable", "Scheduled periods", "Teachers", "Sections", "Rooms", "Average teacher satisfaction", "Hard conflicts"],
            "Value": [pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), len(schedule), len(teacher_scores), schedule.section_id.nunique(), len(rooms), f"{teacher_scores['preference_satisfaction_%'].mean():.1f}%", 0],
        })
        summary.to_excel(writer, sheet_name="Executive Summary", index=False, startrow=2)
        schedule.to_excel(writer, sheet_name="Master Timetable", index=False)
        teacher_scores.to_excel(writer, sheet_name="Teacher Satisfaction", index=False)
        room_report = schedule.groupby("room_id", as_index=False).agg(assigned_periods=("slot", "count"), courses=("course_id", "nunique"))
        rooms.merge(room_report, on="room_id", how="left").fillna(0).to_excel(writer, sheet_name="Room Utilization", index=False)
        for sheet_name, worksheet in writer.sheets.items():
            worksheet.freeze_panes = "A4" if sheet_name == "Executive Summary" else "A2"
            worksheet.auto_filter.ref = worksheet.dimensions
            if sheet_name == "Executive Summary":
                worksheet["A1"] = "UniOptiSchedule - Timetable Quality Report"
                worksheet["A1"].font = Font(size=18, bold=True, color="FFFFFF")
                worksheet["A1"].fill = PatternFill("solid", fgColor=navy)
                worksheet.merge_cells("A1:B1")
            header_row = 3 if sheet_name == "Executive Summary" else 1
            for cell in worksheet[header_row]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor=navy)
                cell.alignment = Alignment(horizontal="center", vertical="center")
            for row in worksheet.iter_rows():
                for cell in row:
                    cell.border = Border(bottom=thin_gray)
                    cell.alignment = Alignment(vertical="center", wrap_text=True)
            for col_idx, column_cells in enumerate(worksheet.columns, start=1):
                width = min(max(max(len(str(c.value or "")) for c in column_cells) + 2, 12), 32)
                worksheet.column_dimensions[get_column_letter(col_idx)].width = width
            worksheet.row_dimensions[header_row].height = 28
        sat_ws = writer.sheets["Teacher Satisfaction"]
        for row in range(2, sat_ws.max_row + 1):
            value = float(sat_ws.cell(row, 5).value or 0)
            sat_ws.cell(row, 5).fill = PatternFill("solid", fgColor=green if value >= 80 else orange)
        master_ws = writer.sheets["Master Timetable"]
        satisfaction_col = list(schedule.columns).index("teacher_satisfaction_%") + 1
        for row in range(2, master_ws.max_row + 1):
            value = float(master_ws.cell(row, satisfaction_col).value or 0)
            master_ws.cell(row, satisfaction_col).fill = PatternFill("solid", fgColor=green if value >= 80 else orange)
    return output.getvalue()


st.sidebar.header("Data sources")
teachers = upload_or_sample("teachers")
sections = upload_or_sample("sections")
rooms = upload_or_sample("rooms")
courses = upload_or_sample("courses")
time_limit = st.sidebar.slider("Solver time limit (seconds)", 5, 120, 20)

with st.expander("Current input summary"):
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Teachers", len(teachers))
    c2.metric("Sections", len(sections))
    c3.metric("Courses", len(courses))
    c4.metric("Rooms", len(rooms))

if st.button("🚀 Generate optimized timetable", type="primary"):
    with st.spinner("Optimizing hard constraints and teacher preferences..."):
        result = solve_timetable(teachers, sections, rooms, courses, time_limit)
    st.session_state["result"] = result

result = st.session_state.get("result")
if result is None:
    st.info("Load the sample data or upload your university CSV files, then generate a timetable.")
    st.stop()

schedule = result.schedule
errors = result.conflicts + validate_schedule(schedule)
if errors:
    st.error("; ".join(errors))
else:
    st.success(f"Feasible timetable generated with objective score {result.objective}.")

if not schedule.empty:
    a, b, c = st.columns(3)
    a.metric("Scheduled periods", len(schedule))
    b.metric("Hard conflicts", len(errors))
    c.metric("Average teacher satisfaction", f"{result.teacher_scores['preference_satisfaction_%'].mean():.1f}%")

    tabs = st.tabs(["Master timetable", "Teacher view", "Section view", "Room view", "Fairness report"])
    with tabs[0]:
        st.dataframe(schedule, use_container_width=True, hide_index=True)
    with tabs[1]:
        selected = st.selectbox("Teacher", sorted(schedule.teacher_name.unique()))
        st.dataframe(schedule[schedule.teacher_name == selected], use_container_width=True, hide_index=True)
    with tabs[2]:
        selected = st.selectbox("Section", sorted(schedule.section_id.unique()))
        st.dataframe(schedule[schedule.section_id == selected], use_container_width=True, hide_index=True)
    with tabs[3]:
        selected = st.selectbox("Room", sorted(schedule.room_id.unique()))
        st.dataframe(schedule[schedule.room_id == selected], use_container_width=True, hide_index=True)
    with tabs[4]:
        st.dataframe(result.teacher_scores, use_container_width=True, hide_index=True)

    report = create_beautiful_report(schedule, result.teacher_scores, rooms)
    st.download_button("⬇️ Download beautiful quality report", report, "UniOptiSchedule_quality_report.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    pdf = build_teacher_pdf(schedule, result.teacher_scores)
    st.download_button("📄 Download teacher-wise PDF timetable", pdf, "UniOptiSchedule_teacher_timetables.pdf", "application/pdf")
