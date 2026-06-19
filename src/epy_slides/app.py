"""epy_slides GUI: multi-tab Markdown slide editor with reveal.js preview.

One Markdown source per tab renders live as a reveal.js deck and exports to
PDF (reveal print mode), standalone HTML and PowerPoint (Pandoc).
"""

from __future__ import annotations

import argparse
import importlib.resources
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtGui import QAction, QActionGroup, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QMainWindow,
    QMenu,
    QMessageBox,
    QStatusBar,
    QTabWidget,
    QToolBar,
    QToolButton,
)

from epy_slides import _i18n as i18n
from epy_slides import snippets, themes
from epy_slides._revealjs_theme import reveal_css_for
from epy_slides.about_dialog import _load_branding_pixmap
from epy_slides.renderer import export_pptx, render_revealjs
from epy_slides.tab import MarkdownTab

APP_NAME = "epy_slides"

SUPPORTED_EXTENSIONS = {".md", ".markdown", ".qmd"}

FILE_FILTER = "Markdown / Quarto (*.md *.markdown *.qmd);;All files (*)"


def _load_manual_text(filename: str = "welcome.md") -> str:
    """Load a bundled manual deck and resolve its image placeholders.

    The manual ships as Markdown under ``assets/`` so it can be edited
    freely. ``__EPY_LOGO__`` and ``__SHOT_*__`` placeholders are replaced
    with ``file://`` URIs to bundled images so they render even though the
    tab has no file path. The Spanish manual (``*_es``) resolves the
    ``*_es.png`` screenshot variants when present.
    """
    text = (
        importlib.resources.files("epy_slides.assets")
        .joinpath(filename)
        .read_text(encoding="utf-8")
    )
    assets = {
        "__EPY_LOGO__": ("branding", "epy_slides.png"),
        "__SHOT_EDITOR__": ("screenshots", "editor.png"),
        "__SHOT_NEW_SLIDE__": ("screenshots", "dlg_new_slide.png"),
        "__SHOT_PROPERTIES__": ("screenshots", "presentation_properties.png"),
        "__SHOT_FIGURE__": ("screenshots", "dlg_figure.png"),
        "__SHOT_TABLE__": ("screenshots", "dlg_table.png"),
        "__SHOT_EQUATION__": ("screenshots", "dlg_equation.png"),
        "__SHOT_THEME_EDITOR__": ("screenshots", "dlg_theme.png"),
    }
    is_es = Path(filename).stem.endswith("_es")
    root = importlib.resources.files("epy_slides.assets")
    for placeholder, (subdir, name) in assets.items():
        if is_es and subdir == "screenshots":
            stem, _, ext = name.rpartition(".")
            es_name = f"{stem}_es.{ext}"
            try:
                if root.joinpath(subdir).joinpath(es_name).is_file():
                    name = es_name
            except OSError:
                pass
        try:
            res = root.joinpath(subdir).joinpath(name)
            uri = Path(str(res)).resolve().as_uri()
        except (FileNotFoundError, ValueError, OSError):
            uri = ""
        text = text.replace(placeholder, uri)
    return text


def _load_welcome() -> str:
    """Return the welcome deck, falling back to a minimal built-in deck."""
    try:
        return _load_manual_text("welcome.md")
    except (FileNotFoundError, OSError):
        return (
            "---\ntitle: Welcome to epy_slides\n"
            "author: ANM Ingeniería\naspect-ratio: \"16:9\"\n---\n\n"
            "## Getting started\n\n- Separate slides with `## `\n"
            "- Use the **Slides** menu to add layouts\n"
            "- Export to PDF, HTML or PowerPoint\n"
        )


class SlideWindow(QMainWindow):
    """Main window: a tab bar with one slide-deck editor per file."""

    def __init__(self) -> None:
        """Build the tab widget, toolbar, menu, and welcome tab."""
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1320, 840)

        self.tabs = QTabWidget(self)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self._close_tab_at)
        self.tabs.currentChanged.connect(self._on_current_changed)
        self.setCentralWidget(self.tabs)
        self.setStatusBar(QStatusBar(self))

        self._build_actions()
        self._build_format_actions()
        self._build_slide_actions()
        self._build_content_actions()
        self._build_menu()
        self._build_toolbar()
        self.menuBar().hide()

        self.setAcceptDrops(True)

        self._settings = QSettings("ANM Ingeniería", "epy_slides")
        saved_theme = str(
            self._settings.value("theme", themes.DEFAULT_THEME_ID)
        )
        self._current_theme: themes.Theme = themes.get(saved_theme)
        self._apply_theme(self._current_theme.id, persist=False)

        self._capture_i18n()
        i18n.on_language_changed(self._retranslate_ui)
        saved_lang = str(self._settings.value("language", "en"))
        if saved_lang in i18n.LANGUAGES and saved_lang != "en":
            i18n.set_language(saved_lang)
        self._sync_language_menu()

        logo_pix = _load_branding_pixmap("epy_slides.png")
        if not logo_pix.isNull():
            self.setWindowIcon(QIcon(logo_pix))

        self._open_welcome_tab()

    # ------------------------------------------------- actions/menus

    def _build_actions(self) -> None:
        """Create file / export / view / help QActions."""
        self.act_new = QAction("New", self)
        self.act_new.setShortcut(QKeySequence.StandardKey.New)
        self.act_new.triggered.connect(self._new_tab)

        self.act_open = QAction("Open...", self)
        self.act_open.setShortcut(QKeySequence.StandardKey.Open)
        self.act_open.triggered.connect(self._open_dialog)

        self.act_save = QAction("Save", self)
        self.act_save.setShortcut(QKeySequence.StandardKey.Save)
        self.act_save.triggered.connect(self._save_current)

        self.act_save_as = QAction("Save As...", self)
        self.act_save_as.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.act_save_as.triggered.connect(self._save_current_as)

        self.act_reload = QAction("Reload", self)
        self.act_reload.setShortcut("F5")
        self.act_reload.triggered.connect(self._reload_current)

        self.act_close = QAction("Close Tab", self)
        self.act_close.setShortcut(QKeySequence.StandardKey.Close)
        self.act_close.triggered.connect(self._close_current_tab)

        self.act_pdf = QAction("Export as PDF...", self)
        self.act_pdf.setShortcut(QKeySequence("Ctrl+P"))
        self.act_pdf.triggered.connect(self._export_pdf)

        self.act_export_html = QAction("Export as HTML...", self)
        self.act_export_html.setShortcut(QKeySequence("Ctrl+Shift+P"))
        self.act_export_html.triggered.connect(self._export_html)

        self.act_export_pptx = QAction("Export as PowerPoint...", self)
        self.act_export_pptx.setShortcut(QKeySequence("Ctrl+Shift+X"))
        self.act_export_pptx.triggered.connect(self._export_pptx)

        self.act_print = QAction("Print...", self)
        self.act_print.setShortcut(QKeySequence("Ctrl+Alt+P"))
        self.act_print.triggered.connect(self._print_document)

        self.act_properties = QAction("Presentation properties…", self)
        self.act_properties.setShortcut(QKeySequence("Ctrl+Shift+Y"))
        self.act_properties.triggered.connect(self._edit_properties)

        self.act_quit = QAction("Quit", self)
        self.act_quit.setShortcut(QKeySequence.StandardKey.Quit)
        self.act_quit.triggered.connect(self.close)

        self.act_manual_en = QAction("User manual (English)", self)
        self.act_manual_en.triggered.connect(
            lambda: self._open_manual("welcome.md")
        )
        self.act_manual_es = QAction("User manual (Spanish)", self)
        self.act_manual_es.triggered.connect(
            lambda: self._open_manual("welcome_es.md")
        )

        self.act_about = QAction("About epy_slides…", self)
        self.act_about.triggered.connect(self._show_about)

        self._build_theme_actions()
        self.act_new_theme = QAction("New theme…", self)
        self.act_new_theme.triggered.connect(
            lambda: self._open_theme_editor(edit_id=None)
        )
        self.act_edit_theme = QAction("Edit current theme…", self)
        self.act_edit_theme.triggered.connect(self._edit_current_theme)
        self.act_delete_theme = QAction("Delete custom theme…", self)
        self.act_delete_theme.triggered.connect(self._delete_custom_theme)

        self.lang_group = QActionGroup(self)
        self.lang_group.setExclusive(True)
        self.lang_actions: dict[str, QAction] = {}
        for code, name in i18n.LANGUAGES.items():
            act = QAction(name, self, checkable=True)
            act.setData(code)
            self.lang_group.addAction(act)
            self.lang_actions[code] = act
        self.lang_group.triggered.connect(
            lambda action: self._set_language(action.data())
        )

    def _on_active_tab(self, fn_name: str, *args) -> None:
        """Forward an action to the active tab if there is one."""
        tab = self._current_tab()
        if tab is None:
            return
        getattr(tab, fn_name)(*args)

    def _build_format_actions(self) -> None:
        """Create text-formatting actions (headings, bold/italic, ...)."""
        self.heading_actions: list[QAction] = []
        for level in range(1, 7):
            act = QAction(f"Heading {level}", self)
            act.setShortcut(QKeySequence(f"Ctrl+{level}"))
            act.triggered.connect(
                lambda checked=False, lv=level: self._on_active_tab(
                    "set_heading_level", lv
                )
            )
            self.heading_actions.append(act)

        self.act_no_heading = QAction("Remove heading", self)
        self.act_no_heading.setShortcut(QKeySequence("Ctrl+0"))
        self.act_no_heading.triggered.connect(
            lambda: self._on_active_tab("set_heading_level", 0)
        )

        self.act_bold = QAction("Bold", self)
        self.act_bold.setShortcut(QKeySequence("Ctrl+B"))
        self.act_bold.triggered.connect(
            lambda: self._on_active_tab("toggle_bold")
        )

        self.act_italic = QAction("Italic", self)
        self.act_italic.setShortcut(QKeySequence("Ctrl+I"))
        self.act_italic.triggered.connect(
            lambda: self._on_active_tab("toggle_italic")
        )

        self.act_inline_code = QAction("Inline code", self)
        self.act_inline_code.setShortcut(QKeySequence("Ctrl+E"))
        self.act_inline_code.triggered.connect(
            lambda: self._on_active_tab("toggle_inline_code")
        )

        self.act_link = QAction("Link...", self)
        self.act_link.setShortcut(QKeySequence("Ctrl+K"))
        self.act_link.triggered.connect(
            lambda: self._on_active_tab("insert_link")
        )

    def _build_slide_actions(self) -> None:
        """Create the Slides menu actions (new slide / slide break)."""
        self.act_new_slide = QAction("New slide…", self)
        self.act_new_slide.setShortcut(QKeySequence("Ctrl+Shift+N"))
        self.act_new_slide.triggered.connect(
            lambda: self._on_active_tab("insert_new_slide")
        )
        self.act_slide_break = QAction("Blank slide break", self)
        self.act_slide_break.triggered.connect(
            lambda: self._on_active_tab("insert_slide_break")
        )

    def _build_content_actions(self) -> None:
        """Create the Content menu actions (blocks inserted on a slide)."""
        self.act_bullets = QAction("Bullet list…", self)
        self.act_bullets.setShortcut(QKeySequence("Ctrl+Shift+B"))
        self.act_bullets.triggered.connect(
            lambda: self._on_active_tab("insert_bullet_list")
        )
        self.act_two_column = QAction("Two columns…", self)
        self.act_two_column.triggered.connect(
            lambda: self._on_active_tab("insert_two_column")
        )
        self.act_quote = QAction("Quote…", self)
        self.act_quote.triggered.connect(
            lambda: self._on_active_tab("insert_quote")
        )
        self.act_notes = QAction("Speaker notes…", self)
        self.act_notes.triggered.connect(
            lambda: self._on_active_tab("insert_speaker_notes")
        )
        self.act_ins_image = QAction("Image from file...", self)
        self.act_ins_image.setShortcut(QKeySequence("Ctrl+Shift+I"))
        self.act_ins_image.triggered.connect(
            lambda: self._on_active_tab("insert_image_from_dialog")
        )
        self.act_ins_figure = QAction("Figure (skeleton)", self)
        self.act_ins_figure.setShortcut(QKeySequence("Ctrl+Shift+F"))
        self.act_ins_figure.triggered.connect(
            lambda: self._on_active_tab("insert_figure")
        )
        self.act_ins_table = QAction("Table", self)
        self.act_ins_table.setShortcut(QKeySequence("Ctrl+Shift+T"))
        self.act_ins_table.triggered.connect(
            lambda: self._on_active_tab("insert_table")
        )
        self.act_ins_equation = QAction("Equation", self)
        self.act_ins_equation.setShortcut(QKeySequence("Ctrl+Shift+Q"))
        self.act_ins_equation.triggered.connect(
            lambda: self._on_active_tab("insert_equation")
        )
        self.act_ins_code_block = QAction("Code block", self)
        self.act_ins_code_block.setShortcut(QKeySequence("Ctrl+Shift+K"))
        self.act_ins_code_block.triggered.connect(
            lambda: self._on_active_tab("insert_code_block")
        )
        self.act_ins_checklist = QAction("Checklist", self)
        self.act_ins_checklist.setShortcut(QKeySequence("Ctrl+Shift+L"))
        self.act_ins_checklist.triggered.connect(
            lambda: self._on_active_tab("insert_checklist")
        )
        self.callout_actions: list[QAction] = []
        for kind in ("note", "tip", "warning", "important", "caution"):
            act = QAction(f"Callout: {kind.title()}", self)
            act.triggered.connect(
                lambda checked=False, k=kind: self._on_active_tab(
                    "insert_callout", k
                )
            )
            self.callout_actions.append(act)
        self.callout_actions[0].setShortcut(QKeySequence("Ctrl+Shift+C"))

        self.act_diagram_mermaid = QAction("Diagram: Mermaid", self)
        self.act_diagram_mermaid.triggered.connect(
            lambda: self._on_active_tab("insert_diagram", "mermaid")
        )
        self.act_diagram_nomnoml = QAction("Diagram: nomnoml (UML)", self)
        self.act_diagram_nomnoml.triggered.connect(
            lambda: self._on_active_tab("insert_diagram", "nomnoml")
        )

    def _build_menu(self) -> None:
        """Build the content menus reused by the toolbar dropdowns."""
        self.file_menu = QMenu("&File", self)
        self.file_menu.addAction(self.act_new)
        self.file_menu.addAction(self.act_open)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.act_save)
        self.file_menu.addAction(self.act_save_as)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.act_reload)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.act_close)
        self.file_menu.addAction(self.act_quit)

        self.text_menu = QMenu("&Text", self)
        self.heading_sub = self.text_menu.addMenu("Heading")
        for act in self.heading_actions:
            self.heading_sub.addAction(act)
        self.heading_sub.addSeparator()
        self.heading_sub.addAction(self.act_no_heading)
        self.text_menu.addSeparator()
        self.text_menu.addAction(self.act_bold)
        self.text_menu.addAction(self.act_italic)
        self.text_menu.addAction(self.act_inline_code)
        self.text_menu.addSeparator()
        self.text_menu.addAction(self.act_link)

        self.slides_menu = QMenu("&Slides", self)
        self.slides_menu.addAction(self.act_new_slide)
        self.slides_menu.addAction(self.act_slide_break)

        self.content_menu = QMenu("&Content", self)
        self.content_menu.addAction(self.act_bullets)
        self.content_menu.addAction(self.act_two_column)
        self.content_menu.addAction(self.act_quote)
        self.content_menu.addSeparator()
        self.content_menu.addAction(self.act_ins_image)
        self.content_menu.addAction(self.act_ins_figure)
        self.content_menu.addAction(self.act_ins_table)
        self.content_menu.addAction(self.act_ins_equation)
        self.content_menu.addAction(self.act_ins_code_block)
        self.content_menu.addAction(self.act_ins_checklist)
        self.callout_sub = self.content_menu.addMenu("Callout")
        for act in self.callout_actions:
            self.callout_sub.addAction(act)
        self.diagram_sub = self.content_menu.addMenu("Diagram")
        self.diagram_sub.addAction(self.act_diagram_mermaid)
        self.diagram_sub.addAction(self.act_diagram_nomnoml)
        self.content_menu.addSeparator()
        self.content_menu.addAction(self.act_notes)

        self.export_menu = QMenu("E&xport", self)
        self.export_menu.addAction(self.act_pdf)
        self.export_menu.addAction(self.act_export_html)
        self.export_menu.addAction(self.act_export_pptx)
        self.export_menu.addSeparator()
        self.export_menu.addAction(self.act_print)

        self.view_menu = QMenu("&View", self)
        self.theme_sub = self.view_menu.addMenu("Theme")
        self._populate_theme_menu()
        self.view_menu.addSeparator()
        self.language_menu = self.view_menu.addMenu("Language")
        for act in self.lang_group.actions():
            self.language_menu.addAction(act)

        self.presentation_menu = QMenu("&Presentation", self)
        self.presentation_menu.addAction(self.act_properties)

        self._build_templates_menu()

        self.help_menu = QMenu("&Help", self)
        self.help_menu.addAction(self.act_manual_en)
        self.help_menu.addAction(self.act_manual_es)
        self.help_menu.addSeparator()
        self.help_menu.addAction(self.act_about)

    def _build_toolbar(self) -> None:
        """Toolbar: one popup dropdown per menu + reload."""
        bar = QToolBar("Main", self)
        bar.setMovable(False)
        self.addToolBar(bar)

        self._toolbar_buttons: list[tuple[QToolButton, str]] = []
        self._add_dropdown(bar, "File", self.file_menu)
        self._add_dropdown(bar, "Text", self.text_menu)
        self._add_dropdown(bar, "Slides", self.slides_menu)
        self._add_dropdown(bar, "Content", self.content_menu)
        self._add_dropdown(bar, "Presentation", self.presentation_menu)
        self._add_dropdown(bar, "Export", self.export_menu)
        self._add_dropdown(bar, "View", self.view_menu)
        self._add_dropdown(bar, "Templates", self.templates_menu)
        self._add_dropdown(bar, "Help", self.help_menu)
        bar.addSeparator()
        bar.addAction(self.act_reload)

    def _add_dropdown(self, bar: QToolBar, text: str, menu: QMenu) -> None:
        """Add a popup-style QToolButton to ``bar`` that opens ``menu``."""
        btn = QToolButton(self)
        btn.setText(i18n.tr(text))
        btn.setMenu(menu)
        btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        bar.addWidget(btn)
        self._toolbar_buttons.append((btn, text))

    # --------------------------------------------- internationalization

    def _capture_i18n(self) -> None:
        """Snapshot the English text of every stable action/menu."""
        self._tr_actions: dict[QAction, str] = {}
        self._tr_menus: dict[QMenu, str] = {}
        for obj in vars(self).values():
            if isinstance(obj, QAction):
                if obj.text():
                    self._tr_actions[obj] = obj.text()
            elif isinstance(obj, QMenu):
                if obj.title():
                    self._tr_menus[obj] = obj.title()
            elif isinstance(obj, QActionGroup):
                for act in obj.actions():
                    if act.text():
                        self._tr_actions[act] = act.text()
            elif isinstance(obj, list):
                for act in obj:
                    if isinstance(act, QAction) and act.text():
                        self._tr_actions[act] = act.text()
            elif isinstance(obj, dict):
                for act in obj.values():
                    if isinstance(act, QAction) and act.text():
                        self._tr_actions[act] = act.text()

    def _retranslate_ui(self) -> None:
        """Re-apply translations to every captured widget (live switch)."""
        for action, english in self._tr_actions.items():
            action.setText(i18n.tr(english))
        for menu, english in self._tr_menus.items():
            menu.setTitle(i18n.tr(english))
        for btn, english in getattr(self, "_toolbar_buttons", []):
            btn.setText(i18n.tr(english))
        self._sync_language_menu()

    def _set_language(self, code: str) -> None:
        """Persist the chosen UI language and relabel the UI live."""
        self._settings.setValue("language", code)
        i18n.set_language(code)

    def _sync_language_menu(self) -> None:
        """Tick the radio item matching the active language."""
        act = self.lang_actions.get(i18n.current_language())
        if act is not None:
            act.setChecked(True)

    # -------------------------------------------------------- themes

    def _apply_theme(self, theme_id: str, *, persist: bool = True) -> None:
        """Switch the application + every tab to ``theme_id``."""
        theme = themes.get(theme_id)
        self._current_theme = theme
        app = QApplication.instance()
        if app is not None:
            themes.apply_palette(app, theme)
            app.setStyleSheet(themes.qss_for(theme))

        css = reveal_css_for(theme)
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if isinstance(widget, MarkdownTab):
                widget.set_theme_css(css)

        if theme.id in self.theme_actions:
            self.theme_actions[theme.id].setChecked(True)

        if persist:
            self._settings.setValue("theme", theme.id)
            self.statusBar().showMessage(
                f"Theme: {theme.display_name}", 2000
            )

    def _build_theme_actions(self) -> None:
        """(Re)create the exclusive group of theme radio actions."""
        self.theme_group = QActionGroup(self)
        self.theme_group.setExclusive(True)
        self.theme_actions: dict[str, QAction] = {}
        for theme in themes.THEMES.values():
            act = QAction(theme.display_name, self, checkable=True)
            act.setData(theme.id)
            self.theme_group.addAction(act)
            self.theme_actions[theme.id] = act
        self.theme_group.triggered.connect(
            lambda action: self._apply_theme(action.data())
        )

    def _populate_theme_menu(self) -> None:
        """Fill the Theme submenu: theme radios + custom-theme actions."""
        self.theme_sub.clear()
        for act in self.theme_group.actions():
            self.theme_sub.addAction(act)
        self.theme_sub.addSeparator()
        self.theme_sub.addAction(self.act_new_theme)
        self.theme_sub.addAction(self.act_edit_theme)
        self.theme_sub.addAction(self.act_delete_theme)

    def _refresh_themes(self, select_id: str | None = None) -> None:
        """Reload bundled + user themes and rebuild the Theme submenu."""
        for act in self.theme_group.actions():
            self._tr_actions.pop(act, None)
        themes.reload()
        self._build_theme_actions()
        self._populate_theme_menu()
        for act in self.theme_group.actions():
            self._tr_actions[act] = act.text()
        if i18n.current_language() != "en":
            self._retranslate_ui()
        if select_id:
            self._apply_theme(select_id)

    def _open_theme_editor(self, edit_id: str | None = None) -> None:
        """Open the theme editor; on save, persist and select the theme."""
        from epy_slides.theme_editor_dialog import (  # noqa: PLC0415
            ThemeEditorDialog,
        )

        dialog = ThemeEditorDialog(
            self, base_theme_id=self._current_theme.id, edit_id=edit_id
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            theme_id = themes.save_user_theme(dialog.epyson_payload())
        except OSError as exc:
            QMessageBox.warning(self, APP_NAME, str(exc))
            return
        self._refresh_themes(select_id=theme_id)
        self.statusBar().showMessage(
            i18n.tr("Theme saved: {name}").format(name=dialog.theme_name()),
            3000,
        )

    def _edit_current_theme(self) -> None:
        """Edit the active theme in place if custom, otherwise clone it."""
        current = self._current_theme.id
        edit_id = current if current in themes.user_theme_ids() else None
        self._open_theme_editor(edit_id=edit_id)

    def _delete_custom_theme(self) -> None:
        """Delete a custom theme chosen from the user-generated set."""
        from PySide6.QtWidgets import QInputDialog  # noqa: PLC0415

        user_ids = sorted(themes.user_theme_ids())
        if not user_ids:
            QMessageBox.information(
                self, APP_NAME, i18n.tr("No custom themes to delete.")
            )
            return
        names = [themes.THEMES[i].display_name for i in user_ids]
        choice, ok = QInputDialog.getItem(
            self, i18n.tr("Delete custom theme…"),
            i18n.tr("Theme:"), names, 0, False,
        )
        if not ok:
            return
        theme_id = user_ids[names.index(choice)]
        confirm = QMessageBox.question(
            self, APP_NAME,
            i18n.tr("Delete the custom theme {name}?").format(name=choice),
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        themes.delete_user_theme(theme_id)
        fallback = (
            themes.DEFAULT_THEME_ID
            if self._current_theme.id == theme_id
            else self._current_theme.id
        )
        self._refresh_themes(select_id=fallback)

    def _show_about(self) -> None:
        """Open the About dialog modally."""
        from epy_slides.about_dialog import AboutDialog  # noqa: PLC0415

        AboutDialog(self).exec()

    # ----------------------------------------------- config templates

    def _build_templates_menu(self) -> None:
        """Build the Templates dropdown (save / apply / delete)."""
        self.templates_menu = QMenu("&Templates", self)
        self.act_save_template = QAction(
            "Save current settings as template…", self
        )
        self.act_save_template.triggered.connect(self._save_template)
        self.apply_template_menu = QMenu("Apply template", self)
        self.delete_template_menu = QMenu("Delete template", self)
        self.templates_menu.addAction(self.act_save_template)
        self.templates_menu.addSeparator()
        self.templates_menu.addMenu(self.apply_template_menu)
        self.templates_menu.addMenu(self.delete_template_menu)
        self.apply_template_menu.aboutToShow.connect(
            self._populate_apply_template_menu
        )
        self.delete_template_menu.aboutToShow.connect(
            self._populate_delete_template_menu
        )

    def _populate_apply_template_menu(self) -> None:
        """Rebuild the Apply-template submenu from disk."""
        from epy_slides import templates  # noqa: PLC0415

        menu = self.apply_template_menu
        menu.clear()
        names = templates.list_templates()
        if not names:
            placeholder = menu.addAction("(no templates saved)")
            placeholder.setEnabled(False)
            return
        for name in names:
            act = menu.addAction(name)
            act.triggered.connect(
                lambda _checked=False, n=name: self._apply_template(n)
            )

    def _populate_delete_template_menu(self) -> None:
        """Rebuild the Delete-template submenu from disk."""
        from epy_slides import templates  # noqa: PLC0415

        menu = self.delete_template_menu
        menu.clear()
        names = templates.list_templates()
        if not names:
            placeholder = menu.addAction("(no templates saved)")
            placeholder.setEnabled(False)
            return
        for name in names:
            act = menu.addAction(name)
            act.triggered.connect(
                lambda _checked=False, n=name: self._delete_template(n)
            )

    def _save_template(self) -> None:
        """Capture the current appearance and save it under a name."""
        from PySide6.QtWidgets import QInputDialog  # noqa: PLC0415

        from epy_slides import templates  # noqa: PLC0415

        name, ok = QInputDialog.getText(
            self, "Save template", "Template name:"
        )
        if not ok or not name.strip():
            return
        tab = self._current_tab()
        meta = (
            snippets.parse_front_matter(tab.editor.toPlainText())
            if tab is not None
            else {}
        )
        data = {
            "theme": self._current_theme.id,
            "aspect-ratio": meta.get("aspect-ratio", ""),
            "transition": meta.get("transition", ""),
            "slide-number": meta.get("slide-number", ""),
            "footer": meta.get("footer", ""),
            "logo": meta.get("logo", ""),
            "watermark": meta.get("watermark", ""),
            "copyright": meta.get("copyright", ""),
        }
        try:
            templates.save_template(name, data)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, APP_NAME, str(exc))
            return
        self.statusBar().showMessage(f"Saved template: {name.strip()}", 3000)

    def _apply_template(self, name: str) -> None:
        """Apply a saved template: theme + appearance front-matter keys."""
        from epy_slides import templates  # noqa: PLC0415

        try:
            tpl = templates.load_template(name)
        except (OSError, FileNotFoundError, ValueError) as exc:
            QMessageBox.warning(self, APP_NAME, str(exc))
            return

        theme_id = tpl.get("theme")
        if theme_id:
            self._apply_theme(theme_id)

        tab = self._current_tab()
        if tab is None:
            return
        text = tab.editor.toPlainText()
        updated = text
        for field in (
            "aspect-ratio", "transition", "slide-number",
            "footer", "logo", "watermark", "copyright",
        ):
            value = tpl.get(field)
            if value in (None, ""):
                continue
            updated = snippets.set_metadata_field(updated, field, str(value))
        if updated != text:
            self._replace_buffer(tab, updated)
        self.statusBar().showMessage(f"Applied template: {name}", 3000)

    def _delete_template(self, name: str) -> None:
        """Delete a saved template after confirmation."""
        from epy_slides import templates  # noqa: PLC0415

        choice = QMessageBox.question(
            self, "Delete template", f"Delete template '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if choice != QMessageBox.StandardButton.Yes:
            return
        templates.delete_template(name)
        self.statusBar().showMessage(f"Deleted template: {name}", 3000)

    # ----------------------------------------------- presentation props

    def _edit_properties(self) -> None:
        """Open the Presentation properties form and write front matter."""
        from epy_slides.presentation_properties_dialog import (  # noqa: PLC0415
            PresentationPropertiesDialog,
        )

        tab = self._current_tab()
        if tab is None:
            return
        text = tab.editor.toPlainText()
        meta = snippets.parse_front_matter(text)
        dialog = PresentationPropertiesDialog(self, meta)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        updates = dialog.updates()
        updated = text
        for field, value, raw in updates:
            # Copy a picked logo / watermark into the project so it travels
            # with the deck and resolves in the preview and every export.
            if field in ("logo", "watermark") and value:
                value = self._localize_asset(tab, value)
            updated = snippets.set_metadata_field(
                updated, field, value, raw=raw
            )
        if updated != text:
            self._replace_buffer(tab, updated)
            # Repaint the preview immediately so title slide, logo and
            # watermark reflect the new properties without waiting.
            tab.set_theme_css(reveal_css_for(self._current_theme))
        # A theme change in the form should also repaint the live preview.
        new_theme = next(
            (v for f, v, _ in updates if f == "theme"), None
        )
        if new_theme and new_theme in themes.THEMES:
            self._apply_theme(new_theme)
        self.statusBar().showMessage("Presentation properties updated", 3000)

    @staticmethod
    def _replace_buffer(tab: MarkdownTab, new_text: str) -> None:
        """Replace a tab's whole buffer atomically (keeps undo history)."""
        cursor = tab.editor.textCursor()
        cursor.beginEditBlock()
        cursor.select(cursor.SelectionType.Document)
        cursor.insertText(new_text)
        cursor.endEditBlock()

    @staticmethod
    def _localize_asset(tab: MarkdownTab, value: str) -> str:
        """Copy a picked image into the deck's ``figures/`` directory.

        Returns a project-relative path (``figures/<name>``) so the logo or
        watermark travels with the deck and resolves in the preview and
        every export. Values that are already relative, missing on disk, or
        belong to an unsaved deck are returned unchanged.
        """
        src = Path(value)
        if tab.path is None or not src.is_absolute() or not src.is_file():
            return value
        figures = tab.path.parent / "figures"
        figures.mkdir(parents=True, exist_ok=True)
        dst = figures / src.name
        if src.resolve() != dst.resolve() and not dst.exists():
            shutil.copy2(str(src), str(dst))
        return f"figures/{dst.name}"

    # ----------------------------------------------- export helpers

    def _export_html(self) -> None:
        """Save the current deck as a standalone reveal.js HTML file."""
        tab = self._current_tab()
        if tab is None:
            return
        default = (
            str(tab.path.with_suffix(".html"))
            if tab.path is not None
            else "untitled.html"
        )
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export HTML", default, "HTML (*.html *.htm)"
        )
        if not filename:
            return
        target = Path(filename)
        if target.suffix == "":
            target = target.with_suffix(".html")
        text = tab.editor.toPlainText()
        base_dir = tab.path.parent if tab.path is not None else None
        title = tab.path.name if tab.path is not None else "untitled"
        # epy_slides is a *presentation* tool: the HTML export is a real
        # reveal.js slideshow (arrow-key navigation, F for full screen,
        # S for speaker notes), not a continuous scroll page — that
        # continuous mode is epy_mdr's job (a web document).
        html = render_revealjs(
            text,
            base_dir=base_dir,
            title=title,
            theme_css=reveal_css_for(self._current_theme),
            for_export=True,
            continuous=False,
        )
        target.write_text(html, encoding="utf-8")
        self.statusBar().showMessage(f"Saved HTML: {target}", 3000)

    def _export_pptx(self) -> None:
        """Save the current deck as a PowerPoint (.pptx) file."""
        tab = self._current_tab()
        if tab is None:
            return
        default = (
            str(tab.path.with_suffix(".pptx"))
            if tab.path is not None
            else "untitled.pptx"
        )
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export PowerPoint", default, "PowerPoint (*.pptx)"
        )
        if not filename:
            return
        target = Path(filename)
        if target.suffix == "":
            target = target.with_suffix(".pptx")
        text = tab.editor.toPlainText()
        base_dir = tab.path.parent if tab.path is not None else None
        try:
            export_pptx(
                text, target, base_dir=base_dir,
                theme_id=self._current_theme.id,
            )
        except (OSError, RuntimeError) as exc:
            QMessageBox.critical(self, "Export PowerPoint failed", str(exc))
            return
        self.statusBar().showMessage(f"Exported {target.name}", 5000)

    def _export_pdf(self) -> None:
        """Export the current deck to a PDF file."""
        tab = self._current_tab()
        if tab is None:
            return
        default = (
            str(tab.path.with_suffix(".pdf"))
            if tab.path is not None
            else "untitled.pdf"
        )
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export PDF", default, "PDF (*.pdf)"
        )
        if not filename:
            return
        target = Path(filename)
        if target.suffix == "":
            target = target.with_suffix(".pdf")
        self.statusBar().showMessage("Exporting PDF...", 0)
        tab.export_pdf(target, self._on_pdf_done)

    def _on_pdf_done(self, path: Path, ok: bool) -> None:
        """Report the result of an asynchronous PDF export."""
        if ok:
            self.statusBar().showMessage(f"Saved PDF: {path}", 5000)
        else:
            self.statusBar().clearMessage()
            QMessageBox.warning(
                self, APP_NAME, f"Failed to write PDF:\n{path}"
            )

    def _print_document(self) -> None:
        """Open the system print dialog for the current preview."""
        tab = self._current_tab()
        if tab is None:
            return
        from PySide6.QtPrintSupport import (  # noqa: PLC0415
            QPrintDialog,
            QPrinter,
        )

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(printer, self)
        if dialog.exec() != QPrintDialog.DialogCode.Accepted:
            return
        self._active_printer = printer
        tab.view.page().print(
            printer, lambda _ok: setattr(self, "_active_printer", None)
        )

    # ----------------------------------------------- tab management

    def _open_welcome_tab(self) -> None:
        """Create the initial untitled tab shown at startup."""
        tab = self._create_tab()
        tab.set_initial_text(_load_welcome(), path=None)

    def _open_manual(self, filename: str) -> None:
        """Open a bundled manual deck (Help menu) in a new tab."""
        try:
            text = _load_manual_text(filename)
        except (FileNotFoundError, OSError):
            QMessageBox.warning(
                self, "Manual unavailable",
                f"Could not load the bundled manual '{filename}'.",
            )
            return
        tab = self._create_tab()
        tab.set_initial_text(text, path=None)

    def _create_tab(self) -> MarkdownTab:
        """Instantiate a new tab and wire its signals."""
        tab = MarkdownTab(self)
        tab.set_theme_css(reveal_css_for(self._current_theme))
        tab.dirtyChanged.connect(
            lambda _flag, t=tab: self._refresh_tab_title(t)
        )
        tab.pathChanged.connect(lambda t=tab: self._refresh_tab_title(t))
        index = self.tabs.addTab(tab, tab.title())
        self.tabs.setCurrentIndex(index)
        return tab

    def _refresh_tab_title(self, tab: MarkdownTab) -> None:
        """Update the tab label and window title for ``tab``."""
        index = self.tabs.indexOf(tab)
        if index < 0:
            return
        self.tabs.setTabText(index, tab.title())
        if tab.path is not None:
            self.tabs.setTabToolTip(index, str(tab.path))
        if tab is self._current_tab():
            self._update_window_title()

    def _update_window_title(self) -> None:
        """Reflect the current tab's title in the main window."""
        tab = self._current_tab()
        if tab is None:
            self.setWindowTitle(APP_NAME)
            return
        self.setWindowTitle(f"{APP_NAME} — {tab.title()}")
        if tab.path is not None:
            self.statusBar().showMessage(str(tab.path))
        else:
            self.statusBar().clearMessage()

    def _current_tab(self) -> MarkdownTab | None:
        """Return the currently visible tab, if any."""
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, MarkdownTab) else None

    def _on_current_changed(self, _index: int) -> None:
        """Refresh window title when the user switches tabs."""
        self._update_window_title()

    # ------------------------------------------------- file actions

    def _new_tab(self) -> MarkdownTab:
        """Create an empty untitled tab and focus it."""
        tab = self._create_tab()
        tab.set_initial_text("", path=None)
        return tab

    def _open_dialog(self) -> None:
        """Show an open-file dialog and load selected files in tabs."""
        current = self._current_tab()
        start = (
            str(current.path.parent)
            if current is not None and current.path is not None
            else ""
        )
        filenames, _ = QFileDialog.getOpenFileNames(
            self, "Open document", start, FILE_FILTER
        )
        for filename in filenames:
            self.open_path(Path(filename))

    def open_path(self, path: Path) -> None:
        """Open ``path`` in a new tab, or focus the existing tab."""
        if not path.is_file():
            QMessageBox.warning(self, APP_NAME, f"Not a file:\n{path}")
            return
        path = path.resolve()
        for i in range(self.tabs.count()):
            existing = self.tabs.widget(i)
            if (
                isinstance(existing, MarkdownTab)
                and existing.path is not None
                and existing.path.resolve() == path
            ):
                self.tabs.setCurrentIndex(i)
                return
        target = self._current_tab()
        if (
            target is None
            or target.path is not None
            or target.dirty
            or target.text().strip()
        ):
            target = self._create_tab()
        target.load_file(path)
        self._refresh_tab_title(target)

    def _save_current(self) -> bool:
        """Save the current tab, falling back to *Save As* if needed."""
        tab = self._current_tab()
        if tab is None:
            return False
        if tab.path is None:
            return self._save_current_as()
        tab.save()
        self._refresh_tab_title(tab)
        self.statusBar().showMessage(f"Saved: {tab.path}", 3000)
        return True

    def _save_current_as(self) -> bool:
        """Prompt for a target path and write the current tab there."""
        tab = self._current_tab()
        if tab is None:
            return False
        default = str(tab.path) if tab.path is not None else "untitled.md"
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save As", default, FILE_FILTER
        )
        if not filename:
            return False
        target = Path(filename)
        if target.suffix == "":
            target = target.with_suffix(".md")
        tab.save_as(target)
        self._refresh_tab_title(tab)
        self.statusBar().showMessage(f"Saved: {target}", 3000)
        return True

    def _reload_current(self) -> None:
        """Discard buffer changes and reload the current tab from disk."""
        tab = self._current_tab()
        if tab is None or tab.path is None:
            return
        if tab.dirty:
            choice = QMessageBox.question(
                self, "Reload",
                "Discard unsaved changes and reload from disk?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if choice != QMessageBox.StandardButton.Yes:
                return
        tab.reload()
        self.statusBar().showMessage(f"Reloaded: {tab.path}", 2000)

    # ------------------------------------------------ closing logic

    def _confirm_close(self, tab: MarkdownTab) -> bool:
        """Prompt how to handle a dirty tab. Returns False to abort."""
        if not tab.dirty:
            return True
        name = tab.path.name if tab.path is not None else "untitled.md"
        choice = QMessageBox.question(
            self, "Unsaved changes",
            f"'{name}' has unsaved changes. Save before closing?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if choice == QMessageBox.StandardButton.Save:
            self.tabs.setCurrentWidget(tab)
            return self._save_current()
        return choice == QMessageBox.StandardButton.Discard

    def _close_tab_at(self, index: int) -> None:
        """Handle the close button on a specific tab."""
        widget = self.tabs.widget(index)
        if not isinstance(widget, MarkdownTab):
            return
        if not self._confirm_close(widget):
            return
        self.tabs.removeTab(index)
        widget.cleanup_preview_tmp()
        widget.deleteLater()
        if self.tabs.count() == 0:
            self._open_welcome_tab()

    def _close_current_tab(self) -> None:
        """Close the active tab via the ``Ctrl+W`` shortcut."""
        index = self.tabs.currentIndex()
        if index >= 0:
            self._close_tab_at(index)

    def closeEvent(self, event) -> None:  # noqa: N802
        """Prompt to save every dirty tab before exiting."""
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if isinstance(widget, MarkdownTab) and not self._confirm_close(
                widget
            ):
                event.ignore()
                return
        event.accept()

    # -------------------------------------------------- drag & drop

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        """Accept drags that carry file URLs."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        """Open every dropped Markdown/Quarto file in its own tab."""
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.suffix.lower() in SUPPORTED_EXTENSIONS:
                self.open_path(path)


def _run_gui(files: list[str]) -> int:
    """Boot the Qt application and open ``files`` in tabs."""
    app = QApplication(sys.argv)
    logo_pix = _load_branding_pixmap("epy_slides.png")
    if not logo_pix.isNull():
        app.setWindowIcon(QIcon(logo_pix))
    window = SlideWindow()
    window.show()
    for raw in files:
        candidate = Path(raw)
        if candidate.exists():
            window.open_path(candidate)
    return app.exec()


def _run_register(make_default: bool) -> int:
    """Register the app for ``.md`` / ``.qmd`` on Windows."""
    from epy_slides import winreg_assoc  # noqa: PLC0415

    try:
        changes = winreg_assoc.register(make_default=make_default)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    for line in changes:
        print(line)
    print(
        f"\nDone. Right-click a .md / .markdown / .qmd file > Open with "
        f"> {APP_NAME}."
    )
    if make_default:
        winreg_assoc.open_default_apps_settings()
    return 0


def _run_set_default() -> int:
    """Open Settings → Default apps so the user can pick this app."""
    from epy_slides import winreg_assoc  # noqa: PLC0415

    if not winreg_assoc.open_default_apps_settings():
        print(
            "Could not open Settings. Open it manually: Settings → Apps "
            f"→ Default apps → search {APP_NAME}.",
            file=sys.stderr,
        )
        return 2
    return 0


def _run_unregister() -> int:
    """Remove the file-association keys created by ``--register``."""
    from epy_slides import winreg_assoc  # noqa: PLC0415

    try:
        changes = winreg_assoc.unregister()
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not changes:
        print("Nothing to remove.")
        return 0
    for line in changes:
        print(line)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    """Build the top-level ``argparse`` parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description="Markdown slide editor with reveal.js preview and "
        "PDF / HTML / PowerPoint export.",
    )
    parser.add_argument(
        "files", nargs="*",
        help="Markdown decks to open in tabs at startup.",
    )
    parser.add_argument(
        "--register", action="store_true",
        help=f"Add an 'Open with {APP_NAME}' entry for .md / .markdown / "
        ".qmd on Windows (HKCU, no admin).",
    )
    parser.add_argument(
        "--as-default", action="store_true",
        help=f"With --register, also set {APP_NAME} as the default program.",
    )
    parser.add_argument(
        "--unregister", action="store_true",
        help="Remove the keys created by --register.",
    )
    parser.add_argument(
        "--set-default", action="store_true",
        help="Open Settings → Default apps so you can pick the handler.",
    )
    return parser


def _ensure_utf8_streams() -> None:
    """Force stdout/stderr to UTF-8 so non-ASCII help text works."""
    import contextlib  # noqa: PLC0415

    for stream in (sys.stdout, sys.stderr):
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        with contextlib.suppress(ValueError, OSError):
            reconfigure(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``epy_slides`` console script."""
    _ensure_utf8_streams()
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.unregister:
        return _run_unregister()
    if args.register:
        return _run_register(make_default=args.as_default)
    if args.set_default:
        return _run_set_default()
    return _run_gui(args.files)


if __name__ == "__main__":
    raise SystemExit(main())
