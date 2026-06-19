# Third-Party Notices and Asset Licensing

epy_slides's **source code** is licensed under the MIT License (see
[LICENSE](LICENSE)). The distributed application bundles or links the
following third-party components, each governed by its own license.

## Bundled / linked components

| Component | License | Notes |
|---|---|---|
| [Qt for Python (PySide6)](https://www.qt.io/qt-for-python) | LGPL-3.0 | Dynamically linked. The frozen distribution keeps the Qt shared libraries as separate files (PyInstaller onedir layout), so they can be replaced as required by the LGPL. Source: <https://code.qt.io/> |
| [Pandoc](https://github.com/jgm/pandoc) | GPL-2.0-or-later | Distributed as a separate, unmodified executable (`pandoc.exe`) invoked as an external tool — mere aggregation, not a derived work. Source code: <https://github.com/jgm/pandoc> |
| [pypandoc](https://github.com/JessicaTegner/pypandoc) | MIT | Python wrapper used to call Pandoc. |
| [reveal.js](https://revealjs.com/) | MIT | Bundled HTML presentation framework; renders the live preview, the HTML export and the print-to-PDF source. |
| [MathJax](https://www.mathjax.org/) | Apache-2.0 | Bundled; typesets LaTeX equations in the preview and every export. |
| [pypdf](https://github.com/py-pdf/pypdf) | BSD-3-Clause | Reads and rewrites the exported PDF to stamp footers / page numbers. |
| [ReportLab](https://www.reportlab.com/) | BSD-3-Clause | Draws the footer overlay merged onto each exported PDF page. |
| [Pillow](https://python-pillow.org/) | MIT-CMU | Runtime: converts the watermark image to grayscale; also build-time icon generation. |
| [PyInstaller](https://pyinstaller.org/) | GPL-2.0 with bootloader exception | Build-time only; the exception explicitly permits distributing frozen applications under any license. |
| [Inno Setup](https://jrsoftware.org/isinfo.php) | Inno Setup License | Build-time only (Windows installer compiler). |

## Proprietary assets (NOT covered by the MIT license)

The following bundled assets are Copyright (c) 2026
**Ing. Angel Navarro-Mora M.Sc. / ANM Ingeniería (estructuraPy)** —
**all rights reserved**:

- `src/epy_slides/assets/branding/` — application logo and the
  ANM Ingeniería / estructuraPy brand images.
- `src/epy_slides/assets/themes/*.epyson` — layout theme definitions.
- `src/epy_slides/assets/reference_pptx/*.pptx` — PowerPoint reference
  (theme) decks.
- `assets_build/` — source images for the application icon.

These assets are licensed to you **only for use as an integral part of
unmodified epy_slides distributions**. Extracting, modifying, rebranding,
or redistributing them separately — in particular for use with other
document-generation products — requires prior written permission from
ANM Ingeniería (<ahnavarro@anmingenieria.com>).
