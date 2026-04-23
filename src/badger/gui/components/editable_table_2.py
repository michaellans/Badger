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

import logging

logger = logging.getLogger(__name__)


class FormulaNameLabel(QLabel):
    """Custom QLineEdit that emits a signal on double-click."""

    double_clicked = pyqtSignal()

    def mouseDoubleClickEvent(self, event):
        """Override to emit signal on double-click."""
        self.double_clicked.emit()
        super().mouseDoubleClickEvent(event)


@dataclass
class ObservableItem:
    checked: bool
    name: str
    is_name_editable: bool = False
    is_formula_editable: bool = False
    formula: dict[str, Any] = field(
        default_factory=lambda: {"formula_str": None, "variable_mapping": {}}
    )


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
    formula_updated = pyqtSignal(str, ObservableItem)  # Emits (new_formula_str)
    formula_double_clicked = pyqtSignal(
        QWidget
    )  # Emitted when formula name is double-clicked

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
        # Disable editing if this is not a formula item
        if not self.item.formula["formula_str"]:
            # self.name_input.setReadOnly(True)
            self.name_input.setStyleSheet("""
                border-radius: 0px;
                border: 1px solid transparent;
                padding: 0px;
            """)
        else:
            self.name_input.setStyleSheet("""
                border: 1px solid transparent;
                border-radius: 0px;
            """)
        layout.addWidget(self.name_input)

        # Rule combobox
        self.rule_combo = QComboBox()
        self.rule_combo.addItems(["MINIMIZE", "MAXIMIZE"])
        self.rule_combo.setCurrentText(self.item.rule)
        self.rule_combo.setFixedWidth(120)
        layout.addWidget(self.rule_combo)

        # !--
        # statistic combobox
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
        # self.stat_combo.setCurrentText(self.item.stat)
        self.stat_combo.setFixedWidth(120)
        # layout.addWidget(self.stat_combo)
        # --!

    def _apply_style(self):
        """Apply alternating row colors."""
        if self.row_index % 2 == 0:
            self.setStyleSheet("alternate-background-color: #262E38;")
        else:
            self.setStyleSheet("background-color: #262E38;")

        if self.item.formula["formula_str"]:
            # need to distinguish between formulas and new non-formula vars, or have a separate flag
            # for new variables?
            # border: 1px solid #356792;
            self.name_input.setStyleSheet("""
                
                                          
                QLabel {
                    color: DarkCyan;
                    border: 1px solid transparent;
                }
                QLabel:hover {
                    
                    color: LightSeaGreen;
                }
                
                """)
            self._update_tooltip()
        else:
            # Read-only items should not respond to hover or clicks
            self.name_input.setStyleSheet("""
                border-radius: 0px;
                border: 1px solid transparent;
                padding: 0px;
            """)

        if self.item.formula["variable_mapping"]:
            self.stat_combo.setEnabled(
                False
            )  # disable stat selection for formula items
            # self.name_input.setStyleSheet("color: LightSeaGreen;")

    def _update_tooltip(self):
        """Update the tooltip to display the formula_str."""
        if self.item.formula["formula_str"]:
            self.name_input.setToolTip(f"Formula: {self.item.formula['formula_str']}")
        else:
            self.name_input.setToolTip("")

    def update_formula_tooltip(self):
        """Public method to update the tooltip when formulas change."""
        self._update_tooltip()

    def _connect_signals(self):
        """Connect UI signals to data updates."""
        self.checkbox.stateChanged.connect(self._on_checkbox_changed)
        self.rule_combo.currentTextChanged.connect(self._on_rule_changed)
        self.stat_combo.currentTextChanged.connect(self._on_stat_changed)
        # self.name_input.returnPressed.connect(self._on_name_changed)
        # self.name_input.editingFinished.connect(self._on_name_changed)  # on focus loss
        # Only connect double-click signal if this is a formula item
        if self.item.formula["formula_str"]:
            self.name_input.double_clicked.connect(
                lambda: self.formula_double_clicked.emit(self)
            )

    def _on_checkbox_changed(self):
        """Update item when checkbox state changes."""
        self.item.checked = self.checkbox.isChecked()

    def _on_rule_changed(self):
        """Update item when rule selection changes."""
        self.item.rule = self.rule_combo.currentText()

    def _on_stat_changed(self):
        """Update item when statistic selection changes."""
        # self.item.formula["stat"] = self.stat_combo.currentText()
        self.item.stat = self.stat_combo.currentText()
        print(
            f" select stat: {self.item.stat} for {self.item.name} NOT IMPLEMENTED YET"
        )

        # removing implementation for now because I need to figure more things out, can revisit

        # new_function = None

        # if not self.item.formula["formula_str"]:
        #    new_function = self._construct_obs_func_str(self.item.stat, self.item.name)
        # elif "`" in self.item.formula["formula_str"]:
        #    try:
        #        stat_key, var_name = self._parse_stat_formula(self.item.formula["formula_str"])
        #        new_function = self._construct_obs_func_str(stat_key, var_name)
        #    except TypeError:
        #        print(f"Failed to parse formula_str: {self.item.formula['formula_str']}")
        #        new_function = None
        #        return
        # else:
        #    new_function = self._construct_obs_func_str(self.item.stat, self.item.formula["formula_str"])
        #    print(f"Constructed new function from formula_str: {new_function}")

        # print(f"Stat changed for {self.item.name}, new function: {new_function}")
        # NOTHING HAPPENS yes because I can't figure out how to make it work
        # self.item.formula["formula_str"] = new_function
        # self.item.formula["variable_mapping"] = {self.item.name: None} if new_function else {}
        # if new_function:
        #    self.formula_updated.emit(new_function, self.item)

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
            self.item_requested.emit(name)
            self.name_input.clear()
        self.name_input.setFocus()


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

        """# Rule column header
        rule_header = QLabel("Rule")
        rule_header.setFixedWidth(120)
        # rule_header.setStyleSheet("font-weight: bold;")
        layout.addWidget(rule_header)

        # Stat column header
        stat_header = QLabel("Statistic")
        stat_header.setFixedWidth(120)
        # rule_header.setStyleSheet("font-weight: bold;")
        layout.addWidget(stat_header)"""

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

        # Create new items from objectives
        for objective in objectives:
            print(f"...   objective: {objective}")
            for name, rule_list in objective.items():
                print(f"...   name: {name}, rule_list: {rule_list}")
                rule = rule_list[0] if rule_list else "MINIMIZE"
                # stat = rule_list[1] if len(rule_list) > 1 else "none"
                item = ObjectiveItem(
                    checked=status.get(name, False),
                    name=name,
                    rule=rule,
                )
                self._all_items.append(item)

        # Update formulas if provided
        if formulas is not None:
            for name in formulas:
                if name in self.item_names:
                    self.items[name].formula = formulas[name]
                    """# check for formula_str and variable_mapping to determine if item should be editable
                    if item.formula["formula_str"] and item.formula["variable_mapping"]:
                        # This is a complete formula with variable mapping
                        item.is_name_editable = True
                        item.is_formula_editable = True
                    elif item.formula["formula_str"]:
                        # This is a formula without variable mapping,
                        # the formula_str is the same as the name
                        item.is_name_editable = True
                        item.is_formula_editable = False"""

                else:
                    # If formula name is not in items, add it as a new item
                    print("HMM I DON'T THINK THIS SHOULD PRINT")

                    """formula_item = FormulaItem(name=name)
                    formula_item.selected = False  # start unselected by default
                    formula_item.info = self.default_info()
                    formula_item.formula = {
                        "formula_str": name,
                        "variable_mapping": name,
                    }
                    self.formulaItems[name] = formula_item"""

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
            widget.deleteLater()
        self.row_widgets.clear()

        # Remove old layout items, skip filtering for
        while self.container_layout.count() > 0:
            item = self.container_layout.takeAt(self.container_layout.count() - 1)
            if item.spacerItem():
                pass
            elif item.widget() == self.insert_row:
                pass

        # Filter and display items
        row_index = 0
        for item in self._all_items:
            if self._passes_filters(item):
                row_widget = ObjectiveRowWidget(item, row_index, parent=self)
                row_widget.item_renamed.connect(self._on_item_renamed)
                row_widget.formula_updated.connect(
                    lambda formula_str, i=item: self.update_item_formula(i, formula_str)
                )
                row_widget.formula_double_clicked.connect(
                    self.formula_double_clicked.emit
                )
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
        return [{item.name: {"rule": item.rule}} for item in selected_items]

    @property
    def item_names(self) -> list[str]:
        """Get a list of all item names."""
        return [item.name for item in self._all_items]

    @property
    def items(self) -> dict[str, ObjectiveItem]:
        """Get a dictionary of items keyed by name."""
        return {item.name: item for item in self._all_items}

    @property
    def formulas(self) -> dict:
        _formulas = {}
        for item in self._all_items:
            if item.formula[
                "formula_str"
            ]:  # "] != "none": # second part saves stat selection
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
        """Add a new objective item to the list.

        Parameters
        ----------
        name : str
            The name of the new objective.
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

        print(f"Adding new item: {name}, formula: {formula_str}")

        # Create new objective item with default rule and formula
        new_item = ObjectiveItem(
            checked=checked,
            name=name,
            rule="MINIMIZE",
        )

        if formula_str:
            # add item as formula
            new_item.formula["formula_str"] = formula_str
            new_item.formula["variable_mapping"] = self.get_variable_mapping(
                formula_str,
                current_name=name,
            )
        else:
            new_item.formula["formula_str"] = name
            if "`" in name:
                new_item.formula["variable_mapping"] = self.get_variable_mapping(
                    name, current_name=name
                )

        # Add to items list
        self._all_items.append(new_item)

        # Rebuild view to display new item
        self._rebuild_view()

        # self.update_vocs()

    def get_variable_mapping(
        self, formula_str: str, current_name: str
    ) -> dict[str, str]:

        matches = self.check_for_var_references(formula_str)  # find variable references
        # matches is a list of variable name strings

        visited = set()

        variable_mapping = {}
        for match in matches:
            if match in visited:
                variable_mapping[match] = None
                continue

            item = self.items[match]

            if item.formula["formula_str"]:
                # If item is formula, get full formula with variable mapping for later expansion
                variable_mapping[item.name] = item.formula
            else:
                # If item is not formula, map to var name
                variable_mapping[item.name] = item.formula["formula_str"]
            print(f"match: {match}, var_map: {variable_mapping}")

        return variable_mapping

    def check_for_var_references(self, expr: str) -> list[str]:
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

    def _on_item_renamed(self, old_name: str, new_name: str) -> None:
        """Handle renaming of an item and update references in other items.

        Parameters
        ----------
        old_name : str
            The previous name of the item
        new_name : str
            The new name of the item
        """
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

        self.check_for_circular_reference(item, new_formula_str)

        # check for duplicate formulas
        if new_formula_str in self.formula_strs:
            self.show_duplicate_warning(new_formula_str)
            return

        item.formula["formula_str"] = new_formula_str
        # Recalculate variable mapping for the updated formula
        item.formula["variable_mapping"] = self.get_variable_mapping(
            new_formula_str, current_name=item.name
        )

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
        item.formula["variable_mapping"] = self.get_variable_mapping(
            new_formula_str, current_name=item.name
        )
        print(item.formula["variable_mapping"])

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
        print(self.get_variable_mapping(new_formula_str, item.name))

        def find_refs(var_mapping: dict):
            for name, mapping in var_mapping.items():
                print(name, mapping)
                if name == item.name:
                    raise ValueError("Circular reference detected!")
                if isinstance(mapping, dict):
                    find_refs(mapping)

        find_refs(self.get_variable_mapping(new_formula_str, item.name))

    def update_vocs(self):
        logging.debug("Emitting data_changed signal from editable_table")
        self.data_changed.emit()
