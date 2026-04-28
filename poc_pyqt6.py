#!/usr/bin/env python3
"""aka-semi-utils PyQt6 POC — 矩形缩略图网格 + 暗色主题 + 配置面板."""

import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPixmap, QImage
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PIL import Image


# ── 常量 ──
THUMB_W, THUMB_H = 100, 75   # 矩形缩略图 (4:3)
GRID_COLS = 5
GRID_ROWS = 2
GRID_MAX = GRID_COLS * GRID_ROWS

# 颜色
BG = "#121212"
SURFACE = "#1E1E1E"
BORDER = "#333333"
TEXT_PRIMARY = "#E0E0E0"
TEXT_SECONDARY = "#999999"
ACCENT = "#E0E0E0"


class ThumbLabel(QLabel):
    """固定矩形的缩略图标签."""

    def __init__(self, path: str | None = None, overflow_text: str = "", parent=None):
        super().__init__(parent)
        self.setFixedSize(THUMB_W, THUMB_H)
        self.setStyleSheet(f"""
            QLabel {{
                border: 1px solid {BORDER};
                border-radius: 4px;
                background-color: {SURFACE};
            }}
        """)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if overflow_text:
            self.setText(overflow_text)
            self.setStyleSheet(f"""
                QLabel {{
                    border: 1px solid {BORDER};
                    border-radius: 4px;
                    background-color: #252525;
                    color: {TEXT_SECONDARY};
                    font-size: 18px;
                    font-weight: bold;
                }}
            """)
        elif path:
            self._load_image(path)

    def _load_image(self, path: str):
        try:
            with Image.open(path) as img:
                img = img.convert("RGB")
                # cover 裁切到目标矩形
                ratio = max(THUMB_W / img.width, THUMB_H / img.height)
                new_size = (int(img.width * ratio), int(img.height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                left = (img.width - THUMB_W) // 2
                top = (img.height - THUMB_H) // 2
                img = img.crop((left, top, left + THUMB_W, top + THUMB_H))

                # PIL -> QPixmap
                data = img.tobytes("raw", "RGB")
                qimg = QImage(data, img.width, img.height, img.width * 3, QImage.Format.Format_RGB888)
                pixmap = QPixmap.fromImage(qimg)
                self.setPixmap(pixmap)
        except Exception as e:
            self.setText("×")
            print(f"缩略图失败: {e}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("aka-semi-utils (PyQt6 POC)")
        self.setFixedSize(620, 780)
        self.selected_paths: list[str] = []

        # 中央部件
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        # ── 标题 ──
        title = QLabel("aka-semi-utils 极简水印")
        title.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 18px; font-weight: bold;")
        root.addWidget(title)

        # ── 分割线 ──
        root.addWidget(self._make_divider())

        # ── 选择行 ──
        select_row = QHBoxLayout()
        self.select_btn = QPushButton(" 选择图片文件")
        self.select_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT};
                color: #121212;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 13px;
            }}
            QPushButton:hover {{ background-color: #FFFFFF; }}
        """)
        self.select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_btn.clicked.connect(self._on_select)

        self.count_label = QLabel("已选择: 0 张")
        self.count_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")

        select_row.addWidget(self.select_btn)
        select_row.addStretch()
        select_row.addWidget(self.count_label)
        root.addLayout(select_row)

        # ── 缩略图区域 ──
        self.thumb_container = QWidget()
        self.thumb_container.setFixedSize(
            GRID_COLS * THUMB_W + (GRID_COLS - 1) * 8 + 8,
            GRID_ROWS * THUMB_H + (GRID_ROWS - 1) * 8 + 8,
        )
        self.thumb_container.setStyleSheet(f"""
            QWidget {{
                background-color: {SURFACE};
                border-radius: 6px;
                border: 1px solid {BORDER};
            }}
        """)
        self.thumb_grid = QGridLayout(self.thumb_container)
        self.thumb_grid.setContentsMargins(4, 4, 4, 4)
        self.thumb_grid.setSpacing(8)
        self.thumb_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        # 空状态提示
        self.empty_hint = QLabel("点击选择图片\n支持 JPG / PNG / HEIC")
        self.empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_hint.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px;")
        self.thumb_grid.addWidget(self.empty_hint, 0, 0, GRID_ROWS, GRID_COLS, Qt.AlignmentFlag.AlignCenter)

        root.addWidget(self.thumb_container, alignment=Qt.AlignmentFlag.AlignCenter)

        # ── 进度条 ──
        self.progress = QProgressBar()
        self.progress.setFixedWidth(520)
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: #333333;
                border: none;
                border-radius: 3px;
                height: 6px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {ACCENT};
                border-radius: 3px;
            }}
        """)
        self.progress.setValue(0)
        root.addWidget(self.progress, alignment=Qt.AlignmentFlag.AlignCenter)

        # ── 状态文字 ──
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        root.addWidget(self.status_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # ── START 按钮 ──
        self.start_btn = QPushButton("S T A R T")
        self.start_btn.setFixedSize(520, 48)
        self.start_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT};
                color: #121212;
                border: none;
                border-radius: 4px;
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #FFFFFF;
                border: 2px solid {ACCENT};
            }}
        """)
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        root.addWidget(self.start_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # ── 分割线 ──
        root.addWidget(self._make_divider())

        # ── 配置面板 ──
        config_label = QLabel("水印配置")
        config_label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 14px; font-weight: bold;")
        root.addWidget(config_label)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                background-color: {SURFACE};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 12px;
            }}
            QTabBar::tab {{
                background-color: {BG};
                color: {TEXT_SECONDARY};
                padding: 8px 16px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }}
            QTabBar::tab:selected {{
                background-color: {SURFACE};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER};
                border-bottom: none;
            }}
            QTabBar::tab:hover {{
                color: {TEXT_PRIMARY};
            }}
        """)

        for corner in ["左上", "左下", "右上", "右下"]:
            self.tabs.addTab(self._build_corner_tab(corner), corner)
        self.tabs.addTab(self._build_logo_tab(), "Logo")

        root.addWidget(self.tabs)

    def _make_divider(self) -> QWidget:
        div = QWidget()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background-color: {BORDER};")
        return div

    def _build_corner_tab(self, corner: str) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        title = QLabel(f"{corner} 水印字段")
        title.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 14px; font-weight: bold;")
        layout.addWidget(title)

        # 字段行
        row = QHBoxLayout()
        combo = self._make_combo(["相机型号", "镜头型号", "拍摄参数", "拍摄日期"])
        sep = self._make_lineedit(" · ", 50)
        add_btn = QPushButton("+ 添加字段")
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #333333;
                color: {TEXT_PRIMARY};
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
            }}
        """)
        row.addWidget(combo)
        row.addWidget(sep)
        row.addWidget(add_btn)
        row.addStretch()
        layout.addLayout(row)

        layout.addWidget(self._make_divider())

        info = QLabel("字体: NotoSansCJKsc-Bold\n颜色: #242424")
        info.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        layout.addWidget(info)
        layout.addStretch()
        return w

    def _build_logo_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        title = QLabel("Logo 设置")
        title.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 14px; font-weight: bold;")
        layout.addWidget(title)

        combo = self._make_combo(["自动匹配", "不使用", "自定义..."])
        layout.addWidget(combo)

        btn = QPushButton("配置品牌替换...")
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #333333;
                color: {TEXT_PRIMARY};
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
            }}
        """)
        layout.addWidget(btn)
        layout.addStretch()
        return w

    def _make_combo(self, items: list[str]) -> QWidget:
        from PyQt6.QtWidgets import QComboBox
        combo = QComboBox()
        combo.addItems(items)
        combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {SURFACE};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER};
                border-radius: 4px;
                padding: 4px 8px;
                min-width: 120px;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {SURFACE};
                color: {TEXT_PRIMARY};
                selection-background-color: #333333;
            }}
        """)
        return combo

    def _make_lineedit(self, text: str, width: int) -> QWidget:
        from PyQt6.QtWidgets import QLineEdit
        le = QLineEdit(text)
        le.setFixedWidth(width)
        le.setStyleSheet(f"""
            QLineEdit {{
                background-color: {SURFACE};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER};
                border-radius: 4px;
                padding: 4px 6px;
            }}
        """)
        return le

    def _on_select(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择图片文件（可多选）",
            "",
            "图片文件 (*.jpg *.jpeg *.png *.heic);;所有文件 (*.*)",
        )
        if not files:
            return

        self.selected_paths = files
        self.count_label.setText(f"已选择: {len(self.selected_paths)} 张")
        self._refresh_thumbnails()

    def _refresh_thumbnails(self):
        # 清空 grid
        while self.thumb_grid.count():
            item = self.thumb_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        show_count = min(len(self.selected_paths), GRID_MAX)

        for i, path in enumerate(self.selected_paths[:show_count]):
            row = i // GRID_COLS
            col = i % GRID_COLS
            thumb = ThumbLabel(path=path)
            thumb.setToolTip(Path(path).name)
            self.thumb_grid.addWidget(thumb, row, col)

        # 溢出
        if len(self.selected_paths) > GRID_MAX:
            overflow = len(self.selected_paths) - GRID_MAX
            row = GRID_ROWS - 1
            col = GRID_COLS - 1
            plus = ThumbLabel(overflow_text=f"+{overflow}")
            plus.setToolTip(f"还有 {overflow} 张未显示")
            self.thumb_grid.addWidget(plus, row, col)

        # 空状态
        if len(self.selected_paths) == 0:
            self.thumb_grid.addWidget(
                self.empty_hint, 0, 0, GRID_ROWS, GRID_COLS, Qt.AlignmentFlag.AlignCenter
            )


def main():
    app = QApplication(sys.argv)

    # 全局暗色 QSS
    app.setStyleSheet(f"""
        QMainWindow {{
            background-color: {BG};
        }}
        QWidget {{
            font-family: "SF Pro", "Segoe UI", "PingFang SC", sans-serif;
        }}
        QTabWidget {{
            background-color: {BG};
        }}
    """)

    # macOS 暗色菜单栏适配
    app.setStyle("Fusion")

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
