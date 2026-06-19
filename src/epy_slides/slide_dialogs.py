"""Dialogs that build slide skeletons and presentation content blocks.

Every dialog follows the same contract as the reused epy_mdr dialogs: it
collects a few fields and exposes ``build_markdown()`` returning the
Markdown snippet the editor drops at the caret. Layout skeletons use plain
uppercase tokens (``TITLE``, ``IMAGE``…) replaced verbatim, so the
fenced-div braces (``{.columns}``) are never confused with format fields.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from epy_slides import _i18n as i18n

# (id, label, one-line description) for the New-Slide picker. ``title`` is
# omitted — the title slide is generated from the presentation properties.
LAYOUT_INFO: list[tuple[str, str, str]] = [
    ("section", "Section divider", "A big centred section title."),
    ("title-content", "Title + bullets", "A heading with a bullet list."),
    ("two-column", "Two columns", "Two side-by-side content columns."),
    ("comparison", "Comparison", "Two labelled columns to compare."),
    ("image-caption", "Image + caption", "A centred image with a caption."),
    ("image-fullbleed", "Full-bleed image", "An edge-to-edge image."),
    ("quote", "Quote", "A large centred quotation."),
    ("code", "Code", "A syntax-highlighted code block."),
    ("blank", "Blank", "An empty slide to fill freely."),
    ("big-stat", "Big numbers", "A row of large key figures."),
    ("agenda", "Agenda", "A numbered agenda / outline."),
    ("cards", "Cards", "A grid of titled cards."),
    ("timeline", "Timeline", "A vertical timeline of milestones."),
    ("image-left", "Image left", "Image left, content right."),
    ("image-right", "Image right", "Content left, image right."),
    ("quote-portrait", "Quote + portrait", "A quote beside a portrait."),
]

# Skeletons use bare tokens replaced with str.replace (NOT str.format) so
# the ``{.columns}`` braces survive untouched.
SLIDE_SKELETONS: dict[str, str] = {
    "section": "## TITLE\n<!-- layout: section -->\n",
    "title-content": (
        "## TITLE\n<!-- layout: title-content -->\n\n"
        "- First point\n- Second point\n- Third point\n"
    ),
    "two-column": (
        "## TITLE\n<!-- layout: two-column -->\n\n"
        ":::: {.columns}\n"
        '::: {.column width="50%"}\n'
        "Left column\n"
        ":::\n"
        '::: {.column width="50%"}\n'
        "Right column\n"
        ":::\n"
        "::::\n"
    ),
    "comparison": (
        "## TITLE\n<!-- layout: comparison -->\n\n"
        ":::: {.columns}\n"
        '::: {.column width="50%"}\n'
        "**Option A**\n\n- Pro\n- Con\n"
        ":::\n"
        '::: {.column width="50%"}\n'
        "**Option B**\n\n- Pro\n- Con\n"
        ":::\n"
        "::::\n"
    ),
    "image-caption": (
        "## TITLE\n<!-- layout: image-caption -->\n\n"
        "![CAPTION](IMAGE){width=70%}\n"
    ),
    "image-fullbleed": (
        '## TITLE {background-image="IMAGE"}\n'
        "<!-- layout: image-fullbleed -->\n"
    ),
    "quote": (
        "## TITLE\n<!-- layout: quote -->\n\n"
        "> Your quotation goes here.\n>\n> — Attribution\n"
    ),
    "code": (
        "## TITLE\n<!-- layout: code -->\n\n"
        "```python\ncode_here()\n```\n"
    ),
    "blank": "## TITLE\n<!-- layout: blank -->\n",
    "big-stat": (
        "## TITLE\n<!-- layout: big-stat -->\n\n"
        ":::: {.stats}\n"
        "::: {.stat}\n**42%**\n\n[first metric]{.stat-label}\n:::\n"
        "::: {.stat}\n**1931**\n\n[second metric]{.stat-label}\n:::\n"
        "::: {.stat}\n**381 m**\n\n[third metric]{.stat-label}\n:::\n"
        "::::\n"
    ),
    "agenda": (
        "## Agenda\n<!-- layout: agenda -->\n\n"
        "::: {.agenda}\n- First topic\n- Second topic\n- Third topic\n:::\n"
    ),
    "cards": (
        "## TITLE\n<!-- layout: cards -->\n\n"
        ":::: {.cards}\n"
        "::: {.card}\n#### Card one\n\nShort description.\n:::\n"
        "::: {.card}\n#### Card two\n\nShort description.\n:::\n"
        "::: {.card}\n#### Card three\n\nShort description.\n:::\n"
        "::::\n"
    ),
    "timeline": (
        "## TITLE\n<!-- layout: timeline -->\n\n"
        "::: {.timeline}\n"
        "- **1929** — Excavation begins\n"
        "- **1930** — Steel frame rises\n"
        "- **1931** — Opening day\n"
        ":::\n"
    ),
    "image-left": (
        "## TITLE\n<!-- layout: image-left -->\n\n"
        ":::: {.columns}\n"
        '::: {.column width="42%"}\n![](IMAGE)\n:::\n'
        '::: {.column width="58%"}\n- Point one\n- Point two\n:::\n'
        "::::\n"
    ),
    "image-right": (
        "## TITLE\n<!-- layout: image-right -->\n\n"
        ":::: {.columns}\n"
        '::: {.column width="58%"}\n- Point one\n- Point two\n:::\n'
        '::: {.column width="42%"}\n![](IMAGE)\n:::\n'
        "::::\n"
    ),
    "quote-portrait": (
        "## TITLE\n<!-- layout: quote-portrait -->\n\n"
        ":::: {.columns}\n"
        '::: {.column width="32%"}\n![](IMAGE)\n:::\n'
        '::: {.column width="68%"}\n'
        "> The quotation goes here.\n>\n> — Attribution\n:::\n"
        "::::\n"
    ),
}

# Layouts that take an image path + caption in the New-Slide dialog.
_IMAGE_LAYOUTS = {
    "image-caption", "image-fullbleed",
    "image-left", "image-right", "quote-portrait",
}


class NewSlideDialog(QDialog):
    """Pick a predefined layout and build its slide skeleton."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the layout picker with a title and optional image."""
        super().__init__(parent)
        self.setWindowTitle("New slide")
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Choose a slide layout:"))

        self._list = QListWidget(self)
        for layout_id, label, description in LAYOUT_INFO:
            item = QListWidgetItem(
                f"{i18n.tr(label)}  —  {i18n.tr(description)}"
            )
            item.setData(0x0100, layout_id)  # Qt.UserRole
            self._list.addItem(item)
        self._list.setCurrentRow(1)  # title + bullets
        self._list.currentRowChanged.connect(self._on_layout_changed)
        layout.addWidget(self._list)

        form = QFormLayout()
        self._title = QLineEdit(self)
        self._title.setText("Slide title")
        form.addRow("Title:", self._title)

        self._image = QLineEdit(self)
        self._image.setPlaceholderText("figures/image.png")
        self._browse = QPushButton("Browse…", self)
        self._browse.clicked.connect(self._pick_image)
        image_row = QHBoxLayout()
        image_row.addWidget(self._image)
        image_row.addWidget(self._browse)
        self._image_widget = QWidget(self)
        self._image_widget.setLayout(image_row)
        form.addRow("Image:", self._image_widget)

        self._caption = QLineEdit(self)
        self._caption.setPlaceholderText("Caption")
        form.addRow("Caption:", self._caption)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._on_layout_changed(self._list.currentRow())
        i18n.translate_widget(self)

    def _pick_image(self) -> None:
        """Pick an image file and store its path."""
        from PySide6.QtWidgets import QFileDialog  # noqa: PLC0415

        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Choose image",
            "",
            "Images (*.png *.jpg *.jpeg *.gif *.svg *.webp *.bmp)"
            ";;All files (*)",
        )
        if filename:
            self._image.setText(filename)

    def selected_layout(self) -> str:
        """Return the chosen layout id."""
        item = self._list.currentItem()
        return item.data(0x0100) if item is not None else "title-content"

    def _on_layout_changed(self, _row: int) -> None:
        """Enable the image fields only for image layouts."""
        is_image = self.selected_layout() in _IMAGE_LAYOUTS
        self._image_widget.setEnabled(is_image)
        self._caption.setEnabled(is_image)

    def build_markdown(self) -> str:
        """Return the slide skeleton for the chosen layout."""
        layout_id = self.selected_layout()
        skeleton = SLIDE_SKELETONS[layout_id]
        title = self._title.text().strip() or "Slide title"
        image = self._image.text().strip() or "figures/image.png"
        caption = self._caption.text().strip() or "Caption"
        md = skeleton.replace("TITLE", title)
        md = md.replace("CAPTION", caption)
        md = md.replace("IMAGE", image)
        return "\n" + md + "\n"


class BulletListDialog(QDialog):
    """Insert a bullet list, optionally revealed incrementally."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the item count + incremental/ordered options."""
        super().__init__(parent)
        self.setWindowTitle("Bullet list")

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._count = QSpinBox(self)
        self._count.setRange(1, 20)
        self._count.setValue(3)
        form.addRow("Items:", self._count)
        self._ordered = QCheckBox("Numbered list", self)
        form.addRow("", self._ordered)
        self._incremental = QCheckBox("Reveal one at a time", self)
        form.addRow("", self._incremental)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        i18n.translate_widget(self)

    def build_markdown(self) -> str:
        """Return the bullet-list Markdown, wrapped if incremental."""
        count = self._count.value()
        ordered = self._ordered.isChecked()
        items = [
            (f"{i + 1}. " if ordered else "- ") + f"Item {i + 1}"
            for i in range(count)
        ]
        body = "\n".join(items)
        if self._incremental.isChecked():
            body = f"::: {{.incremental}}\n{body}\n:::"
        return "\n" + body + "\n"


class SpeakerNotesDialog(QDialog):
    """Insert speaker notes shown only in the presenter view / PowerPoint."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the notes text area."""
        super().__init__(parent)
        self.setWindowTitle("Speaker notes")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Speaker notes (hidden on the slide):"))
        self._text = QPlainTextEdit(self)
        self._text.setPlaceholderText("Notes for the presenter…")
        layout.addWidget(self._text)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        i18n.translate_widget(self)

    def build_markdown(self) -> str:
        """Return the ``::: {.notes}`` block."""
        body = self._text.toPlainText().strip() or "Speaker notes."
        return f"\n::: {{.notes}}\n{body}\n:::\n"


class TwoColumnDialog(QDialog):
    """Insert a two-column block with an adjustable split."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the left/right content and split fields."""
        super().__init__(parent)
        self.setWindowTitle("Two columns")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._left = QLineEdit(self)
        self._left.setText("Left column")
        form.addRow("Left:", self._left)
        self._right = QLineEdit(self)
        self._right.setText("Right column")
        form.addRow("Right:", self._right)
        self._split = QSpinBox(self)
        self._split.setRange(20, 80)
        self._split.setValue(50)
        self._split.setSuffix(" %")
        form.addRow("Left width:", self._split)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        i18n.translate_widget(self)

    def build_markdown(self) -> str:
        """Return the ``.columns`` / ``.column`` block."""
        left_w = self._split.value()
        right_w = 100 - left_w
        left = self._left.text().strip() or "Left column"
        right = self._right.text().strip() or "Right column"
        return (
            "\n:::: {.columns}\n"
            f'::: {{.column width="{left_w}%"}}\n{left}\n:::\n'
            f'::: {{.column width="{right_w}%"}}\n{right}\n:::\n'
            "::::\n"
        )


class QuoteDialog(QDialog):
    """Insert a blockquote with an optional attribution."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the quote and attribution fields."""
        super().__init__(parent)
        self.setWindowTitle("Quote")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Quotation:"))
        self._quote = QPlainTextEdit(self)
        self._quote.setPlaceholderText("The quotation…")
        layout.addWidget(self._quote)
        form = QFormLayout()
        self._attribution = QLineEdit(self)
        self._attribution.setPlaceholderText("Author, Source")
        form.addRow("Attribution:", self._attribution)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        i18n.translate_widget(self)

    def build_markdown(self) -> str:
        """Return the blockquote with an em-dash attribution line."""
        quote = self._quote.toPlainText().strip() or "Your quotation."
        lines = "\n".join(f"> {ln}" for ln in quote.splitlines())
        attribution = self._attribution.text().strip()
        if attribution:
            lines += f"\n>\n> — {attribution}"
        return "\n" + lines + "\n"
