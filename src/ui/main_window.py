"""Main window for DiskExplorer (PyQt6)."""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

from PyQt6.QtCore import QSettings, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..cache import ScanCache
from ..export import ExportHandler
from ..models import DiskDataModel, FileNode
from ..scanner import FileSystemScanner, ScanCancelledError
from .chart_widget import SizeChartWidget
from .recent_files_panel import RecentFilesPanel
from .tree_view import FileSystemTreeView

_logger = logging.getLogger(__name__)


class ScanWorker(QThread):
    """Background thread that runs the file system scan."""

    progress = pyqtSignal(int, str)    # (count, current_path) – throttled
    finished = pyqtSignal(object)      # FileNode on success
    error = pyqtSignal(str)            # error message
    scan_stats = pyqtSignal(float, int)  # (elapsed_seconds, item_count)

    # Minimum interval between progress signal emissions (seconds).
    _PROGRESS_THROTTLE = 0.25

    def __init__(self, scanner: FileSystemScanner, path: str) -> None:
        super().__init__()
        self._scanner = scanner
        self._path = path
        self._last_emit = 0.0
        self._scan_start = 0.0

    def run(self) -> None:
        self._scan_start = time.monotonic()
        try:
            node = self._scanner.scan_directory_threaded(
                self._path,
                progress_callback=self._on_progress,
            )
            elapsed = time.monotonic() - self._scan_start
            self.scan_stats.emit(elapsed, self._scanner._scanned_count)
            self.finished.emit(node)
        except ScanCancelledError:
            self.error.emit("Scan cancelled.")
        except Exception as exc:
            _logger.exception("Unexpected scan error for %s", self._path)
            self.error.emit(str(exc))

    def _on_progress(self, count: int, path: str) -> None:
        # Secondary throttle at the signal-emission layer so that rapid
        # callbacks from the scanner thread don't flood the Qt event queue.
        now = time.monotonic()
        if now - self._last_emit >= self._PROGRESS_THROTTLE:
            self._last_emit = now
            self.progress.emit(count, path)


class MainWindow(QMainWindow):
    """DiskExplorer main application window."""

    _I18N = {
        "en": {
            "title": "DiskExplorer - Disk Space Analyzer",
            "path": "Path:",
            "scan_selected": "Scan Selected Path",
            "cancel": "Cancel",
            "compare": "Compare with Cache",
            "compare_off": "Exit Compare",
            "ready": "Ready. Select a disk or folder to scan.",
            "scan_in_progress": "Scan in progress",
            "scan_in_progress_msg": "A scan is already running. Cancel it first.",
            "use_cache_title": "Use cached data?",
            "cache_exists": "A cached scan from {mins:.0f} minute(s) ago exists.\nUse cached data? (No = re-scan)",
            "scanning": "Scanning: {path}",
            "scanning_status": "Scanning {path}...",
            "scanned": "Scanned {count:,} items... {path}",
            "done": "Done. {size} in {files:,} files. Scanned {count:,} items in {elapsed:.1f}s ({throughput:,.0f} items/s).",
            "error": "Error: {message}",
            "scan_error": "Scan Error",
            "cancelling": "Cancelling...",
            "could_not_locate": "Could not locate: {path}",
            "select_folder": "Select Folder to Scan",
            "cache_cleared_title": "Cache Cleared",
            "cache_cleared": "All cached scan data has been removed.",
            "select_cache_dir": "Select Cache Directory",
            "cache_updated_title": "Cache Directory Updated",
            "cache_updated": "Cache directory set to:\n{dir}\n\nPreviously cached scans from the old directory are no longer used.",
            "nothing_export": "Nothing to export",
            "scan_first": "Please scan a folder first.",
            "about_title": "About DiskExplorer",
            "compare_no_root": "Please scan a folder first before comparing.",
            "compare_no_baseline": "No previous cache exists for this path. Scan once, then re-scan and compare.",
            "file_menu": "&File",
            "view_menu": "&View",
            "help_menu": "&Help",
            "lang_menu": "Language",
            "theme_menu": "Theme",
            "theme_meadow": "Pixel Meadow",
            "theme_dungeon": "Pixel Dungeon",
            "cover_image": "Select Cover Image...",
            "cover_reset": "Reset Cover to Default",
            "cover_filter": "Image Files (*.png *.jpg *.jpeg *.bmp *.webp)",
            "cover_title": "Choose Cover Image",
            "cover_invalid": "Could not load this image file.",
            "cover_missing": "Saved cover image was not found. Reverted to default cover.",
            "scan_folder": "&Scan Folder...",
            "export_csv": "Export as &CSV...",
            "export_html": "Export as &HTML...",
            "export_json": "Export as &JSON...",
            "quit": "&Quit",
            "refresh": "&Refresh / Re-scan",
            "clear_cache": "Clear &Cache",
            "set_cache_dir": "Set Cache &Directory...",
            "manual_compare": "Manual &Compare with Cache",
            "about": "&About",
            "status_compare_on": "Comparison mode enabled (current vs previous cache).",
            "status_compare_off": "Comparison mode disabled.",
        },
        "zh": {
            "title": "DiskExplorer - 磁盘空间分析器",
            "path": "路径:",
            "scan_selected": "扫描所选路径",
            "cancel": "取消",
            "compare": "与缓存对比",
            "compare_off": "退出对比",
            "ready": "准备就绪，请先选择磁盘或文件夹进行扫描。",
            "scan_in_progress": "扫描进行中",
            "scan_in_progress_msg": "已有扫描任务在运行，请先取消后再试。",
            "use_cache_title": "使用缓存数据？",
            "cache_exists": "检测到约 {mins:.0f} 分钟前的缓存结果。\n是否使用缓存？（选否将重新扫描）",
            "scanning": "扫描中: {path}",
            "scanning_status": "正在扫描 {path}...",
            "scanned": "已扫描 {count:,} 项... {path}",
            "done": "完成。总大小 {size}，共 {files:,} 个文件。扫描 {count:,} 项，耗时 {elapsed:.1f}s（{throughput:,.0f} 项/s）。",
            "error": "错误: {message}",
            "scan_error": "扫描错误",
            "cancelling": "正在取消...",
            "could_not_locate": "无法定位: {path}",
            "select_folder": "选择要扫描的文件夹",
            "cache_cleared_title": "缓存已清空",
            "cache_cleared": "所有缓存扫描数据已删除。",
            "select_cache_dir": "选择缓存目录",
            "cache_updated_title": "缓存目录已更新",
            "cache_updated": "缓存目录已设置为:\n{dir}\n\n旧目录中的缓存将不再使用。",
            "nothing_export": "没有可导出的数据",
            "scan_first": "请先扫描一个文件夹。",
            "about_title": "关于 DiskExplorer",
            "compare_no_root": "请先扫描一个目录，再执行对比。",
            "compare_no_baseline": "该路径暂无历史缓存。请先扫描一次，再次扫描后再点击对比。",
            "file_menu": "文件(&F)",
            "view_menu": "视图(&V)",
            "help_menu": "帮助(&H)",
            "lang_menu": "语言",
            "theme_menu": "主题",
            "theme_meadow": "像素田园",
            "theme_dungeon": "像素地牢",
            "cover_image": "选择封面图片...",
            "cover_reset": "恢复默认封面",
            "cover_filter": "图片文件 (*.png *.jpg *.jpeg *.bmp *.webp)",
            "cover_title": "选择封面图片",
            "cover_invalid": "无法加载该图片文件。",
            "cover_missing": "已保存的封面图片不存在，已恢复为默认封面。",
            "scan_folder": "扫描文件夹(&S)...",
            "export_csv": "导出为 CSV(&C)...",
            "export_html": "导出为 HTML(&H)...",
            "export_json": "导出为 JSON(&J)...",
            "quit": "退出(&Q)",
            "refresh": "刷新/重新扫描(&R)",
            "clear_cache": "清空缓存(&C)",
            "set_cache_dir": "设置缓存目录(&D)...",
            "manual_compare": "手动缓存对比(&M)",
            "about": "关于(&A)",
            "status_compare_on": "已开启对比模式（当前扫描 vs 历史缓存）。",
            "status_compare_off": "已退出对比模式。",
        },
    }

    def __init__(self) -> None:
        super().__init__()
        self._language = "zh"
        self._theme = "meadow"
        self._settings = QSettings()
        self._scanner = FileSystemScanner(max_workers=4)
        self._model = DiskDataModel()
        self._cache = ScanCache()
        self._exporter = ExportHandler()
        self._scan_worker: Optional[ScanWorker] = None
        self._current_root: Optional[FileNode] = None
        self._pending_selected_node: Optional[FileNode] = None
        self._selection_timer = QTimer(self)
        self._selection_timer.setSingleShot(True)
        self._selection_timer.setInterval(180)
        self._selection_timer.timeout.connect(self._apply_selected_node)
        self._comparison_mode = False
        self._compare_focus_path: Optional[str] = None
        self._baseline_root: Optional[FileNode] = None
        # Timing populated by ScanWorker.scan_stats signal
        self._last_scan_elapsed: float = 0.0
        self._last_scan_count: int = 0

        self._setup_ui()
        self._setup_menu()
        self._populate_disk_bar()
        self._set_theme(self._theme)
        self._set_language(self._language)
        self._restore_cover_image_from_settings()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        self.setWindowTitle(self._t("title"))
        self.resize(1200, 800)

        # --- Central widget ---
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(4, 4, 4, 4)

        # --- Toolbar row (disk buttons + scan/cancel) ---
        self._disk_toolbar = QToolBar("Disks")
        self._disk_toolbar.setMovable(False)
        self.addToolBar(self._disk_toolbar)

        # --- Address bar ---
        addr_bar = QWidget()
        addr_layout = QHBoxLayout(addr_bar)
        addr_layout.setContentsMargins(4, 2, 4, 2)
        self._addr_label = QLabel(self._t("path"))
        self._scan_btn = QPushButton(self._t("scan_selected"))
        self._scan_btn.clicked.connect(self._on_scan_custom)
        self._cancel_btn = QPushButton(self._t("cancel"))
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self._on_cancel)
        self._compare_btn = QPushButton(self._t("compare"))
        self._compare_btn.clicked.connect(self._on_manual_compare)
        addr_layout.addWidget(self._addr_label)
        addr_layout.addStretch()
        addr_layout.addWidget(self._compare_btn)
        addr_layout.addWidget(self._scan_btn)
        addr_layout.addWidget(self._cancel_btn)
        main_layout.addWidget(addr_bar)

        # --- Progress bar ---
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)  # indeterminate
        self._progress_bar.setVisible(False)
        main_layout.addWidget(self._progress_bar)

        # --- Top splitter: tree (left) + chart (right) ---
        top_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._tree_view = FileSystemTreeView()
        self._tree_view.node_selected.connect(self._on_node_selected)
        self._chart_widget = SizeChartWidget()
        self._chart_widget.compare_path_requested.connect(self._on_compare_chart_clicked)
        top_splitter.addWidget(self._tree_view)
        top_splitter.addWidget(self._chart_widget)
        top_splitter.setSizes([700, 500])

        # --- Recent Files panel ---
        self._recent_panel = RecentFilesPanel()
        self._recent_panel.locate_requested.connect(self._on_locate_requested)

        # --- Vertical splitter: top (tree+chart) + bottom (recent files) ---
        v_splitter = QSplitter(Qt.Orientation.Vertical)
        v_splitter.addWidget(top_splitter)
        v_splitter.addWidget(self._recent_panel)
        v_splitter.setSizes([500, 200])
        main_layout.addWidget(v_splitter)

        # --- Status bar ---
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage(self._t("ready"))
        self._chart_widget.show_cover()

    def _setup_menu(self) -> None:
        menu = self.menuBar()

        # File menu
        self._file_menu = menu.addMenu(self._t("file_menu"))
        self._scan_act = QAction(self._t("scan_folder"), self)
        self._scan_act.setShortcut("Ctrl+O")
        self._scan_act.triggered.connect(self._on_scan_custom)
        self._file_menu.addAction(self._scan_act)

        self._file_menu.addSeparator()
        self._export_csv_act = QAction(self._t("export_csv"), self)
        self._export_csv_act.triggered.connect(lambda: self._export("csv"))
        self._file_menu.addAction(self._export_csv_act)
        self._export_html_act = QAction(self._t("export_html"), self)
        self._export_html_act.triggered.connect(lambda: self._export("html"))
        self._file_menu.addAction(self._export_html_act)
        self._export_json_act = QAction(self._t("export_json"), self)
        self._export_json_act.triggered.connect(lambda: self._export("json"))
        self._file_menu.addAction(self._export_json_act)

        self._file_menu.addSeparator()
        self._quit_act = QAction(self._t("quit"), self)
        self._quit_act.setShortcut("Ctrl+Q")
        self._quit_act.triggered.connect(self.close)
        self._file_menu.addAction(self._quit_act)

        # View menu
        self._view_menu = menu.addMenu(self._t("view_menu"))
        self._refresh_act = QAction(self._t("refresh"), self)
        self._refresh_act.setShortcut("F5")
        self._refresh_act.triggered.connect(self._on_refresh)
        self._view_menu.addAction(self._refresh_act)
        self._clear_cache_act = QAction(self._t("clear_cache"), self)
        self._clear_cache_act.triggered.connect(self._on_clear_cache)
        self._view_menu.addAction(self._clear_cache_act)
        self._set_cache_dir_act = QAction(self._t("set_cache_dir"), self)
        self._set_cache_dir_act.triggered.connect(self._on_set_cache_dir)
        self._view_menu.addAction(self._set_cache_dir_act)

        self._view_menu.addSeparator()
        self._manual_compare_act = QAction(self._t("manual_compare"), self)
        self._manual_compare_act.triggered.connect(self._on_manual_compare)
        self._view_menu.addAction(self._manual_compare_act)

        # Help menu
        self._help_menu = menu.addMenu(self._t("help_menu"))
        self._about_act = QAction(self._t("about"), self)
        self._about_act.triggered.connect(self._on_about)
        self._help_menu.addAction(self._about_act)

        self._lang_menu = menu.addMenu(self._t("lang_menu"))
        self._lang_zh_act = QAction("中文", self)
        self._lang_zh_act.triggered.connect(lambda: self._set_language("zh"))
        self._lang_en_act = QAction("English", self)
        self._lang_en_act.triggered.connect(lambda: self._set_language("en"))
        self._lang_menu.addAction(self._lang_zh_act)
        self._lang_menu.addAction(self._lang_en_act)

        self._theme_menu = menu.addMenu(self._t("theme_menu"))
        self._theme_meadow_act = QAction(self._t("theme_meadow"), self)
        self._theme_meadow_act.triggered.connect(lambda: self._set_theme("meadow"))
        self._theme_dungeon_act = QAction(self._t("theme_dungeon"), self)
        self._theme_dungeon_act.triggered.connect(lambda: self._set_theme("dungeon"))
        self._theme_menu.addAction(self._theme_meadow_act)
        self._theme_menu.addAction(self._theme_dungeon_act)
        self._theme_menu.addSeparator()
        self._cover_image_act = QAction(self._t("cover_image"), self)
        self._cover_image_act.triggered.connect(self._on_select_cover_image)
        self._cover_reset_act = QAction(self._t("cover_reset"), self)
        self._cover_reset_act.triggered.connect(self._on_reset_cover_image)
        self._theme_menu.addAction(self._cover_image_act)
        self._theme_menu.addAction(self._cover_reset_act)

    def _populate_disk_bar(self) -> None:
        """Add one button per detected disk/mount point."""
        disks = FileSystemScanner.list_disks()
        for disk in disks:
            btn = QPushButton(disk)
            btn.setFixedWidth(80)
            btn.clicked.connect(lambda checked, d=disk: self._start_scan(d))
            self._disk_toolbar.addWidget(btn)

    def _t(self, key: str, **kwargs) -> str:
        text = self._I18N.get(self._language, self._I18N["en"]).get(key, key)
        return text.format(**kwargs) if kwargs else text

    def _set_language(self, language: str) -> None:
        self._language = "zh" if language == "zh" else "en"
        self.setWindowTitle(self._t("title"))
        if self._current_root is None:
            self._addr_label.setText(self._t("path"))
        else:
            self._addr_label.setText(
                f"{self._t('path')} {self._current_root.path}  [{self._current_root.formatted_size}]"
            )
        self._scan_btn.setText(self._t("scan_selected"))
        self._cancel_btn.setText(self._t("cancel"))
        self._compare_btn.setText(self._t("compare_off") if self._comparison_mode else self._t("compare"))

        self._file_menu.setTitle(self._t("file_menu"))
        self._scan_act.setText(self._t("scan_folder"))
        self._export_csv_act.setText(self._t("export_csv"))
        self._export_html_act.setText(self._t("export_html"))
        self._export_json_act.setText(self._t("export_json"))
        self._quit_act.setText(self._t("quit"))

        self._view_menu.setTitle(self._t("view_menu"))
        self._refresh_act.setText(self._t("refresh"))
        self._clear_cache_act.setText(self._t("clear_cache"))
        self._set_cache_dir_act.setText(self._t("set_cache_dir"))
        self._manual_compare_act.setText(self._t("manual_compare"))

        self._help_menu.setTitle(self._t("help_menu"))
        self._about_act.setText(self._t("about"))
        self._lang_menu.setTitle(self._t("lang_menu"))
        self._theme_menu.setTitle(self._t("theme_menu"))
        self._theme_meadow_act.setText(self._t("theme_meadow"))
        self._theme_dungeon_act.setText(self._t("theme_dungeon"))
        self._cover_image_act.setText(self._t("cover_image"))
        self._cover_reset_act.setText(self._t("cover_reset"))

        self._tree_view.set_language(self._language)
        self._chart_widget.set_language(self._language)
        self._recent_panel.set_language(self._language)
        if self._comparison_mode:
            self._chart_widget.show_comparison(self._current_root, self._baseline_root, self._compare_focus_path)

    def _set_theme(self, theme: str) -> None:
        self._theme = "dungeon" if theme == "dungeon" else "meadow"
        self._chart_widget.set_cover_theme(self._theme)
        self._tree_view.set_theme(self._theme)

        if self._theme == "dungeon":
            self.setStyleSheet(
                "QMainWindow, QWidget {"
                "background-color: #1f2238;"
                "color: #dde6ff;"
                "}"
                "QPushButton {"
                "background-color: #2f3661;"
                "border: 2px solid #7f8cff;"
                "padding: 4px 10px;"
                "font-weight: 600;"
                "}"
                "QPushButton:hover { background-color: #3d4678; }"
                "QMenuBar, QMenu { background-color: #252941; color: #dde6ff; }"
                "QHeaderView::section { background-color: #2f3661; color: #dde6ff; }"
            )
        else:
            self.setStyleSheet(
                "QMainWindow, QWidget {"
                "background-color: #f3f9ff;"
                "color: #1f3450;"
                "}"
                "QPushButton {"
                "background-color: #f6f1d5;"
                "border: 2px solid #629f4f;"
                "padding: 4px 10px;"
                "font-weight: 600;"
                "}"
                "QPushButton:hover { background-color: #ecf7cb; }"
                "QMenuBar, QMenu { background-color: #e6f2ff; color: #1f3450; }"
                "QHeaderView::section { background-color: #d7ebff; color: #1f3450; }"
            )

    def _restore_cover_image_from_settings(self) -> None:
        image_path = str(self._settings.value("ui/cover_image", "") or "")
        if not image_path:
            return
        if not os.path.exists(image_path):
            self._chart_widget.clear_cover_image()
            self._settings.remove("ui/cover_image")
            self._status_bar.showMessage(self._t("cover_missing"))
            return
        if not self._chart_widget.set_cover_image(image_path):
            self._chart_widget.clear_cover_image()
            self._settings.remove("ui/cover_image")
            self._status_bar.showMessage(self._t("cover_invalid"))

    def _on_select_cover_image(self) -> None:
        image_path, _ = QFileDialog.getOpenFileName(
            self,
            self._t("cover_title"),
            "",
            self._t("cover_filter"),
        )
        if not image_path:
            return
        if not self._chart_widget.set_cover_image(image_path):
            QMessageBox.warning(self, self._t("cover_title"), self._t("cover_invalid"))
            return
        self._settings.setValue("ui/cover_image", image_path)
        self._chart_widget.show_cover()

    def _on_reset_cover_image(self) -> None:
        self._chart_widget.clear_cover_image()
        self._settings.remove("ui/cover_image")
        self._chart_widget.show_cover()

    # ------------------------------------------------------------------
    # Scan lifecycle
    # ------------------------------------------------------------------

    def _start_scan(self, path: str) -> None:
        if self._scan_worker and self._scan_worker.isRunning():
            QMessageBox.warning(self, self._t("scan_in_progress"), self._t("scan_in_progress_msg"))
            return

        # Save existing cache as baseline for manual comparison.
        self._baseline_root = self._cache.load(path)
        self._comparison_mode = False
        self._compare_focus_path = None
        self._compare_btn.setText(self._t("compare"))

        # Check cache
        cached = self._cache.load(path, max_age_seconds=3600)
        if cached is not None:
            age = self._cache.cache_age_seconds(path) or 0
            reply = QMessageBox.question(
                self,
                self._t("use_cache_title"),
                self._t("cache_exists", mins=age / 60),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._display_result(cached)
                return

        self._addr_label.setText(self._t("scanning", path=path))
        self._progress_bar.setVisible(True)
        self._scan_btn.setEnabled(False)
        self._cancel_btn.setEnabled(True)
        self._status_bar.showMessage(self._t("scanning_status", path=path))

        self._scan_worker = ScanWorker(self._scanner, path)
        self._scan_worker.progress.connect(self._on_scan_progress)
        self._scan_worker.finished.connect(self._on_scan_finished)
        self._scan_worker.error.connect(self._on_scan_error)
        self._scan_worker.scan_stats.connect(self._on_scan_stats)
        self._scan_worker.start()

    def _on_scan_progress(self, count: int, path: str) -> None:
        self._status_bar.showMessage(self._t("scanned", count=count, path=path[:80]))

    def _on_scan_stats(self, elapsed: float, count: int) -> None:
        """Store performance stats emitted by the worker before finished."""
        self._last_scan_elapsed = elapsed
        self._last_scan_count = count

    def _on_scan_finished(self, node: FileNode) -> None:
        self._cache.save(node.path, node)
        self._model.set_root(node.path, node)
        self._display_result(node)
        self._reset_scan_controls()
        elapsed = self._last_scan_elapsed
        count = self._last_scan_count
        throughput = count / elapsed if elapsed > 0 else 0
        self._status_bar.showMessage(
            self._t(
                "done",
                size=node.formatted_size,
                files=node.file_count,
                count=count,
                elapsed=elapsed,
                throughput=throughput,
            )
        )
        _logger.info(
            "UI scan finished: path=%s  size=%s  files=%d  "
            "items=%d  elapsed=%.2fs  throughput=%.0f items/s",
            node.path, node.formatted_size, node.file_count,
            count, elapsed, throughput,
        )

    def _on_scan_error(self, message: str) -> None:
        self._reset_scan_controls()
        self._status_bar.showMessage(self._t("error", message=message))
        QMessageBox.warning(self, self._t("scan_error"), message)

    def _on_cancel(self) -> None:
        self._scanner.cancel()
        self._status_bar.showMessage(self._t("cancelling"))

    def _reset_scan_controls(self) -> None:
        self._progress_bar.setVisible(False)
        self._scan_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def _display_result(self, node: FileNode) -> None:
        self._current_root = node
        self._addr_label.setText(f"{self._t('path')} {node.path}  [{node.formatted_size}]")
        self._tree_view.set_root(node)
        self._chart_widget.display(node)
        self._recent_panel.set_root(node)

    def _on_node_selected(self, node: FileNode) -> None:
        self._pending_selected_node = node
        self._selection_timer.start()

    def _apply_selected_node(self) -> None:
        node = self._pending_selected_node
        if node is None:
            return
        if self._comparison_mode:
            self._compare_focus_path = node.path
            self._chart_widget.show_comparison(self._current_root, self._baseline_root, node.path)
        else:
            self._chart_widget.display(node)
        self._status_bar.showMessage(
            f"{node.path}  {node.formatted_size}"
            + (f"  ({node.file_count} files)" if node.is_dir else "")
        )
        # Update Recent Files panel scope when a directory is selected
        if node.is_dir:
            self._recent_panel.set_current_dir(node)

    def _on_locate_requested(self, path: str) -> None:
        """Locate a file path in the tree view (called from Recent Files panel)."""
        if not self._tree_view.navigate_to_path(path):
            self._status_bar.showMessage(self._t("could_not_locate", path=path))

    def _on_compare_chart_clicked(self, path: str) -> None:
        if self._tree_view.navigate_to_path(path):
            self._compare_focus_path = path
            self._chart_widget.show_comparison(self._current_root, self._baseline_root, path)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_scan_custom(self) -> None:
        path = QFileDialog.getExistingDirectory(self, self._t("select_folder"))
        if path:
            self._start_scan(path)

    def _on_manual_compare(self) -> None:
        if self._comparison_mode:
            self._comparison_mode = False
            self._compare_btn.setText(self._t("compare"))
            if self._pending_selected_node is not None:
                self._chart_widget.display(self._pending_selected_node)
            elif self._current_root is not None:
                self._chart_widget.display(self._current_root)
            self._status_bar.showMessage(self._t("status_compare_off"))
            return

        if self._current_root is None:
            QMessageBox.information(self, self._t("scan_in_progress"), self._t("compare_no_root"))
            return
        if self._baseline_root is None:
            QMessageBox.information(self, self._t("use_cache_title"), self._t("compare_no_baseline"))
            return

        self._comparison_mode = True
        self._compare_focus_path = self._current_root.path
        self._compare_btn.setText(self._t("compare_off"))
        self._chart_widget.show_comparison(self._current_root, self._baseline_root, self._compare_focus_path)
        self._status_bar.showMessage(self._t("status_compare_on"))

    def _on_refresh(self) -> None:
        if self._current_root:
            self._cache.invalidate(self._current_root.path)
            self._start_scan(self._current_root.path)

    def _on_clear_cache(self) -> None:
        self._cache.clear_all()
        QMessageBox.information(self, self._t("cache_cleared_title"), self._t("cache_cleared"))

    def _on_set_cache_dir(self) -> None:
        new_dir = QFileDialog.getExistingDirectory(
            self,
            self._t("select_cache_dir"),
            str(self._cache.cache_dir),
        )
        if new_dir:
            self._cache = ScanCache(cache_dir=new_dir)
            QMessageBox.information(
                self,
                self._t("cache_updated_title"),
                self._t("cache_updated", dir=new_dir),
            )

    def _export(self, fmt: str) -> None:
        if not self._current_root:
            QMessageBox.information(self, self._t("nothing_export"), self._t("scan_first"))
            return
        ext_map = {"csv": "CSV Files (*.csv)", "html": "HTML Files (*.html)",
                   "json": "JSON Files (*.json)"}
        path, _ = QFileDialog.getSaveFileName(
            self, f"Export as {fmt.upper()}", f"report.{fmt}", ext_map.get(fmt, "")
        )
        if not path:
            return
        try:
            if fmt == "csv":
                self._exporter.export_csv(self._current_root, path)
            elif fmt == "html":
                self._exporter.export_html(self._current_root, path)
            elif fmt == "json":
                self._exporter.export_json(self._current_root, path)
            self._status_bar.showMessage(f"Exported to {path}")
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", str(exc))

    def _on_about(self) -> None:
        QMessageBox.about(
            self,
            self._t("about_title"),
            "<h3>DiskExplorer v1.0</h3>"
            "<p>A lightweight disk space analysis tool.</p>"
            "<p>Visualise your disk usage in a hierarchical tree view "
            "with charts and export capabilities.</p>",
        )
