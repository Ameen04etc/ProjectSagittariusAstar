from importlib.resources import path
from Sagittarius_A import Ui_SagittariusA
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget,
    QSplitter, QVBoxLayout, QHBoxLayout,
    QGridLayout, QScrollBar, QSizePolicy,
    QPushButton, QToolButton, QToolTip,
    QFrame, QLabel, QTreeView, QGraphicsOpacityEffect,
    QPlainTextEdit, QTextEdit, QFileDialog,
    QListWidget)
from PySide6.QtCore import (QProcess, Qt, QObject,
    Signal, QRectF, QRect,
    Slot, QPointF, QPoint,
    QSize, QEvent, QSignalBlocker,
    QTimer, QRegularExpression, QPropertyAnimation,
    QEasingCurve, QUrl)
from PySide6.QtGui import (QPainter, QColor, QPen,
    QPixmap, QFont, QMouseEvent,
    QImage, QCursor, QPainterPath,
    QStandardItemModel, QStandardItem,
    QFontMetrics, QKeySequence, QTextFormat,
    QTextCursor, QTextBlock, QShortcut,
    QTextCharFormat, QSyntaxHighlighter, QGuiApplication,
    QTextBlockUserData, QFontMetricsF, QWheelEvent,
    QAbstractTextDocumentLayout, QMouseEvent, QTextLayout,
    QKeyEvent)
from enum import Enum, auto
from typing import cast
from pathlib import Path
from tree_sitter import Language, Parser
from LSPManager import *
import tree_sitter_python
import json
import os
import sys
import re
import copy
import threading
import math
import time

RED    = "\033[31m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
BLUE   = "\033[34m"
RESET  = "\033[0m"


class textEdit(QWidget):
    @property
    def document(self):
        return self._document

    def __init__(self, parent):
        super().__init__(parent)
        self._document : list[textBlock] = []
        self.Cursor = textPosition()

        self.Font = QFont()
        self.Font.setFamilies(["Consolas", "Courier New"])
        self.Font.setPixelSize(16)
        self.fm = QFontMetricsF(self.Font)

        self.cellWidth  = self.fm.horizontalAdvance("W")
        self.cellHeight = self.fm.height()
        self.Ascent     = self.fm.ascent()

    def insert(self, ch):
        line = self.Document[self.Cursor.y]
        line.Chars.insert(self.Cursor.x, ch)

    def keyPressEvent(self, event : QKeyEvent):
        text = event.text()
        self.insert(text)
        super().keyPressEvent(event)


class textDocument:
    @property
    def findBlockByNumber(self, blockNumber):
        if blockNumber < len(self.document):
            return self.document[blockNumber]
        return None

    @property
    def block(self, cursor : textPosition):
        blockNo = cursor.y
        if blockNo < len(self.document):
            return self.document[blockNo]
        return None

    def __init__(self):
        self.document : list[textBlock] = []


class textBlock:
    def __init__(self):
        self.Chars : list[textCell] = []


class textCell:
    def __init__(self):
        self.char = ""


class textPosition:

    @property
    def x(self):
        return self.x

    @property
    def y(self):
        return self.y

    def __init__(self):
        self.x = 0
        self.y = 0


class  MainWindow(QMainWindow):
    def __init__(self, parent = None):
        super().__init__(parent)
        # Main = MasterEditor(self)
        Main = textEdit(self)
        self.setWindowTitle("anNaylam")
        self.setCentralWidget(Main)


app = QApplication([])
window = MainWindow()

window.show()

screen = app.primaryScreen()
avail = screen.availableGeometry()

title_bar_height = window.frameGeometry().height() - window.geometry().height()
border_width = window.frameGeometry().width() - window.geometry().width()

target_width = (avail.width() // 2) - border_width
target_height = avail.height() - title_bar_height

window.resize(target_width, target_height)
window.move(avail.x() + (avail.width() // 2), avail.y())

sys.exit(app.exec())