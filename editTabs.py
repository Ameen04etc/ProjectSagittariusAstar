from PySide6.QtWidgets import (QApplication, QButtonGroup, QFrame, QHBoxLayout,
    QHeaderView, QLayout, QLineEdit, QMainWindow,
    QSizePolicy, QSplitter, QStackedWidget, QTabWidget,
    QToolButton, QTreeView, QVBoxLayout, QWidget)

from PySide6.QtGui import (QShortcut, QKeySequence, QAction,
    QFont)

from pathlib import Path
from anNaylam import *

class editTabs(QTabWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setTabsClosable(True)
        self.setTabBarAutoHide(False)

        self.tabFont = QFont()
        self.tabFont.setFamilies(["Segoe WPC", "Segoe UI", "Arial", "sans-serif"])
        self.tabFont.setPixelSize(12)
        self.tabFont.setWeight(QFont.Weight(550))
        self.tabBar().setFont(self.tabFont)

        self.shortCutConfig()
        self.signalManager()

        self.newTab()


    def closeTab(self, index):
        self.removeTab(index)

    def newTab(self, name = None):
        if name is None:
            name = "Untitled"

        tab = QWidget()
        codeEdit = MasterWidget(parent = tab)

        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(codeEdit)

        index = self.addTab(tab, name)

        self.setCurrentIndex(index)
        # self.setCurrentWidget(tab)

    def openFile(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Open File",
            "",
            "All Files (*);;Python Files (*.py)"
        )

        if filepath:
            for index in range(self.count()):
                tab = self.widget(index)
                editorWidget = tab.findChild(MasterWidget)
                if Path(filepath).as_uri() == editorWidget.editor.FilePath:
                    self.setCurrentWidget(tab)
                    # self.setCurrentIndex(index)
                    return
            fileName = Path(filepath).name
            self.newTab(name = fileName)
            editorWidget = self.currentWidget().findChild(MasterWidget)
            editorWidget.editor.openFile(filepath)

    def signalManager(self):
        self.tabCloseRequested.connect(self.closeTab)
        self.newTabAction.triggered.connect(lambda: self.newTab())
        self.closeTabAction.triggered.connect(lambda: self.closeTab(self.currentIndex()))
        self.fileOpenAction.triggered.connect(self.openFile)

    def shortCutConfig(self):
        self.newTabAction = QAction("New Tab", self)
        self.newTabAction.setShortcut(QKeySequence.StandardKey.AddTab)
        self.addAction(self.newTabAction)

        self.closeTabAction = QAction("Close Tab", self)
        self.closeTabAction.setShortcut(QKeySequence("Ctrl + W"))
        self.addAction(self.closeTabAction)

        self.fileOpenAction = QAction("Open File", self)
        self.fileOpenAction.setShortcut(QKeySequence("Ctrl + O"))
        self.addAction(self.fileOpenAction)



