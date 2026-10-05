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


def dotProduct(v1 : tuple, v2 : tuple) -> float:
    arr1 = np.array(v1)
    arr2 = np.array(v2)

    return arr1 @ arr2


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


class textEdit(QWidget):

    def __init__(self, parent):
        super().__init__(parent)
        self._document = textDocument()
        self._Cursor = TextCursor(editor = self, doc = self.document(), row = 0, col = 0)

        self.Font = QFont()
        self.Font.setFamilies(["Consolas", "Courier New"])
        self.fontSize = 15
        self.Font.setPixelSize(self.fontSize)
        self.fm = QFontMetricsF(self.Font)

        self.cellW  = self.fm.horizontalAdvance("W")
        self.cellH  = self.fm.height()
        self.Ascent = self.fm.ascent()

        self._scrollY = 0
        self._scrollX = 0
        self._maxScrollX = 0
        self._maxScrollY = 0
        self.scrollTimer = QTimer()
        self.scrollActive = False
        self.scrollTimer.setSingleShot(True)
        self.scrollTimer.timeout.connect(lambda: setattr(self, "scrollActive", False))
        self.scrollTimer.timeout.connect(self.update)

        self.toggle = False
        self.cursorVisible = True
        self.cursWidth = 2
        self.cursDelay = 500
        self.cursCount = 0
        self.cursTimer = QTimer(self)
        self.cursTimer.start(self.cursDelay)
        self.cursTimer.timeout.connect(self.toggleCursor)

        self.controlModifier = False
        self.shiftModifier   = False

        self._updateReason = None
        self.showReason = False
        self.paintCount = 0

        self.mousePressed = False
        self.mouseMoved = False

        self.setMargins()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def paintEvent(self, event : QPaintEvent):
        self.paintCount += 1
        painter = QPainter(self)
        painter.setFont(self.Font)
        painter.fillRect(event.rect(), QColor(18, 19, 20))
        # if event.rect() != self.rect():
        #     painter.drawRect(event.rect())
        if self.showReason:
            print("Count =", self.paintCount,"reason = ", self._updateReason, "toggle =", self.toggle)
        self._updateReason = None

        start = self.firstVisibleBlock().blockNumber()
        stop  = self.lastVisibleBlock().blockNumber()
        row = start

        if not self.toggle:
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
                for col, cell in enumerate(block.Chars):
                    x = col * self.cellW + self.leftMargin() - self._scrollX
                    if x > self.width() - self.rightMargin():
                        break
                    painter.setPen(cell.color)
                    painter.setBrush(Qt.NoBrush)
                    painter.drawText(
                        x, y + self.Ascent,
                        cell.char
                    )

                    cellRect = QRectF(
                        x, y,
                        self.cellW, self.cellH
                    )
                row += 1

        else:
            if self.showReason:
                print("missed")

        if self.textCursor().hasSelection():
            aRow, aCol = self.textCursor().selectionStart().Coord()
            bRow, bCol = self.textCursor().selectionStop().Coord()

            selectionPath = QPainterPath()

            for row in range(aRow, bRow + 1):
                startCol = aCol if row == aRow else 0
                
                # Add + 1 to totalCharacters() to highlight the invisible newline character
                endCol = bCol if row == bRow else self.document().findBlockByNumber(row).totalCharacters() + 1

                x = startCol * self.cellW - self._scrollX
                y = row * self.cellH - self._scrollY
                width = (endCol - startCol) * self.cellW
                height = self.cellH + 0.1

                line_rect = QRectF(x, y, width, height)

                temp_path = QPainterPath()
                temp_path.addRect(line_rect)

                selectionPath = selectionPath.united(temp_path)
            
            # Smooth the path only ONCE after all rows are united
            roundedSelection = self.smoothPath(selectionPath, radius=6, painter=painter)

            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(72, 184, 232, 128))
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.drawPath(roundedSelection)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        if self.cursorVisible and self.hasFocus():
            cursorPen = QPen(QColor(200, 200, 200, 255), self.cursWidth)
            painter.setPen(cursorPen)
            x = self.textCursor().visibleCol() * self.cellW + self.leftMargin() - self._scrollX
            y = self.textCursor().visibleRow() * self.cellH + self.topMargin() - self._scrollY
            if x == 0: x = 1
            painter.drawLine(x, y + 1.2, x, y + self.cellH - 1.2)

        # row = self.textCursor().visibleRow()
        # col = self.textCursor().visibleCol()

        # ch0 = self.characterAt(row, col - 1)
        # ch1 = self.characterAt(row - 1, col)
        # ch2 = self.characterAt(row, col)
        # ch3 = self.characterAt(row + 1, col)
        # painter.setPen(QPen(QColor(200, 200, 200, 255), 1))
        # if ch0:
        #     x = (col - 1) * self.cellW + self.leftMargin() - self._scrollX
        #     y = row * self.cellH + self.topMargin() - self._scrollY
        #     # painter.drawText(x, y + self.Ascent, ch0)
        # if ch2:
        #     x = col * self.cellW + self.leftMargin() - self._scrollX
        #     y = row * self.cellH + self.topMargin() - self._scrollY
        #     # painter.drawText(x, y + self.Ascent, ch2)

        self.toggle = False

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
                    regions.append([])
                    continue
            elif p != start:
                regions[-1].append(p)

        # painter.fillRect(self.rect(), QColor(18, 19, 20))
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
                # painter.setPen(QPen(qColor, 5))
                # painter.drawPoint(p)

                a = None
                b = None

                if round(p0.x()) == round(p1.x()):
                    sgn = (p1.y() - p0.y())/abs(p1.y() - p0.y())
                    a = QPointF(p1.x(), p1.y() - sgn * r)
                elif round(p0.y()) == round(p1.y()):
                    sgn = (p1.x() - p0.x())/abs(p1.x() - p0.x())
                    a = QPointF(p1.x() - sgn * r, p1.y())

                if round(p2.x()) == round(p1.x()):
                    sgn = (p1.y() - p2.y())/abs(p1.y() - p2.y())
                    b = QPointF(p1.x(), p1.y() - sgn * r)
                elif round(p2.y()) == round(p1.y()):
                    sgn = (p1.x() - p2.x())/abs(p1.x() - p2.x())
                    b = QPointF(p1.x() - sgn * r, p1.y())

                if a and b:
                    if i == 0:
                        roundedPath.moveTo(a)
                        roundedPath.quadTo(p1, b)
                    else:
                        roundedPath.lineTo(a)
                        roundedPath.quadTo(p1, b)

        roundedPath.closeSubpath()
        return roundedPath

    def resetCursor(self):
        self.toggle = False
        self.cursorVisible = True
        cursX = self.textCursor().visibleCol() * self.cellW + self.leftMargin()
        cursY = self.textCursor().visibleRow() * self.cellH + self.topMargin() - self._scrollY
        Rect = QRect(int(cursX) - self.cellW, int(cursY) - 1, 2 * int(self.cellW), int(self.cellH) + 1)
        self.update(Rect)
        self.cursTimer.start(self.cursDelay)

    def toggleCursor(self):
        if self.hasFocus():
            self.toggle = True
            self.cursorVisible = not self.cursorVisible
            cursX = self.textCursor().visibleCol() * self.cellW + self.leftMargin() - self._scrollX
            cursY = self.textCursor().visibleRow() * self.cellH + self.topMargin() - self._scrollY
            if not self.scrollActive:
                self._updateReason = "toggle"
                self.update(QRect(int(cursX) - self.cellW, int(cursY) - 1, 2 * int(self.cellW), int(self.cellH) + 1))
            self.toggle = False

    def document(self):
        return self._document

    def textCursor(self):
        return self._Cursor

    def firstVisibleBlock(self):
        blockNo = int(self._scrollY / self.cellH)
        block = self.document().visibleBlocks()[blockNo]
        block._blockNumber = blockNo

        return block

    def lastVisibleBlock(self):
        blockNo = int((self._scrollY + (self.height() - self.topMargin() - self.bottomMargin())) / self.cellH)
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

    def newLine(self, lineNo=None):
        cursor = self.textCursor()
        doc = self.document()

        if lineNo is None:
            lineNo = cursor.visibleRow() + 1
            col = cursor.visibleCol()
        else:
            lineNo += 1
            col = cursor.visibleCol() if lineNo == cursor.visibleRow() + 1 else doc.findBlockByNumber(lineNo - 1).totalCharacters()

        prevBlock = doc.findBlockByNumber(lineNo - 1)

        block = textBlock(doc, blockNumber=lineNo)
        block.Chars = prevBlock.Chars[col:]
        del prevBlock.Chars[col:]

        doc.blocks().insert(lineNo, block)
        doc.visibleBlocks().insert(lineNo, block)

        self.textCursor().moveTo(lineNo, 0)
        self._maxScrollY += self.cellH
        self.update()

    def insert(self, ch):
        block = self.document().blocks()[self.textCursor().visibleRow()]
        block.Chars.insert(self.textCursor().visibleCol(), textCell(ch = ch))

        self.textCursor().navRight()

    def deleteLeft(self, position : textPosition | None = None):
        if not position:
            row = self.textCursor().visibleRow()
            col = self.textCursor().visibleCol()
        else:
            row = position.row()
            col = position.col()

        if col > 0:
            del self.document().findBlockByNumber(row).Chars[col - 1]
            self.textCursor().navLeft()
        elif row > 0:
            toAppend = self.document().findBlockByNumber(row).Chars[:]
            self.textCursor().navLeft()
            self.document().findBlockByNumber(row - 1).Chars.extend(toAppend)
            abs_row = self.textCursor().visibleToAbsolute(row)
            del self.document().visibleBlocks()[row]
            del self.document().blocks()[abs_row]
            self._maxScrollY -= self.cellH
            if self._maxScrollY < 0: self._maxScrollY = 0
        self.update()

    def keyPressEvent(self, event : QKeyEvent):
        if   event.key() == Qt.Key.Key_Left:
            self.textCursor().navLeft(Anchor = self.shiftModifier)

        elif event.key() == Qt.Key.Key_Right:
            self.textCursor().navRight(Anchor = self.shiftModifier)

        elif event.key() == Qt.Key.Key_Up:
            self.textCursor().navUp(Anchor = self.shiftModifier)

        elif event.key() == Qt.Key.Key_Down:
            self.textCursor().navDn(Anchor = self.shiftModifier)

        elif event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            self.newLine()

        elif event.key() == Qt.Key.Key_Backspace:
            self.deleteLeft()

        elif event.key() == Qt.Key.Key_Shift:
            self.shiftModifier = True

        elif event.key() in {Qt.Key.Key_Control, Qt.Key.Key_Meta}:
            self.controlModifier = True

        elif event.key() == Qt.Key.Key_Tab:
            for _ in range(4):
                self.insert(' ')

        elif self.controlModifier and event.key() == Qt.Key.Key_Equal:
            self.fontSize += 1
            self.Font.setPixelSize(self.fontSize)
            self.fm = QFontMetricsF(self.Font)

            self.cellW  = self.fm.horizontalAdvance("W")
            self.cellH  = self.fm.height()
            self.Ascent = self.fm.ascent()
            self.update()

        elif self.controlModifier and event.key() == Qt.Key.Key_Minus:
            self.fontSize -= 1
            self.Font.setPixelSize(self.fontSize)
            self.fm = QFontMetricsF(self.Font)

            self.cellW  = self.fm.horizontalAdvance("W")
            self.cellH  = self.fm.height()
            self.Ascent = self.fm.ascent()
            self.update()

        elif event.key() == Qt.Key.Key_CapsLock:
            pass

        else:
            text = event.text()
            self.insert(text)
            self.update()
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event : QKeyEvent):
        if   event.key() == Qt.Key.Key_Shift:
            self.shiftModifier = False
        elif event.key() in {Qt.Key.Key_Control, Qt.Key.Key_Meta}:
            self.controlModifier = False
        super().keyReleaseEvent(event)

    def mousePressEvent(self, event : QMouseEvent):
        self.mousePressed = True
        if event.button() == Qt.RightButton:
            self.showReason = True
        x = event.position().x() + self._scrollX
        y = event.position().y() + self._scrollY
        self.textCursor().moveTo(row = int(y / self.cellH), col = int(x / self.cellW + 1 / 2), scroll = False)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event : QMouseEvent):
        if self.mousePressed:
            self.mouseMoved = True
            x = event.position().x() + self._scrollX
            y = event.position().y() + self._scrollY
            self.textCursor().moveTo(row = int(y / self.cellH), col = int(x / self.cellW + 1 / 2), scroll = False, Anchor = True)
        event.accept()

    def mouseReleaseEvent(self, event : QMouseEvent):
        if self.textCursor().hasSelection() and not self.mouseMoved:
            self.textCursor().selection().reset()
        self.mousePressed = False
        self.mouseMoved = False
        event.accept()

    def enterEvent(self, event):
        self.setCursor(Qt.CursorShape.IBeamCursor)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().leaveEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        self._updateReason = "wheelEvent"
        self.scrollTimer.start(100)
        dx = event.angleDelta().x()
        dy = event.angleDelta().y()

        Xdelta = dx * self.cellH / 120
        Ydelta = dy * self.cellW / 120

        prevX = self._scrollX
        prevY = self._scrollY

        self._scrollX -= Xdelta
        self._scrollY -= Ydelta

        if self._scrollX < 0: self._scrollX = 0
        if self._scrollX > self._maxScrollX: self._scrollX = self._maxScrollX
        if self._scrollY < 0: self._scrollY = 0
        if self._scrollY > self._maxScrollY: self._scrollY = self._maxScrollY

        if prevX != self._scrollX or prevY != self._scrollY:
            self.update()
        super().wheelEvent(event)

    def resizeEvent(self, event):
        self._updateReason = "resizeEvent"
        self.update()
        super().resizeEvent(event)


class textDocument:

    def __init__(self):
        self._blocks   : list[textBlock] = [textBlock(self, 0)]
        self._visible  : list[textBlock] = [block for block in self._blocks]
        self._foldHead : list[textBlock] = []

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

    def reEnumerate(self):
        i = 0
        for block in self._blocks:
            block._blockNumber = i
            i += 1

    def removeBlocks(self, blockList : list[int]):
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

    def insertBlock(self, absIndex, visibleIndex):
        newBlock = textBlock(doc = self, blockNumber = absIndex)
        self._blocks.insert(absIndex, newBlock)
        self._visible.insert(visibleIndex, newBlock)


class textBlock:

    def __init__(self, doc : textDocument, blockNumber = 0):
        self.Chars : list[textCell] = []
        self.document = doc
        self._blockNumber = blockNumber
        self.head = False
        self.slave = None

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

    def __init__(self, editor : textEdit, doc : textDocument, row = 0, col = 0):
        self._doc = doc
        self._edit = editor
        self.visibleCoord = textPosition(row, col)
        self.absoluteCoord = textPosition(row, col)
        self._anchor = textPosition(row, col)
        self._storedVisibleCoord = textPosition(row, col)
        self._storedAbsoluteCoord = textPosition(row, col)
        self._selection = textSelection()

    def editor(self):
        return self._edit

    def cellW(self):
        return self._edit.cellW

    def cellH(self):
        return self._edit.cellH

    def Capture(self) -> QRect:
        cursX = self.visibleCol() * self.cellW() + self._edit.leftMargin() - self.editor()._scrollX
        cursY = self.visibleRow() * self.cellH() + self._edit.topMargin() - self._edit._scrollY
        prevRect = QRect(int(cursX), int(cursY) - 1, int(self.cellW()), int(self.cellH()) + 1)

        return prevRect

    def block(self) -> textBlock:
        return self._doc.blocks()[self.visibleCoord.row()]

    def anchor(self):
        return self._anchor

    def visibleCoord(self) -> tuple:
        return(self.visibleRow(), self.visibleCol())

    def visibleRow(self):
        return self.visibleCoord.row()

    def visibleCol(self):
        return self.visibleCoord.col()

    def AbsoluteCoord(self) -> tuple:
        return(self.absoluteRow(), self.absoluteCol())

    def absoluteRow(self):
        return self.absoluteCoord.row()

    def absoluteCol(self):
        return self.absoluteCoord.col()

    def set_Visible_Row(self, row):
        self.visibleCoord.setRow(row)
        abs_row = self.visibleToAbsolute(row)
        self.absoluteCoord.setRow(abs_row)

    def set_Visible_Col(self, col):
        self.visibleCoord.setCol(col)
        self.absoluteCoord.setCol(col)

    def set_Absolute_Row(self, row):
        self.visibleCoord.setRow(row)
        vis_row = self.absoluteToVisible(row)
        if not vis_row:
            self.visibleCoord.setRow(vis_row)
            self.visibleCoord.setCol(None)
            return
        self.visibleCoord.setRow(vis_row)

    def set_Absolute_Col(self, col):
        self.visibleCoord.setCol(col)
        self.absoluteCoord.setCol(col)

    def set_visible_Coord(self, row, col):
        self.visibleCoord.setRow(row)
        self.visibleCoord.setCol(col)

        abs_row = self.visibleToAbsolute(row)

        self.absoluteCoord.setRow(abs_row)
        self.absoluteCoord.setCol(col)

    def set_absolute_Coord(self, row, col):
        self.absoluteCoord.setRow(row)
        self.absoluteCoord.setCol(row)

        vis_row = self.absoluteToVisible(row)

        self.visibleCoord.setRow(row)
        if not vis_row:
            self.visibleCoord.setCol(None)
            return
        self.visibleCoord.setCol(col)

    def stored_Visible_Coord(self):
        return self._storedVisibleCoord

    def stored_Absolute_Coord(self):
        return self._storedAbsoluteCoord

    def set_Stored_Visible_Coord(self, row, col):
        self._storedVisibleCoord.setRow(row)
        self._storedVisibleCoord.setCol(col)

        abs_row = self.visibleToAbsolute(row)

        self._storedAbsoluteCoord.setRow(abs_row)
        self._storedAbsoluteCoord.setCol(col)

    def set_Stored_Absolute_Coord(self, row, col):
        self._storedAbsoluteCoord.setRow(row)
        self._storedAbsoluteCoord.setCol(col)

        vis_row = self.absoluteToVisible(row)

        self._storedAbsoluteCoord.setRow(vis_row)
        if not vis_row:
            self._storedAbsoluteCoord.setCol(None)
        self._storedAbsoluteCoord.setCol(col)

    def sync_Stored_Coord(self):
        self._storedAbsoluteCoord.setRow(self.absoluteCoord.row())
        self._storedAbsoluteCoord.setCol(self.absoluteCoord.col())

        self._storedVisibleCoord.setRow(self.visibleCoord.row())
        self._storedVisibleCoord.setCol(self.visibleCoord.col())

    def absoluteToVisible(self, block : int | textBlock):
        if hasattr(block, int):
            block = self._doc.findBlockByNumber(block)

        if block not in self._doc._visible:
            return None

        for i, b in enumerate(self._doc._visible):
            if b == block:
                return i

    def visibleToAbsolute(self, block : int | textBlock):
        if hasattr(block, 'textBlock'):
            return block.blockNumber()
        else:
            block = self._doc.visibleBlocks()[block]
            return block.blockNumber()

    def scrollConfig(self):
        Rect = self.Capture()
        cursX = Rect.x()
        cursY = Rect.y()

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

    def navLeft(self, Anchor = False):
        if self.visibleCol() > 0:
            row = self.visibleRow()
            col = self.visibleCol() - 1
            self.set_Visible_Col(col)
            self.sync_Stored_Coord()
            self.AnchorConfig(row, col, Anchor)
        else:
            if self.visibleRow() > 0:
                row = self.visibleRow() - 1
                col = len(self._doc.findBlockByNumber(row).Chars)
                self.set_Visible_Row(row)
                self.set_Visible_Col(col)
                self.sync_Stored_Coord()
                self.AnchorConfig(row, col, Anchor)

        self.scrollConfig()
        self._edit.update()
        self._edit.resetCursor()

    def navRight(self, Anchor = False):
        if self.visibleCol() < self._doc.findBlockByNumber(self.visibleRow()).totalCharacters():
            row = self.visibleRow()
            col = self.visibleCol() + 1
            self.set_Visible_Col(col)
            self.sync_Stored_Coord()
            self.AnchorConfig(row, col, Anchor)
        else:
            if self.visibleRow() < self._doc.totalBlocks() - 1:
                row = self.visibleRow() + 1
                col = 0
                self.set_Visible_Row(row)
                self.set_Visible_Col(col)
                self.sync_Stored_Coord()
                self.AnchorConfig(row, col, Anchor)

        self.scrollConfig()
        self._edit.update()
        self._edit.resetCursor()

    def navUp(self, Anchor = False):
        if self.visibleRow() > 0:
            row = self.visibleRow() - 1
            self.set_Visible_Row(row)
            strLength = self._doc.findBlockByNumber(self.visibleRow()).totalCharacters()
            col = min(strLength, self.stored_Visible_Coord().col())
            self.set_Visible_Col(col)
        else:
            row = self.visibleRow()
            col = 0
            self.set_Visible_Col(0)
            self.sync_Stored_Coord()

        self.AnchorConfig(row, col, Anchor)

        self.scrollConfig()
        self._edit.update()
        self._edit.resetCursor()

    def navDn(self, Anchor = False):
        if self.visibleRow() < self._doc.totalBlocks() - 1:
            row = self.visibleRow() + 1
            self.set_Visible_Row(row)
            strLength = self._doc.findBlockByNumber(self.visibleRow()).totalCharacters()
            col = min(strLength, self.stored_Visible_Coord().col())
            self.set_Visible_Col(col)
        else:
            row = self.visibleRow()
            col = self._doc.findBlockByNumber(self._doc.totalBlocks() - 1).totalCharacters()
            self.set_Visible_Col(col)
            self.sync_Stored_Coord()


        self.AnchorConfig(row, col, Anchor)

        self.scrollConfig()
        self._edit.update()
        self._edit.resetCursor()

    def moveTo(self, row, col, scroll = True, Anchor = False):
        lastBlock = self._doc.blocks()[-1]
        ipRow = row
        row = min(row, lastBlock.blockNumber())
        row = max(0, row)
        totalCar = self._doc.blocks()[row].totalCharacters()
        if row == lastBlock.blockNumber() and ipRow != row:
            col = totalCar
        else:
            col = min(col, totalCar)
            col = max(0, col)

        self.set_Visible_Row(row)
        self.set_Visible_Col(col)
        self.sync_Stored_Coord()

        self.AnchorConfig(row, col, Anchor)

        if scroll:
            self.scrollConfig()
        self.editor().resetCursor()
        self.editor().update()

    def AnchorConfig(self, row, col, Anchor=False):
        if not Anchor:
            self._anchor.setRow(row)
            self._anchor.setCol(col)

            self.selectionStart().setRow(row)
            self.selectionStart().setCol(col)

            self.selectionStop().setRow(row)
            self.selectionStop().setCol(col)

            return

        start = min((self._anchor.row(), self._anchor.col()), (self.absoluteRow(), self.absoluteCol()))
        stop  = max((self._anchor.row(), self._anchor.col()), (self.absoluteRow(), self.absoluteCol()))

        self.selectionStop().setRow(stop[0])
        self.selectionStop().setCol(stop[1])

        self.selectionStart().setRow(start[0])
        self.selectionStart().setCol(start[1])

    def hasSelection(self) -> bool:
        return self._selection.hasSelection()

    def selectionStart(self) -> textPosition:
        return self._selection.selectionStart()

    def selectionStop(self) -> textPosition:
        return self._selection.selectionStop()

    def selection(self) -> textSelection:
        return self._selection


class textSelection:

    def __init__(self):
        self.start = textPosition(row = 0, col = 0)
        self.stop  = textPosition(row = 0, col = 0)

    def reset(self):
        self.stop.setRow(self.start.row())
        self.stop.setCol(self.start.col())

    def selectionStart(self) -> textPosition:
        return self.start

    def selectionStop(self) -> textPosition:
        return self.stop

    def hasSelection(self) -> bool:
        if self.selectionStart().row() == self.selectionStop().row() and self.selectionStart().col() == self.selectionStop().col():
            return False
        return True    


class textPosition:

    def Coord(self) -> tuple:
        return (self.row(), self.col())

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

    def __init__(self, row, col):
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



#### SEE IF YOU CAN UPDATE THE RESET CURSOR AND CURSOR NAVIGATIONS WITHOUT COMPUTING ALL THE TEXTS IN THE PAINT EVENT