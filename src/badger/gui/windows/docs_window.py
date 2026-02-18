from PyQt5.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QCheckBox,
    QWidget,
    QMainWindow,
    QTextBrowser,
)
from badger.factory import load_badger_docs
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt5.QtCore import QUrl


class BadgerDocsWindow(QMainWindow):
    def __init__(self, parent, docs: str):
        super().__init__(parent=parent)

        self.render_md = True
        self.docs = None

        self.init_ui()
        self.config_logic()
        self.load_docs()

    def init_ui(self):
        self.setWindowTitle(f"Docs for generator {self.docs}")
        self.resize(640, 640)

        doc_panel = QWidget(self)
        vbox = QVBoxLayout(doc_panel)

        # Toolbar
        toolbar = QWidget()
        hbox_tool = QHBoxLayout(toolbar)
        hbox_tool.setContentsMargins(0, 0, 0, 0)
        self.cb_md = cb_md = QCheckBox("Render as Markdown")
        cb_md.setChecked(True)
        hbox_tool.addStretch()
        hbox_tool.addWidget(cb_md)
        vbox.addWidget(toolbar)

        self.markdown_viewer = QTextBrowser()
        self.markdown_viewer.setOpenExternalLinks(False)
        self.markdown_viewer.anchorClicked.connect(self.handle_link_click)
        vbox.addWidget(self.markdown_viewer)

        self.setCentralWidget(doc_panel)

    def handle_link_click(self, url: "QUrl") -> None:
        """
        Handle links from the markdown viewer. Parses the url and loads the
        corresponding docs.

        Parameters
        ----------
        url : QUrl
            The url that was clicked. Expected format is /<name>#<subdir>
        """
        # format url to string
        href = url.toString()

        # Indicate links not yet supported in GUI docs viewer
        if href.startswith("https://") or href.startswith("mailto:"):
            self.docs = "external links not yet implemented in GUI docs viewer"
            self.load_docs()
            return

        url_end = href.split("/")[-1].split("#")

        self.docs = url_end[0]

        if len(url_end) > 1:
            ptype = url_end[1]
        else:
            ptype = None

        self.load_docs(ptype)

    def config_logic(self):
        self.cb_md.stateChanged.connect(self.switch_render_mode)

    def load_docs(self, subdir: str = None) -> None:
        """
        Load the docs for the current generator and subdir (if provided).

        Parameters
        ----------
        subdir : str, optional
            The subdirectory to load docs from, relatve to 'documentation' / 'docs' / 'guides'
        """
        try:
            self.docs = docs = load_badger_docs(self.docs, subdir)
        except Exception as e:
            self.docs = docs = str(e)

        if self.render_md:
            self.markdown_viewer.setMarkdown(docs)
        else:
            self.markdown_viewer.setText(docs)

    def update_docs(self, name: str, subdir: str = ""):
        """
        Update selected docs and refresh the window with the new docs

        Parameters
        ----------
        name : str
            The name of the file to load docs for
        subdir : str, optional
            The subdirectory in which the file is located
        """
        self.docs = name
        self.setWindowTitle(f"Docs for {subdir} {name}")
        self.load_docs(subdir)

    def switch_render_mode(self):
        self.render_md = self.cb_md.isChecked()
        if self.render_md:
            self.markdown_viewer.setMarkdown(self.docs)
        else:
            self.markdown_viewer.setText(self.docs)
