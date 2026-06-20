"""Presentation properties form — writes the deck's YAML front matter.

Mirrors the epy_reports Document-properties contract: the dialog is built from
the current front matter and exposes ``updates()`` returning
``(field, value, raw)`` triplets the window writes back with
``snippets.set_metadata_field``.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from epy_slides import _i18n as i18n
from epy_slides import themes
from epy_slides.template import is_truthy

_ASPECTS = ["16:9", "4:3"]
_TRANSITIONS = ["none", "fade", "slide", "convex", "concave", "zoom"]


class PresentationPropertiesDialog(QDialog):
    """Edit the deck's title block, theme and slide appearance."""

    def __init__(
        self, parent: QWidget | None = None, meta: dict[str, str] | None = None
    ) -> None:
        """Build the form, pre-filled from ``meta`` (front matter)."""
        super().__init__(parent)
        self.setWindowTitle("Presentation properties")
        self.setMinimumWidth(460)
        meta = meta or {}

        form = QFormLayout()

        self._title = QLineEdit(meta.get("title", ""), self)
        form.addRow("Title:", self._title)
        self._subtitle = QLineEdit(meta.get("subtitle", ""), self)
        form.addRow("Subtitle:", self._subtitle)
        self._author = QLineEdit(meta.get("author", ""), self)
        form.addRow("Author:", self._author)
        self._date = QLineEdit(meta.get("date", ""), self)
        form.addRow("Date:", self._date)

        self._theme = QComboBox(self)
        for theme_id in themes.THEMES:
            self._theme.addItem(themes.THEMES[theme_id].display_name, theme_id)
        self._select_data(self._theme, meta.get("theme", ""))
        form.addRow("Theme:", self._theme)

        self._aspect = QComboBox(self)
        self._aspect.addItems(_ASPECTS)
        if meta.get("aspect-ratio") in _ASPECTS:
            self._aspect.setCurrentText(meta["aspect-ratio"])
        form.addRow("Aspect ratio:", self._aspect)

        self._margin = QLineEdit(meta.get("margin", ""), self)
        self._margin.setPlaceholderText("0.06")
        form.addRow("Margin:", self._margin)

        self._transition = QComboBox(self)
        self._transition.addItems(_TRANSITIONS)
        if (meta.get("transition") or "").lower() in _TRANSITIONS:
            self._transition.setCurrentText(meta["transition"].lower())
        else:
            self._transition.setCurrentText("slide")
        form.addRow("Transition:", self._transition)

        self._slide_number = QCheckBox("Show slide numbers", self)
        self._slide_number.setChecked(is_truthy(meta.get("slide-number")))
        form.addRow("", self._slide_number)

        self._footer = QLineEdit(meta.get("footer", ""), self)
        form.addRow("Footer:", self._footer)

        self._logo = QLineEdit(meta.get("logo", ""), self)
        form.addRow("Logo:", self._path_row(self._logo))

        self._watermark = QLineEdit(meta.get("watermark", ""), self)
        form.addRow("Watermark:", self._path_row(self._watermark))

        self._copyright = QLineEdit(meta.get("copyright", ""), self)
        form.addRow("Copyright:", self._copyright)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)
        i18n.translate_widget(self)

    def _path_row(self, edit: QLineEdit) -> QWidget:
        """Wrap a line edit with a Browse button for image paths."""
        button = QPushButton("Browse…", self)
        button.clicked.connect(lambda: self._pick_image(edit))
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(edit)
        row.addWidget(button)
        wrapper = QWidget(self)
        wrapper.setLayout(row)
        return wrapper

    def _pick_image(self, edit: QLineEdit) -> None:
        """Pick an image file into ``edit``."""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Choose image",
            "",
            "Images (*.png *.jpg *.jpeg *.gif *.svg *.webp *.bmp)"
            ";;All files (*)",
        )
        if filename:
            edit.setText(filename)

    @staticmethod
    def _select_data(combo: QComboBox, data: str) -> None:
        """Select the combo entry whose data equals ``data``, if present."""
        index = combo.findData(data)
        if index >= 0:
            combo.setCurrentIndex(index)

    def updates(self) -> list[tuple[str, str, bool]]:
        """Return ``(field, value, raw)`` triplets for the front matter."""
        return [
            ("title", self._title.text().strip(), False),
            ("subtitle", self._subtitle.text().strip(), False),
            ("author", self._author.text().strip(), False),
            ("date", self._date.text().strip(), False),
            ("theme", self._theme.currentData(), False),
            ("aspect-ratio", self._aspect.currentText(), False),
            ("margin", self._margin.text().strip(), False),
            ("transition", self._transition.currentText(), False),
            (
                "slide-number",
                "true" if self._slide_number.isChecked() else "false",
                False,
            ),
            ("footer", self._footer.text().strip(), False),
            ("logo", self._logo.text().strip(), False),
            ("watermark", self._watermark.text().strip(), False),
            ("copyright", self._copyright.text().strip(), False),
        ]
