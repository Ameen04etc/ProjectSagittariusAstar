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


class textEdit(QWidget):

    def __init__(self, parent):
        super().__init__(parent)
        self._document = textDocument()
        self._Cursor = TextCursor(editor = self, doc = self.document(), row = 0, col = 0)

        self.Font = QFont()
        self.Font.setFamilies(["Consolas", "Courier New"])
        self.fontSize = 30
        self.Font.setPixelSize(self.fontSize)
        self.fm = QFontMetricsF(self.Font)

        self.cellW  = self.fm.horizontalAdvance("W")
        self.cellH  = self.fm.height()
        self.Ascent = self.fm.ascent()
        self._scrollY = 0
        self._scrollX = 0
        self._maxScrollX = 0
        self._maxScrollY = 0

        self.toggle = False
        self.cursorVisible = True
        self.cursWidth = 2
        self.cursDelay = 500
        self.cursTimer = QTimer(self)
        self.cursTimer.start(self.cursDelay)
        self.cursTimer.timeout.connect(self.toggleCursor)

        self.controlModifier = False
        self.shiftModifier   = False

        self.setMargins()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def paintEvent(self, event : QPaintEvent):
        painter = QPainter(self)
        painter.setFont(self.Font)
        painter.fillRect(event.rect(), QColor(18, 19, 20))
        # if event.rect() != self.rect():
        #     painter.drawRect(event.rect())
        # painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        start = self.firstVisibleBlock().blockNumber()
        stop  = self.lastVisibleBlock().blockNumber()
        row = start

        if not self.toggle:
            # print("-------------")
            while True:
                if row > stop:
                    break
                # print("row =", row, "stop =", stop)
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
            cursorPen = QPen(QColor(200, 200, 200, 255), self.cursWidth)
            painter.setPen(cursorPen)
            x = self.textCursor().visibleCol() * self.cellW + self.leftMargin() - self._scrollX
            y = self.textCursor().visibleRow() * self.cellH + self.topMargin() - self._scrollY
            if x == 0: x = 1
            painter.drawLine(x, y + 1.2, x, y + self.cellH - 1.2)

        row = self.textCursor().visibleRow()
        col = self.textCursor().visibleCol()

        ch0 = self.characterAt(row, col - 1)
        ch1 = self.characterAt(row - 1, col)
        ch2 = self.characterAt(row, col)
        ch3 = self.characterAt(row + 1, col)
        painter.setPen(QPen(QColor(200, 200, 200, 255), 1))
        if ch0:
            x = (col - 1) * self.cellW + self.leftMargin() - self._scrollX
            y = row * self.cellH + self.topMargin() - self._scrollY
            painter.drawText(x, y + self.Ascent, ch0)
        if ch2:
            x = col * self.cellW + self.leftMargin() - self._scrollX
            y = row * self.cellH + self.topMargin() - self._scrollY
            painter.drawText(x, y + self.Ascent, ch2)

        self.toggle = False

        painter.end()
        super().paintEvent(event)

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
            self.update(QRect(int(cursX) - 2, int(cursY), 6, int(self.cellH)))

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
            self.textCursor().navLeft()

        elif event.key() == Qt.Key.Key_Right:
            self.textCursor().navRight()

        elif event.key() == Qt.Key.Key_Up:
            self.textCursor().navUp()

        elif event.key() == Qt.Key.Key_Down:
            self.textCursor().navDn()

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
        x = event.position().x() + self._scrollX
        y = event.position().y() + self._scrollY
        self.textCursor().moveTo(row = int(y / self.cellH), col = int(x / self.cellW + 1 / 2), scroll = False)
        super().mousePressEvent(event)

    def enterEvent(self, event):
        self.setCursor(Qt.CursorShape.IBeamCursor)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().leaveEvent(event)

    def wheelEvent(self, event : QWheelEvent):
        Xdelta = event.angleDelta().x() * self.cellH / 120
        Ydelta = event.angleDelta().y() * self.cellW / 120

        self._scrollX -= Xdelta
        self._scrollY -= Ydelta
        print(self._scrollX, self._maxScrollX)
        print(self._scrollY, self._maxScrollY)

        if self._scrollX < 0: self._scrollX = 0
        if self._scrollX > self._maxScrollX: self._scrollX = self._maxScrollX
        if self._scrollY < 0: self._scrollY = 0
        if self._scrollY > self._maxScrollY: self._scrollY = self._maxScrollY
        self.update()
        super().wheelEvent(event)

    def resizeEvent(self, event):
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

    def visibleRow(self):
        return self.visibleCoord.row()

    def visibleCol(self):
        return self.visibleCoord.col()

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

    def navLeft(self):
        if self.visibleCol() > 0:
            self.set_Visible_Col(self.visibleCol() - 1)
            self.sync_Stored_Coord()
        else:
            if self.visibleRow() > 0:
                self.set_Visible_Row(self.visibleRow() - 1)
                self.set_Visible_Col(len(self._doc.findBlockByNumber(self.visibleRow()).Chars))
                self.sync_Stored_Coord()

        self.scrollConfig()
        self._edit.update()
        self._edit.resetCursor()

    def navRight(self):
        if self.visibleCol() < self._doc.findBlockByNumber(self.visibleRow()).totalCharacters():
            self.set_Visible_Col(self.visibleCol() + 1)
            self.sync_Stored_Coord()
        else:
            if self.visibleRow() < self._doc.totalBlocks() - 1:
                self.set_Visible_Row(self.visibleRow() + 1)
                self.set_Visible_Col(0)
                self.sync_Stored_Coord()

        self.scrollConfig()
        self._edit.update()
        self._edit.resetCursor()

    def navUp(self):
        if self.visibleRow() > 0:
            self.set_Visible_Row(self.visibleRow() - 1)
            strLength = self._doc.findBlockByNumber(self.visibleRow()).totalCharacters()
            self.set_Visible_Col(min(strLength, self.stored_Visible_Coord().col()))
        else:
            self.set_Visible_Col(0)
            self.sync_Stored_Coord()

        self.scrollConfig()
        self._edit.update()
        self._edit.resetCursor()

    def navDn(self):
        if self.visibleRow() < self._doc.totalBlocks() - 1:
            self.set_Visible_Row(self.visibleRow() + 1)
            strLength = self._doc.findBlockByNumber(self.visibleRow()).totalCharacters()
            self.set_Visible_Col(min(strLength, self.stored_Visible_Coord().col()))
        else:
            self.set_Visible_Col(self._doc.findBlockByNumber(self._doc.totalBlocks() - 1).totalCharacters())
            self.sync_Stored_Coord()

        self.scrollConfig()
        self._edit.update()
        self._edit.resetCursor()

    def moveTo(self, row, col, scroll = True):
        lastBlock = self._doc.blocks()[-1]
        ipRow = row
        row = min(row, lastBlock.blockNumber())
        totalCar = self._doc.blocks()[row].totalCharacters()
        if row == lastBlock.blockNumber() and ipRow != row:
            col = totalCar
        else:
            col = min(col, totalCar)

        self.set_Visible_Row(row)
        self.set_Visible_Col(col)
        self.sync_Stored_Coord()

        if scroll:
            self.scrollConfig()
        self.editor().update()
        self.editor().resetCursor()

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
        self.start = textPosition(row = None, col = None)
        self.stop  = textPosition(row = None, col = None)

    def reset(self):
        self.start.setRow(None)
        self.start.setCol(None)

        self.stop.setRow(None)
        self.stop.setCol(None)

    def selectionStart(self) -> textPosition:
        return self.start

    def selectionStop(self) -> textPosition:
        return self.stop

    def hasSelection(self) -> bool:
        if self.start.row() and self.start.col() and self.stop.row() and self.stop.col():
            return True
        return False


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