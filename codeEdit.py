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
        self._Cursor = TextCursor(editor = self, doc = self.document())

        self.Font = QFont()
        self.Font.setFamilies(["Consolas", "Courier New"])
        self.fontSize = 17
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

        if self.textCursor().hasSelection():
            aRow, aCol = (self.textCursor().selectionStart().visibleCoord().row(), self.textCursor().selectionStart().visibleCoord().col())
            bRow, bCol = (self.textCursor().selectionStop().visibleCoord().row(), self.textCursor().selectionStop().visibleCoord().col())

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
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            roundedSelection = self.smoothPath(selectionPath, radius=6, painter=painter)

            painter.setPen(Qt.NoPen)
            if self.hasFocus(): painter.setBrush(QColor(79.2, 202.4, 255, 116.36))
            else: painter.setBrush(QColor(50, 147, 183, 64))
            painter.drawPath(roundedSelection)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

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
                row += 1

        else:
            if self.showReason:
                print("missed")

        if self.cursorVisible and self.hasFocus():
            cursorPen = QPen(QColor(200, 200, 200, 255), self.cursWidth)
            painter.setPen(cursorPen)
            x = self.textCursor().visibleCoord().col() * self.cellW + self.leftMargin() - self._scrollX
            y = self.textCursor().visibleCoord().row() * self.cellH + self.topMargin() - self._scrollY
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

        # print("------------------------")
        roundedPath.closeSubpath()
        return roundedPath

    def resetCursor(self):
        self.toggle = False
        self.cursorVisible = True
        cursX = self.textCursor().visibleCoord().col() * self.cellW + self.leftMargin()
        cursY = self.textCursor().visibleCoord().row() * self.cellH + self.topMargin() - self._scrollY
        Rect = QRect(int(cursX) - self.cellW, int(cursY) - 1, 2 * int(self.cellW), int(self.cellH) + 1)
        self.update(Rect)
        self.cursTimer.start(self.cursDelay)

    def toggleCursor(self):
        if self.hasFocus():
            self.toggle = True
            self.cursorVisible = not self.cursorVisible
            cursX = self.textCursor().visibleCoord().col() * self.cellW + self.leftMargin() - self._scrollX
            cursY = self.textCursor().visibleCoord().row() * self.cellH + self.topMargin() - self._scrollY
            if not self.scrollActive:
                self._updateReason = "toggle"
                self.update(QRect(round(cursX) - self.cellW, round(cursY) - 1, 2 * round(self.cellW), round(self.cellH) + 1))
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
            lineNo = cursor.visibleCoord().row() + 1
            col = cursor.visibleCoord().col()
        else:
            lineNo += 1
            col = cursor.visibleCoord().col() if lineNo == cursor.visibleCoord().row() + 1 else doc.findBlockByNumber(lineNo - 1).totalCharacters()

        prevBlock = doc.findBlockByNumber(lineNo - 1)

        block = textBlock(doc, blockNumber=lineNo)
        block.Chars = prevBlock.Chars[col:]
        del prevBlock.Chars[col:]

        doc.blocks().insert(lineNo, block)
        doc.visibleBlocks().insert(lineNo, block)
        doc.reEnumerate()

        self.textCursor().moveTo(lineNo, 0)
        self._maxScrollY += self.cellH
        self.update()

    def insert(self, ch):
        block = self.document().blocks()[self.textCursor().visibleCoord().row()]
        block.Chars.insert(self.textCursor().visibleCoord().col(), textCell(ch = ch))

        self.textCursor().navRight()

    def deleteLeft(self, position : textPosition | None = None):
        if not position:
            row = self.textCursor().visibleCoord().row()
            col = self.textCursor().visibleCoord().col()
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
            abs_row = self.textCursor().absoluteCoord().row()
            del self.document().visibleBlocks()[row]
            del self.document().blocks()[abs_row + 1]
            self.document().reEnumerate()
            self._maxScrollY -= self.cellH
            if self._maxScrollY < 0: self._maxScrollY = 0
        self.update()

    def keyPressEvent(self, event : QKeyEvent):
        if self.controlModifier:
            if   event.key() == Qt.Key.Key_Equal:
                self.fontSize += 1
                self.Font.setPixelSize(self.fontSize)
                self.fm = QFontMetricsF(self.Font)

                self.cellW  = self.fm.horizontalAdvance("W")
                self.cellH  = self.fm.height()
                self.Ascent = self.fm.ascent()
                self.update()
            elif event.key() == Qt.Key.Key_Minus:
                self.fontSize -= 1
                self.Font.setPixelSize(self.fontSize)
                self.fm = QFontMetricsF(self.Font)

                self.cellW  = self.fm.horizontalAdvance("W")
                self.cellH  = self.fm.height()
                self.Ascent = self.fm.ascent()
                self.update()
            elif event.key() == Qt.Key.Key_C:
                if self.textCursor().hasSelection():
                    text = self.textCursor().selectedText()
                    print(text)
                    QGuiApplication.clipboard().setText(text)

        elif event.key() == Qt.Key.Key_Left:
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

    def focusInEvent(self, event):
        self.update()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self.update()
        super().focusOutEvent(event)


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

    def isValid(self):
        if self in self.document:
            return True
        return False

    def blockNumber(self):
        return self._blockNumber

    def totalCharacters(self):
        return len(self.Chars)

    def isHead(self):
        return self.head

    def text(self):
        lineString = ""
        for cell in self.Chars:
            lineString += cell.char
        return lineString

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
    def __init__(self, ch = '', color : QColor = QColor(200, 200, 200, 255)):
        self.char = ch
        self.color = color


class TextCursor:

    def __init__(self, editor : textEdit, doc : textDocument, row = 0, col = 0):
        self._doc = doc
        self._edit = editor
        self.Coord = pairedPosition(doc = self._doc)
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
    def block(self) -> textBlock:return self._doc.blocks()[self.visibleCoord.row()]

    def visibleCoord(self) : return self.Coord.visibleCoord()
    def absoluteCoord(self): return self.Coord.absoluteCoord()
    def anchor(self)       : return self._anchor
    def storedCoord(self)  : return self._storedCoord

    def set_Stored_Visible_Coord(self, row, col):
        self.storedCoord().set_Visible_Row(row)
        self.storedCoord().setCol(col)

    def set_Stored_Absolute_Coord(self, row, col):
        self.storedCoord().set_Absolute_Row(row)
        self.storedCoord().setCol(col)

    def sync_Stored_Coord(self):
        self.storedCoord().set_Absolute_Row(self.absoluteCoord().row())
        self.storedCoord().setCol(self.visibleCoord().col())

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
        if self.visibleCoord().col() > 0:
            row = self.visibleCoord().row()
            col = self.visibleCoord().col() - 1
            self.Coord.setCol(col)
            self.sync_Stored_Coord()
            self.AnchorConfig(row, col, Anchor)
        else:
            if self.visibleCoord().row() > 0:
                row = self.visibleCoord().row() - 1
                col = self._doc.findBlockByNumber(row).totalCharacters()
                self.Coord.set_Visible_Row(row)
                self.Coord.setCol(col)
                self.sync_Stored_Coord()
                self.AnchorConfig(row, col, Anchor)

        self.scrollConfig()
        self._edit.update()
        self._edit.resetCursor()

    def navRight(self, Anchor = False):
        if self.visibleCoord().col() < self._doc.findBlockByNumber(self.visibleCoord().row()).totalCharacters():
            row = self.visibleCoord().row()
            col = self.visibleCoord().col() + 1
            self.Coord.setCol(col)
            self.sync_Stored_Coord()
            self.AnchorConfig(row, col, Anchor)
        else:
            if self.visibleCoord().row() < self._doc.totalBlocks() - 1:
                row = self.visibleCoord().row() + 1
                col = 0
                self.Coord.set_Visible_Row(row)
                self.Coord.setCol(col)
                self.sync_Stored_Coord()
                self.AnchorConfig(row, col, Anchor)

        self.scrollConfig()
        self._edit.update()
        self._edit.resetCursor()

    def navUp(self, Anchor = False):
        if self.visibleCoord().row() > 0:
            row = self.visibleCoord().row() - 1
            self.Coord.set_Visible_Row(row)
            strLength = self._doc.findBlockByNumber(self.visibleCoord().row()).totalCharacters()
            col = min(strLength, self.storedCoord().visibleCoord().col())
            self.Coord.setCol(col)
        else:
            row = self.visibleCoord().row()
            col = 0
            self.Coord.setCol(0)
            self.sync_Stored_Coord()

        self.AnchorConfig(row, col, Anchor)

        self.scrollConfig()
        self._edit.update()
        self._edit.resetCursor()

    def navDn(self, Anchor = False):
        if self.visibleCoord().row() < self._doc.totalBlocks() - 1:
            row = self.visibleCoord().row() + 1
            self.Coord.set_Visible_Row(row)
            strLength = self._doc.findBlockByNumber(self.visibleCoord().row()).totalCharacters()
            col = min(strLength, self.storedCoord().visibleCoord().col())
            self.Coord.setCol(col)
        else:
            row = self.visibleCoord().row()
            col = self._doc.findBlockByNumber(self._doc.totalBlocks() - 1).totalCharacters()
            self.Coord.setCol(col)
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

        self.Coord.set_Visible_Row(row)
        self.Coord.setCol(col)
        self.sync_Stored_Coord()

        self.AnchorConfig(row, col, Anchor)

        if scroll:
            self.scrollConfig()
        self.editor().resetCursor()
        self.editor().update()

    def AnchorConfig(self, visRow, visCol, Anchor=False):
        if not Anchor:
            self.anchor().visibleCoord().setRow(visRow)
            self.anchor().setCol(visCol)

            self.selectionStart().visibleCoord().setRow(visRow)
            self.selectionStart().setCol(visCol)

            self.selectionStop().visibleCoord().setRow(visRow)
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

    def selection(self) -> textSelection:
        return self._selection

    def hasSelection(self) -> bool:
        return self._selection.hasSelection()

    def selectionStart(self) -> pairedPosition:
        return self._selection.selectionStart()

    def selectionStop(self) -> pairedPosition:
        return self._selection.selectionStop()

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


class textSelection:

    def __init__(self, doc : textDocument):
        self.start = pairedPosition(doc = doc)
        self.stop  = pairedPosition(doc = doc)

    def reset(self):
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

    def absoluteToVisible(self, block : int | textBlock):
        if hasattr(block, 'int'):
            block = self._doc.findBlockByNumber(block)
        try:
            return self._doc._visible.index(block)
        except ValueError:
            return None

    def visibleToAbsolute(self, block : int | textBlock):
        if hasattr(block, 'textBlock'):
            return block.blockNumber()
        else:
            block = self._doc.visibleBlocks()[block]
            return block.blockNumber()


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