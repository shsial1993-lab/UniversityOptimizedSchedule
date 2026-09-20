from __future__ import annotations

import io
from datetime import datetime

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas


PAGE_W, PAGE_H = landscape(A4)
NAVY = colors.HexColor("#10158F")
LAVENDER = colors.HexColor("#B7B6FF")
GRID = colors.HexColor("#202020")
DAY_NAMES = [("Monday", "Mo"), ("Tuesday", "Tu"), ("Wednesday", "We"), ("Thursday", "Th"), ("Friday", "Fr"), ("Saturday", "Sa")]
PERIODS = [
    "08:00-09:00", "09:00-10:00", "10:00-11:00", "11:00-12:00", "12:00-13:00", "13:00-14:00",
    "14:00-15:00", "15:00-16:00", "16:00-17:00", "17:00-18:00", "18:00-19:00", "19:00-20:00",
]


def _short_period(period: str) -> str:
    start, end = period.split("-")
    return f"{start}-{end}"


def _draw_centered(c: canvas.Canvas, text: str, x: float, y: float, width: float, font_size: float = 6.5, bold: bool = True):
    c.setFont("Helvetica-Bold" if bold else "Helvetica", font_size)
    c.drawCentredString(x + width / 2, y, str(text))


def _draw_cell_text(c: canvas.Canvas, values: list[str], x: float, y: float, width: float, height: float):
    c.setFillColor(colors.black)
    line_height = 8
    total = len(values) * line_height
    cursor = y + (height + total) / 2 - line_height + 1
    for value in values:
        _draw_centered(c, value, x, cursor, width, 6.2, True)
        cursor -= line_height


def build_teacher_pdf(schedule: pd.DataFrame, teacher_scores: pd.DataFrame, term: str = "FALL-26") -> bytes:
    """Create a teacher-wise landscape PDF similar to the supplied aSc timetable."""
    output = io.BytesIO()
    c = canvas.Canvas(output, pagesize=landscape(A4))
    teachers = list(schedule[["teacher_id", "teacher_name"]].drop_duplicates().itertuples(index=False, name=None))
    satisfaction = dict(zip(teacher_scores.teacher_id.astype(str), teacher_scores["preference_satisfaction_%"]))
    day_abbr = dict(DAY_NAMES)
    left, right, top = 30, 30, 465
    day_w = 62
    grid_w = PAGE_W - left - right
    time_w = (grid_w - day_w) / len(PERIODS)
    header_h, row_h = 39, 45

    for teacher_id, teacher_name in teachers:
        c.setFillColor(NAVY)
        c.roundRect(245, 530, 365, 38, 20, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(427, 542, str(teacher_name))
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 22)
        c.drawRightString(PAGE_W - 55, 544, term)
        score = satisfaction.get(str(teacher_id), 0)
        c.setFont("Helvetica-Bold", 8)
        c.drawRightString(PAGE_W - 55, 533, f"Teacher satisfaction: {score:.1f}%")

        x0, y0 = left, top - header_h - len(DAY_NAMES) * row_h
        c.setStrokeColor(GRID)
        c.setLineWidth(0.7)
        c.setFillColor(colors.white)
        c.rect(x0, y0, grid_w, header_h + len(DAY_NAMES) * row_h, fill=1, stroke=1)
        c.setFillColor(LAVENDER)
        c.roundRect(x0 + 7, y0 + 8, day_w - 14, len(DAY_NAMES) * row_h - 16, 18, fill=1, stroke=0)

        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 8)
        for idx, period in enumerate(PERIODS):
            px = x0 + day_w + idx * time_w
            c.line(px, y0, px, y0 + header_h + len(DAY_NAMES) * row_h)
            _draw_centered(c, str(idx + 1), px, top - 14, time_w, 8, True)
            _draw_centered(c, _short_period(period), px, top - 27, time_w, 5.2, True)
        c.line(x0 + day_w, y0, x0 + day_w, top)
        c.line(x0, top - header_h, x0 + grid_w, top - header_h)
        for day_idx, (day, short) in enumerate(DAY_NAMES):
            row_top = top - header_h - day_idx * row_h
            row_bottom = row_top - row_h
            c.line(x0, row_bottom, x0 + grid_w, row_bottom)
            _draw_centered(c, short, x0, row_bottom + row_h / 2 - 3, day_w, 16, False)

        teacher_rows = schedule[schedule.teacher_id.astype(str) == str(teacher_id)]
        for _, item in teacher_rows.iterrows():
            day = str(item.day)
            time = str(item.time)
            if day not in day_abbr or time not in PERIODS:
                continue
            day_idx = [name for name, _ in DAY_NAMES].index(day)
            period_idx = PERIODS.index(time)
            cell_x = x0 + day_w + period_idx * time_w
            cell_y = top - header_h - (day_idx + 1) * row_h
            c.setFillColor(colors.HexColor("#E8E7FF"))
            c.roundRect(cell_x + 2, cell_y + 2, time_w - 4, row_h - 4, 6, fill=1, stroke=0)
            lines = [str(item.section_id), str(item.course_id), str(item.course_name)[:22], str(item.room_id)]
            _draw_cell_text(c, lines, cell_x, cell_y, time_w, row_h)

        c.setFillColor(colors.black)
        c.setFont("Helvetica", 6)
        c.drawString(left, y0 - 7, f"Timetable generated: {datetime.now().strftime('%Y-%m-%d')}")
        c.drawRightString(PAGE_W - right, y0 - 7, "UniOptiSchedule")
        legend_y = 112
        c.setFillColor(LAVENDER)
        c.roundRect(left + 10, 27, PAGE_W - 2 * left - 20, 72, 28, fill=1, stroke=0)
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(left + 38, 82, "Subjects:")
        teacher_courses = teacher_rows[["course_id", "course_name"]].drop_duplicates()
        lx, ly = left + 38, 63
        for idx, item in enumerate(teacher_courses.itertuples(index=False)):
            c.setFont("Helvetica-Bold", 8)
            c.drawString(lx, ly, str(item.course_id))
            c.setFont("Helvetica", 8)
            c.drawString(lx + 65, ly, str(item.course_name))
            lx += 230
            if (idx + 1) % 3 == 0:
                lx, ly = left + 38, ly - 16
        c.showPage()
    c.save()
    return output.getvalue()
