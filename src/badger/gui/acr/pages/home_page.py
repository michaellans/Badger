import gc
import os
import yaml
import traceback
from importlib import resources
from typing import List

from pandas import DataFrame
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QIcon, QKeySequence
from PyQt5.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QShortcut,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from badger.archive import delete_run, get_base_run_filename, load_run
from badger.db import (
    export_routines,
    get_runs,
    get_runs_by_routine,
    import_routines,
    list_routine,
    load_routine,
    remove_routine,
)
from badger.gui.default.components.data_table import (
    add_row,
    data_table,
    reset_table,
    update_table,
)
from badger.gui.default.components.filter_cbox import BadgerFilterBox
from badger.gui.acr.components.history_navigator import HistoryNavigator
from badger.gui.acr.components.routine_editor import BadgerRoutineEditor
from badger.gui.default.components.routine_item import BadgerRoutineItem
from badger.gui.default.components.run_monitor import BadgerOptMonitor
from badger.gui.default.components.search_bar import search_bar
from badger.gui.acr.components.status_bar import BadgerStatusBar
from badger.gui.acr.components.action_bar import BadgerActionBar
from badger.utils import get_header, strtobool
from badger.settings import init_settings

# from PyQt5.QtGui import QBrush, QColor
from badger.gui.default.windows.message_dialog import BadgerScrollableMessageBox
from badger.gui.default.utils import ModalOverlay

stylesheet = """
QPushButton:hover:pressed
{
    background-color: #C7737B;
}
QPushButton:hover
{
    background-color: #BF616A;
}
QPushButton
{
    background-color: #A9444E;
}
"""


class BadgerHomePage(QWidget):
    sig_routine_activated = pyqtSignal(bool)

    def __init__(self, process_manager=None):
        super().__init__()

        self.mode = "regular"  # home page mode
        self.splitter_state = None  # store the run splitter state
        self.process_manager = process_manager
        self.current_routine = None  # current routine
        self.go_run_failed = False  # flag to indicate go_run failed
        self.init_ui()
        self.config_logic()

        self.load_all_runs()

    def init_ui(self):
        self.config_singleton = init_settings()
        icon_ref = resources.files(__package__) / "../images/add.png"

        with resources.as_file(icon_ref) as icon_path:
            self.icon_add = QIcon(str(icon_path))
        icon_ref = resources.files(__package__) / "../images/import.png"
        with resources.as_file(icon_ref) as icon_path:
            self.icon_import = QIcon(str(icon_path))
        icon_ref = resources.files(__package__) / "../images/export.png"
        with resources.as_file(icon_ref) as icon_path:
            self.icon_export = QIcon(str(icon_path))

        # Set up the layout
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        # History run browser
        self.history_browser = history_browser = HistoryNavigator()
        history_browser.setMinimumWidth(360)

        # Splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        vbox.addWidget(splitter, 1)

        # Routine panel
        self.panel_routine = panel_routine = QWidget()
        panel_routine.setMinimumWidth(360)
        vbox_routine = QVBoxLayout(panel_routine)

        # Search bar
        panel_search = QWidget()
        hbox_search = QHBoxLayout(panel_search)
        hbox_search.setContentsMargins(0, 0, 0, 0)

        self.sbar = sbar = search_bar()
        sbar.setFixedHeight(36)
        f = sbar.font()
        f.setPixelSize(16)
        sbar.setFont(f)
        self.btn_new = btn_new = QPushButton()
        btn_new.setFixedSize(36, 36)
        btn_new.setIcon(self.icon_add)
        btn_new.setToolTip("Create new routine")
        hbox_search.addWidget(sbar)
        # hbox_search.addSpacing(4)
        hbox_search.addWidget(btn_new)
        vbox_routine.addWidget(panel_search)

        # Filters
        self.filter_box = filter_box = BadgerFilterBox(self, title=" Filters")
        if not strtobool(self.config_singleton.read_value("BADGER_ENABLE_ADVANCED")):
            filter_box.hide()
        vbox_routine.addWidget(filter_box)

        # Routine list
        self.routine_list = routine_list = QListWidget()
        routine_list.setAlternatingRowColors(True)
        routine_list.setSpacing(1)
        routine_list.setViewportMargins(0, 0, 17, 0)  # leave space for scrollbar
        self.refresh_routine_list()
        self.prev_routine_item = None  # last selected routine
        vbox_routine.addWidget(routine_list)

        # Action bar
        action_bar = QWidget()
        hbox_action = QHBoxLayout(action_bar)
        hbox_action.setContentsMargins(0, 0, 0, 0)
        self.btn_export = btn_export = QPushButton()
        btn_export.setFixedSize(28, 28)
        btn_export.setIcon(self.icon_export)
        btn_export.setToolTip("Export filtered routines")
        self.btn_import = btn_import = QPushButton()
        btn_import.setFixedSize(28, 28)
        btn_import.setIcon(self.icon_import)
        btn_import.setToolTip("Import routines")
        hbox_action.addStretch(1)
        hbox_action.addWidget(btn_import)
        hbox_action.addWidget(btn_export)
        vbox_routine.addWidget(action_bar)

        # Monitor panel
        panel_monitor = QWidget()
        vbox_monitor = QVBoxLayout(panel_monitor)
        vbox_monitor.setContentsMargins(8, 0, 8, 0)

        # Run monitor
        self.run_view = run_view = QWidget()  # for consistent bg
        vbox_monitor.addWidget(run_view)
        vbox_run_view = QVBoxLayout(run_view)
        vbox_run_view.setContentsMargins(0, 0, 0, 10)
        self.run_monitor = run_monitor = BadgerOptMonitor(self.process_manager)
        vbox_run_view.addWidget(run_monitor)

        # Data table
        self.run_table = run_table = data_table()
        run_table.set_uneditable()  # should not be editable

        # Routine view
        self.routine_view = routine_view = QWidget()  # for consistent bg
        routine_view.setMinimumWidth(640)
        vbox_routine_view = QVBoxLayout(routine_view)
        vbox_routine_view.setContentsMargins(0, 0, 0, 10)
        self.routine_editor = routine_editor = BadgerRoutineEditor()
        vbox_routine_view.addWidget(routine_editor)

        # Add action bar
        self.run_action_bar = run_action_bar = BadgerActionBar()

        # Run panel (routine editor + run monitor + data table + action bar)
        panel_run = QWidget()
        vbox_run = QVBoxLayout(panel_run)
        vbox_run.setContentsMargins(0, 0, 0, 0)
        vbox_run.setSpacing(0)

        splitter_run = QSplitter(Qt.Horizontal)
        splitter_run.setStretchFactor(0, 1)
        splitter_run.setStretchFactor(1, 1)
        splitter_run.setStretchFactor(2, 0)
        vbox_run.addWidget(splitter_run, 1)

        splitter_run.addWidget(routine_view)
        splitter_run.addWidget(panel_monitor)
        splitter_run.addWidget(run_table)

        vbox_run.addWidget(run_action_bar, 0)

        # Add panels to splitter
        splitter.addWidget(history_browser)
        splitter.addWidget(panel_run)

        # Set initial sizes (left fixed, middle and right equal)
        total_width = 1640  # Total width of the splitter
        fixed_width = 360  # Fixed width for the left panel
        remaining_width = total_width - fixed_width
        equal_width = remaining_width // 2
        splitter.setSizes([fixed_width, remaining_width])
        splitter_run.setSizes([equal_width, equal_width, 0])

        self.status_bar = status_bar = BadgerStatusBar()
        status_bar.set_summary("Badger is ready!")
        vbox.addWidget(status_bar)

    def config_logic(self):
        self.colors = ["c", "g", "m", "y", "b", "r", "w"]
        self.symbols = ["o", "t", "t1", "s", "p", "h", "d"]

        self.sbar.textChanged.connect(self.refresh_routine_list)
        self.btn_new.clicked.connect(self.create_new_routine)
        self.routine_list.itemClicked.connect(self.select_routine)
        self.run_table.cellClicked.connect(self.solution_selected)
        self.run_table.itemSelectionChanged.connect(self.table_selection_changed)

        self.filter_box.cb_obj.currentIndexChanged.connect(self.refresh_routine_list)
        self.filter_box.cb_reg.currentIndexChanged.connect(self.refresh_routine_list)
        self.filter_box.cb_gain.currentIndexChanged.connect(self.refresh_routine_list)

        self.history_browser.tree_widget.itemSelectionChanged.connect(self.go_run)

        self.run_monitor.sig_inspect.connect(self.inspect_solution)
        self.run_monitor.sig_lock.connect(self.toggle_lock)
        self.run_monitor.sig_new_run.connect(self.new_run)
        self.run_monitor.sig_run_started.connect(self.uncover_page)
        self.run_monitor.sig_run_name.connect(self.run_name)
        self.run_monitor.sig_status.connect(self.update_status)
        self.run_monitor.sig_progress.connect(self.progress)
        self.run_monitor.sig_del.connect(self.delete_run)
        self.run_monitor.sig_stop_run.connect(self.cover_page)
        self.run_monitor.sig_run_started.connect(self.run_action_bar.run_start)
        self.run_monitor.sig_routine_finished.connect(self.run_action_bar.routine_finished)
        self.run_monitor.sig_lock_action.connect(self.run_action_bar.lock)
        self.run_monitor.sig_toggle_reset.connect(self.run_action_bar.toggle_reset)
        self.run_monitor.sig_toggle_run.connect(self.run_action_bar.toggle_run)
        self.run_monitor.sig_toggle_other.connect(self.run_action_bar.toggle_other)
        self.run_monitor.sig_set_run_action.connect(self.run_action_bar.set_run_action)
        self.run_monitor.sig_env_ready.connect(self.run_action_bar.env_ready)

        self.run_action_bar.sig_start.connect(self.run_monitor.start)
        self.run_action_bar.sig_stop.connect(self.run_monitor.stop)
        self.run_action_bar.sig_delete_run.connect(self.run_monitor.delete_run)
        self.run_action_bar.sig_logbook.connect(self.run_monitor.logbook)
        self.run_action_bar.sig_reset_env.connect(self.run_monitor.reset_env)
        self.run_action_bar.sig_jump_to_optimal.connect(self.run_monitor.jump_to_optimal)
        self.run_action_bar.sig_dial_in.connect(self.run_monitor.set_vars)
        self.run_action_bar.sig_ctrl.connect(self.run_monitor.ctrl_routine)
        self.run_action_bar.sig_run_action.connect(self.run_monitor.set_run_action)
        self.run_action_bar.sig_run_until_action.connect(self.run_monitor.set_run_until_action)
        self.run_action_bar.sig_open_extensions_palette.connect(self.run_monitor.open_extensions_palette)

        self.routine_editor.sig_saved.connect(self.routine_saved)
        self.routine_editor.sig_canceled.connect(self.done_create_routine)
        self.routine_editor.sig_deleted.connect(self.routine_deleted)
        self.routine_editor.routine_page.sig_updated.connect(
            self.routine_description_updated
        )

        # Assign shortcuts
        self.shortcut_go_search = QShortcut(QKeySequence("Ctrl+L"), self)
        self.shortcut_go_search.activated.connect(self.go_search)

        # Export/import routines
        self.btn_export.clicked.connect(self.export_routines)
        self.btn_import.clicked.connect(self.import_routines)

    def go_search(self):
        self.sbar.setFocus()

    def load_all_runs(self):
        runs = get_runs()
        self.history_browser.updateItems(runs)

    def create_new_routine(self):
        self.splitter_state = self.splitter_run.saveState()
        self.routine_editor.set_routine(None)
        self.mode = "new routine"
        self.routine_editor.switch_mode(self.mode)
        self.toggle_lock(True, 0)

    def select_routine(self, routine_item: QListWidgetItem, force=False):
        # force: if True, select the target routine_item even if
        #        it's selected already
        if self.prev_routine_item:
            try:
                self.routine_list.itemWidget(self.prev_routine_item).deactivate()
            except ValueError:
                pass

            if (not force) and (
                self.prev_routine_item.routine_id == routine_item.routine_id
            ):
                # click a routine again to deselect
                self.prev_routine_item = None
                self.current_routine = None
                self.load_all_runs()
                if not self.history_browser.count():
                    self.go_run(-1)  # sometimes we need to trigger this manually
                self.sig_routine_activated.emit(False)
                return

        self.prev_routine_item = routine_item  # note that prev_routine is an item!
        self.sig_routine_activated.emit(True)

        routine, timestamp = load_routine(routine_item.routine_id)
        self.current_routine = routine
        self.routine_editor.set_routine(routine)
        runs = get_runs_by_routine(routine.id)
        self.history_browser.updateItems(runs)
        print(self.history_browser.count())
        if not self.history_browser.count():
            self.go_run(-1)  # sometimes we need to trigger this manually

        if not runs:  # auto plot will not be triggered
            self.run_monitor.init_plots(routine)

        if self.go_run_failed:  # failed to load run, do not select the routine
            self.go_run_failed = False
        else:
            self.routine_list.itemWidget(routine_item).activate()

    def build_routine_list(
        self,
        routine_ids: List[str],
        routine_names: List[str],
        timestamps: List[str],
        environments: List[str],
        descriptions: List[str],
    ):
        # use id instead of name where needed
        try:
            selected_routine = self.prev_routine_item.routine_id
        except Exception:
            selected_routine = None
        self.routine_list.clear()
        BADGER_PLUGIN_ROOT = self.config_singleton.read_value("BADGER_PLUGIN_ROOT")
        env_dict_dir = os.path.join(
            BADGER_PLUGIN_ROOT, "environments", "env_colors.yaml"
        )
        try:
            with open(env_dict_dir, "r") as stream:
                env_dict = yaml.safe_load(stream)
        except (FileNotFoundError, yaml.YAMLError):
            env_dict = {}
        for i, routine_id in enumerate(routine_ids):
            _item = BadgerRoutineItem(
                routine_id,
                routine_names[i],
                timestamps[i],
                environments[i],
                env_dict,
                descriptions[i],
                self,
            )
            _item.sig_del.connect(self.delete_routine)
            item = QListWidgetItem(self.routine_list)
            item.routine_id = routine_id  # dirty trick
            item.setSizeHint(_item.sizeHint())
            self.routine_list.addItem(item)
            self.routine_list.setItemWidget(item, _item)
            if routine_id == selected_routine:
                _item.activate()
                self.prev_routine_item = item

    def get_current_routines(self):
        keyword = self.sbar.text()
        tag_obj = self.filter_box.cb_obj.currentText()
        tag_reg = self.filter_box.cb_reg.currentText()
        tag_gain = self.filter_box.cb_gain.currentText()
        tags = {}
        if tag_obj:
            tags["objective"] = tag_obj
        if tag_reg:
            tags["region"] = tag_reg
        if tag_gain:
            tags["gain"] = tag_gain
        routine_ids, routine_names, timestamps, environments, descriptions = (
            list_routine(keyword, tags)
        )

        return routine_ids, routine_names, timestamps, environments, descriptions

    def refresh_routine_list(self):
        routine_ids, routine_names, timestamps, environments, descriptions = (
            self.get_current_routines()
        )

        self.build_routine_list(
            routine_ids, routine_names, timestamps, environments, descriptions
        )

    def go_run(self, i: int = None):
        gc.collect()

        # if self.cb_history.itemText(0) == "Optimization in progress...":
        #     return

        if i == -1:
            update_table(self.run_table)
            try:
                self.current_routine.data = None  # reset the data
            except AttributeError:  # current routine is None
                pass
            self.run_monitor.init_plots(self.current_routine)
            if not self.current_routine:
                self.routine_editor.set_routine(None)
                self.status_bar.set_summary("No active routine")
            else:
                self.status_bar.set_summary(
                    f"Current routine: {self.current_routine.name}"
                )
            return

        run_filename = get_base_run_filename(self.history_browser.currentText())
        try:
            _routine = load_run(run_filename)
            routine, _ = load_routine(_routine.id)  # get the initial routine
            # TODO: figure out how to recover the original routine
            if routine is None:  # routine not found, could be deleted
                routine = _routine  # make do w/ the routine saved in run
            else:
                routine.data = _routine.data
                routine.vocs = _routine.vocs
                routine.initial_points = _routine.initial_points
                del _routine  # release the resource
                gc.collect()
        except IndexError:
            return
        except Exception as e:  # failed to load the run
            details = traceback.format_exc()
            dialog = BadgerScrollableMessageBox(
                title="Error!", text=str(e), parent=self
            )
            dialog.setIcon(QMessageBox.Critical)
            dialog.setDetailedText(details)
            dialog.exec_()
            self.go_run_failed = True

            # Show info in the nav bar
            # red_brush = QBrush(QColor(255, 0, 0))  # red color
            # self.cb_history.changeCurrentItem(
            #     f"{run_filename} (failed to load)",
            #     # color=red_brush)
            #     color=None,
            # )

            return

        self.current_routine = routine  # update the current routine
        update_table(self.run_table, routine.sorted_data)
        self.run_monitor.init_plots(routine, run_filename)
        self.routine_editor.set_routine(routine, silent=True)
        self.status_bar.set_summary(f"Current routine: {self.current_routine.name}")

    def inspect_solution(self, idx):
        self.run_table.selectRow(idx)

    def solution_selected(self, r, c):
        self.run_monitor.jump_to_solution(r)

    def table_selection_changed(self):
        indices = self.run_table.selectedIndexes()
        if len(indices) == 1:  # let other method handles it
            return

        row = -1
        for index in indices:
            _row = index.row()
            if _row == row:
                continue

            if row == -1:
                row = _row
                continue

            return

        self.run_monitor.jump_to_solution(row)

    def toggle_lock(self, lock, lock_tab=1):
        if lock:
            self.panel_routine.setDisabled(True)
            self.history_browser.setDisabled(True)
        else:
            self.panel_routine.setDisabled(False)
            self.history_browser.setDisabled(False)

            self.uncover_page()

    def new_run(self):
        self.cover_page()

        # self.cb_history.insertItem(0, "Optimization in progress...")
        # self.cb_history.setCurrentIndex(0)

        header = get_header(self.current_routine)
        reset_table(self.run_table, header)

    def run_name(self, name):
        if self.prev_routine_item:
            runs = get_runs_by_routine(self.current_routine.id)
        else:
            runs = get_runs()
        self.history_browser.updateItems(runs)
        self.history_browser._selectItemByRun(name)

    def update_status(self, info):
        self.status_bar.set_summary(info)

    def progress(self, solution: DataFrame):
        vocs = self.current_routine.vocs
        vars = list(solution[vocs.variable_names].to_numpy()[0])
        objs = list(solution[vocs.objective_names].to_numpy()[0])
        cons = list(solution[vocs.constraint_names].to_numpy()[0])
        stas = list(solution[vocs.observable_names].to_numpy()[0])
        add_row(self.run_table, objs + cons + vars + stas)

    def delete_run(self):
        run_name = get_base_run_filename(self.history_browser.currentText())

        reply = QMessageBox.question(
            self,
            "Delete run",
            f"Are you sure you want to delete run {run_name}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        delete_run(run_name)
        # Reset current routine if no routine is selected
        if not self.prev_routine_item:
            self.current_routine = None
            runs = get_runs()
        else:
            runs = get_runs_by_routine(self.current_routine.id)
        self.history_browser.tree_widget.blockSignals(True)
        self.history_browser.updateItems(runs)
        self.history_browser.tree_widget.blockSignals(False)
        self.go_run(-1)

    def routine_saved(self):
        self.refresh_routine_list()
        self.select_routine(self.routine_list.item(0), force=True)
        self.done_create_routine()

    def done_create_routine(self):
        if self.mode == "new routine":
            self.mode = "regular"
            self.routine_editor.switch_mode(self.mode)
            self.routine_editor.set_routine(self.current_routine)
            self.splitter_run.restoreState(self.splitter_state)
            self.splitter_state = None
            self.toggle_lock(False)

    def delete_routine(self, id):
        remove_routine(id)
        self.routine_deleted(id)

    def routine_deleted(self, id=None):
        if self.prev_routine_item:
            if self.prev_routine_item.routine_id == id:
                self.prev_routine_item = None
                self.current_routine = None
                self.load_all_runs()
                if not self.history_browser.count():
                    self.go_run(-1)  # sometimes we need to trigger this manually
                self.sig_routine_activated.emit(False)

        self.refresh_routine_list()

    def routine_description_updated(self, name, descr):
        for i in range(self.routine_list.count()):
            item = self.routine_list.item(i)
            if item is not None:
                routine_item = self.routine_list.itemWidget(item)
                if routine_item.name == name:
                    routine_item.update_description(descr)
                    break

    def export_routines(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Badger routines", "", "Database Files (*.db)", options=options
        )

        if not filename:
            return

        _, ext = os.path.splitext(filename)
        if not ext:
            filename = filename + ".db"

        try:
            routine_ids, _, _, _, _ = self.get_current_routines()
            export_routines(filename, routine_ids)

            QMessageBox.information(
                self,
                "Success!",
                f"Export success: filtered routines exported to {filename}",
            )
        except Exception as e:
            QMessageBox.critical(self, "Export failed!", f"Export failed: {str(e)}")

    def import_routines(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getOpenFileName(
            self, "Import Badger routines", "", "Database Files (*.db)", options=options
        )

        if not filename:
            return

        _, ext = os.path.splitext(filename)
        if not ext:
            filename = filename + ".db"

        try:
            import_routines(filename)

            QMessageBox.information(
                self,
                "Success!",
                f"Import success: imported all routines from {filename}",
            )
        except Exception as e:
            QMessageBox.warning(
                self,
                "Heads-up!",
                f"Failed to import the following routines since they already existed: \n{str(e)}",
            )

    def cover_page(self):
        return  # disable overlay for now

        try:
            self.overlay
        except AttributeError:
            # Set parent to the main window
            try:
                main_window = self.parent().parent()
            except AttributeError:  # in test mode
                return
            self.overlay = ModalOverlay(main_window)
        self.overlay.show()

    def uncover_page(self):
        return  # disable overlay for now

        try:
            self.overlay.hide()
        except AttributeError:  # in test mode
            pass
