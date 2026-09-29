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
    QKeyEvent, QPaintEvent)
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

    def __init__(self, parent):
        super().__init__(parent)
        self._document = textDocument()
        self._Cursor = TextCursor(doc = self.document())

        self.Font = QFont()
        self.Font.setFamilies(["Consolas", "Courier New"])
        self.fontSize = 15
        self.Font.setPixelSize(self.fontSize)
        self.fm = QFontMetricsF(self.Font)

        self.cellW  = self.fm.horizontalAdvance("W")
        self.cellH  = self.fm.height()
        self.Ascent = self.fm.ascent()
        self._scroll = 0

        self.toggle = False
        self.cursorVisible = True
        self.cursTimer = QTimer(self)
        self.cursTimer.start(500)
        self.cursTimer.timeout.connect(self.toggleCursor)

        self.controlModifier = False
        self.shiftModifier   = False

        self.setMargins()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def paintEvent(self, event : QPaintEvent):
        painter = QPainter(self)
        painter.setFont(self.Font)
        painter.fillRect(event.rect(), QColor(18, 19, 20))
        # painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        start = self.firstVisibleBlock().blockNumber()
        stop  = self.lastVisibleBlock().blockNumber()
        row = start

        if not self.toggle:
            # print("-------------")
            while True:
                if row > stop:
                    break
                print("row =", row, "stop =", stop)
                block = self.document().visibleBlocks()[row]
                y = row * self.cellH + self.topMargin() - self._scroll
                if block.head:
                    rect = QRectF(
                        0, y,
                        self.cellW, self.cellH
                    )
                    painter.drawRect(rect)
                for col, cell in enumerate(block.Chars):
                    x = col * self.cellW + self.leftMargin()
                    if x > self.width() - self.rightMargin():
                        break

                    cellRect = QRectF(
                        x, y,
                        self.cellW, self.cellH
                    )

                    painter.setPen(cell.color)
                    # painter.drawRect(cellRect)
                    painter.drawText(
                        x, y + self.Ascent,
                        cell.char
                    )
                #     print(cell.char, end='')
                # print('\r')
                row += 1

        if self.cursorVisible and self.hasFocus():
            cursorPen = QPen(QColor(200, 200, 200, 255), 2)
            painter.setPen(cursorPen)
            x = self.textCursor().col() * self.cellW + self.leftMargin()
            y = self.textCursor().row() * self.cellH + self.topMargin() - self._scroll
            if x == 0: x = 1
            painter.drawLine(x, y + 1, x, y + self.cellH - 1)

        row = self.textCursor().row()
        col = self.textCursor().col()

        ch0 = self.characterAt(row, col - 1)
        ch1 = self.characterAt(row - 1, col)
        ch2 = self.characterAt(row, col)
        ch3 = self.characterAt(row + 1, col)
        painter.setPen(QPen(QColor(200, 200, 200, 255), 1))
        if ch0:
            x = (col - 1) * self.cellW + self.leftMargin()
            y = row * self.cellH + self.topMargin() - self._scroll
            painter.drawText(x, y + self.Ascent, ch0)
        if ch2:
            x = col * self.cellW + self.leftMargin()
            y = row * self.cellH + self.topMargin() - self._scroll
            painter.drawText(x, y + self.Ascent, ch2)

        self.toggle = False

        painter.end()
        super().paintEvent(event)

    def resetCursor(self):
        self.toggle = False
        self.cursorVisible = True
        cursX = self.textCursor().col() * self.cellW + self.leftMargin()
        cursY = self.textCursor().row() * self.cellH + self.topMargin() - self._scroll
        Rect = QRect(int(cursX) - self.cellW // 2, int(cursY) - 1, 2 + self.cellW // 2, int(self.cellH) + 1)
        self.update(Rect)
        self.cursTimer.start(500)

    def toggleCursor(self):
        if self.hasFocus():
            self.toggle = True
            self.cursorVisible = not self.cursorVisible
            cursX = self.textCursor().col() * self.cellW + self.leftMargin()
            cursY = self.textCursor().row() * self.cellH + self.topMargin() - self._scroll
            self.update(QRect(int(cursX) - 2, int(cursY), 6, int(self.cellH)))

    def document(self):
        return self._document

    def textCursor(self):
        return self._Cursor

    def firstVisibleBlock(self):
        blockNo = int(self._scroll / self.cellH)
        block = self.document().visibleBlocks()[blockNo]
        block._blockNumber = blockNo

        return block

    def lastVisibleBlock(self):
        blockNo = int((self._scroll + (self.height() - self.topMargin() - self.bottomMargin())) / self.cellH)
        if blockNo < len(self.document().visibleBlocks()):
            block = self.document().visibleBlocks()[blockNo]
            block._blockNumber = blockNo
        else:
            block = self.document().visibleBlocks()[-1]
            block._blockNumber = len(self.document().visibleBlocks()) - 1

        return block

    def characterAt(self, row, col) -> str | None:
        block = self.document().findBlockByNumber(row)
        if block and block.totalCharacters() > col >= 0:
            return block.Chars[col].char
        return None

    def setMargins(self, left = 0, top = 0, right = 0, bottom = 0):
        self._leftMargin = left
        self._topMargin = top
        self._rightMargin = right
        self._bottomMargin = bottom

    def leftMargin(self):
        return self._leftMargin

    def topMargin(self):
        return self._topMargin

    def rightMargin(self):
        return self._rightMargin

    def bottomMargin(self):
        return self._bottomMargin

    def newLine(self, lineNo = None):
        if lineNo is None:
            lineNo = self.textCursor().row() + 1
        else:
            lineNo += 1

        block = textBlock(self.document(), blockNumber = lineNo)
        self.document().blocks().insert(lineNo, block)
        self.document().visibleBlocks().insert(lineNo, block)
        self.moveTo(lineNo, 0)

    def insert(self, ch):
        block = self.document().blocks()[self.textCursor().row()]
        block.Chars.insert(self.textCursor().col(), textCell(ch = ch))

        self.textCursor().setCol(self.textCursor().col() + 1)
        self.resetCursor()

    def navLeft(self):
        cursX = self.textCursor().col() * self.cellW + self.leftMargin()
        cursY = self.textCursor().row() * self.cellH + self.topMargin() - self._scroll
        prevRect = QRect(int(cursX) - self.cellW // 2, int(cursY) - 1, 2 + self.cellW // 2, int(self.cellH) + 1)

        if self.textCursor().col() > 0:
            self.textCursor().setCol(self.textCursor().col() - 1)
            self.textCursor().syncStoredCoord()
        else:
            if self.textCursor().row() > 0:
                self.textCursor().setRow(self.textCursor().col() - 1)
                self.textCursor().setCol(len(self.document().findBlockByNumber(self.textCursor().row()).Chars))
                self.textCursor().syncStoredCoord()
        self.update(prevRect)
        self.resetCursor()

    def navRight(self):
        cursX = self.textCursor().col() * self.cellW + self.leftMargin()
        cursY = self.textCursor().row() * self.cellH + self.topMargin() - self._scroll
        prevRect = QRect(int(cursX) - self.cellW // 2, int(cursY) - 1, 2 + self.cellW // 2, int(self.cellH) + 1)

        if self.textCursor().col() < self.document().findBlockByNumber(self.textCursor().row()).totalCharacters():
            self.textCursor().setCol(self.textCursor().col() + 1)
            self.textCursor().syncStoredCoord()
        else:
            if self.textCursor().row() < self.document().totalBlocks() - 1:
                self.textCursor().setRow(self.textCursor().col() + 1)
                self.textCursor().setCol(0)
                self.textCursor().syncStoredCoord()
        self.update(prevRect)
        self.resetCursor()

    def navUp(self):
        cursX = self.textCursor().col() * self.cellW + self.leftMargin()
        cursY = self.textCursor().row() * self.cellH + self.topMargin() - self._scroll
        prevRect = QRect(int(cursX) - self.cellW // 2, int(cursY) - 1, 2 + self.cellW // 2, int(self.cellH) + 1)

        if self.textCursor().row() > 0:
            self.textCursor().setRow(self.textCursor().col() - 1)
            strLength = self.document().findBlockByNumber(self.textCursor().row()).totalCharacters()
            self.textCursor().setCol(min(strLength, self.textCursor().storedCol()))
        else:
            self.textCursor().setCol(0)
            self.textCursor().syncStoredCoord()
        self.update(prevRect)
        self.resetCursor()

    def navDn(self):
        cursX = self.textCursor().col() * self.cellW + self.leftMargin()
        cursY = self.textCursor().row() * self.cellH + self.topMargin() - self._scroll
        prevRect = QRect(int(cursX) - self.cellW // 2, int(cursY) - 1, 2 + self.cellW // 2, int(self.cellH) + 1)

        if self.textCursor().row() < self.document().totalBlocks() - 1:
            self.textCursor().setRow(self.textCursor().row() + 1)
            strLength = self.document().findBlockByNumber(self.textCursor().row()).totalCharacters()
            self.textCursor().setCol(min(strLength, self.textCursor().storedCol()))
        else:
            self.textCursor().setCol(self.document().findBlockByNumber(self.document().totalBlocks() - 1).totalCharacters())
            self.textCursor().syncStoredCoord()
        self.update(prevRect)
        self.resetCursor()

    def moveTo(self, row, col):
        cursX = self.textCursor().col() * self.cellW + self.leftMargin()
        cursY = self.textCursor().row() * self.cellH + self.topMargin() - self._scroll
        prevRect = QRect(int(cursX) - self.cellW // 2, int(cursY) - 1, 2 + self.cellW // 2, int(self.cellH) + 1)

        lastBlock = self.document().blocks()[-1]
        row = min(row, lastBlock.blockNumber())
        totalCar = self.document().blocks()[row].totalCharacters()
        col = min(col, totalCar)

        self.textCursor().setRow(row)
        self.textCursor().setCol(col)
        self.textCursor().syncStoredCoord()
        self.update(prevRect)
        self.resetCursor()

    def keyPressEvent(self, event : QKeyEvent):
        if   event.key() == Qt.Key.Key_Left:
            self.navLeft()
        elif event.key() == Qt.Key.Key_Right:
            self.navRight()
        elif event.key() == Qt.Key.Key_Up:
            self.navUp()
        elif event.key() == Qt.Key.Key_Down:
            self.navDn()
        elif event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            self.newLine()
        elif event.key() == Qt.Key.Key_Shift:
            self.shiftModifier = True
        elif event.key() in {Qt.Key.Key_Control, Qt.Key.Key_Meta}:
            self.controlModifier = True
        elif self.controlModifier and event.key() == Qt.Key.Key_Plus:
            self.fontSize += 1
            self.Font.setPixelSize(self.fontSize)
            self.fm = QFontMetricsF(self.Font)

            self.cellW  = self.fm.horizontalAdvance("W")
            self.cellH  = self.fm.height()
            self.Ascent = self.fm.ascent()
        elif self.controlModifier and event.key() == Qt.Key.Key_Minus:
            self.fontSize -= 1
            self.Font.setPixelSize(self.fontSize)
            self.fm = QFontMetricsF(self.Font)

            self.cellW  = self.fm.horizontalAdvance("W")
            self.cellH  = self.fm.height()
            self.Ascent = self.fm.ascent()
        else:
            text = event.text()
            self.insert(text)
            self.update()
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if   event.key() == Qt.Key.Key_Shift:
            self.shiftModifier = False
        elif event.key() in {Qt.Key.Key_Control, Qt.Key.Key_Meta}:
            self.controlModifier = False
        super().keyReleaseEvent(event)

    def mousePressEvent(self, event):
        print("message")
        super().mousePressEvent(event)

    def enterEvent(self, event):
        self.setCursor(Qt.CursorShape.IBeamCursor)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().leaveEvent(event)


class textDocument:
    def __init__(self):
        self._blocks   : list[textBlock] = [textBlock(self, 0)]
        self._visible  : list[textBlock] = [block for block in self._blocks]
        self._foldHead : list[int] = []

    def blocks(self):
        return self._blocks

    def totalBlocks(self):
        return len(self.blocks())

    def findBlockByNumber(self, blockNumber) -> textBlock | None:
        if blockNumber < len(self._blocks):
            return self._blocks[blockNumber]
        return None

    def findBlock(self, textCursor : textPosition):
        blockNo = textCursor.col()
        if blockNo < len(self.document):
            return self._blocks[blockNo]
        return None

    def visibleBlocks(self):
        return self._visible

    def totalVisibleBlocks(self):
        return len(self._visible)


class textBlock:
    def __init__(self, doc : textDocument, blockNumber = 0):
        self.Chars : list[textCell] = []
        self.document = doc
        self._blockNumber = blockNumber
        self.slave = 0
        self.head = False

    def blockNumber(self):
        return self._blockNumber

    def totalCharacters(self):
        return len(self.Chars)

    def isHead(self):
        return self.head

    def string(self):
        lineString = ""
        for cell in self.Chars:
            lineString += cell.char
        return lineString

    def next(self):
        if self._blockNumber < len(self.document) - 1:
            return self.document[self._blockNumber + 1]
        return None

    def prev(self):
        if self._blockNumber > 0:
            return self.document[self._blockNumber - 1]
        return None

    def nextVis(self):
        if self._blockNumber < len(self.document.visibleBlocks()) - 1:
            return self.document.visibleBlocks()[self._blockNumber + 1]
        return None

    def prevVis(self):
        if self._blockNumber > 0:
            return self.document.visibleBlocks()[self._blockNumber - 1]
        return None


class textCell:
    def __init__(self, ch = '', color : QColor = QColor(200, 200, 200, 255)):
        self.char = ch
        self.color = color


class TextCursor:
    def __init__(self, doc : textDocument):
        self._doc = doc
        self.Coord = textPosition()
        self.storedCoord = textPosition()

    def block(self):
        return self._doc.blocks()[self.Coord.row()]

    def row(self):
        return self.Coord.row()

    def col(self):
        return self.Coord.col()

    def setRow(self, row):
        return self.Coord.setRow(row)

    def setCol(self, col):
        return self.Coord.setCol(col)

    def storedRow(self):
        return self.storedCoord.row()

    def storedCol(self):
        return self.storedCoord.col()

    def setStoredCoord(self, coord : textPosition):
        self.storedCoord.setRow(coord.row())
        self.storedCoord.setCol(coord.col())

    def syncStoredCoord(self):
        self.storedCoord.setRow(self.Coord.row())
        self.storedCoord.setCol(self.Coord.col())


class textPosition:
    def row(self):
        return self._y

    def col(self):
        return self._x

    def setRow(self, row, refreshStored = False):
        self._y = row
        if refreshStored:
            self.storeRow(row)

    def setCol(self, col, refreshStored = False):
        self._x = col
        if refreshStored:
            self.storeCol(col)

    def __init__(self):
        self._x = 0
        self._y = 0


class  MainWindow(QMainWindow):
    def __init__(self, parent = None):
        super().__init__(parent)
        # Main = MasterEditor(self)
        Main = textEdit(self)
        self.setWindowTitle("CodeEdit")
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