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
    QKeyEvent, QPaintEvent, QWheelEvent)
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
import numpy as np

RED    = "\033[31m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
BLUE   = "\033[34m"
RESET  = "\033[0m"

COLORMAP = {
    0   : f"{RED}",
    1   : f"{GREEN}",
    2   : f"{YELLOW}",
    3   : f"{BLUE}"
}

QT_COLORMAP = {
    0: Qt.red,
    1: Qt.green,
    2: Qt.yellow,
    3: Qt.blue
}

PAIR_BRACE = {
    '(' : ')',
    '{' : '}',
    '[' : ']',
    '"' : '"',
    "'" : "'"
}

OPEN_BRACES = set(PAIR_BRACE.keys())
CLOSE_BRACES = set(PAIR_BRACE.values())


def stringGroup(ch : str):
    if ch.isalnum() or ch == '_':
        return 1
    if ch == ' ' or ch == ',':
        return 2
    if ch in OPEN_BRACES:
        return 3
    if ch in CLOSE_BRACES:
        return 4
    return 5


def angle(v1 : tuple, v2 : tuple) -> float:
    arr1 = np.array(v1)
    arr2 = np.array(v2)

    dot = arr1 @ arr2

    mag1 = np.linalg.norm(arr1)
    mag2 = np.linalg.norm(arr2)

    if mag1 == 0 or mag2 == 0:
        return 0.0

    cos_theta = dot / (mag1 * mag2)

    # Clip the value to [-1.0, 1.0] to prevent math domain errors
    # caused by tiny floating-point precision inaccuracies
    cos_theta = np.clip(cos_theta, -1.0, 1.0)

    # Returns the angle in radians
    return np.degrees(np.arccos(cos_theta))


class CoordinateType(Enum):
    VISIBLE = auto()
    ABSOLUTE = auto()


class dummyCursorType(Enum):
    UNASSIGNED = auto()
    TRANSFER = auto()
    EXTRA    = auto()


class textEdit(QWidget):

    def __init__(self, parent):
        super().__init__(parent)
        self._document = textDocument()
        self._Cursor = TextCursor(editor = self, doc = self.document())
        self.extraCursors : list[dummyCursor] = []
        self.editFlag = False

        self.Font = QFont()
        self.Font.setFamilies(["Consolas", "Courier New"])
        self.fontSize = 17
        self.Font.setPixelSize(self.fontSize)
        self.fm = QFontMetricsF(self.Font)

        self.cellW  = self.fm.horizontalAdvance("W")
        self.cellH  = self.fm.height()
        self.Ascent = self.fm.ascent()
        self.longLine = 0

        self._scrollY = 0
        self._scrollX = 0
        self._maxScrollX = 0
        self._maxScrollY = 0
        self.scrollActive = False

        self.toggle = False
        self.cursorVisible = True
        self.cursWidth = 2
        self.cursDelay = 500
        self.cursCount = 255
        self.cursTimer = QTimer(self)
        self.cursTimer.start(self.cursDelay)
        self.cursTimer.timeout.connect(self.toggleCursor)

        self.selectTimer = QTimer(self)
        self.selectUpdate = 10
        self.selectTimer.start(self.selectUpdate)
        self.selectTimer.timeout.connect(self.extendSelection)

        self.controlModifier = False
        self.shiftModifier   = False

        self._updateReason = None
        self.showReason = False
        self.paintCount = 0

        self.mousePressed = False
        self.mouseMoved = False
        self.selectTransfer = False
        self.trippleClickEN = False
        self.quadClickEN = False
        self.doubleClicked = False
        self.trippleClicked = False
        self.quadClicked = False
        self.clickTimer = QTimer(self)
        self.clickTimer.setSingleShot(True)
        self.clickTimer.timeout.connect(self.clickConfig)
        self.doubleClickTimer = QTimer(self)
        self.doubleClickTimer.setSingleShot(True)
        self.mouseX = 0
        self.mouseY = 0

        self.UndoRedoStack = UndoRedoManager()
        self.commandGroup  = []
        self.UndRedTimer   = QTimer(self)
        self.UndRedTimer.setSingleShot(True)
        self.UndRedTimer.timeout.connect(self.commandDispatch)

        self.prevH = self.height()
        self.prevW = self.width()

        self.setMargins()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def paintEvent(self, event : QPaintEvent):
        self.paintCount += 1
        painter = QPainter(self)
        painter.setFont(self.Font)
        painter.fillRect(event.rect(), QColor(18, 19, 20))
        # if event.rect() != self.rect():
        #     painter.drawRect(event.rect())
        self._updateReason = None

        if self.scrollActive:
            start = self.firstVisibleBlock(rect = event.rect()).blockNumber()
            stop  = self.lastVisibleBlock(rect = event.rect()).blockNumber()
            self.scrollActive = False
        else:
            start = self.firstVisibleBlock().blockNumber()
            stop  = self.lastVisibleBlock().blockNumber()

        if self.textCursor().hasSelection():
            aRow, aCol = (self.textCursor().selectionStart().visibleCoord().row(), self.textCursor().selectionStart().visibleCoord().col())
            bRow, bCol = (self.textCursor().selectionStop().visibleCoord().row(), self.textCursor().selectionStop().visibleCoord().col())
            selectionPath = QPainterPath()

            aRow = max(aRow, start - 1)
            bRow = min(bRow, stop + 1)

            for row in range(aRow, bRow + 1):
                startCol = aCol if row == aRow else 0

                # Add + 1 to totalCharacters() to highlight the invisible newline character
                endCol = bCol if row == bRow else self.document().findBlockByNumber(row).totalCharacters() + 1

                x = startCol * self.cellW - self._scrollX + self.leftMargin()
                y = row * self.cellH - self._scrollY + self.topMargin()
                width = (endCol - startCol) * self.cellW
                height = self.cellH + 0.1

                line_rect = QRectF(x, y, width, height)

                temp_path = QPainterPath()
                temp_path.addRect(line_rect)
                selectionPath = selectionPath.united(temp_path)

            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            roundedSelection = self.smoothPath(selectionPath, radius=6, painter=painter)

            painter.setPen(Qt.NoPen)
            if self.hasFocus(): painter.setBrush(QColor(52, 166, 209, 100))
            else: painter.setBrush(QColor(50, 147, 183, 64))
            painter.drawPath(roundedSelection)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        row = start

        if not self.toggle:
            painter.setPen(QPen(QColor(200, 200, 200), 1))
            painter.setBrush(Qt.NoBrush)
            while True:
                if row > stop:
                    break
                block = self.document().visibleBlocks()[row]
                y = row * self.cellH + self.topMargin() - self._scrollY

                if block.head:
                    rect = QRectF(
                        0, y,
                        self.cellW, self.cellH
                    )
                    painter.drawRect(rect)

                for col, ch in enumerate(block.text()):
                    x = col * self.cellW + self.leftMargin() - self._scrollX
                    if x > self.width() - self.rightMargin():
                        break
                    # rect = QRectF(
                    #     x, y,
                    #     self.cellW, self.cellH
                    # )
                    # painter.drawRect(rect)
                    painter.drawText(
                        x, y + self.Ascent,
                        ch
                    )
                row += 1

        else:
            if self.showReason:
                print("missed")

        if self.cursorVisible and self.hasFocus():
            # cursorPen = QPen(QColor(200, 200, 200, self.cursCount), self.cursWidth)
            cursorPen = QPen(QColor(200, 200, 200, 255), self.cursWidth)
            painter.setPen(cursorPen)
            x = self.textCursor().visibleCoord().col() * self.cellW + self.leftMargin() - self._scrollX
            y = self.textCursor().visibleCoord().row() * self.cellH + self.topMargin() - self._scrollY
            if x == 0: x = 1
            painter.drawLine(x, y + 1.2, x, y + self.cellH - 1.2)

            for curs in self.extraCursors:
                if curs.type == dummyCursorType.EXTRA:
                    x = curs.visibleCoord().col() * self.cellW + self.leftMargin() - self._scrollX
                    y = curs.visibleCoord().row() * self.cellH + self.topMargin() - self._scrollY
                    if x == 0: x = 1
                    painter.drawLine(x, y + 1.2, x, y + self.cellH - 1.2)
    
        if self.hasFocus():
            for curs in self.extraCursors:
                if curs.type == dummyCursorType.TRANSFER and self.selectTransfer:
                    cursorPen = QPen(QColor(200, 200, 200, 255), self.cursWidth)
                    cursorPen.setDashPattern([0.5, 1.5])
                    painter.setPen(cursorPen)
                    x = curs.visibleCoord().col() * self.cellW + self.leftMargin() - self._scrollX
                    y = curs.visibleCoord().row() * self.cellH + self.topMargin() - self._scrollY
                    if x == 0: x = 1
                    painter.drawLine(x, y + 1.2, x, y + self.cellH - 0.2)
                    cursorPen.setStyle(Qt.PenStyle.SolidLine)


        self.toggle = False
        painter.fillRect(QRect(0, 0, self.leftMargin(), self.height()), QColor(18, 19, 20))
        painter.fillRect(QRect(0, 0, self.width(), self.topMargin()), QColor(18, 19, 20))
        painter.fillRect(QRect(0, self.height(), self.width(), -self.bottomMargin()), QColor(18, 19, 20))
        painter.fillRect(QRect(self.width(), self.height(), -self.rightMargin(), -self.height()), QColor(18, 19, 20))
        painter.end()
        super().paintEvent(event)

    def smoothPath(self, path: QPainterPath, radius: float = 4.0, painter : QPainter = None) -> QPainterPath:
        polygon = path.toFillPolygon()

        # A valid selection polygon needs at least 3 points
        if polygon.size() < 3:
            return path

        points = [polygon.at(i) for i in range(polygon.size())]

        if points[0] == points[-1]:
            points.pop()

        n = len(points)
        if n < 3:
            return path

        roundedPath = QPainterPath()
        reducedPoints = []

        for p in points:
            if len(reducedPoints) < 2:
                reducedPoints.append(p)
                continue

            p1 = reducedPoints[-2]
            p2 = reducedPoints[-1]
            p3 = p

            is_horizontal = (round(p1.y()) == round(p2.y()) == round(p3.y()))
            is_vertical = (round(p1.x()) == round(p2.x()) == round(p3.x()))

            if is_horizontal or is_vertical:
                reducedPoints[-1] = p3
            else:
                reducedPoints.append(p3)

        # reducedPoints = points

        # painter.fillRect(self.rect(), QColor(18, 19, 20))
        # for i, p in enumerate(reducedPoints):
        #     qColor = QT_COLORMAP[i % 4]
        #     color = COLORMAP[i % 4]
        #     print(color, (p.x(), p.y()), f"{RESET}")
        #     pen = QPen(qColor, 5)
        #     pen.setCapStyle(Qt.RoundCap)
        #     painter.setPen(pen)
        #     painter.drawPoint(p)
        # print("------")

        r = self.cellW // 2
        start = reducedPoints[0]
        regions = [[]]
        New = False

        for p in reducedPoints:
            if New:
                start = p
                New = False
            if p == start:
                if p not in regions[-1]:
                    regions[-1].append(p)
                else:
                    New = True
                    if len(regions[-1]) < 3:
                        regions.pop(-1)
                    regions.append([])
                    continue
            elif p != start:
                regions[-1].append(p)

        for region in regions:
            n = len(region)
            # print("---")

            for i in range(n):
                p0 = region[i - 1]
                p1 = region[i]
                p2 = region[(i + 1) % n]

                # color = COLORMAP[i % 4]
                # qColor = QT_COLORMAP[i % 4]
                # print(color, (p1.x(), p1.y()), f"{RESET}")
                # painter.setPen(QPen(qColor, 2))
                # painter.drawPoint(p)

                if round(p1.x()) <= self.leftMargin() and round(p1.y()) == round(self.textCursor().selectionStop().visibleCoord().row() * self.cellH + self.topMargin() - self._scrollY) and self.textCursor().selectionStop().visibleCoord().col() == 0:
                    if i == 0:
                        roundedPath.moveTo(p1)
                    else:
                        roundedPath.lineTo(p1)
                    continue

                a = None
                b = None

                if round(p0.x()) == round(p1.x()):
                    if p1.y() == p0.y():
                        continue
                    sgn = (p1.y() - p0.y())/abs(p1.y() - p0.y())
                    a = QPointF(p1.x(), p1.y() - sgn * r)
                elif round(p0.y()) == round(p1.y()):
                    if p1.x() == p0.x():
                        continue
                    sgn = (p1.x() - p0.x())/abs(p1.x() - p0.x())
                    a = QPointF(p1.x() - sgn * r, p1.y())

                if round(p2.x()) == round(p1.x()):
                    if p1.y() == p2.y():
                        continue
                    sgn = (p1.y() - p2.y())/abs(p1.y() - p2.y())
                    b = QPointF(p1.x(), p1.y() - sgn * r)
                elif round(p2.y()) == round(p1.y()):
                    if p1.x() == p2.x():
                        continue
                    sgn = (p1.x() - p2.x())/abs(p1.x() - p2.x())
                    b = QPointF(p1.x() - sgn * r, p1.y())

                if a and b:
                    if i == 0:
                        roundedPath.moveTo(a)
                        roundedPath.quadTo(p1, b)
                    else:
                        roundedPath.lineTo(a)
                        roundedPath.quadTo(p1, b)

        # print("------------------------")
        roundedPath.closeSubpath()
        t1 = time.perf_counter()
        return roundedPath

    def resetCursor(self):
        self.toggle = False
        self.cursorVisible = True
        # self.cursCount = 255
        cursX = self.textCursor().visibleCoord().col() * self.cellW + self.leftMargin()
        cursY = self.textCursor().visibleCoord().row() * self.cellH + self.topMargin() - self._scrollY
        Rect = QRect(int(cursX) - self.cellW, int(cursY) - 1, 2 * int(self.cellW), int(self.cellH) + 1)
        self.update(Rect)
        self.cursTimer.start(self.cursDelay)

    def toggleCursor(self):
        if self.hasFocus():
            self.toggle = True
            self.cursorVisible = not self.cursorVisible
            # self.cursCount -= 16
            # if self.cursCount < -32: self.cursCount = 255
            cursX = self.textCursor().visibleCoord().col() * self.cellW + self.leftMargin() - self._scrollX
            cursY = self.textCursor().visibleCoord().row() * self.cellH + self.topMargin() - self._scrollY
            if not self.scrollActive:
                self._updateReason = "toggle"
                self.update(QRect(round(cursX) - self.cellW, round(cursY) - 1, 2 * round(self.cellW), round(self.cellH) + 1))
            self.toggle = False

    def clickConfig(self):
        self.trippleClickEN = False
        self.quadClickEN = False

    def maxScrollConfig(self):
        self.longLine = max(self.document().lineLog)
        maxScroll = (self.longLine + 2) * self.cellW - self.prevW

        if self._maxScrollX != maxScroll:
            self._maxScrollX = maxScroll
            self.update()

    def document(self): return self._document
    def textCursor(self): return self._Cursor

    def firstVisibleBlock(self, rect : QRect | None = None):
        blocks = self.document().visibleBlocks()
        if not blocks:
            return None

        offset = max(0, rect.y() - self.topMargin()) if rect is not None else 0
        total_y = max(0, self._scrollY + offset)
        blockNo = min(int(total_y // self.cellH), len(blocks) - 1)

        block = blocks[blockNo]
        block._blockNumber = blockNo
        return block

    def lastVisibleBlock(self, rect : QRect | None = None):
        blocks = self.document().visibleBlocks()
        if not blocks:
            return None

        if rect is None:
            available_height = self.height() - self.topMargin() - self.bottomMargin()
            offset = max(0, available_height - 1)
        else:
            offset = max(0, rect.bottom() - self.topMargin())

        total_y = max(0, self._scrollY + offset)
        blockNo = min(int(total_y // self.cellH), len(blocks) - 1)

        block = blocks[blockNo]
        block._blockNumber = blockNo
        return block

    def characterAt(self, row, col, coordType : CoordinateType) -> str | None:
        if coordType == CoordinateType.ABSOLUTE:
            block = self.document().findBlockByNumber(row)
            if block and block.totalCharacters() > col >= 0:
                return block.text()[col]
        elif coordType == CoordinateType.VISIBLE:
            block = self.document().findBlockByVisibleNumber(row)
            if block and block.totalCharacters() > col >= 0:
                return block.text()[col]
        return None

    def setMargins(self, left = 0, top = 0, right = 0, bottom = 0):
        self._leftMargin = left
        self._topMargin = top
        self._rightMargin = right
        self._bottomMargin = bottom

    def leftMargin(self)  : return self._leftMargin
    def topMargin(self)   : return self._topMargin
    def rightMargin(self) : return self._rightMargin
    def bottomMargin(self): return self._bottomMargin

    def newLine(self, visLineNo = None, enumerate = True, dispatch = False):
        maxconfig = False
        cursor = self.textCursor()
        doc = self.document()

        if cursor.block().totalCharacters() >= self.longLine:
            maxconfig = True

        if visLineNo is None:
            visLineNo = cursor.visibleCoord().row() + 1
            col = cursor.visibleCoord().col()
            absLineNo = self.textCursor().Coord().visibleToAbsolute(visLineNo - 1) + 1
        else:
            absLineNo = self.textCursor().Coord().visibleToAbsolute(visLineNo) + 1
            visLineNo += 1
            if visLineNo == cursor.visibleCoord().row() + 1:
                col = cursor.visibleCoord().col()
            else:
                col = doc.findBlockByNumber(absLineNo - 1).totalCharacters()

        prevBlock = doc.findBlockByNumber(absLineNo - 1)

        block = textBlock(doc, blockNumber = absLineNo)
        block.setText(prevBlock.text()[col:])
        prevBlock.setText(prevBlock.text()[:col])

        self.document().blocks().insert(absLineNo, block)
        self.document().visibleBlocks().insert(visLineNo, block)
        self.document().lineLog.insert(absLineNo, block.totalCharacters())
        self.document().lineLog[absLineNo - 1] = col

        if enumerate: doc.reEnumerate()

        if dispatch:
            command = newLine(self, doc, (absLineNo, col))
            self.commandGroup.append(command)
            self.commandDispatch()

        self.textCursor().moveTo(visLineNo, 0)
        self._maxScrollY += self.cellH
        self.update()

        if maxconfig:
            QTimer.singleShot(100, self.maxScrollConfig)

    def insert(self, text : str, absPosition : TextCursor | textPosition | None = None, moveRight = True):
        maxConfig = False

        if absPosition is None:
            absoluteRow = self.textCursor().absoluteCoord().row()
            col = self.textCursor().Coord().col()
        else:
            if isinstance(absPosition, textPosition):
                absoluteRow = absPosition.row()
                col = absPosition.col()
            elif isinstance(absPosition, TextCursor):
                absoluteRow = absPosition.absoluteCoord().row()
                col = absPosition.Coord().col()

        block = self.document().findBlockByNumber(absoluteRow)
        if self.longLine <= block.totalCharacters():
            maxConfig = True

        block.setText(block.text()[:col] + text + block.text()[col:])

        length = len(text)
        if moveRight:
            if length == 1:
                self.textCursor().navRight()
            else:
                self.textCursor().moveToCol(col + length)
        self.document().lineLog[absoluteRow] += length

        if self.document().lineLog[absoluteRow] > self.longLine:
            self.longLine = self.document().lineLog[absoluteRow]
            self._maxScrollX = (self.longLine + 2) * self.cellW - self.prevW
            maxConfig = False
        self.update()

        if maxConfig:
            QTimer.singleShot(100, self.maxScrollConfig)

    def deleteLeft(self, visPosition : textPosition | None = None, dispatch = False):
        maxConfig = False
        if self.longLine <= self.textCursor().block().totalCharacters():
            maxConfig = True

        if not visPosition:
            row = self.textCursor().visibleCoord().row()
            col = self.textCursor().visibleCoord().col()
        else:
            row = visPosition.row()
            col = visPosition.col()

        block = self.document().findBlockByVisibleNumber(row)
        abs_row = self.document().visibleToAbsolute(row)

        if col > 0:
            if dispatch:
                ch = block.text()[col - 1]
                command = deleteText(self, self.document(), (abs_row, col - 1), ch)
                self.commandGroup.append(command)
                self.UndRedTimer.start(500)

            block.setText(block.text()[:col - 1] + block.text()[col:])
            self.document().lineLog[abs_row] -= 1
            self.textCursor().navLeft()
        elif row > 0:
            if dispatch:
                self.commandDispatch()
                command = deleteLine(self, self.document(), abs_row)
                self.commandGroup.append(command)
                self.commandDispatch()

            toAppend = self.document().findBlockByVisibleNumber(row).text()[:]
            self.textCursor().navLeft()
            self.document().findBlockByVisibleNumber(row - 1)._string += toAppend

            del self.document().visibleBlocks()[row]
            del self.document().blocks()[abs_row]

            self.document().lineLog[abs_row - 1] += self.document().lineLog[abs_row]
            del self.document().lineLog[abs_row]

            if self.document().lineLog[abs_row - 1] > self.longLine:
                self.longLine = self.document().lineLog[abs_row - 1]
                self._maxScrollX = (self.longLine + 2) * self.cellW - self.prevW
                maxConfig = False

            self.document().reEnumerate()
            self._maxScrollY -= self.cellH
            if self._maxScrollY < 0: self._maxScrollY = 0
        self.update()

        if maxConfig:
            QTimer.singleShot(100, self.maxScrollConfig)

    def deleteRight(self, position : textPosition | None = None, dispatch = False):
        maxConfig = False
        if self.longLine <= self.textCursor().block().totalCharacters():
            maxConfig = True

        if not position:
            row = self.textCursor().visibleCoord().row()
            col = self.textCursor().visibleCoord().col()
        else:
            row = position.row()
            col = position.col()
        block = self.document().findBlockByVisibleNumber(row)
        blockLength = block.totalCharacters()

        abs_row = self.document().visibleToAbsolute(row)

        if col < blockLength:
            if dispatch:
                ch = block.text()[col]
                command = deleteText(self, self.document(), (abs_row, col), ch)
                self.commandGroup.append(command)
                self.UndRedTimer.start(500)

            block.setText(block.text()[:col] + block.text()[(col + 1):])
            self.document().lineLog[row] -= 1
        elif abs_row < len(self.document().blocks()) - 1:
            if dispatch:
                self.commandDispatch()
                command = deleteLine(self, self.document(), abs_row + 1)
                self.commandGroup.append(command)
                self.commandDispatch()

            toAppend = block.next().text()[:]
            block._string += toAppend
            if row + 1 < len(self.document().visibleBlocks()):
                del self.document().visibleBlocks()[row + 1]
            del self.document().blocks()[abs_row + 1]

            self.document().lineLog[abs_row] += self.document().lineLog[abs_row + 1]
            del self.document().lineLog[abs_row + 1]

            if self.document().lineLog[abs_row] > self.longLine:
                self.longLine = self.document().lineLog[abs_row]
                self._maxScrollX = (self.longLine + 2) * self.cellW - self.prevW
                maxConfig = False

            self.document().reEnumerate()
            self._maxScrollY -= self.cellH
            if self._maxScrollY < 0: self._maxScrollY = 0
        self.update()

        if maxConfig:
            QTimer.singleShot(100, self.maxScrollConfig)

    def deleteSelection(self, dispatch = False):
        maxconfig = False
        if self.textCursor().hasSelection():
            if dispatch:
                text = self.textCursor().selectedText()
                print("deleted text =", repr(text))
            startRow = self.textCursor().selectionStart().absoluteCoord().row()
            startCol = self.textCursor().selectionStart().absoluteCoord().col()
            stopRow  = self.textCursor().selectionStop().absoluteCoord().row()
            stopCol  = self.textCursor().selectionStop().absoluteCoord().col()
            self.textCursor().moveTo(visRow = startRow, col = startCol)
            self.textCursor().selection().reset()
            if startRow == stopRow:
                block = self.document().blocks()[startRow]
                if block.totalCharacters() >= self.longLine:
                    maxconfig = True
                block.setText(block.text()[:startCol] + block.text()[stopCol:])

                nDel = stopCol - startCol
                self.document().lineLog[startRow] -= nDel
            else:
                maxconfig = True
                self.document().lineLog[stopRow] -= stopCol
                self.document().lineLog[startRow] = startCol + self.document().lineLog[stopRow] 

                startBlock = self.document().blocks()[startRow]
                stopBlock  = self.document().blocks()[stopRow]
                visibleStart = self.textCursor().Coord().absoluteToVisible(startRow)
                visibleStop  = self.textCursor().Coord().absoluteToVisible(stopRow)
                startBlock.setText(startBlock.text()[:startCol] + stopBlock.text()[stopCol:])

                del self.document().visibleBlocks()[visibleStart + 1 : visibleStop + 1]
                del self.document().blocks()[startRow + 1 : stopRow + 1]
                del self.document().lineLog[startRow + 1 : stopRow + 1]

                self._maxScrollY -= (visibleStop - visibleStart) * self.cellH

                self.document().reEnumerate()

            if maxconfig:
                QTimer.singleShot(100, self.maxScrollConfig)

            if dispatch:
                self.commandDispatch()
                absPosition = (self.textCursor().absoluteCoord().row(), self.textCursor().Coord().col())
                command = deleteText(editor = self, document = self.document(), absPosition = absPosition, selection = True, text = text)
                self.commandGroup.append(command)
                self.commandDispatch()

    def copySelection(self):
        if self.textCursor().hasSelection():
            text = self.textCursor().selectedText()
            # print(text)
            QGuiApplication.clipboard().setText(text)

    def extendSelection(self):
        if not self.mouseMoved:
            return

        prevX = self._scrollX
        prevY = self._scrollY

        if self.mouseX < self.leftMargin():
            # dist = self.leftMargin() - self.mouseX
            # self._scrollX -= dist * 2
            if not self.textCursor().isAtBlockStart():
                self.textCursor().navLeft(Anchor = True)
        elif self.mouseX > self.width() - self.rightMargin():
            # dist = self.mouseX - self.width() + self.rightMargin()
            # self._scrollX += dist * 2
            if not self.textCursor().isAtBlockEnd():
                self.textCursor().navRight(Anchor = True)
        elif self.mouseY < self.topMargin():
            dist = self.topMargin() - self.mouseY
            self._scrollY -= dist * 2
        elif self.mouseY > self.height() - self.bottomMargin():
            dist = self.mouseY - self.height() + self.bottomMargin()
            self._scrollY += dist * 2

        if self._scrollX > self._maxScrollX: self._scrollX = self._maxScrollX
        if self._scrollY > self._maxScrollY: self._scrollY = self._maxScrollY
        if self._scrollX < 0: self._scrollX = 0
        if self._scrollY < 0: self._scrollY = 0

        if prevX != self._scrollX or prevY != self._scrollY:
            x = self.mouseX + self._scrollX
            y = self.mouseY + self._scrollY
            self.textCursor().moveTo(visRow = int(y / self.cellH), col = int(x / self.cellW + 1 / 2), scroll = False, Anchor = True)
            self.update()

    def pasteText(self, text : str, absPosition : TextCursor | textPosition | None = None, Anchor = False, dispatch = False, debug = False):
        if absPosition is None:
            row = self.textCursor().visibleCoord().row()
            col = self.textCursor().visibleCoord().col()
        elif isinstance(absPosition, textPosition):
            row = self.document().absoluteToVisible(absPosition.row())
            col = absPosition.col()
        elif isinstance(absPosition, TextCursor):
            row = absPosition.visibleCoord().row()
            col = absPosition.Coord().col()

        if dispatch:
            self.commandDispatch()
            if absPosition is None:
                position = (self.textCursor().absoluteCoord().row(), self.textCursor().Coord().col())
            elif isinstance(absPosition, textPosition):
                position = (absPosition.row(), absPosition().col)
            elif isinstance(absPosition, TextCursor):
                position = (absPosition.absoluteCoord().row(), absPosition.Coord().col())

        nLine = 0
        lines = text.split('\n')
        totalLines = len(lines)
        if debug: print("No of Pasted lines =", totalLines)

        for i, line in enumerate(reversed(lines)):
            if debug:
                self.debug(2373, 2386)
                print("Line No =", i, "Line Text =", (line))
            if line:
                self.insert(text = line, absPosition = absPosition, moveRight = False)

            if i < totalLines - 1:
                nLine += 1
                if nLine > 500:
                    nLine = 0
                    self.update()

                if debug:
                    print("NewLine")
                    self.debug(2373, 2386)

                self.newLine(visLineNo=row, enumerate=False)
                self.textCursor().navBlockEnd()
                self.textCursor().navUp()
                self.textCursor().moveToCol(col)

                if debug: self.debug(2373, 2386)

        self.textCursor().navBlockEnd()
        self.textCursor().moveToCol(col)
        self.document().reEnumerate()

        if debug: self.debug(2373, 2386)

        nRows = text.count('\n')
        if nRows > 0:
            self.textCursor().Coord().setCol(0)
            col = 0

        lastNewlineIdx = text.rfind('\n')
        if lastNewlineIdx == -1:
            nCols = len(text)
        else:
            nCols = len(text) - 1 - lastNewlineIdx

        self.textCursor().moveTo(
            visRow = (row + nRows),
            col = (col + nCols),
            Anchor = Anchor
        )

        if debug: self.debug(2373, 2386)

        self.update()

        if dispatch:
            command = pasteText(editor = self, document = self.document(), absPosition = position, text = text)
            self.commandGroup.append(command)
            self.commandDispatch()

    def jumpLeft(self, Anchor = False):
        col = self.textCursor().Coord().col()
        row = self.textCursor().absoluteCoord().row()

        if col == 0:
            if row > 0:
                self.textCursor().navLeft(Anchor = Anchor)
            return

        block = self.document().findBlockByNumber(row)
        ch = block.text()[col - 1]
        initGroup = stringGroup(ch)
        initChar  = ch

        while True:
            col -= 1
            if col < 0:
                col = 0
                break
            ch = block.text()[col - 1]
            if initGroup in {3, 4} and ch in {'"', "'"}:
                continue
            if initChar in {'"', "'"} and stringGroup(ch) in {3, 4}:
                if ch not in {'"', "'"}:
                    initGroup = stringGroup(ch)
                    initChar = None
                continue
            if stringGroup(ch) != initGroup:
                break
        self.textCursor().moveToCol(col = col, Anchor = Anchor)

        self.update()
        self.resetCursor()

    def jumpRight(self, Anchor = False):
        col = self.textCursor().Coord().col()
        row = self.textCursor().absoluteCoord().row()

        block = self.document().findBlockByNumber(row)
        blockLen = block.totalCharacters()
        if col == blockLen:
            if row < self.document().totalBlocks() - 1:
                self.textCursor().navRight(Anchor = Anchor)
            return

        ch = block.text()[col]
        initGroup = stringGroup(ch)
        initChar  = ch

        while True:
            col += 1
            if col >= blockLen:
                col = blockLen
                break
            ch = block.text()[col]
            if initGroup in {3, 4} and ch in {'"', "'"}:
                continue
            if initChar in {'"', "'"} and stringGroup(ch) in {3, 4}:
                if ch not in {'"', "'"}:
                    initGroup = stringGroup(ch)
                    initChar = None
                continue
            if stringGroup(ch) != initGroup:
                break
        self.textCursor().moveToCol(col = col, Anchor = Anchor)

        self.update()
        self.resetCursor()

    def commandDispatch(self):
        if not self.commandGroup:
            return
        if self.editFlag:
            return

        self.UndoRedoStack.undoStack.append(self.commandGroup.copy())
        self.commandGroup.clear()
        self.UndoRedoStack.redoStack.clear()

    def beginEdit(self):
        self.commandDispatch()
        self.editFlag = True

    def endEdit(self):
        self.editFlag = False
        self.commandDispatch()

    def keyPressEvent(self, event : QKeyEvent):
        if self.controlModifier:
            if   event.key() == Qt.Key.Key_Shift:
                self.shiftModifier = True
            elif event.key() == Qt.Key.Key_Equal:
                pCellW = self.cellW
                pCellH = self.cellH
                self.fontSize += 1
                self.Font.setPixelSize(self.fontSize)
                self.fm = QFontMetricsF(self.Font)

                self.cellW  = self.fm.horizontalAdvance("W")
                self.cellH  = self.fm.height()
                self.Ascent = self.fm.ascent()

                self._scrollX = self._scrollX * self.cellW / pCellW
                self._scrollY = self._scrollY * self.cellH / pCellH
                self._maxScrollX = self._maxScrollX * self.cellW / pCellW
                self._maxScrollY = self._maxScrollY * self.cellH / pCellH

                self.update()
            elif event.key() == Qt.Key.Key_Minus:
                pCellW = self.cellW
                pCellH = self.cellH
                self.fontSize -= 1
                self.Font.setPixelSize(self.fontSize)
                self.fm = QFontMetricsF(self.Font)

                self.cellW  = self.fm.horizontalAdvance("W")
                self.cellH  = self.fm.height()
                self.Ascent = self.fm.ascent()

                self._scrollX = self._scrollX * self.cellW / pCellW
                self._scrollY = self._scrollY * self.cellH / pCellH
                self._maxScrollX = self._maxScrollX * self.cellW / pCellW
                self._maxScrollY = self._maxScrollY * self.cellH / pCellH

                self.update()
            elif event.key() == Qt.Key.Key_C:
                self.copySelection()
            elif event.key() == Qt.Key.Key_X:
                self.commandDispatch()
                if self.textCursor().hasSelection():
                    absPosition = (self.textCursor().selectionStart().absoluteCoord().row(), self.textCursor().selectionStart().col())
                    text = self.textCursor().selectedText()
                    self.copySelection()
                    self.deleteSelection()
                else:
                    if self.textCursor().visibleCoord().row() != 0:
                        self.textCursor().navUp()
                        self.textCursor().navBlockEnd()
                        self.textCursor().navRight(Anchor = True)
                        self.textCursor().navBlockEnd(Anchor = True)

                        absPosition = (self.textCursor().selectionStart().absoluteCoord().row(), self.textCursor().selectionStart().col())
                        text = self.textCursor().selectedText()
                    else:
                        self.textCursor().navBlockStart()
                        self.textCursor().navBlockEnd(Anchor = True)

                        absPosition = (self.textCursor().selectionStart().absoluteCoord().row(), self.textCursor().selectionStart().col())
                        text = self.textCursor().selectedText()
                    self.copySelection()
                    self.deleteSelection()

                command = cutText(self, self.document(), absPosition, text)
                self.commandGroup.append(command)
                self.commandDispatch()
                self.update()
            elif event.key() == Qt.Key.Key_V:
                self.commandDispatch()
                text = QGuiApplication.clipboard().text()
                # print(repr(text))
                if self.textCursor().hasSelection():
                    absPosition = (self.textCursor().selectionStart().absoluteCoord().row(), self.textCursor().selectionStart().col())
                    command = deleteText(self, self.document(), absPosition, self.textCursor().selectedText())
                    self.commandGroup.append(command)
                    self.deleteSelection()
                absPosition = (self.textCursor().absoluteCoord().row(), self.textCursor().Coord().col())
                command2 = pasteText(self, self.document(), absPosition, text)
                self.commandGroup.append(command2)
                self.pasteText(text = text)
                self.commandDispatch()
            elif event.key() == Qt.Key.Key_A:
                self.textCursor().navToStart(scroll = False)
                self.textCursor().navToEnd(scroll = False, Anchor = True)
                self.update()
            elif event.key() == Qt.Key.Key_Left:
                self.jumpLeft(Anchor = self.shiftModifier)
            elif event.key() == Qt.Key.Key_Right:
                self.jumpRight(Anchor = self.shiftModifier)
            elif event.key() == Qt.Key.Key_Up:
                self.textCursor().navUp(Anchor = self.shiftModifier)
            elif event.key() == Qt.Key.Key_Down:
                self.textCursor().navDn(Anchor = self.shiftModifier)
            elif event.key() == Qt.Key.Key_Backspace:
                self.jumpLeft(Anchor = True)

                self.commandDispatch()
                text = self.textCursor().selectedText()
                absPosition = (self.textCursor().selectionStart().absoluteCoord().row(), self.textCursor().selectionStart().col())
                command = deleteText(editor = self, document = self.document(), absPosition = absPosition, text = text)
                self.commandGroup.append(command)
                self.commandDispatch()

                self.deleteSelection()
            elif event.key() == Qt.Key.Key_Delete:
                self.jumpRight(Anchor = True)

                self.commandDispatch()
                text = self.textCursor().selectedText()
                absPosition = (self.textCursor().selectionStart().absoluteCoord().row(), self.textCursor().selectionStart().col())
                command = deleteText(editor = self, document = self.document(), absPosition = absPosition, text = text)
                self.commandGroup.append(command)
                self.commandDispatch()

                self.deleteSelection()
            elif event.key() == Qt.Key.Key_Z:
                self.commandDispatch()
                self.UndoRedoStack.undo()
            elif event.key() == Qt.Key.Key_Y:
                self.UndoRedoStack.redo()

        elif event.key() == Qt.Key.Key_Left:
            if self.textCursor().hasSelection() and not self.shiftModifier:
                row = self.textCursor().selectionStart().visibleCoord().row()
                col = self.textCursor().selectionStart().visibleCoord().col()
                self.textCursor().moveTo(visRow = row, col = col)
            else:
                self.textCursor().navLeft(Anchor = self.shiftModifier)

        elif event.key() == Qt.Key.Key_Right:
            if self.textCursor().hasSelection() and not self.shiftModifier:
                row = self.textCursor().selectionStop().visibleCoord().row()
                col = self.textCursor().selectionStop().visibleCoord().col()
                self.textCursor().moveTo(visRow = row, col = col)
            else:
                self.textCursor().navRight(Anchor = self.shiftModifier)

        elif event.key() == Qt.Key.Key_Up:
            self.textCursor().navUp(Anchor = self.shiftModifier)

        elif event.key() == Qt.Key.Key_Down:
            self.textCursor().navDn(Anchor = self.shiftModifier)

        elif event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            self.commandDispatch()
            if self.textCursor().hasSelection():
                self.commandDispatch()
                text = self.textCursor().selectedText()
                absPosition = (self.textCursor().selectionStart().absoluteCoord().row(), self.textCursor().selectionStart().col())
                command = deleteText(editor = self, document = self.document(), absPosition = absPosition, text = text, selection = True)
                self.commandGroup.append(command)
                self.deleteSelection()
            self.newLine(dispatch = True)

        elif event.key() == Qt.Key.Key_Backspace:
            if self.textCursor().hasSelection():
                self.commandDispatch()
                text = self.textCursor().selectedText()
                absPosition = (self.textCursor().selectionStart().absoluteCoord().row(), self.textCursor().selectionStart().col())
                command = deleteText(editor = self, document = self.document(), absPosition = absPosition, text = text, selection = True)
                self.commandGroup.append(command)
                self.commandDispatch()
                self.deleteSelection()
            else:
                if self.commandGroup and not isinstance(self.commandGroup[-1], deleteText): self.commandDispatch()
                self.deleteLeft(dispatch = True)

        elif event.key() == Qt.Key.Key_Delete:
            if self.textCursor().hasSelection():
                self.commandDispatch()
                text = self.textCursor().selectedText()
                absPosition = (self.textCursor().selectionStart().absoluteCoord().row(), self.textCursor().selectionStart().col())
                command = deleteText(editor = self, document = self.document(), absPosition = absPosition, text = text, selection = True)
                self.commandGroup.append(command)
                self.commandDispatch()
                self.deleteSelection()
            else:
                if self.commandGroup and not isinstance(self.commandGroup[-1], deleteText): self.commandDispatch()
                self.deleteRight(dispatch = True)

        elif event.key() == Qt.Key.Key_Shift:
            self.shiftModifier = True

        elif event.key() in {Qt.Key.Key_Control, Qt.Key.Key_Meta}:
            self.controlModifier = True

        elif event.key() == Qt.Key.Key_Tab:
            tab = '    '
            self.commandDispatch()
            absPosition = (self.textCursor().absoluteCoord().row(), self.textCursor().Coord().col())
            command = insertText(editor = self, document = self.document(), absPosition = absPosition, text = tab)
            self.commandGroup.append(command)
            self.commandDispatch()

            self.insert(tab)
            self.resetCursor()

        elif event.key() == Qt.Key.Key_CapsLock:
            pass

        else:
            text = event.text()
            absPosition = (self.textCursor().absoluteCoord().row(), self.textCursor().Coord().col())

            if self.commandGroup and not isinstance(self.commandGroup[-1], insertText):
                self.commandDispatch()

            if self.textCursor().hasSelection():
                self.commandDispatch()
                command = deleteText(self, self.document(), absPosition, self.textCursor().selectedText(), True)
                self.commandGroup.append(command)
                self.deleteSelection()

            command2 = insertText(editor = self, document = self.document(), absPosition = absPosition, text = text)
            self.commandGroup.append(command2)
            self.UndRedTimer.start(500)

            self.insert(text)
            self.update()
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event : QKeyEvent):
        if event.key() == Qt.Key.Key_Shift:
            self.shiftModifier = False
        if event.key() in {Qt.Key.Key_Control, Qt.Key.Key_Meta}:
            self.controlModifier = False
        super().keyReleaseEvent(event)

    def mousePressEvent(self, event : QMouseEvent):
        if self.trippleClickEN:
            self.trippleClicked = True
            self.textCursor().navBlockStart()
            self.textCursor().navDn(Anchor = True)
            self.update()
            self.trippleClickEN = False
            self.quadClickEN = True
            self.clickTimer.start(500)
            return

        self.mousePressed = True
        if event.button() == Qt.RightButton:
            self.showReason = True
            print(self.document().lineLog)
        self.mouseX = event.position().x()
        self.mouseY = event.position().y()
        x = self.mouseX + self._scrollX - self.leftMargin()
        y = self.mouseY + self._scrollY - self.topMargin()
        row = int(y / self.cellH)
        col = round(x / self.cellW)
        if self.textCursor().hasSelection():
            start = (self.textCursor().selectionStart().absoluteCoord().row(), self.textCursor().selectionStart().col())
            stop = (self.textCursor().selectionStop().absoluteCoord().row(), self.textCursor().selectionStop().col())
            if start <= (row , col) <= stop:
                self.selectTransfer = True
                return
            else:
                self.textCursor().moveTo(visRow = row, col = col, scroll = False)
        self.textCursor().moveTo(visRow = row, col = col, scroll = False)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event : QMouseEvent):
        dx = event.position().x() - self.mouseX
        dy = event.position().y() - self.mouseY
        self.mouseX = event.position().x()
        self.mouseY = event.position().y()

        if self.mousePressed:
            self.mouseMoved = True
            x = self.mouseX + self._scrollX - self.leftMargin()
            y = self.mouseY + self._scrollY - self.topMargin()
            row = int(y / self.cellH)
            col = round(x / self.cellW)
            if self.selectTransfer:
                start = (self.textCursor().selectionStart().absoluteCoord().row(), self.textCursor().selectionStart().col())
                stop = (self.textCursor().selectionStop().absoluteCoord().row(), self.textCursor().selectionStop().col())
                if start <= (row, col) <= stop:
                    event.accept()
                    return
                else:
                    cursor = None
                    for curs in self.extraCursors:
                        if curs.type == dummyCursorType.TRANSFER:
                            cursor = curs
                            break
                    if not cursor:
                        cursor = dummyCursor(editor = self, doc = self.document(), cursType = dummyCursorType.TRANSFER)
                        cursor.cursVisible = True
                        self.extraCursors.append(cursor)
                    cursor.moveTo(visRow = row, col = col)
                    self.update()
                    event.accept()
                    return

            self.textCursor().moveTo(visRow = row, col = col, scroll = False, Anchor = True)

        elif self.doubleClicked:
            self.mouseMoved = True

            x = self.mouseX + self._scrollX - self.leftMargin()
            y = self.mouseY + self._scrollY - self.topMargin()

            anch = (self.textCursor().anchor().visibleCoord().row(), self.textCursor().anchor().col())
            stor = (self.textCursor().storedCoord().visibleCoord().row(), self.textCursor().storedCoord().col())
            curs = (int(y / self.cellH), round(x / self.cellW))

            # print("anch =", anch)
            # print("stor =", stor)
            # print("curs =", curs)
            # print("--------------", end ='->')


            if (anch <= curs <= stor or anch >= curs >= stor):
                # print("1", end = '')
                if anch > stor:
                    # print("a", end = ' ')
                    buff = anch
                    anch = stor
                    stor = buff
                    self.textCursor().anchor().set_Visible_Coord(row = anch[0], col = anch[1])

                self.textCursor().moveTo(visRow=stor[0], col=stor[1], scroll=False)
                self.jumpLeft()
                self.jumpRight(Anchor = True)
                anch = (self.textCursor().anchor().visibleCoord().row(), self.textCursor().anchor().col())
                print(anch)
                self.textCursor().set_Stored_Visible_Coord(row = stor[0], col = stor[1])
                print()
            elif (curs < anch):
                # print("2", end='')
                if anch < stor:
                    # print("a", end='')
                    buff = anch
                    anch = stor
                    stor = buff
                    self.textCursor().anchor().set_Visible_Coord(row = anch[0], col = anch[1])
                self.textCursor().moveTo(visRow=curs[0], col=curs[1], scroll=False, Anchor=True)
                self.jumpRight(Anchor=True)
                self.jumpLeft(Anchor=True)
                self.textCursor().set_Stored_Visible_Coord(row = stor[0], col = stor[1])
                print()
            elif (curs > anch):
                # print("3", end='')
                if anch > stor:
                    # print("a", end='')
                    buff = anch
                    anch = stor
                    stor = buff
                    self.textCursor().anchor().set_Visible_Coord(row = anch[0], col = anch[1])
                self.textCursor().moveTo(visRow=curs[0], col=curs[1], scroll=False, Anchor=True)
                self.jumpLeft(Anchor=True)
                self.jumpRight(Anchor=True)
                self.textCursor().set_Stored_Visible_Coord(row = stor[0], col = stor[1])
                # print()

        event.accept()

    def mouseReleaseEvent(self, event : QMouseEvent):
        self.mouseX = event.position().x()
        self.mouseY = event.position().y()
        x = self.mouseX + self._scrollX - self.leftMargin()
        y = self.mouseY + self._scrollY - self.topMargin()
        row = int(y / self.cellH)
        col = round(x / self.cellW)
        if self.textCursor().hasSelection() and not self.mouseMoved and not self.doubleClicked and not self.trippleClicked and not self.quadClicked:
            if self.textCursor().hasSelection():
                start = (self.textCursor().selectionStart().absoluteCoord().row(), self.textCursor().selectionStart().col())
                stop = (self.textCursor().selectionStop().absoluteCoord().row(), self.textCursor().selectionStop().col())
                if start <= (row, col) <= stop:
                    self.textCursor().moveTo(visRow = row, col = col, scroll = False)
            self.textCursor().selection().reset()
            self.update()
        elif self.textCursor().hasSelection() and self.mouseMoved and self.selectTransfer:
            start = (self.textCursor().selectionStart().absoluteCoord().row(), self.textCursor().selectionStart().col())
            stop = (self.textCursor().selectionStop().absoluteCoord().row(), self.textCursor().selectionStop().col())
            if (row, col) < start or (row, col) > stop:
                cursor = None
                cursID = 0
                for idx, curs in enumerate(self.extraCursors):
                    if curs.type == dummyCursorType.TRANSFER:
                        cursor = curs
                        cursID = idx
                if cursor:
                    text  = self.textCursor().selectedText()
                    print(repr(text))
                    start = (self.textCursor().selectionStart().visibleCoord().row(), self.textCursor().selectionStart().col())
                    stop  = (self.textCursor().selectionStop().visibleCoord().row(), self.textCursor().selectionStop().col())
                    if (row, col) < start:
                        self.beginEdit()
                        self.deleteSelection(dispatch = True)
                        self.textCursor().moveTo(visRow = row, col = col, sync = False)
                        self.pasteText(text = text, Anchor = True, dispatch = True)
                        self.endEdit()
                    self.extraCursors.pop(cursID)

        self.doubleClicked = False
        self.trippleClicked = False
        self.quadClicked = False
        self.mousePressed = False
        self.mouseMoved = False
        self.selectTransfer = False
        event.accept()

    def mouseDoubleClickEvent(self, event : QMouseEvent):
        if self.quadClickEN:
            self.quadClicked = True
            self.textCursor().navToStart(scroll = False)
            self.textCursor().navToEnd(scroll = False, Anchor = True)
            self.update()
            self.quadClickEN = False
        else:
            self.doubleClicked = True
            row = self.textCursor().visibleCoord().row()
            col = self.textCursor().visibleCoord().col()
            chL = self.characterAt(row = row, col = col - 1, coordType = CoordinateType.VISIBLE)
            chR = self.characterAt(row = row, col = col, coordType = CoordinateType.VISIBLE)

            if not chR:
                self.jumpLeft()
                self.jumpRight(Anchor = True)
            elif not chL:
                self.jumpRight()
                self.jumpLeft(Anchor = True)
            elif chL.isalpha() or chL.isdigit():
                self.jumpLeft()
                self.jumpRight(Anchor = True)
            elif chR.isalpha() or chR.isdigit():
                self.jumpRight()
                self.jumpLeft(Anchor = True)
            elif chL == ' ':
                self.jumpLeft()
                self.jumpRight(Anchor = True)
            elif chR == ' ':
                self.jumpRight()
                self.jumpLeft(Anchor = True)

            self.trippleClickEN = True
            self.clickTimer.start(400)
        event.accept()

    def enterEvent(self, event):
        self.setCursor(Qt.CursorShape.IBeamCursor)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().leaveEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        self._updateReason = "wheelEvent"
        dx = event.angleDelta().x()
        dy = event.angleDelta().y()

        Xdelta = round(dx * self.cellH * 3 / 120)
        Ydelta = round(dy * self.cellW * 3 / 120)

        prevX = self._scrollX
        prevY = self._scrollY

        self._scrollX -= Xdelta
        self._scrollY -= Ydelta

        if self._scrollX > self._maxScrollX:
            self._scrollX = self._maxScrollX
        if self._scrollX < 0:
            self._scrollX = 0
        if self._scrollY > self._maxScrollY:
            self._scrollY = self._maxScrollY
        if self._scrollY < 0:
            self._scrollY = 0

        Xdelta = prevX - self._scrollX
        Ydelta = prevY - self._scrollY

        if prevX != self._scrollX or prevY != self._scrollY:
            if (abs(Ydelta) >= self.height() - self.topMargin() - self.bottomMargin()) or (abs(Xdelta) >= self.width() - self.leftMargin() - self.rightMargin()):
                self.update()
                event.accept()
                return
            self.scrollActive = True
            if Ydelta < 0:
                self.update(QRect(self.leftMargin(), self.height() - self.bottomMargin() + Ydelta, self.width() - self.leftMargin() - self.rightMargin(), Ydelta))
            if Ydelta > 0:
                self.update(QRect(self.leftMargin(), self.topMargin(), self.width() - self.leftMargin() - self.rightMargin(), Ydelta))

            if Xdelta < 0:
                self.update(QRect(self.width() - self.rightMargin() + Xdelta, self.topMargin(), Xdelta, self.height() - self.topMargin() - self.bottomMargin()))
            if Xdelta > 0:
                self.update(QRect(self.leftMargin(), self.topMargin(), Xdelta, self.height() - self.topMargin() - self.bottomMargin()))

            self.scroll(Xdelta, Ydelta)

        event.accept()

    def resizeEvent(self, event):
        self._updateReason = "resizeEvent"
        delY = self.height() - self.prevH
        delX = self.width() - self.prevW

        self.prevH = self.height()
        self.prevW = self.width()

        self._maxScrollX -= delX
        self._maxScrollY -= delY

        if self._scrollX > self._maxScrollX: self._scrollX = self._maxScrollX
        if self._scrollX < 0: self._scrollX = 0
        if self._scrollY > self._maxScrollY: self._scrollY = self._maxScrollY
        if self._scrollY < 0: self._scrollY = 0
        self.update()
        super().resizeEvent(event)

    def focusInEvent(self, event):
        self.update()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self.update()
        super().focusOutEvent(event)

    def debug(self, startRow = None, stopRow = None):
        text = ""
        cursRow = self.textCursor().absoluteCoord().row()
        cursCol = self.textCursor().Coord().col()
        ancRow = self.textCursor().anchor().absoluteCoord().row()
        ancCol = self.textCursor().anchor().col()
        if startRow is None:
            startRow = 0
        if stopRow is None:
            stopRow = self.document().totalBlocks()
        nRows = stopRow - startRow
        blocks = self.document().blocks()[startRow:stopRow]

        if ancRow == cursRow and ancCol == cursCol:
            drawAnch = False
        else:
            drawAnch = True
        if drawAnch:
            for i, block in enumerate(blocks):
                if i + startRow == cursRow or i + startRow == ancRow:
                    if cursRow == ancRow:
                        if cursCol < ancCol:
                            text += (block.text()[:cursCol] + '|' + block.text()[cursCol:ancCol] + '┊' + block.text()[ancCol:])
                        else:
                            text += (block.text()[:ancCol] + '|' + block.text()[ancCol:cursCol] + '┊' + block.text()[cursCol:])
                    elif i + startRow == cursRow:
                        text += (block.text()[:cursCol] + '|' + block.text()[cursCol:])
                    elif i + startRow == ancRow:
                        text += (block.text()[:ancCol] + '┊' + block.text()[ancCol:])
                else:
                    text += block.text()
                if i < nRows - 1:
                    text += '\n'
        else:
            for i, block in enumerate(self.document().blocks()):
                if i + startRow == cursRow:
                    text += (block.text()[:cursCol] + '|' + block.text()[cursCol:])
                else:
                    text += block.text()
                if i + startRow < nRows - 1:
                    text += '\n'
        print(text)


class command:
    def undo(self, document : textDocument):
        raise NotImplementedError

    def redo(self, document : textDocument):
        raise NotImplementedError


class insertText(command):
    def __init__(self, editor : textEdit, document : textDocument, absPosition : tuple, text : str):
        super().__init__()
        self.editor   = editor
        self.document = document
        self.position = absPosition
        self.text     = text

    def undo(self):
        nDel = len(self.text)
        visRow = self.document.absoluteToVisible(self.position[0])
        visCol = self.position[1]
        visPosition = textPosition(row = visRow, col = visCol)
        self.editor.textCursor().moveTo(visRow = visRow, col = visCol)
        for _ in range(nDel):
            self.editor.deleteRight(position = visPosition)

    def redo(self):
        absPosition = textPosition(row = self.position[0], col = self.position[1])
        self.editor.pasteText(text = self.text, absPosition = absPosition)


class deleteText(command):
    def __init__(self, editor : textEdit, document : textDocument, absPosition : tuple, text : str, selection = False):
        super().__init__()
        self.editor   = editor
        self.document = document
        self.position = absPosition
        self.text     = text
        self.selection = selection

    def undo(self):
        absPosition = textPosition(row = self.position[0], col = self.position[1])
        # print("pasted text =", repr(self.text))
        self.editor.pasteText(text = self.text, absPosition = absPosition, Anchor = self.selection, debug = True)

    def redo(self):
        nDel = len(self.text)
        visRow = self.document.absoluteToVisible(self.position[0])
        visCol = self.position[1]
        visPosition = textPosition(row = visRow, col = visCol)
        self.editor.textCursor().moveTo(visRow = visRow, col = visCol, sync = False)
        for _ in range(nDel):
            self.editor.deleteRight()


class cutText(command):
    def __init__(self, editor : textEdit, document : textDocument, absPosition : tuple, text : str):
        super().__init__()
        self.editor   = editor
        self.document = document
        self.position = absPosition
        self.text     = text
        self.config()

    def undo(self):
        absPosition = textPosition(row = self.position[0], col = self.position[1])
        self.editor.pasteText(text = self.text, absPosition = absPosition)
        cursor = self.editor.textCursor()
        cursor.moveTo(visRow = self.start_Vis_Row, col = self.position[1])
        cursor.moveTo(visRow = self.end_Vis_Row, col = self.endCol, Anchor = True)

    def redo(self):
        cursor = self.editor.textCursor()
        cursor.moveTo(visRow = self.start_Vis_Row, col = self.position[1])
        cursor.moveTo(visRow = self.end_Vis_Row, col = self.endCol, Anchor = True)
        # self.editor.copySelection()
        self.editor.deleteSelection()

    def config(self):
        self.start_Vis_Row = self.document.absoluteToVisible(self.position[0])
        visCol = self.position[1]

        nRows = self.text.count('\n')
        if nRows > 0:
            visCol = 0
        lastNewlineIdx = self.text.rfind('\n')
        if lastNewlineIdx == -1:
            nCols = len(self.text)
        else:
            nCols = len(self.text) - 1 - lastNewlineIdx
        self.end_Vis_Row = self.start_Vis_Row + nRows
        self.endCol = visCol + nCols


class pasteText(command):
    def __init__(self, editor : textEdit, document : textDocument, absPosition : tuple, text : str):
        super().__init__()
        self.editor   = editor
        self.document = document
        self.position = absPosition
        self.text     = text
        self.config()

    def undo(self):
        cursor = self.editor.textCursor()
        cursor.moveTo(visRow = self.start_Vis_Row, col = self.position[1])
        cursor.moveTo(visRow = self.end_Vis_Row, col = self.endCol, Anchor = True)
        # self.editor.copySelection()
        self.editor.deleteSelection()

    def redo(self):
        absPosition = textPosition(row = self.position[0], col = self.position[1])
        self.editor.pasteText(text = self.text, absPosition = absPosition)
        cursor = self.editor.textCursor()
        cursor.moveTo(visRow = self.start_Vis_Row, col = self.position[1])
        cursor.moveTo(visRow = self.end_Vis_Row, col = self.endCol, Anchor = True)

    def config(self):
        self.start_Vis_Row = self.document.absoluteToVisible(self.position[0])
        visCol = self.position[1]

        nRows = self.text.count('\n')
        if nRows > 0:
            visCol = 0
        lastNewlineIdx = self.text.rfind('\n')
        if lastNewlineIdx == -1:
            nCols = len(self.text)
        else:
            nCols = len(self.text) - 1 - lastNewlineIdx
        self.end_Vis_Row = self.start_Vis_Row + nRows
        self.endCol = visCol + nCols


class newLine(command):
    def __init__(self, editor : textEdit, document : textDocument, absPosition : tuple):
        super().__init__()
        self.editor   = editor
        self.document = document
        self.absRow   = absPosition[0]
        self.visRow   = self.document.absoluteToVisible(self.absRow)
        self.col      = absPosition[1]

    def undo(self):
        self.editor.textCursor().navUp()
        self.editor.textCursor().navBlockEnd()
        block = self.document.findBlockByNumber(self.absRow)
        prevBlock = self.document.findBlockByNumber(self.absRow - 1)
        prevBlock.setText(prevBlock.text() + block.text())
        del self.document.blocks()[self.absRow]
        del self.document.visibleBlocks()[self.visRow]
        self.document.reEnumerate()

    def redo(self):
        prevBlock = self.document.findBlockByNumber(self.absRow - 1)
        block = textBlock(doc = self.document)
        block.setText(prevBlock.text()[self.col:])
        prevBlock.setText(prevBlock.text()[:self.col])
        self.document.blocks().insert(self.absRow, block)
        self.document.visibleBlocks().insert(self.visRow, block)
        self.editor.textCursor().moveTo(visRow = self.visRow, col = 0)
        print("visRow =", self.visRow, "position =", self.editor.textCursor().visibleCoord().row())
        self.document.reEnumerate()


class deleteLine(command):
    def __init__(self, editor : textEdit, document : textDocument, absRow):
        super().__init__()
        self.editor   = editor
        self.document = document
        self.absRow   = absRow
        self.visRow   = self.document.absoluteToVisible(self.absRow)
        self.col      = self.document.findBlockByNumber(absRow - 1).totalCharacters()

    def undo(self):
        prevBlock = self.document.findBlockByNumber(self.absRow - 1)
        block = textBlock(self.document)
        block.setText(prevBlock.text()[self.col:])
        prevBlock.setText(prevBlock.text()[:self.col])
        self.document.blocks().insert(self.absRow, block)
        self.document.visibleBlocks().insert(self.visRow, block)
        self.editor.textCursor().moveTo(visRow = self.visRow, col = 0)
        self.document.reEnumerate()

    def redo(self):
        self.editor.textCursor().navUp()
        self.editor.textCursor().navBlockEnd()
        block = self.document.findBlockByNumber(self.absRow)
        prevBlock = self.document.findBlockByNumber(self.absRow - 1)
        prevBlock.setText(prevBlock.text() + block.text())
        del self.document.blocks()[self.absRow]
        del self.document.visibleBlocks()[self.visRow]
        self.document.reEnumerate()


class UndoRedoManager:
    def __init__(self):
        self.undoStack : list[list[command]] = []
        self.redoStack : list[list[command]] = []

    def undo(self):
        if not self.undoStack:
            return

        commandGroup = self.undoStack.pop()
        idx = len(commandGroup) - 1
        while idx >= 0:
            command = commandGroup[idx]
            command.undo()
            idx -= 1
        self.redoStack.append(commandGroup)

    def redo(self):
        if not self.redoStack:
            return

        commandGroup = self.redoStack.pop()
        for command in commandGroup:
            command.redo()
        self.undoStack.append(commandGroup)


class textDocument:

    def __init__(self):
        self._blocks   : list[textBlock] = [textBlock(self, 0)]
        self._visible  : list[textBlock] = [block for block in self._blocks]
        self._foldHead : list[textBlock] = []
        self.lineLog   : list[int]       = [0]
        self.longLine  : list[int]       = [0]

    def blocks(self): return self._blocks
    def totalBlocks(self): return len(self.blocks())

    def findBlockByNumber(self, blockNumber) -> textBlock | None:
        if blockNumber < len(self._blocks):
            return self._blocks[blockNumber]
        return None

    def findBlockByVisibleNumber(self, visibleIndex) -> textBlock | None:
        if visibleIndex < len(self._visible):
            return self._visible[visibleIndex]
        return None

    def findBlock(self, textCursor : textPosition):
        blockNo = textCursor.col()
        if blockNo < len(self.document):
            return self._blocks[blockNo]
        return None

    def visibleBlocks(self): return self._visible
    def totalVisibleBlocks(self): return len(self._visible)

    def reEnumerate(self):
        i = 0
        for block in self._blocks:
            block._blockNumber = i
            i += 1

    def removeBlocks(self, blockList : list[int], enumerate = True):
        remove_indices = set(blockList)

        new_blocks = []
        removed_blocks = set()

        for i, block in enumerate(self.blocks()):
            if i in remove_indices:
                removed_blocks.add(block)
            else:
                new_blocks.append(block)

        self._blocks = new_blocks
        self._visible = [b for b in self._visible if b not in removed_blocks]
        if enumerate: self.reEnumerate()

    def insertBlock(self, absIndex = None, visibleIndex = None, enumerate = True):
        if (absIndex is not None) and (visibleIndex is None):
            visibleIndex = self.absoluteToVisible(absIndex)
        elif (visibleIndex is not None) and (absIndex is None):
            absIndex = self.visibleToAbsolute(visibleBlock = visibleIndex)
        newBlock = textBlock(doc = self, blockNumber = absIndex)
        self._blocks.insert(absIndex, newBlock)
        self._visible.insert(visibleIndex, newBlock)
        if enumerate: self.reEnumerate()

    def absoluteToVisible(self, absoluteBlock : int | textBlock):
        if isinstance(absoluteBlock, textBlock):
            absoluteBlock = absoluteBlock.blockNumber()
        visibleIdx = absoluteBlock

        idx = 0
        nHeads = len(self._foldHead)

        if idx >= nHeads:
            return visibleIdx

        head = self._foldHead[idx]
        preHead = head
        slaveLast = head.slave

        while True:
            head = self._foldHead[idx]
            if head.slave < slaveLast:
                idx += 1
                if idx >= nHeads:
                    return visibleIdx
                continue
            elif head.slave == slaveLast and head.blockNumber() > preHead:
                idx += 1
                if idx >= nHeads:
                    return visibleIdx
                continue
            else:
                if head.blockNumber() >= absoluteBlock:
                    return visibleIdx
                slaveLast = head.slave
                if slaveLast < absoluteBlock:
                    visibleIdx -= (slaveLast - head.blockNumber())
                else:
                    visibleIdx -= (absoluteBlock - head.blockNumber())
                preHead = head
                idx += 1
                if idx >= nHeads:
                    return visibleIdx

    def visibleToAbsolute(self, visibleBlock : int | textBlock):
        if hasattr(visibleBlock, 'textBlock'):
            return visibleBlock.blockNumber()
        else:
            visibleBlock = self.visibleBlocks()[visibleBlock]
            return visibleBlock.blockNumber()


class textBlock:

    def __init__(self, doc : textDocument, blockNumber = 0):
        self.Chars : list[textCell] = []
        self._string : str = ''
        self.document = doc
        self._blockNumber = blockNumber
        self.head = False
        self.slave = None

    def isValid(self):
        if self in self.document:
            return True
        return False

    def blockNumber(self): return self._blockNumber
    def totalCharacters(self): return len(self._string)
    def isHead(self): return self.head
    def setText(self, text : str): self._string = text
    def text(self): return self._string

    def next(self):
        if self._blockNumber < len(self.document.blocks()) - 1:
            return self.document.blocks()[self._blockNumber + 1]
        return None

    def prev(self):
        if self._blockNumber > 0:
            return self.document.blocks()[self._blockNumber - 1]
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
    def __init__(self, ch = ''):
        self.char :str = ch


class TextCursor:

    def __init__(self, editor : textEdit, doc : textDocument, row = 0, col = 0):
        self._doc = doc
        self._edit = editor
        self._coord = pairedPosition(doc = self._doc)
        self._anchor = pairedPosition(doc = self._doc)
        self._storedCoord = pairedPosition(doc = self._doc)
        self._selection = textSelection(doc = self._doc)

    def editor(self):return self._edit
    def cellW(self):return self._edit.cellW
    def cellH(self):return self._edit.cellH

    def Capture(self) -> QRect:
        cursX = self.visibleCoord().col() * self.cellW() + self._edit.leftMargin() - self.editor()._scrollX
        cursY = self.visibleCoord().row() * self.cellH() + self._edit.topMargin() - self._edit._scrollY
        prevRect = QRect(int(cursX), int(cursY) - 1, int(self.cellW()), int(self.cellH()) + 1)

        return prevRect 

    def document(self) -> textDocument: return self._doc
    def block(self) -> textBlock:return self._doc.findBlockByVisibleNumber(self.visibleCoord().row())

    def Coord(self)        : return self._coord
    def visibleCoord(self) : return self._coord.visibleCoord()
    def absoluteCoord(self): return self._coord.absoluteCoord()
    def anchor(self)       : return self._anchor
    def storedCoord(self)  : return self._storedCoord

    def set_Stored_Visible_Coord(self, row, col):
        self.storedCoord().set_Visible_Row(row)
        self.storedCoord().setCol(col)

    def set_Stored_Absolute_Coord(self, row, col):
        self.storedCoord().set_Absolute_Row(row)
        self.storedCoord().setCol(col)

    def sync_Stored_Coord(self):
        self.storedCoord().set_Visible_Row(self.visibleCoord().row())
        self.storedCoord().setCol(self.visibleCoord().col())

    def scrollConfig(self, scroll = True):
        Rect = self.Capture()
        cursX = Rect.x()
        cursY = Rect.y()

        if not scroll:
            prev_x = self.editor()._scrollX
            prev_y = self.editor()._scrollY

        headroomXLeft = cursX - self.editor().leftMargin()
        headroomXRight = self.editor().width() - self.editor().rightMargin() - cursX
        headroomYUp = cursY - self.editor().topMargin()
        headroomYDown = self.editor().height() - self.editor().bottomMargin() - cursY

        if headroomXLeft < 2 * self.cellW():
            diff = 2 * self.cellW() - headroomXLeft
            self.editor()._scrollX -= diff
            if self.editor()._scrollX < 0: self.editor()._scrollX = 0
        if headroomXRight < 2 * self.cellW():
            diff = 2 * self.cellW() - headroomXRight
            self.editor()._scrollX += diff

        if headroomYUp < 2 * self.cellH():
            diff = 2 * self.cellH() - headroomYUp
            self.editor()._scrollY -= diff
            if self.editor()._scrollY < 0: self.editor()._scrollY = 0
        if headroomYDown < 2 * self.cellH():
            diff = 2 * self.cellH() - headroomYDown
            self.editor()._scrollY += diff

        if self.editor()._scrollX > self.editor()._maxScrollX:
            self.editor()._maxScrollX = self.editor()._scrollX
        if self.editor()._scrollY > self.editor()._maxScrollY:
            self.editor()._maxScrollY = self.editor()._scrollY

        if not scroll:
            self.editor()._scrollX = prev_x
            self.editor()._scrollY = prev_y

    def navLeft(self, Anchor = False):
        if self.visibleCoord().col() > 0:
            row = self.visibleCoord().row()
            col = self.visibleCoord().col() - 1
            self._coord.setCol(col)
            self.sync_Stored_Coord()
            self.AnchorConfig(row, col, Anchor)
        else:
            if self.visibleCoord().row() > 0:
                row = self.visibleCoord().row() - 1
                col = self._doc.findBlockByVisibleNumber(row).totalCharacters()
                self._coord.set_Visible_Row(row)
                self._coord.setCol(col)
                self.sync_Stored_Coord()
                self.AnchorConfig(row, col, Anchor)

        self.scrollConfig()
        self._edit.update()
        self._edit.resetCursor()

    def navRight(self, Anchor = False):
        if self.visibleCoord().col() < self._doc.findBlockByVisibleNumber(self.visibleCoord().row()).totalCharacters():
            row = self.visibleCoord().row()
            col = self.visibleCoord().col() + 1
            self._coord.setCol(col)
            self.sync_Stored_Coord()
            self.AnchorConfig(row, col, Anchor)
        else:
            if self.visibleCoord().row() < self._doc.totalBlocks() - 1:
                row = self.visibleCoord().row() + 1
                col = 0
                self._coord.set_Visible_Row(row)
                self._coord.setCol(col)
                self.sync_Stored_Coord()
                self.AnchorConfig(row, col, Anchor)

        self.scrollConfig()
        self._edit.update()
        self._edit.resetCursor()

    def navUp(self, Anchor = False):
        if self.visibleCoord().row() > 0:
            row = self.visibleCoord().row() - 1
            self._coord.set_Visible_Row(row)
            strLength = self._doc.findBlockByVisibleNumber(self.visibleCoord().row()).totalCharacters()
            col = min(strLength, self.storedCoord().visibleCoord().col())
            self._coord.setCol(col)
        else:
            row = self.visibleCoord().row()
            col = 0
            self._coord.setCol(0)
            self.sync_Stored_Coord()

        self.AnchorConfig(row, col, Anchor)

        self.scrollConfig()
        self._edit.update()
        self._edit.resetCursor()

    def navDn(self, Anchor = False):
        if self.visibleCoord().row() < self._doc.totalVisibleBlocks() - 1:
            row = self.visibleCoord().row() + 1
            self._coord.set_Visible_Row(row)
            strLength = self._doc.findBlockByVisibleNumber(self.visibleCoord().row()).totalCharacters()
            col = min(strLength, self.storedCoord().visibleCoord().col())
            self._coord.setCol(col)
        else:
            row = self.visibleCoord().row()
            col = self._doc.findBlockByNumber(self._doc.totalVisibleBlocks() - 1).totalCharacters()
            self._coord.setCol(col)
            self.sync_Stored_Coord()

        self.AnchorConfig(row, col, Anchor)

        self.scrollConfig()
        self._edit.update()
        self._edit.resetCursor()

    def moveTo(self, visRow, col, sync = True, scroll = True, Anchor = False):
        lastBlock = self._doc.blocks()[-1]
        ipRow = visRow
        visRow = min(visRow, lastBlock.blockNumber())
        visRow = max(0, visRow)
        totalCar = self._doc.blocks()[visRow].totalCharacters()
        if visRow == lastBlock.blockNumber() and ipRow != visRow:
            col = totalCar
        else:
            col = min(col, totalCar)
            col = max(0, col)

        self._coord.set_Visible_Row(visRow)
        self._coord.setCol(col)

        if sync: self.sync_Stored_Coord()
        self.scrollConfig(scroll)
        self.AnchorConfig(visRow, col, Anchor)
        self.editor().resetCursor()
        self.editor().update()

    def moveToCol(self, col, scroll = True, Anchor = False):
        maxCol = self.block().totalCharacters()
        if col > maxCol:
            return
        self.Coord().setCol(col)

        self.sync_Stored_Coord()
        self.scrollConfig(scroll)
        self.AnchorConfig(visCol = col, Anchor = Anchor)

    def navToStart(self, scroll = True, Anchor = False):
        self.Coord().set_Absolute_Coord(row = 0, col = 0)

        self.sync_Stored_Coord()
        self.scrollConfig(scroll)
        self.AnchorConfig(visRow = 0, visCol = 0, Anchor = Anchor)
        self.editor().update()
        self.editor().resetCursor()

    def navToEnd(self, scroll = True, Anchor = False):
        row = len(self.document().blocks()) - 1
        col = self.document().findBlockByNumber(row).totalCharacters()
        self.Coord().set_Absolute_Coord(row = row, col = col)

        self.sync_Stored_Coord()
        self.scrollConfig(scroll)
        self.AnchorConfig(visRow = row, visCol = col, Anchor = Anchor)
        self.editor().update()
        self.editor().resetCursor()

    def navBlockStart(self, Anchor = False):
        self.Coord().setCol(0)

        self.sync_Stored_Coord()
        self.AnchorConfig(visRow = self.visibleCoord().row(), visCol = 0, Anchor = Anchor)
        self.scrollConfig()
        self._edit.update()
        self._edit.resetCursor()

    def navBlockEnd(self, Anchor = False):
        row = self.visibleCoord().row()
        block = self.document().visibleBlocks()[row]
        col = block.totalCharacters()
        self.Coord().setCol(col)
        self.sync_Stored_Coord()
        self.AnchorConfig(visRow = row, visCol = col, Anchor = Anchor)

        self.scrollConfig()
        self._edit.update()
        self._edit.resetCursor()

    def AnchorConfig(self, visRow = None, visCol = None, Anchor=False):
        if not Anchor:
            if visRow is not None:
                self.anchor().set_Visible_Row(visRow)
                self.selectionStart().set_Visible_Row(visRow)
                self.selectionStop().set_Visible_Row(visRow)

            if visCol is not None:
                self.anchor().setCol(visCol)
                self.selectionStart().setCol(visCol)
                self.selectionStop().setCol(visCol)
            return

        start = min(
            (self.anchor().visibleCoord().row(), self.anchor().visibleCoord().col()),
            (self.visibleCoord().row(), self.visibleCoord().col())
        )
        stop  = max(
            (self.anchor().visibleCoord().row(), self.anchor().visibleCoord().col()),
            (self.visibleCoord().row(), self.visibleCoord().col())
        )

        self.selectionStop().set_Visible_Row(stop[0])
        self.selectionStop().setCol(stop[1])

        self.selectionStart().set_Visible_Row(start[0])
        self.selectionStart().setCol(start[1])

    def anchorReset(self):
        self.anchor().set_Visible_Row(self.visibleCoord().row())
        self.anchor().setCol(self.Coord().col())

    def isAtBlockEnd(self):
        col = self.Coord().col()
        block = self.block()
        blockLen = block.totalCharacters()
        if col == blockLen:
            return True
        return False

    def isAtBlockStart(self):
        col = self.Coord().col()
        if col == 0:
            return True
        return False

    def selection(self)      -> textSelection : return self._selection
    def hasSelection(self)   -> bool          : return self._selection.hasSelection()
    def selectionStart(self) -> pairedPosition: return self._selection.selectionStart()
    def selectionStop(self)  -> pairedPosition: return self._selection.selectionStop()

    def selectedText(self) -> str | None:
        if self.hasSelection():
            startRow = self.selectionStart().absoluteCoord().row()
            stopRow  = self.selectionStop().absoluteCoord().row()
            startCol = self.selectionStart().absoluteCoord().col()
            stopCol  = self.selectionStop().absoluteCoord().col()
            string = ""
            if startRow == stopRow:
                block = self.document().findBlockByNumber(startRow)
                string += block.text()[startCol:stopCol]
            else:
                block = self.document().findBlockByNumber(startRow)
                while True:
                    if not block:
                        break
                    if block.blockNumber() == startRow:
                        string += block.text()[startCol:]
                        string += '\n'
                    elif block.blockNumber() == stopRow:
                        string += block.text()[:stopCol]
                        break
                    else:
                        string += block.text()
                        string += '\n'
                    block = block.next()
            return string
        else:
            return None


class dummyCursor(TextCursor):
    def __init__(self, editor, doc, cursType : dummyCursorType = dummyCursorType.UNASSIGNED):
        super().__init__(editor, doc)
        self.type = cursType
        self.cursVisible = False
        self.selectionVisible = False


class textSelection:

    def __init__(self, doc : textDocument):
        self.start = pairedPosition(doc = doc)
        self.stop  = pairedPosition(doc = doc)

    def reset(self, reverse = False):
        if reverse:
            self.start.set_Visible_Row(self.stop.visibleCoord().row())
            self.start.setCol(self.stop.visibleCoord().col())
            return
        self.stop.set_Visible_Row(self.start.visibleCoord().row())
        self.stop.setCol(self.start.visibleCoord().col())

    def selectionStart(self) -> pairedPosition: return self.start
    def selectionStop(self) -> pairedPosition: return self.stop

    def hasSelection(self) -> bool:
        if (self.selectionStart().visibleCoord().row() == self.selectionStop().visibleCoord().row() and
            self.selectionStart().absoluteCoord().row() == self.selectionStop().absoluteCoord().row() and
            self.selectionStart().visibleCoord().col() == self.selectionStop().visibleCoord().col()):
            return False
        return True


class pairedPosition:

    def __init__(self, doc : textDocument):
        self._visible = textPosition()
        self._abslute = textPosition()
        self._doc     = doc

    def document(self)      -> textDocument: return self._doc
    def visibleCoord(self)  -> textPosition: return self._visible
    def absoluteCoord(self) -> textPosition: return self._abslute
    def col(self): return self._abslute.col()

    def set_Visible_Row(self, row):
        self.visibleCoord().setRow(row)
        absRow = self.visibleToAbsolute(row)
        self.absoluteCoord().setRow(absRow)

    def set_Absolute_Row(self, row):
        self.absoluteCoord().setRow(row)
        vis_row = self.absoluteToVisible(row)
        if not vis_row:
            self.visibleCoord().setRow(vis_row)
            self.visibleCoord().setCol(None)
            return
        self.visibleCoord().setRow(vis_row)

    def setCol(self, col):
        self.visibleCoord().setCol(col)
        self.absoluteCoord().setCol(col)

    def set_Visible_Coord(self, row, col):
        self.set_Visible_Row(row)
        self.setCol(col)

    def set_Absolute_Coord(self, row, col):
        self.set_Absolute_Row(row)
        self.setCol(col)

    def absoluteToVisible(self, absoluteBlock : int | textBlock):
        if isinstance(absoluteBlock, textBlock):
            absoluteBlock = absoluteBlock.blockNumber()
        visibleIdx = absoluteBlock

        idx = 0
        nHeads = len(self.document()._foldHead)

        if idx >= nHeads:
            return visibleIdx

        head = self.document()._foldHead[idx]
        preHead = head
        slaveLast = head.slave

        while True:
            head = self.document()._foldHead[idx]
            if head.slave < slaveLast:
                idx += 1
                if idx >= nHeads:
                    return visibleIdx
                continue
            elif head.slave == slaveLast and head.blockNumber() > preHead:
                idx += 1
                if idx >= nHeads:
                    return visibleIdx
                continue
            else:
                if head.blockNumber() >= absoluteBlock:
                    return visibleIdx
                slaveLast = head.slave
                if slaveLast < absoluteBlock:
                    visibleIdx -= (slaveLast - head.blockNumber())
                else:
                    visibleIdx -= (absoluteBlock - head.blockNumber())
                preHead = head
                idx += 1
                if idx >= nHeads:
                    return visibleIdx

    def visibleToAbsolute(self, visibleBlock : int | textBlock):
        if hasattr(visibleBlock, 'textBlock'):
            return visibleBlock.blockNumber()
        else:
            visibleBlock = self._doc.visibleBlocks()[visibleBlock]
            return visibleBlock.blockNumber()


class textPosition:

    def Coord(self) -> tuple: return (self.row(), self.col())
    def row(self): return self._y
    def col(self): return self._x

    def setRow(self, row, refreshStored = False):
        self._y = row
        if refreshStored:
            self.storeRow(row)

    def setCol(self, col, refreshStored = False):
        self._x = col
        if refreshStored:
            self.storeCol(col)

    def __init__(self, row = 0, col = 0):
        self._x = col
        self._y = row


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



#### SEE IF YOU CAN UPDATE THE RESET CURSOR AND CURSOR NAVIGATIONS WITHOUT COMPUTING ALL THE TEXTS IN THE PAINT EVENT