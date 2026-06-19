"""A single editor/preview tab used by the epy_slides window.

The left pane is a plain-text Markdown editor; the right pane is a live
reveal.js preview rendered from the same source by
:func:`epy_slides.renderer.render_revealjs`. Slide and content blocks are
inserted through small dialogs that drop Markdown snippets at the caret.
"""

from __future__ import annotations

import contextlib
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QMarginsF, QSizeF, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QFont,
    QFontDatabase,
    QPageLayout,
    QPageSize,
    QTextCursor,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QInputDialog,
    QPlainTextEdit,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from epy_slides import snippets
from epy_slides.checklist_dialog import ChecklistDialog
from epy_slides.equation_dialog import EquationDialog
from epy_slides.figure_dialog import FigureDialog
from epy_slides.renderer import render_revealjs
from epy_slides.slide_dialogs import (
    BulletListDialog,
    NewSlideDialog,
    QuoteDialog,
    SpeakerNotesDialog,
    TwoColumnDialog,
)
from epy_slides.table_dialog import TableDialog

RENDER_DEBOUNCE_MS = 250
UNTITLED = "untitled.md"

# Export readiness poll (reveal init + MathJax typeset) before giving up.
_EXPORT_TIMEOUT_MS = 60_000
_EXPORT_POLL_MS = 100

# Reads the slide reveal is showing so the next preview render can return to
# it (see ``_RESTORE_FN`` in template.py). Returns "" before reveal exists.
_CAPTURE_POS_JS = (
    "(function () {"
    "  try {"
    "    var d = window._epyDeck;"
    "    if (d && d.getIndices) {"
    "      var i = d.getIndices();"
    "      return 'epypos=v:' + (i.h || 0) + '.' + (i.v || 0);"
    "    }"
    "  } catch (e) {}"
    "  return '';"
    "})()"
)


def next_label_suffix(text: str, kind: str) -> str:
    """Return the next sequential integer suffix for ``kind`` labels.

    Scans Quarto labels of the given kind in ``text`` (``fig`` / ``tbl`` /
    ``eq``) and returns ``str(max + 1)``, or ``"1"`` when none exist. Kept
    module-level so it is unit-testable without a widget instance.
    """
    labels = snippets.find_labels(text)
    prefix = f"{kind}-"
    ints = [
        int(label.name[len(prefix):])
        for label in labels
        if label.kind == kind and label.name[len(prefix):].isdigit()
    ]
    return str(max(ints) + 1) if ints else "1"


class MarkdownTab(QWidget):
    """Editor + live reveal.js preview for one slide-deck buffer.

    Signals:
        pathChanged: Emitted when the on-disk path is set or changed.
        dirtyChanged: Emitted with the new dirty flag when it flips.
    """

    pathChanged = Signal()  # noqa: N815 (Qt signal naming convention)
    dirtyChanged = Signal(bool)  # noqa: N815 (Qt signal naming)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the editor, the web preview and the debounce timer."""
        super().__init__(parent)

        self._path: Path | None = None
        self._dirty = False
        self._suppress_change = False
        self._theme_css: str = ""

        self.editor = QPlainTextEdit(self)
        self._setup_editor()

        self.view = QWebEngineView(self)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self.editor)
        splitter.addWidget(self.view)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([480, 640])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(RENDER_DEBOUNCE_MS)
        self._render_timer.timeout.connect(self._render_scheduled)

        self.editor.textChanged.connect(self._on_text_changed)

    def _setup_editor(self) -> None:
        """Configure the editor with a monospace font and 4-space tabs."""
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        if font.pointSize() < 1:
            font = QFont("Consolas")
        font.setPointSize(11)
        self.editor.setFont(font)
        metrics = self.editor.fontMetrics()
        self.editor.setTabStopDistance(4 * metrics.horizontalAdvance(" "))
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.editor.setPlaceholderText(
            "Write slides in Markdown. Separate slides with '## '. "
            "Preview updates on the right."
        )

    # ------------------------------------------------------------- API

    @property
    def path(self) -> Path | None:
        """Return the on-disk path, or ``None`` for unsaved buffers."""
        return self._path

    @property
    def dirty(self) -> bool:
        """Return ``True`` if the buffer has unsaved changes."""
        return self._dirty

    def title(self) -> str:
        """Return the tab title, suffixed with ``*`` when dirty."""
        base = self._path.name if self._path is not None else UNTITLED
        return f"{base} *" if self._dirty else base

    def text(self) -> str:
        """Return the current editor text."""
        return self.editor.toPlainText()

    def set_initial_text(self, text: str, path: Path | None = None) -> None:
        """Populate the buffer from disk or a template, then render."""
        self._suppress_change = True
        self.editor.setPlainText(text)
        self._suppress_change = False
        self._path = path
        self._set_dirty(False)
        self._render_now()
        self.pathChanged.emit()

    def load_file(self, path: Path) -> None:
        """Load a Markdown file from disk into this tab."""
        text = path.read_text(encoding="utf-8")
        self.set_initial_text(text, path)

    def save(self) -> bool:
        """Save the buffer to its current path (False if no path yet)."""
        if self._path is None:
            return False
        self._path.write_text(self.editor.toPlainText(), encoding="utf-8")
        self._set_dirty(False)
        return True

    def save_as(self, path: Path) -> None:
        """Save the buffer to ``path`` and adopt it as the current path."""
        path.write_text(self.editor.toPlainText(), encoding="utf-8")
        self._path = path
        self._set_dirty(False)
        self.pathChanged.emit()
        self._render_now()

    def reload(self) -> None:
        """Reload the buffer from disk, discarding in-memory changes."""
        if self._path is None:
            return
        self.load_file(self._path)

    def set_theme_css(self, css: str) -> None:
        """Update the preview's reveal theme CSS and re-render."""
        self._theme_css = css
        # Same deck, only the theme changed — keep the current slide.
        self._render_now(preserve=True)

    # --------------------------------------------------- slide blocks

    def _insert_block(self, md: str) -> None:
        """Insert a multi-line block at the caret on its own line."""
        cursor = self.editor.textCursor()
        if cursor.positionInBlock() != 0:
            cursor.insertText("\n")
        cursor.insertText(md if md.endswith("\n") else md + "\n")
        self.editor.setFocus()

    def insert_new_slide(self) -> None:
        """Open the layout picker and insert the chosen slide skeleton."""
        dialog = NewSlideDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._insert_block(dialog.build_markdown())

    def insert_slide_break(self) -> None:
        """Insert a manual blank slide break (``---``)."""
        self._insert_block("\n---\n")

    def insert_bullet_list(self) -> None:
        """Open the bullet-list dialog and insert the list."""
        dialog = BulletListDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._insert_block(dialog.build_markdown())

    def insert_speaker_notes(self) -> None:
        """Open the speaker-notes dialog and insert the notes block."""
        dialog = SpeakerNotesDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._insert_block(dialog.build_markdown())

    def insert_two_column(self) -> None:
        """Open the two-column dialog and insert the columns block."""
        dialog = TwoColumnDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._insert_block(dialog.build_markdown())

    def insert_quote(self) -> None:
        """Open the quote dialog and insert the blockquote."""
        dialog = QuoteDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._insert_block(dialog.build_markdown())

    def insert_diagram(self, engine: str = "mermaid") -> None:
        """Insert a diagram code block (Mermaid or nomnoml) at the caret."""
        skeletons = {
            "mermaid": (
                "```mermaid\nflowchart LR\n"
                "  A[Start] --> B[Build] --> C[Ship]\n```"
            ),
            "nomnoml": (
                "```nomnoml\n[First] -> [Second]\n[Second] -> [Third]\n```"
            ),
        }
        self._insert_block(skeletons.get(engine, skeletons["mermaid"]))

    # --------------------------------------------- reused content blocks

    def _next_label_suffix(self, kind: str) -> str:
        """Return the next sequential integer suffix for ``kind``."""
        return next_label_suffix(self.editor.toPlainText(), kind)

    def insert_figure(self) -> None:
        """Open FigureDialog; insert figure Markdown on accept."""
        dialog = FigureDialog(self, default_id=self._next_label_suffix("fig"))
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._insert_block(dialog.build_markdown())

    def insert_table(self) -> None:
        """Open TableDialog; insert a pipe table with caption."""
        dialog = TableDialog(self, default_id=self._next_label_suffix("tbl"))
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._insert_block(dialog.build_markdown())

    def insert_equation(self) -> None:
        """Open EquationDialog; insert a display equation on accept."""
        dialog = EquationDialog(self, default_id=self._next_label_suffix("eq"))
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._insert_block(dialog.build_markdown())

    def insert_checklist(self) -> None:
        """Open ChecklistDialog; insert task-list items at the caret."""
        dialog = ChecklistDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        cursor = self.editor.textCursor()
        cursor.insertText(dialog.build_markdown())
        self.editor.setFocus()

    def insert_code_block(self) -> None:
        """Insert a fenced Python code-block skeleton."""
        self._insert_template(snippets.CODE_BLOCK_TEMPLATE, "CODE")

    def insert_callout(self, kind: str = "note") -> None:
        """Insert a Quarto fenced callout, prompting for a title if needed."""
        template = snippets.CALLOUT_TEMPLATES.get(
            kind, snippets.CALLOUT_TEMPLATES["note"]
        )
        if "TITLE" in template:
            title, ok = QInputDialog.getText(
                self, "Callout title", "Title:", text=kind.title()
            )
            if ok and title:
                template = template.replace("TITLE", title)
        token = "TITLE" if "TITLE" in template else "BODY"
        self._insert_template(template, token)

    def insert_image_from_dialog(self) -> None:
        """Pick an image file, copy it to ``figures/`` and insert it."""
        start_dir = str(self._path.parent) if self._path is not None else ""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Insert image",
            start_dir,
            "Images (*.png *.jpg *.jpeg *.gif *.svg *.webp *.bmp)"
            ";;All files (*)",
        )
        if not filename:
            return
        src = Path(filename)
        figures_dir = (
            self._path.parent / "figures"
            if self._path is not None
            else Path.cwd() / "figures"
        )
        figures_dir.mkdir(parents=True, exist_ok=True)
        dst = figures_dir / src.name
        counter = 1
        while dst.exists():
            dst = figures_dir / f"{src.stem}-{counter}{src.suffix}"
            counter += 1
        shutil.copy2(str(src), str(dst))
        rel = (
            dst.relative_to(self._path.parent)
            if self._path is not None
            else dst
        )
        md_path = str(rel).replace("\\", "/")
        caption, ok = QInputDialog.getText(
            self, "Image caption", "Caption:", text=src.stem
        )
        caption = (caption or src.stem) if ok else src.stem
        width, ok = QInputDialog.getText(
            self, "Image width", "Width (e.g. 70%, 300px):", text="70%"
        )
        if not ok or not width.strip():
            width = "70%"
        md = f"![{caption}]({md_path}){{width={width}}}"
        self._insert_block(md)

    # ----------------------------------------------- text formatting

    def toggle_bold(self) -> None:
        """Wrap the current selection (or caret) in ``**...**``."""
        self._wrap_selection("**", "**", placeholder="bold")

    def toggle_italic(self) -> None:
        """Wrap the current selection (or caret) in ``*...*``."""
        self._wrap_selection("*", "*", placeholder="italic")

    def toggle_inline_code(self) -> None:
        """Wrap the current selection (or caret) in ``` `...` ```."""
        self._wrap_selection("`", "`", placeholder="code")

    def set_heading_level(self, level: int) -> None:
        """Replace the current line's heading prefix with ``level``."""
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.movePosition(
            QTextCursor.MoveOperation.EndOfBlock,
            QTextCursor.MoveMode.KeepAnchor,
        )
        line = cursor.selectedText()
        stripped = line.lstrip("#").lstrip(" ")
        if level <= 0:
            new_line = stripped
        else:
            level = max(1, min(level, 6))
            prefix = "#" * level
            new_line = f"{prefix} {stripped}" if stripped else f"{prefix} "
        cursor.insertText(new_line)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()

    def insert_link(self) -> None:
        """Insert ``[text](url)``; uses the current selection as text."""
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            text = cursor.selectedText()
            cursor.insertText(f"[{text}](URL)")
        else:
            self._insert_template(snippets.LINK_TEMPLATE, "TEXT")
        self.editor.setFocus()

    # ----------------------------------------------------- PDF export

    def export_pdf(
        self,
        target: Path,
        on_done: Callable[[Path, bool], None] | None = None,
    ) -> None:
        """Export the deck to ``target`` as a PDF via reveal's print mode.

        Renders an export deck, loads it with the ``?print-pdf`` query so
        reveal lays one slide per page, waits for reveal init and MathJax,
        prints with a slide-sized landscape page (zero margins), then
        stamps PDF metadata (including the copyright notice) and the
        optional grayscale watermark before delivering the file.

        Args:
            target: Destination ``.pdf`` path.
            on_done: Optional callback ``(target, ok)`` invoked when the
                export finishes (success or failure).
        """
        text = self.editor.toPlainText()
        meta = snippets.parse_front_matter(text)
        base_dir = self._path.parent if self._path is not None else None
        title = self._path.name if self._path is not None else UNTITLED

        width_in, height_in = self._slide_inches(meta)
        author = meta.get("author", "").strip()
        rights = meta.get("copyright", "").strip()
        if not rights and author:
            year = meta.get("date", "")[:4].strip()
            rights = f"© {year} {author}" if year.isdigit() else f"© {author}"

        watermark_path: Path | None = None
        watermark = meta.get("watermark", "").strip()
        if watermark:
            candidate = Path(watermark)
            if not candidate.is_absolute() and base_dir is not None:
                candidate = base_dir / watermark
            if candidate.is_file():
                watermark_path = candidate

        export_html = render_revealjs(
            text,
            base_dir=base_dir,
            title=title,
            theme_css=self._theme_css,
            for_export=True,
        )

        tmp_dir = Path(tempfile.mkdtemp(prefix="epy_slides_pdf_"))
        html_file = tmp_dir / "deck.html"
        out_pdf = tmp_dir / "export.pdf"
        html_file.write_text(export_html, encoding="utf-8")

        def finalize(ok: bool) -> None:
            result_ok = ok
            try:
                if ok:
                    from epy_slides import _pdf_footer  # noqa: PLC0415

                    if watermark_path is not None:
                        with contextlib.suppress(OSError, RuntimeError):
                            _pdf_footer.add_watermark(out_pdf, watermark_path)
                    _pdf_footer.add_metadata(
                        out_pdf,
                        title=meta.get("title", "").strip() or title,
                        author=author,
                        subject=meta.get("subtitle", "").strip(),
                        keywords=meta.get("keywords", "").strip(),
                        rights=rights,
                    )
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(out_pdf), str(target))
            except (OSError, RuntimeError):
                result_ok = False
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                self._render_now()
            if on_done is not None:
                on_done(target, result_ok)

        def do_print() -> None:
            self.view.page().pdfPrintingFinished.connect(
                lambda _p, ok: finalize(ok),
                Qt.ConnectionType.SingleShotConnection,
            )
            self.view.page().printToPdf(
                str(out_pdf), self._slide_page_layout(width_in, height_in)
            )

        def on_loaded(ok: bool) -> None:
            if not ok:
                finalize(False)
                return
            self._wait_for_export_ready(do_print)

        self.view.loadFinished.connect(
            on_loaded, Qt.ConnectionType.SingleShotConnection
        )
        url = QUrl.fromLocalFile(str(html_file.resolve()))
        url.setQuery("print-pdf")
        self.view.load(url)

    @staticmethod
    def _slide_inches(meta: dict[str, str]) -> tuple[float, float]:
        """Return the slide page size in inches for the deck aspect ratio."""
        aspect = (meta.get("aspect-ratio") or "16:9").strip()
        return (10.0, 7.5) if aspect == "4:3" else (13.333, 7.5)

    @staticmethod
    def _slide_page_layout(width_in: float, height_in: float) -> QPageLayout:
        """Return a slide-sized, zero-margin page layout (one slide/page).

        The size is given already landscape-shaped (``width_in`` >
        ``height_in``); Qt keeps a custom :class:`QPageSize` verbatim under
        ``Portrait`` orientation, whereas ``Landscape`` would swap it back
        to portrait. So Portrait is what yields the wide slide page.
        """
        size = QPageSize(
            QSizeF(width_in, height_in),
            QPageSize.Unit.Inch,
            "slide",
            QPageSize.SizeMatchPolicy.ExactMatch,
        )
        return QPageLayout(
            size,
            QPageLayout.Orientation.Portrait,
            QMarginsF(0.0, 0.0, 0.0, 0.0),
            QPageLayout.Unit.Inch,
        )

    def _wait_for_export_ready(self, then: Callable[[], None]) -> None:
        """Poll until reveal has initialised and MathJax has typeset."""
        elapsed = [0]

        def check() -> None:
            def handle(done: object) -> None:
                if done is True:
                    then()
                    return
                elapsed[0] += _EXPORT_POLL_MS
                if elapsed[0] >= _EXPORT_TIMEOUT_MS:
                    then()
                    return
                QTimer.singleShot(_EXPORT_POLL_MS, check)

            self.view.page().runJavaScript(
                "window._reveal_done === true && "
                "window._mathjax_done === true && "
                "window._diagrams_done === true",
                handle,
            )

        check()

    # -------------------------------------------- editor primitives

    def _wrap_selection(
        self, left: str, right: str, placeholder: str = ""
    ) -> None:
        """Wrap the selection in ``left``/``right`` or insert markers."""
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            text = cursor.selectedText()
            cursor.insertText(f"{left}{text}{right}")
        else:
            cursor.insertText(f"{left}{placeholder}{right}")
            end = cursor.position()
            cursor.setPosition(end - len(right) - len(placeholder))
            cursor.setPosition(
                end - len(right), QTextCursor.MoveMode.KeepAnchor
            )
            self.editor.setTextCursor(cursor)
        self.editor.setFocus()

    def _insert_template(self, template: str, select_token: str) -> None:
        """Insert ``template`` at the caret and select ``select_token``."""
        cursor = self.editor.textCursor()
        if "\n" in template and cursor.positionInBlock() != 0:
            cursor.insertText("\n")
        start = cursor.position()
        cursor.insertText(template)
        index = template.find(select_token)
        if index >= 0:
            cursor.setPosition(start + index)
            cursor.setPosition(
                start + index + len(select_token),
                QTextCursor.MoveMode.KeepAnchor,
            )
            self.editor.setTextCursor(cursor)
        self.editor.setFocus()

    # ----------------------------------------------------- internals

    def _set_dirty(self, value: bool) -> None:
        """Update the dirty flag and notify listeners on change."""
        if self._dirty != value:
            self._dirty = value
            self.dirtyChanged.emit(value)

    def _on_text_changed(self) -> None:
        """React to user edits: flag dirty and schedule a re-render."""
        if self._suppress_change:
            return
        if not self._dirty:
            self._set_dirty(True)
        self._render_timer.start()

    def _render_scheduled(self) -> None:
        """Debounced re-render after an edit; keeps the current slide."""
        self._render_now(preserve=True)

    def _render_now(self, *, preserve: bool = False) -> None:
        """Render the buffer into the preview via a temp ``file://`` URL.

        The deck embeds reveal.js and the ~2 MB MathJax bundle inline, so
        ``setHtml`` (capped at 2 MB) would truncate it; writing to a temp
        file and using ``view.load`` removes the cap. The ``<base href>``
        still points at the document directory so relative images resolve.

        When ``preserve`` is set (an edit or a theme change to the same
        deck), the slide reveal is currently showing is captured and
        re-applied after the reload, so the preview does not jump back to
        the first slide on every keystroke.
        """
        text = self.editor.toPlainText()
        base_dir = self._path.parent if self._path is not None else None
        title = self._path.name if self._path is not None else UNTITLED
        html = render_revealjs(
            text, base_dir=base_dir, title=title, theme_css=self._theme_css
        )
        if not hasattr(self, "_preview_tmp_dir"):
            self._preview_tmp_dir = Path(
                tempfile.mkdtemp(prefix="epy_slides_preview_")
            )
        preview_path = self._preview_tmp_dir / "preview.html"
        preview_path.write_text(html, encoding="utf-8")
        url = QUrl.fromLocalFile(str(preview_path.resolve()))
        if preserve:
            self.view.page().runJavaScript(
                _CAPTURE_POS_JS,
                lambda pos: self._load_preview(url, pos),
            )
        else:
            self._load_preview(url, None)

    def _load_preview(self, url: QUrl, pos: object) -> None:
        """Load ``url`` into the preview, optionally with a restore hash."""
        if isinstance(pos, str) and pos:
            url = QUrl(url)
            url.setFragment(pos)
        self.view.load(url)

    def cleanup_preview_tmp(self) -> None:
        """Delete the temp dir backing the live preview (call on close)."""
        tmp = getattr(self, "_preview_tmp_dir", None)
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)
            self._preview_tmp_dir = None
