from dataclasses import dataclass, field
from PyQt5.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QScrollArea,
    QCheckBox,
    QLabel,
    QComboBox,
    QSizePolicy,
    QFrame,
    QLineEdit,
    QMessageBox,
)
from PyQt5.QtCore import pyqtSignal
from typing import Any, Optional, Tuple
import re
from enum import Enum, auto

import logging

logger = logging.getLogger(__name__)


class FormulaNameLabel(QLineEdit):
    """Custom QLineEdit that emits a signal on double-click."""

    double_clicked = pyqtSignal()
    # mouse_enter = pyqtSignal()
    # mouse_leave = pyqtSignal()

    def mouseDoubleClickEvent(self, event):
        """Override to emit signal on double-click."""
        self.double_clicked.emit()

        super().mouseDoubleClickEvent(event)

    # def enterEvent(self, event):
    #    self.mouse_enter.emit()
    #    super().enterEvent(event)

    # def leaveEvent(self, event):
    #    self.mouse_leave.emit()
    #    super().leaveEvent(event)


class Origin(Enum):
    """
    Enum class for identifying observable origin as
    defined in environment or user added.
    """

    ENVIRONMENT = auto()
    USER = auto()


@dataclass
class ObservableItem:
    checked: bool
    name: str

    origin: Origin = Origin.ENVIRONMENT  # default environment
    is_formula: bool = False
    rename_allowed: bool = False

    formula: dict[str, Any] = field(
        default_factory=lambda: {"formula_str": "", "variable_mapping": {}}
    )
    stat: str = "none"


@dataclass
class ObjectiveItem(ObservableItem):
    """
    Dataclass to represent an objective row.

    """

    rule: str = "MINIMIZE"


@dataclass
class ConstraintItem(ObservableItem):
    """Dataclass to represent a constraint row."""

    relation: str = "<"
    threshold: float = 0.0
    critical: bool = False


# Matches any of:
# mean(`x`), std(`x`), percentile(`x`,80/75/50/25), std(`x`)/mean(`x`)
_PATTERNS = [
    ("mean", re.compile(r"^\s*mean\s*\(\s*`(?P<var>[^`]+)`\s*\)\s*$", re.I)),
    ("std", re.compile(r"^\s*std\s*\(\s*`(?P<var>[^`]+)`\s*\)\s*$", re.I)),
    (
        "p80",
        re.compile(r"^\s*percentile\s*\(\s*`(?P<var>[^`]+)`\s*,\s*80\s*\)\s*$", re.I),
    ),
    (
        "p75",
        re.compile(r"^\s*percentile\s*\(\s*`(?P<var>[^`]+)`\s*,\s*75\s*\)\s*$", re.I),
    ),
    (
        "p25",
        re.compile(r"^\s*percentile\s*\(\s*`(?P<var>[^`]+)`\s*,\s*25\s*\)\s*$", re.I),
    ),
    (
        "median",
        re.compile(r"^\s*percentile\s*\(\s*`(?P<var>[^`]+)`\s*,\s*50\s*\)\s*$", re.I),
    ),
    (
        "std_rel",
        re.compile(
            r"^\s*std\s*\(\s*`(?P<var>[^`]+)`\s*\)\s*/\s*mean\s*\(\s*`(?P=var)`\s*\)\s*$",
            re.I,
        ),
    ),
]


class ObjectiveRowWidget(QWidget):
    """A custom widget representing a single objective row with checkbox, name, and rule combobox."""

    item_renamed = pyqtSignal(str, str)  # Emits (old_name, new_name)
    formula_updated = pyqtSignal(str, ObservableItem)  # Emits (new_formula_str, item)
    formula_double_clicked = pyqtSignal(
        QWidget
    )  # Emitted when formula name is double-clicked
    obs_double_clicked = pyqtSignal(QWidget)

    def __init__(self, objective_item: ObjectiveItem, row_index: int, parent=None):
        super().__init__(parent)
        self.item = objective_item
        # print(f"Creating ObjectiveRowWidget for item: {self.item.name}, stat: {self.item.stat}")
        self.row_index = row_index
        self._init_ui()
        self._connect_signals()
        self._apply_style()

    def _init_ui(self):
        """Initialize the UI components."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 1, 1, 4)
        layout.setSpacing(1)
        self.setStyleSheet("""
            border-radius: 0px;
        """)

        # Checkbox
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(self.item.checked)
        self.checkbox.setFixedWidth(20)
        layout.addWidget(self.checkbox)

        # Name input field
        self.name_input = FormulaNameLabel(self.item.name)
        self.name_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        # self.name_input.setFixedWidth(230)
        self.name_input.setCursorPosition(0)
        # if self.item.formula["formula_str"] or not self.item.origin == Origin.USER:
        self.name_input.setReadOnly(True)  # Edit by double-clicking

        # self.name_input.setFocusPolicy(Qt.NoFocus)

        # if not self.item.formula["formula_str"]:
        #    self.name_input.setReadOnly(True)

        layout.addWidget(self.name_input)

        # if not self.item.formula["formula_str"]:
        #    self.indicator = QLabel("*")
        #    self.indicator.hide()
        #    # self.indicator.
        #    layout.addWidget(self.indicator)
        # layout.addStretch(stretch=0)

        # Rule combobox
        self.rule_combo = QComboBox()
        self.rule_combo.addItems(["MINIMIZE", "MAXIMIZE"])
        self.rule_combo.setCurrentText(self.item.rule)
        self.rule_combo.setFixedWidth(120)
        layout.addWidget(self.rule_combo)

        # !--
        # statistic combobox
        # Not implemented
        self.stat_combo = QComboBox()
        self.stat_combo.addItems(
            [
                "none",
                "mean",
                "std",
                "std_rel",
                "p80",
                "p75",
                "median",
                "p25",
            ]
        )
        # print(f"ObjectiveRowWidget stat: {self.item.stat}")
        self.stat_combo.setCurrentText(self.item.stat)
        self.stat_combo.setFixedWidth(120)
        # layout.addWidget(self.stat_combo) # Don't add stat combo to GUI
        # --!

    def _apply_style(self):
        """Apply alternating row colors."""
        if self.row_index % 2 == 0:
            self.setStyleSheet("alternate-background-color: #262E38;")
        else:
            self.setStyleSheet("background-color: #262E38;")

        if self.item.formula["formula_str"]:
            # styling for formula items
            self.name_input.setStyleSheet("""
                QLineEdit {
                    color: LightSeaGreen;
                    border: 1px solid transparent;
                }

                QLabel:hover {
                    color: #00CCCC
                }

                QLineEdit:hover {
                    border: 1px solid DarkCyan;
                }

                """)

        else:
            # Styling for non-formula observables
            self.name_input.setStyleSheet("""
                QLineEdit {
                    color: lightGray;
                    border: 1px solid transparent;
                }

                QLabel:hover {
                    color: #E8E8E8;
                }

                QLineEdit:hover {
                    border: 1px solid Gray;
                }
            """)
            if self.item.origin == Origin.USER:
                self.name_input.setStyleSheet("""
                    QLineEdit {
                        color: darkGray;
                        border: 1px solid transparent;
                    }

                    QLabel:hover {
                        color: lightGray;
                    }

                    QLineEdit:hover {
                        border: 1px solid Gray;
                    }
                """)
            # alternative styling with '*' indicator
            # if hasattr(self, "indicator"):
            #    self.name_input.mouse_enter.connect(lambda: self.indicator.show())
            #    self.name_input.mouse_leave.connect(lambda: self.indicator.hide())
        self._update_tooltip()
        if self.item.formula["formula_str"]:
            self.stat_combo.setEditable(True)
            self.stat_combo.setCurrentText("formula")
            self.stat_combo.setEnabled(
                False
            )  # disable stat selection for formula items
            # self.name_input.setStyleSheet("color: LightSeaGreen;")

    def _update_tooltip(self):
        """Update the tooltip to display the formula_str."""
        if self.item.formula["formula_str"]:
            self.name_input.setToolTip(f"Formula: {self.item.formula['formula_str']}")
        elif self.item.stat:
            self.name_input.setToolTip(f"Statistic: {self.item.stat}")

    def update_formula_tooltip(self):
        """Public method to update the tooltip when formulas change."""
        self._update_tooltip()

    def _connect_signals(self):
        """Connect UI signals to data updates."""
        self.checkbox.stateChanged.connect(self._on_checkbox_changed)
        self.rule_combo.currentTextChanged.connect(self._on_rule_changed)
        self.stat_combo.currentTextChanged.connect(self._on_stat_changed)
        self.name_input.returnPressed.connect(self._on_name_changed)
        self.name_input.editingFinished.connect(self._on_name_changed)  # on focus loss
        # Only connect double-click signal if this is a formula item
        if self.item.formula["formula_str"]:
            self.name_input.double_clicked.connect(
                lambda: self.formula_double_clicked.emit(self)
            )
        else:  # if self.item.origin == Origin.USER:
            self.name_input.double_clicked.connect(
                lambda: self.obs_double_clicked.emit(self)
            )

    def _on_checkbox_changed(self):
        """Update item when checkbox state changes."""
        self.item.checked = self.checkbox.isChecked()

    def _on_rule_changed(self):
        """Update item when rule selection changes."""
        self.item.rule = self.rule_combo.currentText()

    def _on_stat_changed(self):
        """Update item when statistic selection changes."""
        self.item.formula["stat"] = self.stat_combo.currentText()
        self.item.stat = self.stat_combo.currentText()
        print(f" select stat: {self.item.stat} for {self.item.name}")

    def _construct_obs_func_str(self, operation: str, obj_name: str):
        print(
            f"Constructing observable function string for operation: {operation}, object: {obj_name}"
        )
        stats_mapping = {
            "mean": lambda x: f"mean(`{x}`)",
            "std": lambda x: f"std(`{x}`)",
            "p80": lambda x: f"percentile(`{x}`,80)",
            "p75": lambda x: f"percentile(`{x}`,75)",
            "p25": lambda x: f"percentile(`{x}`,25)",
            "median": lambda x: f"percentile(`{x}`,50)",
            "std_rel": lambda x: f"std(`{x}`)/mean(`{x}`)",
        }

        if operation in stats_mapping:
            new_obj_name = stats_mapping[operation](obj_name)
            print(f"Constructed new observable function string: {new_obj_name}")
            return new_obj_name
        # pass

    def _parse_stat_formula(self, expr: str) -> Optional[Tuple[str, str]]:
        """
        Returns (stat_key, variable_name) if expr matches one of the supported formulas,
        else None.
        """
        for key, rx in _PATTERNS:
            m = rx.match(expr)
            if m:
                return key, m.group("var")
        return None

    def update_item_name(self, new_name: str):
        """
        Update the name of the item. This is called to update the
        name externally (e.g. from FormulaEditor rather than name_input QLineEdit).
        emits item_renamed signal so that the parent can update references.
        """
        old_name = self.item.name
        self.item.name = new_name
        self.name_input.setText(new_name)
        self.item_renamed.emit(old_name, new_name)

    def _on_name_changed(self):
        """
        Update item when name text changes. This is called from the
        item_name QLineEdit. Updates the item name with the current text
        and emits item_renamed signal so that the parent can update references.
        """
        old_name = self.item.name
        new_name = self.name_input.text()

        print(f"change name: {old_name} -> {new_name}")

        if old_name != new_name:
            self.item.name = new_name
            self.item_renamed.emit(old_name, new_name)


class ObjectiveInsertRowWidget(QWidget):
    """A custom widget for inserting new objectives with a QLineEdit for the name."""

    item_requested = pyqtSignal(str)  # Emits the name when user presses Enter

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        """Initialize the UI components."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)

        # Checkbox (disabled, just for alignment)
        checkbox_spacer = QLabel("")
        # self.checkbox.setEnabled(False)
        checkbox_spacer.setFixedWidth(20)
        checkbox_spacer.setStyleSheet("""
            border-radius: 0px;
        """)
        layout.addWidget(checkbox_spacer)

        # Name input field
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter new objective name...")
        self.name_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.name_input.setStyleSheet("""
            border-radius: 0px;
        """)
        layout.addWidget(self.name_input)

        # Spacer to align with rule column
        spacer = QLabel("")
        spacer.setFixedWidth(120)
        spacer.setStyleSheet("""
            border-radius: 0px;
        """)
        layout.addWidget(spacer)

        # Style
        self.setStyleSheet("""
            background-color: #303A45;
            border-top: 1px solid #455364;
        """)

    def _connect_signals(self):
        """Connect signals for inserting new items."""
        self.name_input.returnPressed.connect(self._on_return_pressed)

    def _on_return_pressed(self):
        """Handle Enter key press."""
        name = self.name_input.text().strip()
        if name:
            if "`" in name:
                self.show_name_warning()
                return
            self.item_requested.emit(name)
            self.name_input.clear()
        self.name_input.setFocus()

    def show_name_warning(self) -> None:
        QMessageBox.warning(
            self,
            "Use 'add formula' button to add equations!",
            "Use 'add formula' button to add equations!",
        )


class HeaderWidget(QWidget):
    """A custom widget representing the table header."""

    def __init__(self, parent=None, additional_columns: list[str] = []):
        super().__init__(parent)
        self._init_ui(additional_columns)

    def _init_ui(self, additional_columns: list[str]) -> None:
        """Initialize the header UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 4)
        layout.setSpacing(1)

        # Checkbox column header (empty or with a master checkbox)
        checkbox_header = QLabel("")
        checkbox_header.setFixedWidth(20)
        layout.addWidget(checkbox_header)

        # Name column header
        name_header = QLabel("Name")
        name_header.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        # name_header.setStyleSheet("font-weight: bold;")
        layout.addWidget(name_header)

        # Add additional column headers
        for column_name in additional_columns:
            col_header = QLabel(column_name)
            col_header.setFixedWidth(120)
            layout.addWidget(col_header)

        # Style the header
        self.setStyleSheet("""
            background-color: #455364;
            border-bottom: 1px solid #a0a0a0;
            border-radius: 0px;
        """)
        self.setFixedHeight(30)


class ObjectivesListView(QScrollArea):
    """A scrollable list view for displaying objectives as row widgets with filtering support."""

    data_changed = pyqtSignal()  # Signal to indicate that data has changed
    formula_double_clicked = pyqtSignal(ObjectiveRowWidget)
    obs_double_clicked = pyqtSignal(ObjectiveRowWidget)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.StyledPanel)
        self.setMinimumHeight(200)

        # Main container widget
        main_container = QWidget()
        main_layout = QVBoxLayout(main_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Add header
        self.header = HeaderWidget(additional_columns=["Rule"])  # , "Statistic"])
        main_layout.addWidget(self.header)

        # Container widget to hold all row widgets
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(0)

        main_layout.addWidget(self.container)

        self.setWidget(main_container)

        # Apply table-like styling
        self.setStyleSheet("""
            QScrollArea {
                border: 1px solid #455364;
            }
        """)

        # Store all items
        self._all_items: list[ObjectiveItem] = []
        # self._additional_observables: list[ObservableItem] = [] # keep track of new

        # Store currently displayed row widgets
        self.row_widgets: list[ObjectiveRowWidget] = []

        # Filter state
        self._filter_text = ""
        self._show_checked_only = False

        # Create insert row widget (will be added to layout in _rebuild_view)
        self.insert_row = ObjectiveInsertRowWidget(parent=self)
        self.insert_row.item_requested.connect(self.add_item)
        self.insert_row.hide()

    def update_items(
        self,
        objectives: list[dict[str, Any]],
        status: dict[str, bool],
        formulas: dict[str, dict[str, Any]] | None = None,
        vocs_signal: bool = False,
        env_observables: list[str] = [],
    ) -> None:
        """Update the list with objectives data.

        Parameters
        ----------
        objectives : dict
            Dictionary with form {name: [rule]}
        status : dict
            Status information for each objective
        vocs_signal : bool
            Whether to emit a signal (not used currently)
        """
        # Clear all items
        self._all_items.clear()
        print("UPDATING OBJECTIVES LIST VIEW")

        print(f"-- {env_observables}, {objectives}")

        # Create new items from objectives
        for objective in objectives:
            print(f"...   objective: {objective}")
            for name, rule_list in objective.items():
                print(f"...   name: {name}, rule_list: {rule_list}")
                rule = rule_list[0] if rule_list else "MINIMIZE"
                stat = rule_list[1] if len(rule_list) > 1 else "none"
                item = ObjectiveItem(
                    checked=status.get(name, False),
                    name=name,
                    rule=rule,
                    stat=stat,
                    origin=Origin.USER
                    if env_observables and name not in env_observables
                    else Origin.ENVIRONMENT,
                )
                self._all_items.append(item)

        # Update formulas if provided
        if formulas is not None:
            for name in formulas:
                if name in self.item_names:
                    self.items[name].formula = formulas[name]
                    if "variable_mapping" not in self.items[name].formula:
                        self.items[name].formula["variable_mapping"] = {}

                else:
                    # If formula name is not in items, add it as a new item
                    print("HMM I DON'T THINK THIS SHOULD PRINT")

        # Rebuild view with current filters
        self._rebuild_view()

        if vocs_signal:
            self.update_vocs()

    def _rebuild_view(self) -> None:
        """Rebuild the visible row widgets based on current filters."""
        print("Rebuilding objectives list view...")
        # Clear existing displayed widgets
        for widget in self.row_widgets:
            widget.item_renamed.disconnect()
            widget.formula_double_clicked.disconnect()
            widget.obs_double_clicked.disconnect()
            widget.deleteLater()
        self.row_widgets.clear()

        # Remove old layout items, skip filtering for
        while self.container_layout.count() > 0:
            item = self.container_layout.takeAt(self.container_layout.count() - 1)
            if item.spacerItem():
                pass
            elif item.widget() == self.insert_row:
                pass

        all_names = self.item_names
        sorted_names = sorted(all_names)
        items = self.items

        # Filter and display items
        row_index = 0
        for name in sorted_names:
            item = items[name]
            if self._passes_filters(item):
                row_widget = ObjectiveRowWidget(item, row_index, parent=self)
                row_widget.item_renamed.connect(self._on_item_renamed)
                row_widget.formula_updated.connect(
                    lambda formula_str, i=item: self.update_item_formula(i, formula_str)
                )
                row_widget.formula_double_clicked.connect(
                    self.formula_double_clicked.emit
                )
                row_widget.obs_double_clicked.connect(self.obs_double_clicked.emit)
                self.row_widgets.append(row_widget)
                self.container_layout.addWidget(row_widget)
                row_index += 1

        # Show and add insert row
        self.insert_row.show()
        self.container_layout.addWidget(self.insert_row)

        # Add stretch at the end to push items to top
        self.container_layout.addStretch()

    def _passes_filters(self, item: ObjectiveItem) -> bool:
        """Check if an item passes all active filters."""
        # Filter by text (case-insensitive substring match)
        if self._filter_text:
            if self._filter_text.lower() not in item.name.lower():
                return False

        # Filter by checked status
        if self._show_checked_only and not item.checked:
            return False

        return True

    def set_filter(self, text: str) -> None:
        """Filter items by name substring (case-insensitive).

        Parameters
        ----------
        text : str
            Substring to filter by. Empty string clears the filter.
        """
        self._filter_text = text
        self._rebuild_view()

    def show_checked_only(self, enabled: bool) -> None:
        """Show only checked items.

        Parameters
        ----------
        enabled : bool
            If True, only checked items will be displayed.
        """
        self._show_checked_only = enabled
        self._rebuild_view()

    def get_items(self) -> list[ObjectiveItem]:
        """Get the unfiltered list of all ObjectiveItem objects.

        Returns
        -------
        list[ObjectiveItem]
            All items, regardless of current filter state.
        """
        return self._all_items

    def get_selected_items(self) -> list[ObjectiveItem]:
        """Get the list of currently selected (checked) items.

        Returns
        -------
        list[ObjectiveItem]
            List of checked items.
        """
        return [item for item in self._all_items if item.checked]

    def export_data(self):
        selected_items = self.get_selected_items()
        print(
            f"Exporting data for selected items: {[item.name for item in selected_items]}"
        )
        return [
            {item.name: {"rule": item.rule, "stat": item.stat}}
            for item in selected_items
        ]

    @property
    def item_names(self) -> list[str]:
        """Get a list of all item names."""
        # print(f"item names: {[item.name for item in self._all_items]}")
        return [item.name for item in self._all_items]

    @property
    def items(self) -> dict[str, ObjectiveItem]:
        """Get a dictionary of items keyed by name."""
        # print("items property called")
        return {item.name: item for item in self._all_items}

    @property
    def formulas(self) -> dict:
        _formulas = {}
        for item in self._all_items:
            if (
                item.formula["formula_str"] or item.origin == Origin.USER
            ):  # not sure if this is a good approach
                _formulas[item.name] = item.formula

        return _formulas

    @property
    def formula_strs(self) -> list[str]:
        return [
            item.formula["formula_str"]
            for item in self._all_items
            if item.formula["formula_str"]
        ]

    def show_duplicate_warning(self, name: str) -> None:
        QMessageBox.warning(
            self,
            "Item already exists!",
            f"Item {name} already exists!",
        )

    def add_item(
        self, name: str, formula_str: str = None, checked: bool = False
    ) -> None:
        """Add a new observable item to the list. This is called
        either by formula dialog (add formula, with formula_str)
        or by adding a new observable from the new item line.

        Parameters
        ----------
        name : str
            The name of the new observable.
        """
        if name in self.item_names:
            # If an item with the same name already exists, show a warning and do not add
            self.show_duplicate_warning(name)
            return

        # check for duplicate formulas
        if name in self.formula_strs:
            self.show_duplicate_warning(name)
            return

        # check for duplicate formulas
        if formula_str in self.formula_strs:
            self.show_duplicate_warning(formula_str)
            return

        print(
            f"ObjectivesListView add_item: {name}, formula: {formula_str}, no mapping yet"
        )

        # Create new objective item with default rule and formula
        new_item = ObjectiveItem(
            checked=checked,
            name=name,
            rule="MINIMIZE",
            origin=Origin.USER,
        )

        if formula_str:
            # add item as formula
            new_item.formula["formula_str"] = formula_str
            new_item.formula["variable_mapping"] = self.get_variable_mapping(
                formula_str
            )
        else:
            # Item added from UI line as new observable with no formula.
            if "`" in name:
                new_item.formula["formula_str"] = name
                new_item.formula["variable_mapping"] = self.get_variable_mapping(name)

        print(f"end add_item: {new_item.name}, {new_item.formula}")

        # Add to items list
        self._all_items.append(new_item)

        # Rebuild view to display new item
        self._rebuild_view()

        # self.update_vocs()

    def get_variable_mapping(self, formula_str: str) -> dict[str, str]:
        matches = self.check_for_var_references(formula_str)  # find variable references
        # matches is a list of variable name strings
        print(f"get_variable_mapping: matches: {matches}")
        visited = set()

        variable_mapping = {}
        for match in matches:
            if match in visited:
                variable_mapping[match] = None
                continue

            item = self.items[match]
            print(f"match: {item.name}, {item.formula}")
            if item.formula["formula_str"]:
                # If item is formula, get full formula with variable mapping for later expansion
                variable_mapping[item.name] = item.formula
            else:
                # If item is not formula, map to var name
                variable_mapping[item.name] = item.formula["formula_str"]

            visited.add(match)
            print(f"match: {match}, var_map: {variable_mapping}")

        print(f"return var mapping: {variable_mapping}")
        return variable_mapping

    def check_for_var_references(self, expr: str) -> list[str]:
        """
        if not self.item_names:
            return []
        pat = re.compile(
            rf"(?<![A-Za-z0-9_.])(?:{'|'.join(map(re.escape, self.item_names))})(?![A-Za-z0-9_(.])"
        )
        # pat = re.compile(
        #    rf"(?<=`)(?:{'|'.join(map(re.escape, self.item_names))})(?=`)"
        # )
        matches = pat.findall(expr)
        return matches
        """

        if not self.item_names:
            return []

        alts = "|".join(map(re.escape, self.item_names))

        # Allowed token separators
        left_sep = r"[()\+\-*/\s`]"
        right_sep = r"[()\+\-*/\s`]"

        # regex pattern to look for matches in formula string
        # formula names will be matched unless they are
        # immediately before a "." or "(", so you
        # can name a func "mean" and still do
        # mean(`f`) without matching mean
        # this will match substrings which are:

        pat = re.compile(
            rf"""

            (?:(?<=^)|(?<={left_sep})) # start OR preceded by left_sep
            (?:{alts})                           # match name

            (?![.(])                             # not followed by . or (
            (?=$|{right_sep})               # end OR right_sep or "**" after
            """,
            re.VERBOSE,
        )

        # (?<!`)                               # not immediately preceded by backtick
        # (?!`)                                # not immediately followed by backtick

        return pat.findall(expr)

    def _on_item_renamed(self, old_name: str, new_name: str) -> None:
        """Handle renaming of an item and update references in other items.

        Parameters
        ----------
        old_name : str
            The previous name of the item
        new_name : str
            The new name of the item
        """
        if new_name in self.item_names:
            self.show_duplicate_warning(new_name)
            return

        # Update formula_str in all items that reference the old name
        for item in self._all_items:
            if item.formula["formula_str"]:
                # Only match variable names within backticks
                old_pattern = rf"`{re.escape(old_name)}`"
                item.formula["formula_str"] = re.sub(
                    old_pattern, f"`{new_name}`", item.formula["formula_str"]
                )

                # Update variable_mapping keys
                if old_name in item.formula["variable_mapping"]:
                    item.formula["variable_mapping"][new_name] = item.formula[
                        "variable_mapping"
                    ].pop(old_name)

        # Update tooltips for all visible row widgets
        for row_widget in self.row_widgets:
            row_widget.update_formula_tooltip()

    def update_item_formula(self, item: ObjectiveItem, new_formula_str: str) -> None:
        """Handle updating an item's formula and recalculate its variable mapping.

        Parameters
        ----------
        item : ObjectiveItem
            The item whose formula is being updated
        new_formula_str : str
            The new formula string


        """

        # self.check_for_circular_reference(item, new_formula_str)
        print("UPDATE ITEM FORMULA this is different than _on_item_formula_updated")

        # check for duplicate formulas
        if new_formula_str in self.formula_strs:
            self.show_duplicate_warning(new_formula_str)
            return

        item.formula["formula_str"] = new_formula_str
        # Recalculate variable mapping for the updated formula
        mapping = self.get_variable_mapping(new_formula_str)
        print(f"mapping: {mapping}")
        # item.formula["variable_mapping"] = self.get_variable_mapping(
        #    new_formula_str, current_name=item.name
        # )
        print(f"item: {item.formula['variable_mapping']}")
        item.formula["variable_mapping"] = mapping
        print(f"mapping: {mapping}")
        print(f"update_item_formula: {item.formula['variable_mapping']}")

        # update variable_mapping for any items that reference this item as a variable
        for other_item in self._all_items:
            if other_item.formula["formula_str"]:
                # print(f"other item: {other_item.name}, formula: {other_item.formula}")
                # replace old variable mapping with new formula for this item
                if item.name in other_item.formula["variable_mapping"]:
                    other_item.formula["variable_mapping"][item.name] = item.formula

        # Update tooltips for all visible row widgets
        for row_widget in self.row_widgets:
            row_widget.update_formula_tooltip()

    def _on_item_formula_updated(
        self, item: ObjectiveItem, new_formula_str: str
    ) -> None:
        """ """
        # check for duplicate formulas
        if new_formula_str in self.formula_strs:
            self.show_duplicate_warning(new_formula_str)
            return
        print(f"Updating formula for item {item.name}, new formula: {new_formula_str}")
        item.formula["formula_str"] = new_formula_str
        # Recalculate variable mapping for the updated formula
        item.formula["variable_mapping"] = self.get_variable_mapping(new_formula_str)
        print(f"UPDATE FORMULA: {item.formula['variable_mapping']}")

        # update variable_mapping for any items that reference this item as a variable
        for other_item in self._all_items:
            if other_item.formula["formula_str"]:
                # print(f"other item: {other_item.name}, formula: {other_item.formula}")
                # replace old variable mapping with new formula for this item
                if item.name in other_item.formula["variable_mapping"]:
                    other_item.formula["variable_mapping"][item.name] = item.formula

        # Update tooltips for all visible row widgets
        for row_widget in self.row_widgets:
            row_widget.update_formula_tooltip()

    """def check_for_circular_reference(self, item: ObjectiveItem, new_formula_str: str) -> None:
        var_map = self.get_variable_mapping(new_formula_str, current_name=item.name)

        def find_refs(var_mapping: dict, depth: int = 0):
            for name, mapping in var_mapping.items():
                # Allow A referencing A directly in its own formula (depth == 0),
                # but disallow A being reached through another dependency (depth > 0).
                if name == item.name and depth > 0:
                    raise ValueError("Circular reference detected!")

                if isinstance(mapping, dict):
                    find_refs(mapping, depth + 1)

        find_refs(var_map, 0)"""

    def check_for_circular_reference(
        self, item: ObjectiveItem, new_formula_str: str
    ) -> bool:
        # Check for circular references
        print("check for circular references")
        print(self.get_variable_mapping(new_formula_str))

        def find_refs(var_mapping: dict):
            for name, mapping in var_mapping.items():
                print(name, mapping)
                if name == item.name:
                    raise ValueError("Circular reference detected!")
                if isinstance(mapping, dict):
                    find_refs(mapping)

        find_refs(self.get_variable_mapping(new_formula_str))

    def update_vocs(self):
        logging.debug("Emitting data_changed signal from editable_table")
        self.data_changed.emit()
