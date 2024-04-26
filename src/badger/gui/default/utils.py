from importlib import resources
from PyQt5.QtWidgets import QWidget, QAbstractSpinBox, QPushButton
from PyQt5.QtCore import Qt, QObject, QEvent, QSize
from PyQt5.QtGui import QIcon
import copy


def preventAnnoyingSpinboxScrollBehaviour(
        self, control: QAbstractSpinBox) -> None:
    control.setFocusPolicy(Qt.StrongFocus)
    control.installEventFilter(self.MouseWheelWidgetAdjustmentGuard(control))


class MouseWheelWidgetAdjustmentGuard(QObject):
    def __init__(self, parent: QObject):
        super().__init__(parent)

    def eventFilter(self, o: QObject, e: QEvent) -> bool:
        widget: QWidget = o
        if e.type() == QEvent.Wheel and not widget.hasFocus():
            e.ignore()
            return True
        return super().eventFilter(o, e)


def create_button(icon_file, tooltip,
                  stylesheet=None, size=(32, 32), icon_size=None):
    icon_ref = resources.files(__package__) / f'./images/{icon_file}'
    with resources.as_file(icon_ref) as icon_path:
        icon = QIcon(str(icon_path))

    btn = QPushButton()
    if size:
        btn.setFixedSize(*size)
    btn.setIcon(icon)
    btn.setToolTip(tooltip)
    if icon_size:
        btn.setIconSize(QSize(*icon_size))

    if stylesheet is not None:
        btn.setStyleSheet(stylesheet)

    return btn


def filter_generator_config(name, config):
    filtered_config = {}
    if name == 'neldermead':
        filtered_config['xatol'] = config['xatol']
        filtered_config['fatol'] = config['fatol']
        filtered_config['adaptive'] = config['adaptive']
    elif name == 'expected_improvement':
        filtered_config['turbo_controller'] = config['turbo_controller']
        filtered_config['numerical_optimizer'] = config['numerical_optimizer']
        filtered_config['max_travel_distances'] = config['max_travel_distances']
        filtered_config['n_interpolate_points'] = config['n_interpolate_points']
    elif name == 'rcds':
        filtered_config['noise'] = config['noise']
        filtered_config['step'] = config['step']
        filtered_config['tol'] = config['tol']
    else:
        filtered_config = config

    return copy.deepcopy(filtered_config)
