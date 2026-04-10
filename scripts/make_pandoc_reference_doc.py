#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml.ns import qn
from docx.shared import Inches, Pt


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    REPO_ROOT / "docs/reports/aims5790_pandoc_reference_template_20260409.docx"
)


def _set_font(style, *, size: int, bold: bool = False, italic: bool = False) -> None:
    style.font.name = "Times New Roman"
    style.font.size = Pt(size)
    style.font.bold = bold
    style.font.italic = italic
    # Keep East Asian font consistent when Word falls back.
    style.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")


def _configure_paragraph_format(
    style,
    *,
    before: int = 0,
    after: int = 0,
    line_spacing: float | None = None,
    keep_with_next: bool | None = None,
    page_break_before: bool | None = None,
    first_line_indent: float | None = None,
) -> None:
    fmt = style.paragraph_format
    fmt.space_before = Pt(before)
    fmt.space_after = Pt(after)
    if line_spacing is not None:
        fmt.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
        fmt.line_spacing = line_spacing
    if keep_with_next is not None:
        fmt.keep_with_next = keep_with_next
    if page_break_before is not None:
        fmt.page_break_before = page_break_before
    if first_line_indent is not None:
        fmt.first_line_indent = Inches(first_line_indent)


def _get_style(doc: Document, name: str):
    for style in doc.styles:
        if style.name == name:
            return style
    return doc.styles[name]


def build_reference_doc(output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        default_doc = Path(tmpdir) / "reference.docx"
        with default_doc.open("wb") as handle:
            subprocess.run(
                ["pandoc", "--print-default-data-file", "reference.docx"],
                check=True,
                stdout=handle,
            )

        doc = Document(default_doc)

        section = doc.sections[0]
        section.page_width = Inches(8.27)
        section.page_height = Inches(11.69)
        section.start_type = WD_SECTION_START.NEW_PAGE
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

        normal = _get_style(doc, "Normal")
        _set_font(normal, size=12)
        _configure_paragraph_format(
            normal,
            before=0,
            after=6,
            line_spacing=1.5,
            first_line_indent=0.0,
        )

        title = _get_style(doc, "Title")
        _set_font(title, size=16, bold=True)
        title.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _configure_paragraph_format(title, before=0, after=12, line_spacing=1.15)

        subtitle = _get_style(doc, "Subtitle")
        _set_font(subtitle, size=12)
        subtitle.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _configure_paragraph_format(subtitle, before=0, after=12, line_spacing=1.15)

        heading1 = _get_style(doc, "Heading 1")
        _set_font(heading1, size=14, bold=True)
        _configure_paragraph_format(
            heading1,
            before=12,
            after=6,
            line_spacing=1.15,
            keep_with_next=True,
        )

        heading2 = _get_style(doc, "Heading 2")
        _set_font(heading2, size=13, bold=True)
        _configure_paragraph_format(
            heading2,
            before=12,
            after=6,
            line_spacing=1.15,
            keep_with_next=True,
        )

        heading3 = _get_style(doc, "Heading 3")
        _set_font(heading3, size=12, bold=True)
        _configure_paragraph_format(
            heading3,
            before=10,
            after=4,
            line_spacing=1.15,
            keep_with_next=True,
        )

        block_text = _get_style(doc, "Block Text")
        _set_font(block_text, size=11)
        _configure_paragraph_format(block_text, before=0, after=6, line_spacing=1.2)

        caption = _get_style(doc, "Caption")
        _set_font(caption, size=10)
        caption.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _configure_paragraph_format(caption, before=6, after=6, line_spacing=1.0)

        try:
            quote = _get_style(doc, "Quote")
        except KeyError:
            quote = None
        if quote is not None:
            _set_font(quote, size=11, italic=True)
            _configure_paragraph_format(quote, before=0, after=6, line_spacing=1.2)

        # Keep the document otherwise empty; pandoc will reuse only layout/styles.
        for paragraph in list(doc.paragraphs):
            p = paragraph._element
            p.getparent().remove(p)

        doc.save(output_path)


def main() -> int:
    output_path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_OUTPUT
    build_reference_doc(output_path)
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
