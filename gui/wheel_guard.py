"""滚轮保护工具。

配置面板放在 :class:`QScrollArea` 中时，`QSpinBox` / `QComboBox` / `QSlider`
等控件默认会吃掉鼠标滚轮并改变值，导致用户想滚动设置页时误改配置。

本模块提供统一事件过滤器：配置控件不再响应滚轮，避免 PyQt6 在事件过滤器里同步转发同一个事件导致递归崩溃。
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtWidgets import (
    QAbstractScrollArea,
    QComboBox,
    QDoubleSpinBox,
    QSlider,
    QSpinBox,
    QWidget,
)

WheelGuardWidget = QComboBox | QDoubleSpinBox | QSlider | QSpinBox


class _WheelGuardFilter(QObject):
    """拦截值控件的滚轮，避免滚动设置页时误改配置。"""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() != QEvent.Type.Wheel:
            return False

        # 不在这里调用 QApplication.sendEvent 转发同一个 Wheel 事件。
        # PyQt6 在 macOS 下可能因 eventFilter 递归进入 QApplication.notify 而 abort。
        # 直接忽略并拦截即可；滚动页本身在鼠标位于非值控件区域时仍正常滚动。
        event.ignore()
        return True


def _nearest_scroll_area(widget: QWidget) -> QAbstractScrollArea | None:
    """查找控件所在的最近滚动区域。"""
    parent = widget.parentWidget()
    while parent is not None:
        if isinstance(parent, QAbstractScrollArea):
            return parent
        parent = parent.parentWidget()
    return None


def guard_wheel(widget: WheelGuardWidget) -> WheelGuardWidget:
    """禁止单个配置值控件响应鼠标滚轮，并把滚轮交还给滚动页。"""
    if widget.property("wheel_guard_installed"):
        return widget

    # StrongFocus 保留点击/Tab 聚焦能力，但鼠标滚轮不再隐式改值。
    widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    wheel_filter = _WheelGuardFilter(widget)
    widget.installEventFilter(wheel_filter)
    widget.setProperty("wheel_guard_installed", True)
    return widget


def guard_wheel_for_children(parent: QWidget) -> None:
    """为 parent 下已有的所有值控件安装滚轮保护。"""
    for widget in parent.findChildren((QComboBox, QDoubleSpinBox, QSlider, QSpinBox)):
        guard_wheel(widget)
