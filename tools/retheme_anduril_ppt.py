from __future__ import annotations

import re
import sys
import math
from pathlib import Path

from pptx import Presentation
from pptx.enum.text import MSO_AUTO_SIZE, PP_ALIGN
from pptx.dml.color import RGBColor
from pptx.util import Pt, Inches


SRC_DEFAULT = Path("external/anduril-sdk介绍_原文仅排版修正版.pptx")
DST_DEFAULT = Path("external/anduril-sdk介绍_原文仅排版修正版.pptx")


TITLE_FONT = "SimHei"
BODY_FONT = "Microsoft YaHei"
EN_FONT = "Arial"

BG = "FFFFFF"
TEXT = "111111"
ACCENT = "E36C0A"
MUTED = "5A5A5A"


FONT_PLAN = {
    "sparse": {"title": 26, "subtitle": 20, "heading": 20, "body": 18, "table": 16, "breadcrumb": 16},
    "medium": {"title": 24, "subtitle": 18, "heading": 18, "body": 17, "table": 16, "breadcrumb": 16},
    "dense": {"title": 22, "subtitle": 18, "heading": 18, "body": 16, "table": 16, "breadcrumb": 16},
}


def slide_density(slide) -> str:
    chars = 0
    text_boxes = 0
    for sh in slide.shapes:
        if not getattr(sh, "has_text_frame", False) or is_numeric_badge(sh):
            continue
        text = "".join(p.text for p in sh.text_frame.paragraphs).strip()
        if text:
            chars += len(text)
            text_boxes += 1
    if chars <= 220 and text_boxes <= 18:
        return "sparse"
    if chars <= 420:
        return "medium"
    return "dense"


def is_numeric_badge(shape) -> bool:
    if not getattr(shape, "has_text_frame", False):
        return False
    text = "".join(p.text for p in shape.text_frame.paragraphs).strip()
    return bool(re.fullmatch(r"\d{1,3}", text)) and shape.left > Inches(11.0) and shape.top > Inches(6.5)


def is_top_title(shape) -> bool:
    if not getattr(shape, "has_text_frame", False):
        return False
    if is_numeric_badge(shape):
        return False
    text = " ".join(p.text.strip() for p in shape.text_frame.paragraphs if p.text.strip())
    if not text:
        return False
    return shape.top < Inches(1.4) and shape.width > Inches(5.0) and len(text) <= 50


def is_subtitle(shape) -> bool:
    if not getattr(shape, "has_text_frame", False):
        return False
    if is_numeric_badge(shape):
        return False
    text = " ".join(p.text.strip() for p in shape.text_frame.paragraphs if p.text.strip())
    if not text:
        return False
    return shape.top < Inches(2.1) and shape.width > Inches(6.0) and len(text) > 20 and not is_top_title(shape)


def classify_shape(shape, slide_idx: int) -> str | None:
    if is_numeric_badge(shape):
        return "badge"
    if not getattr(shape, "has_text_frame", False):
        return None
    text = " ".join(p.text.strip() for p in shape.text_frame.paragraphs if p.text.strip())
    if not text:
        return None
    if slide_idx in {3, 7, 22, 49} and shape.top < Inches(0.45) and shape.left < Inches(1.0) and re.match(r"^\d{2}\s+", text):
        return "breadcrumb"
    if slide_idx == 2 and re.match(r"^\d{2}\s+", text):
        return "heading"
    if is_top_title(shape):
        return "title"
    if is_subtitle(shape):
        return "subtitle"
    if len(text) <= 20:
        return "heading"
    return "body"


def _shape_text(shape) -> str:
    if not getattr(shape, "has_text_frame", False):
        return ""
    return "\n".join(p.text for p in shape.text_frame.paragraphs).strip()


def _est_lines(text: str, width_in: float, font_size: float) -> int:
    if not text:
        return 1
    # Heuristic tuned for Chinese business decks.
    chars_per_line = max(5, int((width_in * 72) / max(10.0, font_size) * 1.6))
    total = 0
    for paragraph in text.split("\n"):
        p = paragraph.strip()
        if not p:
            total += 1
            continue
        # Keep bullets from collapsing into one line.
        p = p.replace("•", "").strip()
        total += max(1, math.ceil(len(p) / chars_per_line))
    return total


def estimate_shape_height(shape, slide_mode: str) -> float:
    if hasattr(shape, "has_table") and shape.has_table:
        return shape.height.inches
    if not getattr(shape, "has_text_frame", False) or is_numeric_badge(shape):
        return shape.height.inches
    text = _shape_text(shape)
    if not text:
        return shape.height.inches
    sizes = [r.font.size.pt for p in shape.text_frame.paragraphs for r in p.runs if r.font.size]
    font_size = max(sizes) if sizes else FONT_PLAN[slide_mode]["body"]
    lines = _est_lines(text, max(0.8, shape.width.inches - 0.08), font_size)
    line_h = font_size * 1.28 / 72.0
    pad = 0.08 if font_size <= 18 else 0.12
    return max(shape.height.inches, lines * line_h + pad)


def x_overlap(a, b) -> float:
    ax1 = a.left.inches
    ax2 = ax1 + a.width.inches
    bx1 = b.left.inches
    bx2 = bx1 + b.width.inches
    inter = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    if inter <= 0:
        return 0.0
    return inter / max(0.01, min(a.width.inches, b.width.inches))


def reflow_slide(slide, slide_mode: str):
    shapes = []
    for sh in slide.shapes:
        if not getattr(sh, "has_text_frame", False) or is_numeric_badge(sh):
            continue
        if not _shape_text(sh):
            continue
        shapes.append(sh)

    shapes.sort(key=lambda s: (s.top.inches, s.left.inches))
    for i, sh in enumerate(shapes):
        desired_h = estimate_shape_height(sh, slide_mode)
        old_h = sh.height.inches
        if desired_h > old_h + 0.02:
            delta = desired_h - old_h
            sh.height = Inches(desired_h)
            bottom = sh.top.inches + desired_h
            for other in shapes[i + 1:]:
                if other.top.inches > 6.55:
                    continue
                if x_overlap(sh, other) >= 0.28 and other.top.inches < bottom + 0.05:
                    other.top = Inches(other.top.inches + delta)


def resize_table_rows(slide, slide_mode: str):
    for sh in slide.shapes:
        if not (hasattr(sh, "has_table") and sh.has_table):
            continue
        tbl = sh.table
        # Estimate each row based on the tallest cell.
        for r_idx, row in enumerate(tbl.rows):
            row_max = row.height.inches
            for c_idx, cell in enumerate(row.cells):
                text = cell.text_frame.text.strip()
                if not text:
                    continue
                sizes = [r.font.size.pt for p in cell.text_frame.paragraphs for r in p.runs if r.font.size]
                font_size = max(sizes) if sizes else FONT_PLAN[slide_mode]["table"]
                width_in = max(0.6, tbl.columns[c_idx].width.inches - 0.05)
                lines = _est_lines(text, width_in, font_size)
                need = lines * font_size * 1.24 / 72.0 + 0.08
                row_max = max(row_max, need)
            try:
                row.height = Inches(min(2.35, row_max))
            except Exception:
                pass


def set_run_font(run, *, size=None, name=None, bold=None, color=None):
    f = run.font
    if size is not None:
        f.size = Pt(size)
    if name is not None:
        f.name = name
    if bold is not None:
        f.bold = bold
    if color is not None:
        f.color.rgb = color if isinstance(color, RGBColor) else RGBColor.from_string(color)


def process_text_shape(shape, slide_idx: int, role: str = "body", slide_mode: str = "medium"):
    tf = shape.text_frame
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.NONE
    # Tighten margins a bit so larger font sizes have more usable space.
    tf.margin_left = Inches(0.05)
    tf.margin_right = Inches(0.05)
    tf.margin_top = Inches(0.03)
    tf.margin_bottom = Inches(0.03)

    text = " ".join(p.text.strip() for p in tf.paragraphs if p.text.strip())
    numeric_badge = is_numeric_badge(shape)
    if numeric_badge:
        for p in tf.paragraphs:
            for r in p.runs:
                set_run_font(r, size=8, name=BODY_FONT, bold=False, color=TEXT)
        return

    plan = FONT_PLAN[slide_mode]
    target = plan.get(role, plan["body"])

    # Expand boxes a little when we upscale text.
    current_sizes = [r.font.size.pt for p in tf.paragraphs for r in p.runs if r.font.size]
    current = max(current_sizes) if current_sizes else None
    grow_w = 1.0
    grow_h = 1.0
    if role in {"title", "subtitle", "heading", "body", "breadcrumb"} and (current is None or target > current):
        ratio = target / max(1.0, current or target)
        grow_h = min(1.35, 1.02 + max(0.0, ratio - 1.0) * 1.6)
        if len(text) > 20 and shape.width < Inches(7.0):
            grow_w = min(1.18, 1.0 + max(0.0, ratio - 1.0) * 0.55)
        elif len(text) > 10 and shape.width < Inches(4.8):
            grow_w = min(1.12, 1.0 + max(0.0, ratio - 1.0) * 0.45)

    if grow_w != 1.0 or grow_h != 1.0:
        shape.width = Inches(min(12.8, shape.width.inches * grow_w))
        shape.height = Inches(min(6.5, shape.height.inches * grow_h))

    for p in tf.paragraphs:
        p.alignment = PP_ALIGN.LEFT
        if hasattr(p, "line_spacing"):
            try:
                p.line_spacing = 1.05 if slide_mode == "dense" else 1.08
            except Exception:
                pass
        for r in p.runs:
            current = r.font.size.pt if r.font.size else None
            if role == "title":
                set_run_font(r, size=max(plan["title"], current or 0), name=TITLE_FONT, bold=True, color=TEXT)
            elif role == "subtitle":
                set_run_font(r, size=max(plan["subtitle"], current or 0), name=BODY_FONT, bold=False, color=TEXT)
            elif role == "breadcrumb":
                set_run_font(r, size=max(plan["breadcrumb"], current or 0), name=BODY_FONT, bold=True, color=TEXT)
            elif role == "heading":
                set_run_font(r, size=max(plan["heading"], current or 0), name=BODY_FONT, bold=True, color=TEXT)
            else:
                set_run_font(r, size=max(plan["body"], current or 0), name=BODY_FONT, bold=False, color=TEXT)


def adjust_page_number(slide, slide_number: int):
    for sh in slide.shapes:
        if not getattr(sh, "has_text_frame", False):
            continue
        text = "".join(p.text for p in sh.text_frame.paragraphs).strip()
        if re.fullmatch(r"\d{1,3}", text) and sh.left > Inches(11.0) and sh.top > Inches(6.5):
            # keep the existing page badge style, only update the number
            for p in sh.text_frame.paragraphs:
                for r in p.runs:
                    r.text = str(slide_number)
                    set_run_font(r, size=8, name=BODY_FONT, bold=False, color=TEXT)
            return


def add_or_update_title_style(slide):
    slide_mode = slide_density(slide)
    for sh in slide.shapes:
        if not getattr(sh, "has_text_frame", False):
            continue
        if is_numeric_badge(sh):
            continue
        text = " ".join(p.text.strip() for p in sh.text_frame.paragraphs if p.text.strip())
        if not text:
            continue
        role = classify_shape(sh, getattr(slide, "slide_id", 0))
        if role:
            process_text_shape(sh, getattr(slide, "slide_id", 0), role=role, slide_mode=slide_mode)


def set_slide_background(slide):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = RGBColor.from_string(BG)


def add_consistent_cover_style(slide):
    slide_mode = slide_density(slide)
    for sh in slide.shapes:
        if not getattr(sh, "has_text_frame", False):
            continue
        if is_numeric_badge(sh):
            continue
        text = " ".join(p.text.strip() for p in sh.text_frame.paragraphs if p.text.strip())
        if not text:
            continue
        role = classify_shape(sh, 1)
        if role:
            process_text_shape(sh, 1, role=role, slide_mode=slide_mode)


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else SRC_DEFAULT
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else DST_DEFAULT
    prs = Presentation(str(src))

    for idx, slide in enumerate(prs.slides, start=1):
        slide_mode = slide_density(slide)
        set_slide_background(slide)
        if idx == 1:
            add_consistent_cover_style(slide)
        else:
            add_or_update_title_style(slide)
        adjust_page_number(slide, idx)

        # Tables get a dedicated minimum font size and enough row height to match it.
        resize_table_rows(slide, slide_mode)
        for sh in slide.shapes:
            if hasattr(sh, "has_table") and sh.has_table:
                for row in sh.table.rows:
                    for cell in row.cells:
                        tf = cell.text_frame
                        tf.word_wrap = True
                        tf.auto_size = MSO_AUTO_SIZE.NONE
                        tf.margin_left = Inches(0.04)
                        tf.margin_right = Inches(0.04)
                        tf.margin_top = Inches(0.03)
                        tf.margin_bottom = Inches(0.03)
                        for p in tf.paragraphs:
                            p.alignment = PP_ALIGN.LEFT
                            for r in p.runs:
                                current = r.font.size.pt if r.font.size else 0
                                target = max(FONT_PLAN[slide_mode]["table"], current)
                                set_run_font(r, size=target, name=BODY_FONT, bold=False, color=TEXT)

        # Slide-specific tidying for the fake Lattice section.
        if idx in {59, 60, 61, 62}:
            for sh in slide.shapes:
                if not getattr(sh, "has_text_frame", False) or is_numeric_badge(sh):
                    continue
                text = " ".join(p.text.strip() for p in sh.text_frame.paragraphs if p.text.strip())
                if not text:
                    continue
                role = classify_shape(sh, idx)
                if role:
                    process_text_shape(sh, idx, role=role, slide_mode=slide_mode)
        if idx in {63, 64, 65}:
            # These are screenshot slides. Give the text a clean presentation and fix the page marker.
            for sh in slide.shapes:
                if not getattr(sh, "has_text_frame", False) or is_numeric_badge(sh):
                    continue
                role = classify_shape(sh, idx)
                if role:
                    process_text_shape(sh, idx, role=role, slide_mode=slide_mode)
                for p in sh.text_frame.paragraphs:
                    for r in p.runs:
                        if r.font.color and getattr(r.font.color, "rgb", None) is None:
                            r.font.color.rgb = RGBColor.from_string(TEXT)
            # Update the visible page badge to the actual slide number.
            adjust_page_number(slide, idx)

        # Finally, expand text boxes and push anything underneath them down if they collide.
        reflow_slide(slide, slide_mode)

    prs.save(str(dst))


if __name__ == "__main__":
    main()
