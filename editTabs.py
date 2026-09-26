from PySide6.QtWidgets import (QApplication, QButtonGroup, QFrame, QHBoxLayout,
    QHeaderView, QLayout, QLineEdit, QMainWindow,
    QSizePolicy, QSplitter, QStackedWidget, QTabWidget,
    QToolButton, QTreeView, QVBoxLayout, QWidget)

from PySide6.QtGui import (QShortcut, QKeySequence, QAction, QKeyEvent,
    QFont, QPalette)

from PySide6.QtCore import (QUrl, Qt)

from pathlib import Path
from anNaylam import *
import re

class editTabs(QTabWidget):

    def __init__(self, parent):
        super().__init__(parent)
        self.setTabsClosable(True)
        self.setTabBarAutoHide(False)
        self.setMovable(True)
        self.tabBar().setExpanding(False)

        self.setAttribute(Qt.WA_StyledBackground, True)
        self.tabBar().setAttribute(Qt.WA_StyledBackground, True)

        # self.setAutoFillBackground(True)
        # self.palette().setColor(QPalette.ColorRole.Window, QColor("#FE0000"))

        self.unTitledTabs = []

        self.shortCutConfig()
        self.styleConfig()
        self.signalManager()

        self.tabFont = QFont()
        self.tabFont.setFamilies(["Segoe WPC", "Segoe UI", "Arial", "sans-serif"])
        self.tabFont.setPixelSize(12)
        self.tabFont.setWeight(QFont.Weight(550))
        self.tabBar().setFont(self.tabFont)

        self.newTab()

    def closeTab(self, index):
        if index is None: index = self.currentIndex()
        title = self.tabText(index)
        lead  = title.rsplit("-", 1)[0]
        if lead == "Untitled":
            match = re.search(r"\d+$", title.strip())
            if match:
                self.unTitledTabs.remove(int(match.group()))

        self.removeTab(index)

    def newTab(self, name = None):
        if name is None:
            if not self.unTitledTabs:
                self.unTitledTabs.append(1)
            else:
                self.unTitledTabs.append(self.unTitledTabs[-1] + 1)
            name = f"Untitled-{self.unTitledTabs[-1]}"

        tab = QWidget()
        codeEdit = MasterEditor(parent = tab)

        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(codeEdit)

        index = self.addTab(tab, name)

        self.setCurrentIndex(index)
        # self.setCurrentWidget(tab)

    def switchTab(self, index):
        if index == 0:
            index = 10
        
        if index > self.count():
            return

        self.setCurrentIndex(index - 1)

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
                editorWidget = tab.findChild(MasterEditor)
                if Path(filepath).as_uri() == editorWidget.editor.FilePath:
                    self.setCurrentWidget(tab)
                    # self.setCurrentIndex(index)
                    return
            fileName = Path(filepath).name
            self.newTab(name = fileName)
            editorWidget = self.currentWidget().findChild(MasterEditor)
            editorWidget.editor.openFile(filepath)

    def saveFile(self, saveAs = False):
        editor = self.currentWidget().findChild(MasterEditor)
        if editor.editor.FilePath is None or saveAs:
            filePath, _ = QFileDialog.getSaveFileName(
                parent  = self.currentWidget(),
                caption = "Save File As",
                filter  = "Python Files (*.py);;Text Files (*.txt);;All Files (*)"
            )

            if filePath:
                with open(filePath, "w", encoding = "utf-8") as f:
                    f.write(editor.editor.toPlainText())
                editor.editor.FilePath = Path(filePath).as_uri()
                fileName = Path(filePath).name

                title = self.tabText(self.currentIndex())
                lead  = title.rsplit("-", 1)[0]
                if lead == "Untitled":
                    match = re.search(r"\d+$", title.strip())
                    if match:
                        self.unTitledTabs.remove(int(match.group()))

                self.setTabText(self.currentIndex(), fileName)

            else:
                pass
        else:
            url = QUrl(editor.editor.FilePath).toLocalFile()
            with open(url, "w", encoding = "utf-8") as f:
                f.write(editor.editor.toPlainText())

    def signalManager(self):
        self.tabCloseRequested       .connect(self.closeTab)
        self.fileOpenAction.triggered.connect(self.openFile)
        self.fileSaveAction.triggered.connect(self.saveFile)
        self.saveAsAction.triggered  .connect(lambda: self.saveFile(saveAs = True))
        self.newTabAction.triggered  .connect(lambda: self.newTab())
        self.closeTabAction.triggered.connect(lambda: self.closeTab(self.currentIndex()))

    def shortCutConfig(self):
        self.newTabAction = QAction("New Tab", self)
        self.newTabAction.setShortcut(QKeySequence.StandardKey.AddTab)
        self.addAction(self.newTabAction)

        self.closeTabAction = QAction("Close Tab", self)
        self.closeTabAction.setShortcut(QKeySequence("Ctrl+W"))
        self.addAction(self.closeTabAction)

        self.fileOpenAction = QAction("Open File", self)
        self.fileOpenAction.setShortcut(QKeySequence("Ctrl+O"))
        self.addAction(self.fileOpenAction)

        self.fileSaveAction = QAction("Save File", self)
        self.fileSaveAction.setShortcut(QKeySequence("Ctrl+S"))
        self.addAction(self.fileSaveAction)

        self.saveAsAction = QAction("Save As", self)
        self.saveAsAction.setShortcut(QKeySequence("ctrl+Shift+S"))
        self.addAction(self.saveAsAction)

        for digit in range(10):
            action = QAction(f"Switch tab {digit}", self)
            action.setShortcut(QKeySequence(f"Ctrl+{digit}"))
            self.addAction(action)
            action.setData(digit)
            action.triggered.connect(lambda checked = False, d = digit: self.switchTab(index = d))

    def styleConfig(self):
        self.setStyleSheet("""
            /* 1. Base widget & header background */
            QTabWidget {
                background-color: rgb(18, 19, 20);
            }

            /* 2. The document / page area below the tabs (keep your dark editor color here) */
            QTabWidget::pane {
                border: none;
                background-color: rgb(18, 19, 20); /* Your editor dark background */
                top: 2px;
            }

            /* 3. The tab bar strip itself */
            QTabBar {
                background-color: rgb(18, 19, 20);
            }

            /* 4. Base / Inactive Tabs: Blend seamlessly into the red strip */
            QTabBar::tab {
                margin-top: 4px;
                margin-bottom: 0px;
                margin-left: 4px;

                font-family: "Segoe WPC", "Segoe UI", "Arial", "sans-serif";
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 0.5px;

                background-color: rgb(18, 19, 20);
                color: rgb(200, 200, 200);

                border: none;
                padding: 0px 14px;
                min-height: 25px;
            }

            /* Inactive hover: subtle darkening on the red */
            QTabBar::tab:hover {
                margin-top: 4px;
                margin-bottom: 0px;
                margin-left: 4px;

                background-color: rgb(37, 38, 38);
                color: rgb(200, 200, 200);
                border: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                border-bottom-left-radius: 4px;
                border-bottom-right-radius: 4px;
            }

            /* 5. Active Selected Tab: The only distinct element */
            QTabBar::tab:selected {
                margin-top: 4px;
                margin-bottom: 0px;
                margin-left: 4px;

                background-color: rgb(44, 45, 46);
                color: rgb(255, 255, 255);
                border: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                border-bottom-left-radius: 4px;
                border-bottom-right-radius: 4px;
            }

            /* 6. Close Button */
            QTabBar::close-button: {
                margin-right: 10px;
            }
        """)


class LSPClient(QObject):
    def __init__(self, parent):
        super().__init__(parent)