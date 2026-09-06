"""Original light and dark styling for the native Studio workspace."""

def stylesheet(dark=True):
    bg,panel,field,fg,muted,border,hover = (
        ("#161d27","#202a37","#141c26","#e3ebf4","#98aec2","#344354","#30465c") if dark else
        ("#e8edf3","#f7f9fc","#ffffff","#25364a","#62778c","#cad4df","#dceafb"))
    return f"""
    QWidget {{ font-family: 'Segoe UI', 'Noto Sans', sans-serif; font-size: 12px; color: {fg}; }}
    QMainWindow, QDialog {{ background: {bg}; }}
    QMenuBar, QMenu, QToolBar, QDockWidget > QWidget {{ background: {panel}; }}
    QMenuBar::item:selected, QMenu::item:selected {{ background: {hover}; }}
    QMenu::item {{ padding: 7px 28px 7px 15px; }}
    QToolBar {{ border: 0; border-bottom: 1px solid {border}; spacing: 6px; padding: 5px; }}
    QToolButton {{ border: 1px solid transparent; border-radius: 4px; padding: 5px; }}
    QToolButton:hover, QPushButton:hover {{ background: {hover}; border-color: #4f96d0; }}
    QToolButton:checked, QPushButton:checked {{ background: {hover}; border: 1px solid #4f96d0; }}
    QToolButton:disabled, QPushButton:disabled {{ color: {muted}; }}
    QTabWidget::pane {{ border: 0; }}
    QTabBar::tab {{ background: {panel}; padding: 9px 15px; border-bottom: 3px solid transparent; }}
    QTabBar::tab:selected {{ border-bottom: 3px solid #54aaff; color: #54aaff; }}
    QTabBar::tab:hover {{ background: {hover}; }}
    QTabWidget#ribbon, QTabWidget#ribbon QScrollArea, QTabWidget#ribbon QScrollArea > QWidget > QWidget {{ background: {panel}; }}
    QLabel#groupCaption {{ color: {muted}; font-size: 10px; padding-top: 3px; }}
    QFrame#ribbonRule {{ color: {border}; }}
    QDockWidget::title {{ background: {panel}; padding: 8px; border-bottom: 1px solid {border}; }}
    QTreeWidget, QListWidget, QPlainTextEdit, QTextEdit {{ background: {field}; border: 1px solid {border}; outline: 0; }}
    QTreeWidget::item, QListWidget::item {{ padding: 5px 3px; min-height: 20px; }}
    QTreeWidget::item:selected, QListWidget::item:selected {{ background: {hover}; color: {fg}; }}
    QLineEdit, QDoubleSpinBox, QComboBox {{ background: {field}; border: 1px solid {border}; border-radius: 3px; padding: 5px; selection-background-color: #327cb7; }}
    QLineEdit:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border-color: #54aaff; }}
    QComboBox QAbstractItemView {{ background: {field}; selection-background-color: {hover}; }}
    QPushButton {{ background: {panel}; border: 1px solid {border}; border-radius: 4px; padding: 7px 12px; }}
    QPushButton#primary {{ background: #236fa8; border: 1px solid #418ecc; color: white; }}
    QLabel#brand {{ font-size: 15px; font-weight: 700; padding: 0 18px 0 8px; }}
    QLabel#breadcrumb {{ background: {panel}; color: {muted}; padding: 7px 12px; }}
    QLabel#viewportFallback {{ background: {field}; color: {muted}; font-size: 16px; padding: 35px; }}
    QLabel#inspectorTitle {{ font-size: 18px; font-weight: 600; padding: 8px 0; }}
    QLabel#hint {{ color: {muted}; padding: 8px 0; }}
    QStatusBar {{ background: {panel}; border-top: 1px solid {border}; }}
    QStatusBar::item {{ border: 0; }}
    QScrollBar:vertical {{ background: {panel}; width: 10px; }}
    QScrollBar::handle:vertical {{ background: {border}; min-height: 25px; border-radius: 4px; }}
    QScrollBar:horizontal {{ background: {panel}; height: 10px; }}
    QScrollBar::handle:horizontal {{ background: {border}; min-width: 25px; border-radius: 4px; }}
    QSplitter::handle {{ background: {border}; }}
    QToolTip {{ background: {panel}; color: {fg}; border: 1px solid #4f96d0; padding: 6px; }}
    """
