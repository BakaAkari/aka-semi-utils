"""滚轮保护工具。

配置面板放在 :class:`QScrollArea` 中时，`QSpinBox` / `QComboBox` / `QSlider`
等控件默认会吃掉鼠标滚轮并改变值，导致用户想滚动设置页时误改配置。

本模块提供统一事件过滤器：配置控件不再响应滚轮；如果它位于滚动区域内，滚轮事件会转发给最近的滚动区域 viewport，让页面继续滚动。
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtWidgets import (
    QAbstractScrollArea,
    QApplication,
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

        if isinstance(watched, QWidget):
            scroll_area = _nearest_scroll_area(watched)
            if scroll_area is not None:
                event.ignore()
                QApplication.sendEvent(scroll_area.viewport(), event)

        # 无论是否找到滚动区域，都不让 SpinBox/ComboBox/Slider 自己处理滚轮。
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
