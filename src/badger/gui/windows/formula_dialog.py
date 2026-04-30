from PyQt5.QtWidgets import (
    QDialog,
    QWidget,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QLabel,
    QTextEdit,
    QLineEdit,
    QCompleter,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QTextCursor
import re

from badger.formula_utils import sanitize_for_validation, validate_formula
from badger.gui.components.editable_table_2 import (
    ObjectivesListView,
    ObjectiveRowWidget,
)


stylesheet_run = """
QPushButton:hover:pressed
{
    background-color: #92D38C;
}
QPushButton:hover
{
    background-color: #6EC566;
}
QPushButton
{
    background-color: #4AB640;
    color: #000000;
}
"""


def _surround_with_backticks(string_list, text):
    """
    Surrounds any strings from string_list found in text with backticks,
    but only if not already backticked.

    Args:
        string_list: List of strings to search for
        text: The string to search in and modify

    Returns:
        Modified text with matching strings surrounded by backticks
    """
    result = text

    # Sort by length (longest first) to handle overlapping matches correctly
    sorted_list = sorted(string_list, key=len, reverse=True)

    for string in sorted_list:
        # Escape the string for use in regex
        escaped = re.escape(string)

        # Pattern: match string NOT preceded or followed by backtick
        # (?<!`) - negative lookbehind: not preceded by backtick
        # (?!`) - negative lookahead: not followed by backtick
        pattern = rf"(?<!`){escaped}(?!`)"

        # Replace with backtick-surrounded version
        result = re.sub(pattern, f"`{string}`", result)

    return result


class CompleterTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._completer = None

    def setCompleter(self, completer: QCompleter):
        if self._completer is completer:
            return

        if self._completer is not None:
            try:
                self._completer.activated[str].disconnect(
                    self.insert_completion_backticked
                )
            except TypeError:
                pass
            self._completer.setWidget(None)

        self._completer = completer
        if self._completer is None:
            return

        self._completer.setWidget(self)
        self._completer.setCompletionMode(QCompleter.PopupCompletion)  # dropdown
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.activated[str].connect(self.insert_completion_backticked)

    def completer(self):
        return self._completer

    def _prefix_under_cursor(self):
        tc = self.textCursor()
        tc.select(QTextCursor.WordUnderCursor)
        return tc.selectedText()

    def insert_completion_backticked(self, completion: str):
        prefix = self._prefix_under_cursor()
        tc = self.textCursor()
        tc.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, len(prefix))
        tc.insertText(f"`{completion}`")
        self.setTextCursor(tc)

    def keyPressEvent(self, e):
        if self._completer is None:
            super().keyPressEvent(e)
            return

        # Let the completer's popup handle navigation/accept keys
        if self._completer.popup().isVisible() and e.key() in (
            Qt.Key_Enter,
            Qt.Key_Return,
            Qt.Key_Escape,
            Qt.Key_Tab,
            Qt.Key_Backtab,
            Qt.Key_Up,
            Qt.Key_Down,
            Qt.Key_PageUp,
            Qt.Key_PageDown,
        ):
            e.ignore()
            return

        super().keyPressEvent(e)

        prefix = self._prefix_under_cursor()
        if not prefix:
            self._completer.popup().hide()
            return

        self._completer.setCompletionPrefix(prefix)
        self._completer.popup().setCurrentIndex(
            self._completer.completionModel().index(0, 0)
        )

        # Show popup at cursor position (dropdown list)
        cr = self.cursorRect()
        popup = self._completer.popup()
        cr.setWidth(popup.sizeHintForColumn(0) + popup.frameWidth() * 2)
        self._completer.complete(cr)


class BadgerFormulaDialog(QDialog):
    """
    Dialog for adding formula observable in Badger.
    """

    def __init__(
        self,
        parent: QWidget,
        table: ObjectivesListView,
    ):
        """
        Initialize the dialog.

        """
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)

        self.table = table

        self.items = self.table.items
        self.variables = {}

        self.init_ui()
        self.config_logic()

        self.setup_var_table()

    def setup_var_table(self):
        for i, item in enumerate(self.items):
            # print(item, i)
            pass

    def init_ui(self) -> None:
        """
        Initialize the user interface.
        """

        self.setWindowTitle("Add formula")
        self.setFixedWidth(360)

        root_vbox = QVBoxLayout(self)

        # Header and labels
        header = QWidget()
        header_hbox = QHBoxLayout(header)
        header_hbox.setContentsMargins(0, 0, 0, 0)

        label = QLabel("test label info would be here")
        label.setFixedWidth(360)

        header_hbox.addWidget(label)

        content_widget = QWidget()
        hbox_content = QHBoxLayout(content_widget)
        hbox_content.setContentsMargins(0, 0, 0, 0)

        formula_widget = self.build_formula_input()
        self.help_widget = self.build_help_widget()
        self.help_widget.hide()

        # Button set
        button_set = QWidget()
        hbox_set = QHBoxLayout(button_set)
        hbox_set.setContentsMargins(0, 0, 0, 0)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_add = QPushButton("Add")
        self.btn_cancel.setFixedSize(96, 24)
        self.btn_add.setFixedSize(96, 24)
        hbox_set.addSpacing(114)
        hbox_set.addWidget(self.btn_cancel)
        hbox_set.addWidget(self.btn_add)
        hbox_set.addStretch()

        hbox_content.addWidget(formula_widget)
        hbox_content.addWidget(self.help_widget)

        # vbox.addWidget(header)
        root_vbox.addWidget(content_widget)
        root_vbox.addWidget(button_set)

    def build_formula_input(self) -> QWidget:
        formula_widget = QWidget()
        formula_layout = QVBoxLayout(formula_widget)
        formula_layout.setContentsMargins(0, 0, 0, 0)
        formula_widget.setFixedWidth(320)

        name_widget = QWidget()
        name_layout = QVBoxLayout(name_widget)
        name_layout.setContentsMargins(0, 0, 0, 0)

        name_header = QWidget()
        name_header_layout = QHBoxLayout(name_header)
        name_header_layout.setContentsMargins(0, 0, 0, 0)

        name_label = QLabel("Name: ")
        name_label.setToolTip("This is what shows up on the GUI")

        self.info_button = QPushButton("Show Info >")
        self.info_button.setCheckable(True)
        self.info_button.setFixedWidth(85)

        name_header_layout.addWidget(name_label)
        name_header_layout.addStretch()
        name_header_layout.addWidget(self.info_button)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter objective name")
        name_layout.addWidget(name_header)
        name_layout.addWidget(self.name_edit)

        variable_widget = QWidget()
        variable_layout = QVBoxLayout(variable_widget)
        variable_layout.setContentsMargins(0, 0, 0, 0)
        variable_label = QLabel("Variables: ")
        variable_edit_widget = QWidget()
        self.variable_edit_layout = QVBoxLayout(variable_edit_widget)

        variable_layout.addWidget(variable_label)
        variable_layout.addWidget(variable_edit_widget)

        formula_edit_widget = QWidget()
        formula_edit_layout = QVBoxLayout(formula_edit_widget)
        formula_edit_layout.setContentsMargins(0, 0, 0, 0)
        formula_label = QLabel("Formula: ")
        formula_label.setToolTip(
            "This is what will actually be    \n"
            + "passed to the interface. If    \n"
            + "other formulas are referenced  \n"
            + "they will be expanded, and any \n"
            + "calculations will be done after\n"
            + "data is retrieved."
        )

        self.formula_edit = CompleterTextEdit()
        self.formula_edit.setPlaceholderText(
            "Enter formula, for example mean(`f`) or np.std(`f`)**2\n"
            + "Formula syntax:\n"
            + "  - Enter variable names in backticks: `f`\n"
            + "  - Use any python.statistics or numpy expression: \n"
            + "    - mean(`f`), std(`f`), percentile(`f`, 80)\n"
            + "    - operators including *, +, -, /, **\n"
        )
        self.formula_edit.setStyleSheet("""
                color: darkGray;
            """)
        completer = QCompleter(self.table.item_names, self.formula_edit)
        completer.setCaseSensitivity(Qt.CaseInsensitive)  # ignore case
        # completer.setFilterMode(Qt.MatchContains)  # match substring (optional)
        completer.setFilterMode(Qt.MatchStartsWith)  # default behavior

        self.formula_edit.setCompleter(completer)
        formula_edit_layout.addWidget(formula_label)
        formula_edit_layout.addWidget(self.formula_edit)

        formula_layout.addWidget(name_widget)
        # formula_layout.addWidget(variable_widget)
        formula_layout.addWidget(formula_edit_widget)

        return formula_widget

    def build_help_widget(self) -> QWidget:
        help_widget = QWidget()
        help_layout = QVBoxLayout(help_widget)
        help_layout.setContentsMargins(0, 0, 0, 0)
        help_widget.setFixedWidth(220)
        help_widget.setStyleSheet("""
            border: 1px solid #455364;
            background-color: #37414F;
            color: LightGray;
        """)

        help_label = QLabel(
            "Helpful Formula Info:             \n"
            "                                  \n"
            "  - Variable names are backticked:\n"
            "     `f`, `equation_b`, `PV:NAME` \n"
            "                                  \n"
            "  - Use any expression from numpy,\n"
            "     python.statistics , or       \n"
            "     python.math such as:         \n"
            "      - mean(`f`), std(`f`)       \n"
            "      - max(`f`, `g`, `h`)        \n"
            "      - percentile(`f`, 80)       \n"
            "      - percentile(`f`, 50)       \n"
            "                                  \n"
            "  - Supported operators:          \n"
            "     +, -, *, /, **               \n"
        )
        help_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        help_layout.addWidget(help_label)

        return help_widget

    def config_logic(self) -> None:
        self.btn_cancel.clicked.connect(self.cancel)
        self.btn_add.clicked.connect(self.construct_formula_str)
        self.info_button.clicked.connect(self.show_info_panel)
        # self.stat_combo.currentTextChanged.connect(self.update_stat_formula)
        # self.name_edit.textChanged.connect(self.update_stat_formula)

    def show_info_panel(self):
        if self.info_button.isChecked():
            self.info_button.setText("Hide Info < ")
            self.setFixedWidth(590)
            self.help_widget.setVisible(True)
        else:
            self.info_button.setText("Show Info >")
            self.setFixedWidth(360)
            self.help_widget.setVisible(False)

    def construct_formula_str(self):
        name = self.name_edit.text()
        formula_str = self.formula_edit.toPlainText().strip()
        if self.validate_formula(formula_str):  # make sure formula is valid
            print(f"formula_dialog adding formula: {name}, {formula_str}")
            self.table.add_item(name, formula_str, checked=True)
            self.close()
        else:
            print(f"invalid formula: {formula_str}")

    def validate_formula(self, expr: str) -> bool:
        """
        Validate the formula expression by sanitizing it and checking if it can be parsed
        using allowed symbols
        """
        print(f"dialog validate formula: {expr}")
        matches = self.table.check_for_var_references(expr)
        # I don't think this is still needed, allowed separately
        # referencing vars in backticks and formulas without
        expr = _surround_with_backticks(matches, expr)

        python_expr, allowed = sanitize_for_validation(expr)
        try:
            validate_formula(python_expr, allowed_symbols=allowed)
            return True
        except TypeError:
            return False

    def cancel(self):
        self.close()


class FormulaEdit(BadgerFormulaDialog):
    def __init__(
        self,
        parent: QWidget,
        table: ObjectivesListView,
        row_widget: ObjectiveRowWidget,
    ):
        """
        Initialize the dialog.

        """
        super().__init__(parent, table)
        if not isinstance(row_widget, ObjectiveRowWidget):
            raise ValueError("row_widget must be an instance of ObjectiveRowWidget")
        self.row_widget = row_widget
        self.item = item = row_widget.item
        if item:
            self.name_edit.setText(item.name)
            self.formula_edit.setText(item.formula["formula_str"])

    def init_ui(self) -> None:
        super().init_ui()
        self.setWindowTitle("Edit formula")
        self.btn_add.setText("Save")

    def config_logic(self):
        super().config_logic()
        self.btn_add.clicked.disconnect()
        self.btn_add.clicked.connect(self.construct_formula_str)

    def construct_formula_str(self):
        name = self.name_edit.text()
        formula_str = " ".join(
            self.formula_edit.toPlainText().split()
        )  # strip newlines, tabs, extra spaces
        if self.validate_formula(formula_str):  # make sure formula is valid
            print(f"Update formula: {name}, {formula_str}")
            if formula_str != self.item.formula["formula_str"]:
                # only update formula
                self.table.update_item_formula(self.row_widget.item, formula_str)
            if name != self.item.name:
                # only update name
                self.row_widget.update_item_name(name)
            self.close()
        else:
            print(f"invalid formula: {formula_str}")
