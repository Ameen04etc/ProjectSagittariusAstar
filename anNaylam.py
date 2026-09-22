from importlib.resources import path
from Sagittarius_A import Ui_SagittariusA
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget,
    QSplitter, QVBoxLayout, QHBoxLayout,
    QGridLayout, QScrollBar, QSizePolicy,
    QPushButton, QToolButton, QToolTip,
    QFrame, QLabel, QTreeView, QGraphicsOpacityEffect,
    QPlainTextEdit, QTextEdit, QFileDialog)
from PySide6.QtCore import (QProcess, Qt, QObject,
    Signal, QRectF, QRect,
    Slot, QPointF, QPoint,
    QSize, QEvent, QSignalBlocker,
    QTimer, QRegularExpression, QPropertyAnimation,
    QEasingCurve)
from PySide6.QtGui import (QPainter, QColor, QPen,
    QPixmap, QFont, QMouseEvent,
    QImage, QCursor, QPainterPath,
    QStandardItemModel, QStandardItem,
    QFontMetrics, QKeySequence, QTextFormat,
    QTextCursor, QTextBlock, QShortcut,
    QTextCharFormat, QSyntaxHighlighter, QGuiApplication,
    QTextBlockUserData, QFontMetricsF, QWheelEvent,
    QAbstractTextDocumentLayout)
from enum import Enum, auto
from typing import cast
from pathlib import Path
from tree_sitter import Language, Parser
import tree_sitter_python
import json
import os
import sys
import re
import threading
import math
import time

RED    = "\033[31m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
BLUE   = "\033[34m"
RESET  = "\033[0m"

LANGUAGE_MAP = {
    ".py"   : "python",
    ".js"   : "javascript",
    ".ts"   : "typescript",
    ".html" : "html",
    ".css"  : "css",
    ".json" : "json",
    ".cpp"  : "cpp",
    ".c"    : "c"
}

VS_CONTROL_FLOW = {
    "if", "elif", "else", "for", "while", "break", "continue", 
    "return", "yield", "try", "except", "finally", "raise", 
    "match", "case", "with"
}

VS_KEYWORDS = {
    "global", "nonlocal", "pass", 
    "true", "false", "none", 
    "and", "or", "not", "is", "in", "async", "await"
}

VS_OPERATORS = {
    "+", "-", "*", "/", "%", "**", "//", "=", "==", "!=", 
    "<", ">", "<=", ">=", "@", "&", "|", "^", "~", "<<" , ">>"
}

DUNDER_METHODS = {
    # Construction & Destruction
    "__new__", "__init__", "__del__",

    # Representation & Conversion
    "__repr__", "__str__", "__bytes__", "__format__",
    "__hash__", "__bool__",

    # Comparisons
    "__lt__", "__le__", "__eq__", "__ne__", "__gt__", "__ge__",

    # Attribute Access
    "__getattr__", "__getattribute__", "__setattr__", "__delattr__",
    "__dir__",

    # Descriptors
    "__get__", "__set__", "__delete__", "__set_name__",

    # Class Customization & Metaclasses
    "__init_subclass__", "__class_getitem__", "__prepare__",
    "__instancecheck__", "__subclasscheck__",

    # Callables
    "__call__",

    # Containers & Sequences
    "__len__", "__length_hint__", "__getitem__", "__setitem__",
    "__delitem__", "__missing__", "__iter__", "__reversed__",
    "__contains__",

    # Context Managers
    "__enter__", "__exit__",

    # Asynchronous Features
    "__await__", "__aiter__", "__anext__",
    "__aenter__", "__aexit__",

    # Numeric & Arithmetic
    "__add__", "__sub__", "__mul__", "__matmul__",
    "__truediv__", "__floordiv__", "__mod__", "__divmod__",
    "__pow__", "__lshift__", "__rshift__", "__and__",
    "__xor__", "__or__",

    # Reflected Arithmetic
    "__radd__", "__rsub__", "__rmul__", "__rmatmul__",
    "__rtruediv__", "__rfloordiv__", "__rmod__", "__rdivmod__",
    "__rpow__", "__rlshift__", "__rrshift__", "__rand__",
    "__rxor__", "__ror__",

    # In-place Arithmetic
    "__iadd__", "__isub__", "__imul__", "__imatmul__",
    "__itruediv__", "__ifloordiv__", "__imod__", "__ipow__",
    "__ilshift__", "__irshift__", "__iand__", "__ixor__", "__ior__",

    # Unary & Built-in Math
    "__neg__", "__pos__", "__abs__", "__invert__",
    "__complex__", "__int__", "__float__", "__index__",
    "__round__", "__trunc__", "__floor__", "__ceil__",

    # Serialization / Pickling
    "__reduce__", "__reduce_ex__", "__getstate__", "__setstate__",
    "__getnewargs__", "__getnewargs_ex__",
}

PAIR_BRACE = {
    '(' : ')',
    '{' : '}',
    '[' : ']',
    '"' : '"',
    "'" : "'"
}

INVERT_PAIR_BRACE = {
    ')' : '(',
    '}' : '{',
    ']' : '[',
    '"' : '"',
    "'" : "'"
}

CLOSING_CHARS = set(PAIR_BRACE.values())

AUTO_CLOSE_BEFORE = {' ', '\t', '\n', '\r', ')', ']', '}', '>', ',', ';', ':', '.', '"', "'", '`', ''}

DELIMITER = {
    "subscript"               : ("[", "]"),
    "list"                    : ("[", "]"),
    "list_comprehension"      : ("[", "]"),
    "list_pattern"            : ("[", "]"),
    "type_parameter"          : ("[", "]"),

    "set"                     : ("{", "}"),
    "set_comprehension"       : ("{", "}"),
    "dictionary"              : ("{", "}"),
    "dictionary_comprehension": ("{", "}"),
    "interpolation"           : ("{", "}"),

    "parenthesized_expression": ("(", ")"),
    "parameters"              : ("(", ")"),
    "tuple"                   : ("(", ")"),
    "tuple_pattern"           : ("(", ")"),
    "argument_list"           : ("(", ")")
}

RAINBOW_COLORS = [
    QColor("#ffd700"),
    QColor("#d86fd4"),
    QColor("#179fff"),
]

INDENT = {"if_statement", "else_clause", "elif_clause", "for_statement", "while_statement", "function_definition", "class_definition"}

DEDENT = {"return_statement", "break_statement"}

def ListIdx(listObject : list, target):
    try:
        idx = listObject.index(target)
    except ValueError:
        idx = None

    return idx


class LineIndent(Enum):
    Indent = auto()
    Dedent = auto()
    Keep   = auto()


class Delimiter:
    def __init__(self, id, ch, start, end):
        self.id        = id
        self.delimiter = ch
        self.start     = start
        self.end       = end


class DelimitterArray:
    def __init__(self):
        self.Dlist : list[Delimiter] = []

    def __iter__(self):
        return iter(self.Dlist)

    def __len__(self):
        return len(self.Dlist)

    def __getitem__(self, key):
        return self.Dlist[key]

    def append(self, item : Delimiter):
        self.Dlist.append(item)

    def startPositions(self):
        startList = [d.start for d in self.Dlist]
        return startList

    def endPositions(self):
        endlist = [d.end for d in self.Dlist]
        return endlist

    def checkInside(self, byteOffset):
        insideList = []
        for delim in self.Dlist:
            if delim.start < byteOffset < delim.end:
                insideList.append(delim)

        if insideList:
            return True, insideList

        return False, insideList


class BlockBracketData(QTextBlockUserData):
    def __init__(self):
        super().__init__()
        self.bracketMap = {}
        self.bracketStack = []


class LineNumberArea(QWidget):
    scrollEmit     = Signal(object)
    lineSelectEmit = Signal(int, bool)

    def __init__(self, parent, editor : 'CodeEditor', Font : QFont):
        super().__init__(parent)
        self.editor     = editor
        self.Font       = Font

        self.cellWidth  = QFontMetrics(self.Font).horizontalAdvance("W")
        self.cellHeight = QFontMetrics(self.Font).height()
        self.Ascent     = QFontMetrics(self.Font).ascent()

        self.TotalLines = 1
        self.TopIdx     = 0
        self.BotIdx     = 0
        self.CursIdx    = 0

        self.LeftMargin  = 5
        self.RightMargin = 10

        self.updateWidth()
        self.setStyleSheet("""
            border: 2px solid rgb(45, 45, 48);
            border-radius: 8px;
        """)

    def paintEvent(self, event):
        self.TotalLines = 0
        painter = QPainter(self)
        painter.setFont(self.Font)
        painter.fillRect(self.rect(), QColor(18, 19, 20))

        block = self.editor.firstVisibleBlock()
        blockNumber = block.blockNumber()

        top = round(self.editor.blockBoundingGeometry(block).translated(self.editor.contentOffset()).top())
        bottom = top + round(self.editor.blockBoundingRect(block).height())

        self.TopIdx = block.blockNumber() + 1

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                self.TotalLines += 1
                opacity = 80
                if blockNumber == self.CursIdx:
                    opacity = 200
                
                painter.setPen(QPen(QColor(255, 255, 255, opacity)))

                line_str = str(blockNumber + 1)
                textWidth = self.fontMetrics().horizontalAdvance(line_str)
                x = self.width() - self.RightMargin - textWidth

                painter.drawText(x, top + self.Ascent, line_str)

                # painter.drawRect(x, top, self.RightMargin + textWidth, self.cellHeight)
                # cellRect = QRect(
                #     x + 1, top + 1,
                #     self.cellWidth - 2, self.cellHeight - 2
                # )
                # painter.drawRect(cellRect)

            block = block.next()
            top = bottom
            bottom = top + round(self.editor.blockBoundingRect(block).height())
            blockNumber += 1

    def updateWidth(self):
        digits = max(2, len(str(self.TotalLines)))
        newWidth = self.LeftMargin + (digits * self.cellWidth) + self.RightMargin

        self.setFixedWidth(newWidth)
        self.update()

    def mousePressEvent(self, event):
        x = event.position().x()
        y = event.position().y()
        if self.LeftMargin < x < self.width() - self.RightMargin:
            LineSelect = int((y - round(self.editor.blockBoundingGeometry(self.editor.firstVisibleBlock()).translated(self.editor.contentOffset()).top())) / self.cellHeight) + self.TopIdx
            # print("LineSelect =", LineSelect)
            if self.TopIdx <= LineSelect <= self.TotalLines + self.TopIdx - 1:
                self.lineSelectEmit.emit((LineSelect - 1), False)
        super().mousePressEvent(event)

    def wheelEvent(self, event):
        self.scrollEmit.emit(event)
        super().wheelEvent(event)

    def enterEvent(self, event):
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().leaveEvent(event)


class CodeEditor(QPlainTextEdit):
    fileOpened = Signal(object)

    def __init__(self, parent = None):
        super().__init__(parent)
        self.Language  = PythonLanguage(self.document(), self)
        self.version   = 1
        self.FilePath  = None
        self.FileExt   = "plaintext"
        self.NewFile   = False
        self.LoadFile  = False
        self.Selection = CodeSelection()
        self.Context   = CodeContext(editor = self)

        # self.ChangeFlag = False

        self.delimiterCreation = False
        self.FreshDelimiters   = DelimitterArray()
        self.FreshDelimitCount = 0
        self.DelimiterID       = 0

        self.errSelections = []
        self.errSquiggles  : list[Squiggle] = []
        self.warnSquiggles : list[Squiggle] = []

        self.Diagnostics = {}

        self.Font = QFont()
        self.Font.setFamilies(["Consolas", "Courier New"])
        self.Font.setPixelSize(15)
        self.setFont(self.Font)
        self.fm   = QFontMetricsF(self.Font)

        self.NormalFormat = QTextCharFormat()
        self.NormalFormat.setForeground(QColor("white"))
        self.textCursor().mergeCharFormat(self.NormalFormat)

        self.LineWidget = LineNumberArea(self.parent(), self, self.Font)

        self.cellWidth  = self.fm.horizontalAdvance("W")
        self.cellHeight = self.fm.height()
        self.Ascent     = self.fm.ascent()

        # self.cellWidth  = self.fontMetrics().horizontalAdvance("W")
        # self.cellHeight = self.fontMetrics().height()
        # self.Ascent     = self.fontMetrics().ascent()

        self.SpacePerTab = 4
        self.OldText     = self.document().toPlainText()

        self.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.NoWrap
            )
        self.setTabStopDistance(
            4 * self.cellWidth
        )

        self.Language.syntax.sourceUpdate(self.document().toPlainText().encode())
        # self.Language.syntax.printSyntax()
        self.oldTree = self.Language.syntax.Tree
        self.newTree = self.Language.syntax.Tree
        self.oldNode = self.Language.syntax.Tree.root_node
        self.newNode = self.Language.syntax.Tree.root_node

        self.highlightVersion = 0
        self.pendingBlocks    = set()
        self.highlightTimer   = QTimer()
        self.highlightTimer.setSingleShot(True)

        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.floating_vbar = self.verticalScrollBar()
        self.floating_hbar = self.horizontalScrollBar()

        self.floating_vbar.setParent(self)
        self.floating_hbar.setParent(self)

        self.styleConfig(self.floating_vbar)
        self.styleConfig(self.floating_hbar)

        # self.incompleteStacks = []
        # self.brackets = {}
        # self.bracketStack = []
        # self.blockBracketStack = [[]]
        # self.bracketMap = [{}]

        self._blink_reset_timer = QTimer(self)
        self._blink_reset_timer.setSingleShot(True)
        self._blink_reset_timer.timeout.connect(self._restore_blinking)

        blockdata = BlockBracketData()
        self.firstVisibleBlock().setUserData(blockdata)

        self.StyleConfig()
        self.HighLightLine()
        self.SignalManager()
        self.setCursorWidth(2)

        # -- Vertical Bar Animation Setup --
        self.vbar_effect = QGraphicsOpacityEffect(self.floating_vbar)
        self.floating_vbar.setGraphicsEffect(self.vbar_effect)
        
        self.vbar_anim = QPropertyAnimation(self.vbar_effect, b"opacity")
        self.vbar_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.vbar_anim.finished.connect(self._on_vbar_fade_finished)

        # -- Horizontal Bar Animation Setup --
        self.hbar_effect = QGraphicsOpacityEffect(self.floating_hbar)
        self.floating_hbar.setGraphicsEffect(self.hbar_effect)

        self.hbar_anim = QPropertyAnimation(self.hbar_effect, b"opacity")
        self.hbar_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.hbar_anim.finished.connect(self._on_hbar_fade_finished)

        self.scrollOffset = 0

    def paintEvent(self, e):
        painter = QPainter(self.viewport())
        # painter.translate(0, self.scrollOffset)
        painter.fillRect(e.rect(), QColor(18, 19, 20))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setPen(QPen(QColor(205, 49, 49), 1.5))
        for squiggle in self.errSquiggles: self.drawSquiggle(painter, squiggle)

        painter.setPen(QPen(QColor(229, 229, 16), 1.5))
        for squiggle in self.warnSquiggles: self.drawSquiggle(painter, squiggle)

        base_x = self.document().documentMargin() + self.contentOffset().x()
        active_pos = None
        min_block_num = -1
        max_block_num = -1
        
        cursor_block = self.textCursor().block()
        c_text = cursor_block.text()
        
        # If cursor is on an empty line, look upwards to inherit its scope context
        temp_block = cursor_block
        while not c_text.strip() and temp_block.isValid():
            temp_block = temp_block.previous()
            if temp_block.isValid():
                c_text = temp_block.text()

        c_ls = len(c_text) - len(c_text.lstrip(' '))
        c_levels = list(range(0, c_ls, 4))
        
        if c_levels:
            active_pos = c_levels[-1] # The deepest valid guide for the current block
            
            # Scan upwards to find where this indentation scope starts
            b = temp_block
            start_block = b
            while b.isValid():
                t = b.text()
                if t.strip():
                    if (len(t) - len(t.lstrip(' '))) <= active_pos:
                        break
                start_block = b
                b = b.previous()
                
            # Scan downwards to find where this indentation scope ends
            b = temp_block
            end_block = b
            while b.isValid():
                t = b.text()
                if t.strip():
                    if (len(t) - len(t.lstrip(' '))) <= active_pos:
                        break
                end_block = b
                b = b.next()
                
            min_block_num = start_block.blockNumber()
            max_block_num = end_block.blockNumber()

        # --- STEP 2: DRAW THE GUIDES ---
        viewport_rect = self.viewport().rect()
        block = self.firstVisibleBlock()
        content_offset = self.contentOffset()

        while block.isValid():
            geom = self.blockBoundingGeometry(block).translated(content_offset)
            top = geom.top()
            bottom = geom.bottom()

            if top > viewport_rect.bottom():
                break

            if bottom >= 0 and block.isVisible():
                text = block.text()
                
                # VS Code trick: Bridge empty lines so the vertical lines don't break
                if not text.strip():
                    # Find indent of previous valid line
                    pb = block.previous()
                    while pb.isValid() and not pb.text().strip(): pb = pb.previous()
                    p_ls = len(pb.text()) - len(pb.text().lstrip(' ')) if pb.isValid() else 0
                    
                    # Find indent of next valid line
                    nb = block.next()
                    while nb.isValid() and not nb.text().strip(): nb = nb.next()
                    n_ls = len(nb.text()) - len(nb.text().lstrip(' ')) if nb.isValid() else 0
                    
                    leading_spaces = min(p_ls, n_ls)
                else:
                    leading_spaces = len(text) - len(text.lstrip(' '))

                levels = list(range(0, leading_spaces, 4))
                
                for pos in levels:
                    x = base_x + (pos * self.cellWidth) + 2
                    # If this vertical line is the active scope AND this block falls within the contiguous scope boundaries
                    is_active_scope_line = (pos == active_pos) and (min_block_num <= block.blockNumber() <= max_block_num)

                    if is_active_scope_line:
                        painter.setPen(QColor(255, 255, 255, 255))  # Bright white for active scope
                    else:
                        painter.setPen(QColor(255, 255, 255, 50))   # Dim white for background scopes

                    painter.drawLine(x, int(top), x, int(bottom))

            block = block.next()

        # layout = self.document().documentLayout()
        # ctx = QAbstractTextDocumentLayout.PaintContext()
        # ctx.palette = self.palette()
        # ctx.clip = QRectF(e.rect())

        # painter.setClipRect(e.rect())

        # # Move document into the viewport.
        # painter.translate(
        #     self.contentOffset()
        # )

        # layout.draw(painter, ctx)

        painter.end()
        super().paintEvent(e)

    def drawSquiggle(self, painter : QPainter, squiggle : Squiggle):
        for line in range(squiggle.start.row, squiggle.end.row + 1):
            block = self.document().findBlockByNumber(line)
            if not block.isValid():
                continue

            blockLen = max(0, block.length() - 1)
            if line == squiggle.start.row:
                colStart = min(squiggle.start.col, blockLen)
                cursor = QTextCursor(block)
                cursor.setPosition(block.position() + colStart)
                startRect = self.cursorRect(cursor)
                x0 = startRect.x()
            else:
                cursor = QTextCursor(block)
                cursor.setPosition(block.position())
                startRect = self.cursorRect(cursor)
                x0 = startRect.x()

            if line == squiggle.end.row:
                if line > squiggle.start.row and squiggle.end.col == 0:
                    continue
                colEnd = min(squiggle.end.col, blockLen)
                cursor = QTextCursor(block)
                cursor.setPosition(block.position() + colEnd)
                endRect = self.cursorRect(cursor)
                x1 = endRect.x()
            else:
                cursor = QTextCursor(block)
                cursor.setPosition(block.position() + block.length() - 1)
                endRect = self.cursorRect(cursor)
                x1 = endRect.right()
            
            if x0 == x1: 
                x0 -= self.cellWidth // 2
                x1 += self.cellWidth // 2

            yoff = startRect.bottom()
            locus = QPainterPath()
            locus.moveTo(x0, yoff)

            A = 1.4
            l = 6

            for x in range(int(x0), int(x1) + 1):
                y = A * math.sin((x) * (2 * math.pi / l)) + yoff
                locus.lineTo(x, y)

            painter.drawPath(locus)

    def reportChange(self):
        # self.ChangeFlag = True
        if self.NewFile: self.version = 1
        else: self.version += 1

    def moveCursor(self, blockID, end = True):
        block = self.document().findBlockByNumber(blockID)
        if block.isValid():
            cursor = QTextCursor(block)
            if end:
                cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)
            else:
                cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            self.setTextCursor(cursor)
            self.ensureCursorVisible()

    def selectLine(self, blockID, *args):
        block = self.document().findBlockByNumber(blockID)
        if block.isValid():
            cursor = QTextCursor(block)
            cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
            self.setTextCursor(cursor)

    def HighLightLine(self):
        if self.textCursor().hasSelection():
            self.setExtraSelections(self.errSelections)
            return
        
        line_color = QColor(255, 255, 255, 15)

        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(line_color)
        selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)

        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()
        self.setExtraSelections([selection] + self.errSelections)
        # self.setExtraSelections(self.errSelections)

    def BlockIndent(self):
        cursor = self.textCursor()
        cursor.beginEditBlock()

        currentBlock = self.Selection.FirstBlock
        while currentBlock.isValid():
            self.Indent(currentBlock)

            if currentBlock == self.Selection.LastBlock: break
            currentBlock = currentBlock.next()

        cursor.endEditBlock()

    def BlockUnIndent(self):
        cursor   = self.textCursor()
        
        cursor.beginEditBlock()

        currentBlock = self.Selection.FirstBlock
        while currentBlock.isValid():
            self.unIndent(currentBlock)
            if currentBlock == self.Selection.LastBlock: break
            currentBlock = currentBlock.next()

        cursor.endEditBlock()

    def Indent(self, block : QTextBlock, InPlace = False):
        if InPlace:
            cursorPosition = self.textCursor().positionInBlock()
            preText = block.text()[:cursorPosition]
            totalSpace = len(preText) if preText else 0
            toInsert = self.SpacePerTab - totalSpace % self.SpacePerTab
            blockCursor = self.textCursor()

        else:
            toInsert = self.SpacePerTab
            blockCursor = QTextCursor(block)
        
        blockCursor.insertText(" " * toInsert)

    def unIndent(self, block : QTextBlock, InPlace = False):
        blockCursor = QTextCursor(block)
        codeText    = self.document()
        if InPlace:
            cursorPosition = self.textCursor().positionInBlock()
            preText = block.text()[:cursorPosition]
            spaces  = re.match(r"^\s+", preText)
        else:
            blockText   = block.text()
            spaces      = re.match(r"^\s+", blockText)
        totalSpace  = len(spaces.group(0).expandtabs(self.SpacePerTab)) if spaces else 0
        if totalSpace == 0:
            return
    
        toRem = totalSpace % self.SpacePerTab
        if toRem == 0: toRem = self.SpacePerTab

        spaceCount  = 0
        while True:
            char = codeText.characterAt(blockCursor.position())
            if char == "\t":
                remaining = toRem - spaceCount
                toAdd = self.SpacePerTab - remaining
                blockCursor.deleteChar()
                if toAdd > 0:
                    blockCursor.insertText(" " * toAdd)
                break

            elif char == " ":
                blockCursor.deleteChar()
                spaceCount += 1
                if spaceCount == toRem:
                    break
            else:
                break

    def bracketInput(self, ch: str):
        cursor = self.textCursor()
        position = cursor.position()
        docLen = self.document().characterCount() - 1

        cursor.beginEditBlock()

        if cursor.hasSelection():
            if ch in PAIR_BRACE:
                self.delimiterCreation = True

                selection   = cursor.selectedText()
                selectStart = cursor.selectionStart()
                selectEnd   = cursor.selectionEnd()
                cursor.insertText(f"{ch}{selection}{PAIR_BRACE[ch]}")
                if position == selectStart:
                    cursor.setPosition(selectEnd + 1)
                    cursor.setPosition(selectStart + 1, QTextCursor.MoveMode.KeepAnchor)
                else:
                    cursor.setPosition(selectStart + 1)
                    cursor.setPosition(selectEnd + 1, QTextCursor.MoveMode.KeepAnchor)

                self.setTextCursor(cursor)
                self.ensureCursorVisible()
                cursor.endEditBlock()

                node  = self.fetchCursorNode(position = self.textCursor().position())
                start = node.start_byte
                end   = node.end_byte

                self.DelimiterID += 1

                self.FreshDelimiters.append(Delimiter(id = self.DelimiterID, ch = ch, start = start, end = end))

                self.delimiterCreation = False
                self.FreshDelimitCount += 1
                self.Context.fetchCursorContext(fresh = True, chAdd = 0)

                return True

        if ch in CLOSING_CHARS:
            nextChar = self.document().characterAt(position) if position < docLen else ""
            prevChar = self.document().characterAt(position - 1) if position > 0  else ""
            node = self.fetchCursorNode(position = position + 1) if nextChar != "" else None
            _, _, _, byteOffset = self.QOffsetToCoords(text = self.toPlainText(), offset = position)

            isInside, dlist = self.FreshDelimiters.checkInside(byteOffset = byteOffset)
            print("isInside =", isInside)
            print("ENDS =", [delim.end for delim in dlist])
            print("OFFSET =", byteOffset)
            if isInside:
                closestEnd = min([delim.end for delim in dlist])

            if ch == nextChar and isInside and (closestEnd - byteOffset) == 1:
                cursor.movePosition(QTextCursor.MoveOperation.Right)
                self.setTextCursor(cursor)
                cursor.endEditBlock()
                self.Context.fetchCursorContext()

                return True

        if ch in PAIR_BRACE:
            nextChar = self.document().characterAt(position) if position < docLen else ""
            if nextChar == '\u2029': nextChar = '\n'
            if nextChar in AUTO_CLOSE_BEFORE:
                self.delimiterCreation = True

                cursor.insertText(ch + PAIR_BRACE[ch])
                cursor.movePosition(QTextCursor.MoveOperation.Left)
                self.setTextCursor(cursor)
                cursor.endEditBlock()

                node  = self.fetchCursorNode(position = self.textCursor().position())
                start = node.start_byte
                end   = node.end_byte

                self.DelimiterID += 1

                self.FreshDelimiters.append(Delimiter(id = self.DelimiterID, ch = ch, start = start, end = end))

                self.delimiterCreation = False
                self.FreshDelimitCount += 1
                self.Context.fetchCursorContext(fresh = True, chAdd = 0)

                return True

        cursor.endEditBlock()
        return False

    def removeBracket(self, ch, pos):
        success = False
        freshFlag = False

        if self.document().characterAt(pos) == PAIR_BRACE[ch]:
            _, _, _, byteOffset = self.QOffsetToCoords(text = self.toPlainText(), offset = pos)
            isInside = self.FreshDelimiters.checkInside(byteOffset = byteOffset)

            if isInside:
                for delim in self.FreshDelimiters:
                    if delim.start < byteOffset < delim.end:
                        if abs(delim.end - delim.start - 2) == 0:
                            freshFlag = True
                            break

        self.textCursor().deletePreviousChar()

        if freshFlag:
            self.textCursor().deleteChar()
            success = True

        return success

    def updateLineData(self, *args):
        totalLines = self.blockCount()
        cursLine = self.textCursor().blockNumber()

        self.LineWidget.TotalLines = totalLines
        self.LineWidget.CursIdx    = cursLine

        self.LineWidget.updateWidth()
        self.LineWidget.update()

    def updateSelection(self):
        cursor = self.textCursor()

        if cursor.hasSelection():
            self.Selection.Select = True
            selectStart = cursor.selectionStart()
            selectStop  = cursor.selectionEnd()
            CodeText    = self.document()

            if selectStop > selectStart and CodeText.findBlock(selectStop).position() == selectStop:
                selectStop -= 1

            self.Selection.FirstBlock = CodeText.findBlock(selectStart)
            self.Selection.LastBlock  = CodeText.findBlock(selectStop)
        else:
            self.Selection.resetSelection()

        # print(self.Selection.Select,"\n",
        #       self.Selection.FirstBlock.blockNumber(), "\n",
        #       self.Selection.LastBlock.blockNumber())

    def openFile(self, filepath = None):
        # filepath, _ = QFileDialog.getOpenFileName(
        #     self,
        #     "Open File",
        #     "",
        #     "All Files (*);;Python Files (*.py)"
        # )

        if filepath:
            self.NewFile = True
            self.FilePath   = Path(filepath).as_uri()
            _, self.FileExt = os.path.splitext(filepath)    # Splits "C:/scripts/main.py" into ("C:/scripts/main", ".py")
            with open(filepath, "r", encoding = "utf-8") as file:
                text = file.read()

            self.LoadFile = True
            self.setPlainText(text)
            self.LoadFile = False

            self.Language.syntax.sourceUpdate(
                self.toPlainText().encode("utf-8"),
                incremental = False
                )
            self.OldText = self.toPlainText()
            # self.fileOpened.emit(fileName)

            QTimer.singleShot(50, lambda: self.codeHighlight(refresh = True))

            # QTimer.singleShot(50, self.Language.Highlighter.rehighlight)
            # self.Language.Highlighter.rehighlight()

    def diagnose(self, uri, version, diagnostics : dict):
        # print("Current =", self.version)
        # print("Response =", version)
        # print("FilePath =", self.FilePath)
        # print("uri =", uri)
        if version != self.version:
            return
        # if uri != self.FilePath:
        #     return
        
        self.Diagnostics = diagnostics
        self.errSquiggles.clear()
        self.warnSquiggles.clear()

        for  diagnostic in self.Diagnostics:
            if "range" in diagnostic.keys():
                if diagnostic["severity"] == 1:
                    err = Squiggle()
                    err.start.row = diagnostic["range"]["start"]["line"]
                    err.start.col = diagnostic["range"]["start"]["character"]
                    err.end.row = diagnostic["range"]["end"]["line"]
                    err.end.col = diagnostic["range"]["end"]["character"]
                    self.errSquiggles.append(err)
                elif diagnostic["severity"] == 2:
                    warn = Squiggle()
                    warn.start.row = diagnostic["range"]["start"]["line"]
                    warn.start.col = diagnostic["range"]["start"]["character"]
                    warn.end.row = diagnostic["range"]["end"]["line"]
                    warn.end.col = diagnostic["range"]["end"]["character"]
                    self.warnSquiggles.append(warn)
        self.viewport().update()

    def LSPDocConfig(self):
        self.Language.client.Document.uri        = self.FilePath
        self.Language.client.Document.languageId = LANGUAGE_MAP.get(self.FileExt.lower(), "python")
        self.Language.client.Document.text       = self.toPlainText()
        if self.NewFile:
            self.Language.client.Document.version = 1
            self.NewFile = False
            self.Language.client.didOpenMessage()
        else:
            self.Language.client.Document.version += 1
            self.Language.client.didChangeMessage()

    def QOffsetToCoords(self, text, offset):
        preText = text[:offset]
        Row = preText.count('\n')

        lastNewline = preText.rfind('\n')
        lineStart   = lastNewline + 1
        lineText    = text[lineStart:offset]

        Colutf16 = len(lineText.encode("utf-16-le")) // 2
        Colutf8 = len(lineText.encode("utf-8"))
        byteOffset = len(preText.encode("utf-8"))

        return Row, Colutf16, Colutf8, byteOffset

    def byteToQOffset(self, text, byteOffset):
        encoded = text.encode("utf-8")
        prefix  = encoded[:byteOffset]
        decoded = prefix.decode("utf-8").encode("utf-16-le")
        return len(decoded) // 2

    def incrementCapture(self, position, charRem, charAdd):
        if self.LoadFile:
            return        
        
        self.oldTree = self.Language.syntax.Tree.copy()
        newText = self.document().toPlainText()

        oldStart = position
        oldEnd   = position + charRem
        oldStartRow, oldStartCol16, oldStartCol8, oldStartByte = self.QOffsetToCoords(self.OldText, oldStart)
        oldEndRow  , oldEndCol16  , oldEndCol8  , oldEndByte   = self.QOffsetToCoords(self.OldText, oldEnd)

        newEnd   = position + charAdd
        newEndRow, newEndCol16, newEndCol8, newEndByte = self.QOffsetToCoords(newText, newEnd)

        self.oldTree.edit(
            start_byte   = oldStartByte,
            old_end_byte = oldEndByte,
            new_end_byte = newEndByte,

            start_point   = (oldStartRow, oldStartCol8),
            old_end_point = (oldEndRow, oldEndCol8),
            new_end_point = (newEndRow, newEndCol8),
        )
        
        self.Language.syntax.Tree.edit(
            start_byte   = oldStartByte,
            old_end_byte = oldEndByte,
            new_end_byte = newEndByte,

            start_point   = (oldStartRow, oldStartCol8),
            old_end_point = (oldEndRow, oldEndCol8),
            new_end_point = (newEndRow, newEndCol8),
        )


        self.Language.syntax.sourceUpdate(newText.encode("utf-8"), incremental = True)

        self.newTree = self.Language.syntax.Tree
        changed_ranges = self.oldTree.changed_ranges(self.newTree)

        affectedBlocks = set()

        for row in range(oldStartRow, newEndRow + 1):
            affectedBlocks.add(row)

        for rng in changed_ranges:
            for row in range(rng.start_point[0], rng.end_point[0] + 1):
                affectedBlocks.add(row)

        self.pendingBlocks.update(affectedBlocks)
        self.highlightVersion += 1
        self.highlightTimer.start(300)

        self.OldText = newText

    def executeHighlight(self):
        blocks = sorted(list(self.pendingBlocks))
        self.pendingBlocks.clear()
        self.codeHighlight(blocks = blocks)

    def codeHighlight(self, blocks = None, refresh = False):
        if refresh:
            blocks = list(range(self.blockCount()))
        blocks = list(range(self.blockCount()))

        if not blocks:
            return

        currentVersion = self.highlightVersion

        new = self.bracketMatching(affectedBlocks = blocks)
        # print("WILL REHIGHLIGHT:", blocks)
        blocks.extend(new)

        chunkLen = 6

        def highlightNextChunk(idx):
            if currentVersion != self.highlightVersion:
                return
            
            chunk = blocks[idx:idx + chunkLen]

            for blockID in chunk:
                block = self.document().findBlockByNumber(blockID)

                if block.isValid():
                    self.Language.Highlighter.rehighlightBlock(block)
                    # pass

            nextIdx = idx + chunkLen

            if nextIdx < len(blocks):
                QTimer.singleShot(
                    0,
                    lambda: highlightNextChunk(nextIdx)
                )

        highlightNextChunk(0)

    def bracketMatching(self, affectedBlocks):
        # print("Old =", self.blockBracketStack)
        firstAffected = min(affectedBlocks)
        lastAffected  = max(affectedBlocks)

        firstAffBlock = self.document().findBlockByNumber(firstAffected)
        lastAffBlock  = self.document().findBlockByNumber(lastAffected)

        if firstAffected == 0:
            preStack = []
        else:
            data = firstAffBlock.userData()
            preStack = data.bracketStack.copy() if data else []

        # print("PreStack =", preStack)

        # print("AFFECTED BLOCKS =", affectedBlocks)

        for blockNo in affectedBlocks:
            block = self.document().findBlockByNumber(blockNo)
            text = block.text()
            blockDataCurr = BlockBracketData()
            blockDataCurr.bracketStack = preStack.copy()

            if preStack and preStack[-1][0] == "#":
                preStack.pop(-1)

            # print("Block =", blockNo)
            for i, ch in enumerate(text):
                # print("ch = ", ch, "prestack =", preStack)
                if ch == "#":
                    if preStack:
                        if preStack[-1][0] not in {"'", '"'}:
                            preStack.append([ch, blockNo, i])
                            break
                    else:
                        preStack.append([ch, blockNo, i])
                        break

                elif ch in {"'", '"'}:
                    if not preStack:
                        preStack.append([ch, blockNo, i])
                    elif preStack[-1][0] != ch:
                        if preStack[-1][0] not in {"'", '"'}:
                            preStack.append([ch, blockNo, i])
                    else:
                        preStack.pop(-1)

                elif ch in {"(", "{", "["}:
                    if not preStack:
                        preStack.append([ch, blockNo, i])

                        blockDataCurr.bracketMap.update({
                            i : [ch, QColor("#FF0000")]
                        })

                    elif preStack[-1][0] not in {"'", '"'}:
                        preStack.append([ch, blockNo, i])

                        blockDataCurr.bracketMap.update({
                            i : [ch, QColor("#FF0000")]
                        })

                elif ch in {")", "}", "]"}:
                    if preStack and preStack[-1][0] not in {"'", '"'}:
                        temp = []
                        match = False
                        while preStack:
                            bracket, row, col = preStack.pop(-1)
                            temp.append([bracket, row, col])
                            refBlock = self.document().findBlockByNumber(row)

                            if bracket == INVERT_PAIR_BRACE[ch]:
                                match = True
                                level = len(preStack)
                                color = RAINBOW_COLORS[level % len(RAINBOW_COLORS)]

                                blockDataCurr.bracketMap.update({
                                    i : [ch, color]
                                })
                                if blockNo != refBlock.blockNumber():
                                    refBlock.userData().bracketMap.update({
                                        col : [bracket, color]
                                    })
                                else:
                                    blockDataCurr.bracketMap.update({
                                        col : [bracket, color]
                                    })

                                break

                        if not match:
                            blockDataCurr.bracketMap.update({
                                i : [ch, QColor("#FF0000")]
                            })
                            preStack.extend(reversed(temp))

            block.setUserData(blockDataCurr)

            # print("CONFIGURED DATA =", block.userData().bracketMap)
        
        newBlocks = []

        blockNo = lastAffected
        block = self.document().findBlockByNumber(blockNo)
        while True:
            nextBlock = block.next()
            if not nextBlock.isValid():
                break
            elif nextBlock.userData() and preStack == nextBlock.userData().bracketStack:
                break
            else:
                block = nextBlock
                blockNo += 1
                blockData = BlockBracketData()
                blockData.bracketStack = preStack.copy()
                # print("Block =", blockNo)

                if blockNo not in affectedBlocks and blockNo not in newBlocks:
                    newBlocks.append(blockNo)

                text = block.text()
                for i, ch in enumerate(text):
                    # print("ch = ", ch, "prestack =", preStack)
                    if ch == "#":
                        if preStack:
                            if preStack[-1][0] not in {"'", '"'}:
                                preStack.append([ch, blockNo, i])
                                break
                        else:
                            preStack.append([ch, blockNo, i])
                            break

                    elif ch in {"'", '"'}:
                        if not preStack:
                            preStack.append([ch, blockNo, i])
                        elif preStack[-1][0] != ch:
                            if preStack[-1][0] not in {"'", '"'}:
                                preStack.append([ch, blockNo, i])
                        else:
                            preStack.pop(-1)

                    elif ch in {"(", "{", "["}:
                        if not preStack:
                            preStack.append([ch, blockNo, i])

                            blockData.bracketMap.update({
                                i : [ch, QColor("#FF0000")]
                            })

                        elif preStack[-1][0] not in {"'", '"'}:
                            preStack.append([ch, blockNo, i])

                            blockData.bracketMap.update({
                                i : [ch, QColor("#FF0000")]
                            })

                    elif ch in {")", "}", "]"} and preStack and (preStack[-1][0] not in {"'", '"'}):
                        temp = []
                        match = False
                        while preStack:
                            bracket, row, col = preStack.pop(-1)
                            temp.append([bracket, row, col])
                            refBlock = self.document().findBlockByNumber(row)

                            if bracket == INVERT_PAIR_BRACE[ch]:
                                match = True
                                level = len(preStack)
                                color = RAINBOW_COLORS[level % len(RAINBOW_COLORS)]
                                blockData.bracketMap.update({
                                    i : [ch, color]
                                })
                                if blockNo != refBlock.blockNumber():
                                    refBlock.userData().bracketMap.update({
                                        col : [bracket, color]
                                    })
                                else:
                                    blockData.bracketMap.update({
                                        col : [bracket, color]
                                    })

                                break

                        if not match:
                            blockData.bracketMap.update({
                                i : [ch, QColor("#FF0000")]
                            })
                            preStack.extend(reversed(temp))

                block.setUserData(blockData)

        # print("Updated =", self.blockBracketStack)

        return newBlocks









        # dStack = []
        # dFormat = QTextCharFormat()
        # maxBlocNo = max(affectedBlocks)
        # minBlocNo = min(affectedBlocks)
        # tempBrackets  = {}

        # nowComplete = []

        # for blockNo in self.incompleteStacks:
        #     # print("PRE")
        #     compList = [0, 0, 0]
        #     if blockNo in affectedBlocks or blockNo > minBlocNo:
        #         continue

        #     block = self.document().findBlockByNumber(blockNo)
        #     blockPosition = block.position()
        #     text = block.text()
        #     # print("block", blockNo, "-->", text)

        #     for i, ch in enumerate(text):
        #         absPosition = blockPosition + i
        #         if ch in {"(", "{", "["}:
        #             node = self.fetchCursorNode(position = absPosition)
        #             if  node.type in {"comment", "string", "string_start", "string_content", "escape_sequence"}:
        #                 continue

        #             if   ch == "(": compList[0] += 1
        #             elif ch == "{": compList[1] += 1
        #             elif ch == "[": compList[2] += 1

        #             dStack.append((ch, blockNo, i))
        #             tempBrackets.update({
        #                 (blockNo, i) : QColor("#FF0000")
        #             })

        #         elif ch in {")", "}", "]"}:
        #             node = self.fetchCursorNode(position = absPosition)
        #             if node.type in {"comment", "string", "string_start", "string_content", "escape_sequence"}:
        #                 continue

        #             match = False

        #             if   ch == ")": compList[0] -= 1
        #             elif ch == "}": compList[1] -= 1
        #             elif ch == "]": compList[2] -= 1

        #             while dStack:
        #                 opening, blockNumber, position = dStack.pop()

        #                 if ch == PAIR_BRACE[opening]:
        #                     match = True
        #                     level = len(dStack)
        #                     color = RAINBOW_COLORS[level % len(RAINBOW_COLORS)]

        #                     tempBrackets.update({
        #                         (blockNumber, position) : color,
        #                         (blockNo, i)     : color
        #                     })

        #                     break

        #             if not match:
        #                 tempBrackets.update({
        #                     blockNo : [i, QColor("#FF0000")]
        #                 })

        #     if compList == [0, 0, 0]:
        #         nowComplete.append(blockNo)

        # self.incompleteStacks[:] = [
        #     blockNo
        #     for blockNo in self.incompleteStacks
        #     if blockNo not in nowComplete
        # ]
        # # print("NowComplete =", nowComplete)

        # # print("PRE incomplete stacks =", self.incompleteStacks)

        # for blockNo in affectedBlocks:
        #     # print("MID")
        #     block = self.document().findBlockByNumber(blockNo)
        #     blockPosition = block.position()
        #     text = block.text()

        #     isComplete = [0, 0, 0]

        #     for i, ch in enumerate(text):
        #         absPosition = blockPosition + i
        #         if ch in {"(", "{", "["}:
        #             node = self.fetchCursorNode(position = absPosition)
        #             if  node.type in {"comment", "string", "string_start", "string_content", "escape_sequence"}:
        #                 continue

        #             if   ch == "(": isComplete[0] += 1
        #             elif ch == "{": isComplete[1] += 1
        #             elif ch == "[": isComplete[2] += 1

        #             dStack.append((ch, blockNo, i))
        #             tempBrackets.update({
        #                 (blockNo, i) : QColor("#FF0000")
        #             })
                    
        #         elif ch in {")", "}", "]"}:
        #             node = self.fetchCursorNode(position = absPosition)
        #             if node.type in {"comment", "string", "string_start", "string_content", "escape_sequence"}:
        #                 continue

        #             match = False

        #             if   ch == ")": isComplete[0] -= 1
        #             elif ch == "}": isComplete[1] -= 1
        #             elif ch == "]": isComplete[2] -= 1

        #             while dStack:
        #                 opening, blockNumber, position = dStack.pop()

        #                 if ch == PAIR_BRACE[opening]:
        #                     match = True
        #                     level = len(dStack)
        #                     color = RAINBOW_COLORS[level % len(RAINBOW_COLORS)]
        #                     dFormat.setForeground(color)

        #                     tempBrackets.update({
        #                         (blockNumber, position) : color,
        #                         (blockNo, i)     : color
        #                     })

        #                     break

        #             if not match:
        #                 tempBrackets.update({
        #                     (blockNo, i) : QColor("#FF0000")
        #                 })
        #     # print("IsComplete Mid =", isComplete)
        #     if any(i != 0 for i in isComplete):
        #             if blockNo not in self.incompleteStacks:
        #                 self.incompleteStacks.append(blockNo)
        #     elif blockNo in self.incompleteStacks:
        #         self.incompleteStacks.remove(blockNo)

        # # print("MID incomplete stacks =", self.incompleteStacks)

        # for blockNo in self.incompleteStacks:
        #     # print("POST")
        #     compList = [0, 0, 0]
        #     if blockNo in affectedBlocks or blockNo < maxBlocNo:
        #         continue

        #     block = self.document().findBlockByNumber(blockNo)
        #     blockPosition = block.position()
        #     text = block.text()

        #     for i, ch in enumerate(text):
        #         absPosition = blockPosition + i
        #         if ch in {"(", "{", "["}:
        #             node = self.fetchCursorNode(position = absPosition)
        #             if  node.type in {"comment", "string", "string_start", "string_content", "escape_sequence"}:
        #                 continue

        #             if   ch == "(": compList[0] += 1
        #             elif ch == "{": compList[1] += 1
        #             elif ch == "[": compList[2] += 1

        #             dStack.append((ch, blockNo, i))
        #             tempBrackets.update({
        #                 (blockNo, i) : QColor("#FF0000")
        #             })

        #         elif ch in {")", "}", "]"}:
        #             node = self.fetchCursorNode(position = absPosition)
        #             if node.type in {"comment", "string", "string_start", "string_content", "escape_sequence"}:
        #                 continue

        #             match = False

        #             if   ch == ")": compList[0] -= 1
        #             elif ch == "}": compList[1] -= 1
        #             elif ch == "]": compList[2] -= 1

        #             while dStack:
        #                 opening, blockNumber, position = dStack.pop()

        #                 if ch == PAIR_BRACE[opening]:
        #                     match = True
        #                     level = len(dStack)
        #                     color = RAINBOW_COLORS[level % len(RAINBOW_COLORS)]

        #                     tempBrackets.update({
        #                         (blockNumber, position) : color,
        #                         (blockNo, i)            : color
        #                     })

        #                     break

        #             if not match:
        #                 tempBrackets.update({
        #                     (blockNo, i) : QColor("#FF0000")
        #                 })

        #     if compList == [0, 0, 0]:
        #         nowComplete.append(blockNo)

        # self.incompleteStacks[:] = [
        #     blockNo
        #     for blockNo in self.incompleteStacks
        #     if blockNo not in nowComplete
        # ]

        # print("POST incomplete stacks =", self.incompleteStacks)
        # self.brackets = tempBrackets

        # for key in self.brackets:
        #     print(key, self.brackets[key])

    def fetchCursorNode(self, Tree = None, position =  None):
        if Tree is None: Tree = self.Language.syntax.Tree
        cursor = self.textCursor()
        if position is None:
            position = cursor.position()
        elif position < 0:
            position += 1
        text = self.toPlainText()
        row, col16, col8, byteOffset = self.QOffsetToCoords(text, position)
        byteOffset = max(0, byteOffset - 1)

        node = Tree.root_node.named_descendant_for_byte_range(byteOffset, byteOffset)

        return node

    def inputMethodEvent(self, event):
        if event.commitString():
            cursor = self.textCursor()
            cursor.insertText(event.commitString())
            self.setTextCursor(cursor)

    def SignalManager(self):
        # self.fileOpenShortcut = QShortcut(QKeySequence("Ctrl + O"), self)
        # self.fileOpenShortcut.activated      .connect(self.openFile)
        self.blockCountChanged               .connect(self.updateLineData)
        self.cursorPositionChanged           .connect(self.updateLineData)
        self.cursorPositionChanged           .connect(self.HighLightLine)
        self.cursorPositionChanged           .connect(lambda: self.viewport().update())
        self.selectionChanged                .connect(self.HighLightLine)
        self.updateRequest                   .connect(self.LineWidget.update)
        self.selectionChanged                .connect(self.updateSelection)
        self.textChanged                     .connect(self.reportChange)
        self.LineWidget.scrollEmit           .connect(super().wheelEvent)
        self.LineWidget.lineSelectEmit       .connect(self.selectLine)
        self.document().contentsChange       .connect(self.incrementCapture)
        self.textChanged                     .connect(self.LSPDocConfig)
        self.Language.client.diagnosticsReady.connect(self.diagnose)
        self.document().contentsChange       .connect(lambda _, rem, add: self.Context.fetchCursorContext(chRem = rem, chAdd = add))
        self.floating_vbar.rangeChanged      .connect(self.updateFloatingScrollBars)
        self.floating_hbar.rangeChanged      .connect(self.updateFloatingScrollBars)
        self.floating_hbar.valueChanged      .connect(lambda: self.viewport().update())
        self.highlightTimer.timeout          .connect(self.executeHighlight)

    def StyleConfig(self):
        self.setStyleSheet(
            """
            QPlainTextEdit {
                border: none;
                background-color: transparent;
                selection-background-color: rgba(17, 168, 225, 100);
            }
            """
        )

    def keyPressEvent(self, e):
        cursor = self.textCursor()
        ch = e.text()

        app = QApplication.instance()
        app.setCursorFlashTime(0)

        # if ch not in {'', '\t'}:
        #     if cursor.hasSelection():
        #         selectStartAt = self.Selection.FirstBlock.blockNumber()
        #         selectEndAt   = self.Selection.LastBlock.blockNumber()
        #         cursorAt      = selectStartAt

        #         del self.blockBracketStack[selectStartAt + 1 : selectEndAt + 1]
        #         del self.bracketMap[selectStartAt + 1 : selectEndAt + 1]

        #         if ch == '\r':
        #             self.blockBracketStack.insert((cursorAt + 1), [])
        #             self.bracketMap.insert((cursorAt + 1), {})

        #         elif ch == '\x16':
        #             pastedText = QGuiApplication.clipboard().text()
        #             linestoAdd = pastedText.count('\n')

        #             for _ in range(linestoAdd):
        #                 self.blockBracketStack.insert((cursorAt + 1), [])
        #                 self.bracketMap.insert((cursorAt + 1), {})

        #     else:
        #         if ch == '\r':
        #             self.blockBracketStack.insert((cursorAt + 1), [])
        #             self.bracketMap.insert((cursorAt + 1), {})

        #         elif ch == '\x08' and cursor.position() != 0 and cursor.atBlockStart():
        #             self.blockBracketStack.pop(cursorAt)
        #             self.bracketMap.pop(cursorAt)

        #         elif ch == '\x7f' and (self.document().blockCount() > (cursorAt + 1)) and cursor.atBlockEnd():
        #             self.blockBracketStack.pop(cursorAt + 1)
        #             self.bracketMap.pop(cursorAt + 1)

        #         elif ch == '\x16':
        #             pastedText = QGuiApplication.clipboard().text()
        #             linestoAdd = pastedText.count("\n")

        #             for _ in range(linestoAdd):
        #                 self.blockBracketStack.insert((cursorAt + 1), [])
        #                 self.bracketMap.insert((cursorAt + 1), {})

        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            print("Delimiter Context =", self.Context.delimiter.stack)
            print("Node Type =", self.fetchCursorNode().type)

            text        = self.textCursor().block().text()
            match       = re.match(r"^[ \t]*", text)
            indentation = match.group(0) if match else ""

            self.Context.fetchCursorContext()
            node = self.fetchCursorNode()
            if node.type == "module":
                preText = text[:cursor.positionInBlock()]
                stripped = preText.rstrip(" \t")
                strippedPosition = len(stripped)
                node = self.fetchCursorNode(position = cursor.block().position() + strippedPosition)
                if node.type in INDENT:
                    nextIndent = LineIndent.Indent
                elif node.type in DEDENT:
                    nextIndent = LineIndent.Dedent
                else:
                    nextIndent = LineIndent.Keep
            elif node.type in INDENT:
                nextIndent = LineIndent.Indent
            elif node.type in DEDENT:
                nextIndent = LineIndent.Dedent
            else:
                nextIndent = LineIndent.Keep

            cursor.insertText("\n" + indentation)

            if   nextIndent == LineIndent.Indent: self.Indent(cursor.block())
            elif nextIndent == LineIndent.Dedent: self.unIndent(cursor.block())

            self._blink_reset_timer.start(50)
            return

        if e.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Right, Qt.Key.Key_Left):
            super().keyPressEvent(e)
            self.Context.fetchCursorContext()
            self._blink_reset_timer.start(50)
            return

        elif e.text() in PAIR_BRACE or e.text() in CLOSING_CHARS:
            if self.bracketInput(e.text()):
                self._blink_reset_timer.start(50)
                return

        elif e.key() == Qt.Key_Tab:
            if self.Selection.Select:
                self.BlockIndent()
                self._blink_reset_timer.start(50)
                return

            else:
                self.Indent(self.textCursor().block(), InPlace = True)
                self._blink_reset_timer.start(50)
                return

        elif e.key() == Qt.Key_Backspace:
            self.highlightDelay = 300
            cursor = self.textCursor()
            pos = cursor.position()
            ch = self.document().characterAt(pos - 1)
            if pos > 0 and ch in PAIR_BRACE:
                self.removeBracket(ch, pos)
                self._blink_reset_timer.start(50)
                return

            if not self.Selection.Select:
                cursor    = self.textCursor()
                blockText = cursor.block().text()
                preText   =  blockText[:cursor.positionInBlock()]
                uniqChars = set(preText)
                if not (uniqChars - {" ", "\t"}) and uniqChars:
                    self.unIndent(cursor.block(), InPlace = True)
                    self._blink_reset_timer.start(50)
                    return

        elif e.key() == Qt.Key_Backtab:
            if self.Selection.Select:
                self.BlockUnIndent()
                self._blink_reset_timer.start(50)
                return
            else:
                codeBlock = self.textCursor().block()
                self.unIndent(codeBlock)
                self._blink_reset_timer.start(50)
                return

        super().keyPressEvent(e)
        self._blink_reset_timer.start(50)

    def mousePressEvent(self, e):
        app = QApplication.instance()
        app.setCursorFlashTime(0)
        super().mousePressEvent(e)
        self._blink_reset_timer.start(50)
        # self.Context.fetchCursorContext()
        # for stackInput in self.blockBracketStack:
        #     print(stackInput)
        # print("------")
        if e.button() == Qt.RightButton:
            self.Language.syntax.printSyntax()
        node = self.fetchCursorNode(position = self.textCursor().position())
        # self.Language.syntax.printSyntax(node = node)
        # print(self.document().characterCount())
    
    def resizeEvent(self, e):
            super().resizeEvent(e)
            self.viewport().setGeometry(self.rect())
            self.updateFloatingScrollBars()

    def enterEvent(self, event):
        super().enterEvent(event)
        self.updateFloatingScrollBars()
        if self.floating_hbar.isVisible():
            self.vbar_anim.stop()
            self.vbar_anim.setDuration(10)
            self.vbar_anim.setStartValue(self.vbar_effect.opacity())
            self.vbar_anim.setEndValue(1.0)
            self.vbar_anim.start()

        if self.floating_vbar.isVisible():
            self.hbar_anim.stop()
            self.hbar_anim.setDuration(10)
            self.hbar_anim.setStartValue(self.hbar_effect.opacity())
            self.hbar_anim.setEndValue(1.0)
            self.hbar_anim.start()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        
        if self.floating_vbar.isVisible():
            self.vbar_anim.stop()
            self.vbar_anim.setDuration(500)  # 500 milliseconds fade
            self.vbar_anim.setStartValue(self.vbar_effect.opacity())
            self.vbar_anim.setEndValue(0.0)
            self.vbar_anim.start()

        # Fade out horizontal bar
        if self.floating_hbar.isVisible():
            self.hbar_anim.stop()
            self.hbar_anim.setDuration(500)
            self.hbar_anim.setStartValue(self.hbar_effect.opacity())
            self.hbar_anim.setEndValue(0.0)
            self.hbar_anim.start()

    def wheelEvent(self, e : QWheelEvent):
        deltaX = (e.angleDelta().x() / 120) * 10
        deltaY = (e.angleDelta().y() / 120) * 10
        self.scrollOffset += deltaY
        print(self.scrollOffset)

        event = QWheelEvent(
            e.position(),
            e.globalPosition(),
            QPoint(e.pixelDelta().x(), 0),
            QPoint(e.angleDelta().x(), 0),
            e.buttons(),
            e.modifiers(),
            e.phase(),
            e.inverted(),
            e.source(),
        )
        super().wheelEvent(event)

    def updateFloatingScrollBars(self, *args):
        bar_thickness = 10
        self.viewport().setGeometry(self.rect())

        v_needed = self.floating_vbar.maximum() > self.floating_vbar.minimum()
        h_needed = self.floating_hbar.maximum() > self.floating_hbar.minimum()

        if v_needed:
            self.floating_vbar.show()
            self.floating_vbar.setGeometry(
                self.width() - bar_thickness,
                0,
                bar_thickness,
                self.height() - (bar_thickness if h_needed else 0),
            )
            self.floating_vbar.raise_()
        else:
            self.floating_vbar.hide()

        if h_needed:
            self.floating_hbar.show()
            self.floating_hbar.setGeometry(
                0,
                self.height() - bar_thickness,
                self.width() - (bar_thickness if v_needed else 0),
                bar_thickness,
            )
            self.floating_hbar.raise_()
        else:
            self.floating_hbar.hide()

    def _restore_blinking(self):
            # Restore default system blink time (usually ~1000ms in Qt)
            app = QApplication.instance()
            app.setCursorFlashTime(1000)

    def _on_vbar_fade_finished(self):
        if self.vbar_effect.opacity() == 0.0:
            self.floating_vbar.hide()

    def _on_hbar_fade_finished(self):
        if self.hbar_effect.opacity() == 0.0:
            self.floating_hbar.hide()
        
    def styleConfig(self, widget : QScrollBar):
        orientation = "vertical" if widget.orientation() == Qt.Orientation.Vertical else "horizontal"
        dimension = "width: 8px;" if orientation == "vertical" else "height: 8px;"
        subdimension = "height: 0px;" if orientation == "vertical" else "width: 0px;"
        mindimension = "min-height: 25px;" if orientation == "vertical" else "min-width: 25px;"
        widget.setStyleSheet(f"""
            QScrollBar:{orientation} {{
                background: rgba(18, 19, 20, 128);
                {dimension}
                margin: 0px;
                border: none;
            }}

            QScrollBar::handle:{orientation} {{
                background: rgba(100, 100, 100, 128);
                {mindimension}
                border: none;
                border-radius: 3px;
            }}

            QScrollBar::handle:{orientation}:hover {{
                background: rgba(130, 130, 130, 130);
            }}

            QScrollBar::add-page:{orientation},
            QScrollBar::sub-page:{orientation} {{
                background: rgba(18, 19, 20, 0);
            }}

            QScrollBar::add-line:{orientation},
            QScrollBar::sub-line:{orientation} {{
                {subdimension}
                background: none;
                border: none;
            }}
            """)


class CodeSelection:
    def __init__(self):
        self.Select     = False
        self.FirstBlock = None
        self.LastBlock  = None

    def resetSelection(self):
        self.Select     = False
        self.FirstBlock = None
        self.LastBlock  = None


class delimiterContext:
    def __init__(self):
        self.level = 0
        self.stack = []


class scopeContext:
    def __init__(self):
        pass


class CodeContext:

    def __init__(self, editor : CodeEditor):
        self.editor    = editor
        self.delimiter = delimiterContext()
        self.string    = None
        self.comment   = None
        self.scope     = None
        self.syntax    = None

    def fetchCursorContext(self, fresh = False, chRem = 0, chAdd = 0):
        if chAdd > 0 or chRem > 0:
            for delim in self.editor.FreshDelimiters:
                delim.end += chAdd
                delim.end -= chRem

        if not self.editor.delimiterCreation:
            cursor = self.editor.textCursor()
            position = cursor.position()
            node = self.editor.fetchCursorNode(position = position)

            prevDelimiters = self.delimiter.stack.copy()

            self.delimiter.stack.clear()
            self.delimiter.level = 0

            _, _, _, byteOffset = self.editor.QOffsetToCoords(text = self.editor.toPlainText(), offset = position)

            while node:
                if node.type in DELIMITER:
                    nodeStart = node.start_byte
                    nodeEnd   = node.end_byte
                    
                    # print("type =", node.type)
                    # print("start =", nodeStart)
                    # print("stop =", nodeEnd)
                    if nodeStart < byteOffset < nodeEnd:
                        self.delimiter.stack.append(node)
                        self.delimiter.level += 1
                node = node.parent

            self.delimiter.stack.reverse()

            # print("offset =", position)

            self.editor.FreshDelimiters.Dlist[:] = [
                delim
                for delim in self.editor.FreshDelimiters
                if delim.start < byteOffset < delim.end
            ]

            # for delim in self.editor.FreshDelimiters:
            #     print("(", delim.start, delim.end, ")")

            # print("level =", self.delimiter.level)

            removedNests = set(prevDelimiters) - set(self.delimiter.stack)
            # print("removed =", removedNests)
            # print("prev =", prevDelimiters)
            # print("current =", self.delimiter.stack)
            if not fresh:
                if self.editor.FreshDelimitCount > self.delimiter.level:
                    self.editor.FreshDelimitCount -= len(removedNests)
                    self.editor.FreshDelimitCount  = max(self.editor.FreshDelimitCount, 0)
            
            # print("Nfresh =", self.editor.FreshDelimitCount)
            # print("------")


class Squiggle:
    def __init__(self):
        self.start = Coordinate()
        self.end   = Coordinate()


class Coordinate:
    def __init__(self, lineId = 0, chId = 0):
        self.row = lineId
        self.col = chId


class codeLanguage:

    def nextIndentation(self, cursor : QTextCursor):
        raise NotImplementedError

    def commentSyntax(self):
        raise NotImplementedError

    def keyWords(self):
        raise NotImplementedError


class syntaxTree:

    def __init__(self, language):
        self.Parser = Parser(language)
        self.Source = b""
        self.Tree   = self.Parser.parse(self.Source)
    
    def sourceUpdate(self, source, incremental = True):
        self.Source =  source
        if incremental: self.Tree = self.Parser.parse(self.Source, self.Tree)
        else: self.Tree = self.Parser.parse(self.Source)

    def printSyntax(self, node = None, prefix="", is_last=True, is_root=True, field_name=None):
        if node is None: node = self.Tree.root_node
        if is_root:
            print(f"({node.type})")
            new_prefix = ""
        else:
            connector = "└── " if is_last else "├── "
            field_str = f"{field_name}: " if field_name else ""
            print(f"{prefix}{connector}{field_str}({node.type}, {repr(node.text.decode())})")

            new_prefix = prefix + ("    " if is_last else "│   ")

        children = []
        cursor = node.walk()
        if cursor.goto_first_child():
            while True:
                if cursor.node.is_named:
                    children.append((cursor.node, cursor.field_name))
                if not cursor.goto_next_sibling():
                    break
            cursor.goto_parent()

        # Recursion
        for i, (child_node, child_field) in enumerate(children):
            is_last_child = i == (len(children) - 1)
            self.printSyntax(child_node, new_prefix, is_last_child, False, child_field)

    def printAllNodes(self, node = None):
        if node is None: node = self.Tree.root_node
        print(node.type, node.start_point, node.end_point)

        for child in node.children:
            self.printAllNodes(child)


class PythonLanguage(codeLanguage):

    def __init__(self, document, editor : QPlainTextEdit):
        super().__init__()
        self.syntax      = syntaxTree(Language(tree_sitter_python.language()))
        self.Highlighter = syntaxHighlighter(document, self.syntax, editor)
        self.client      = LSPClient()

    def nextIndentation(self, cursor : QTextCursor):
            block = cursor.block()
            preText = block.text()[:cursor.positionInBlock()]
    
            """
                rstrip ---> goes to the end of a string (preText in this case) and strips off
                the characters passed in its argument from the right (" " and "\t" in this case) INPLACE
                endswith operates on a string checks if its last element is the passed argument or not
            """
            decision = preText.rstrip(" \t").endswith(":")
            if decision:
                return LineIndent.Indent
            else:
                return LineIndent.Keep

    def commentSyntax(self):
        return "#"


class syntaxHighlighter(QSyntaxHighlighter):

    def __init__(self, document : QPlainTextEdit.document, syntax, editor : CodeEditor):
        super().__init__(document)
        self.syntax = syntax
        self.editor = editor
        self.dStack = []

        self.prevBlockNo = 0
        self.prevdStackLen = 0

    def highlightBlock(self, text):
        if not self.syntax.Tree: return

        blockNumber = self.currentBlock().blockNumber()
        blockPosition = self.currentBlock().position()

        # print("BLOCK NO =", blockNumber)

        line_bytes = text.encode("utf-8")

        alpha = 255

        stack = [(self.syntax.Tree.root_node, False)]

        while stack:
            currentNode, parent_dimmed = stack.pop()

            start_row = currentNode.start_point[0]
            end_row = currentNode.end_point[0]

            if end_row < blockNumber or start_row > blockNumber:
                continue

            is_dimmed = parent_dimmed
            if not is_dimmed and currentNode.parent:
                for sibling in currentNode.parent.children:
                    if sibling.type in DEDENT:
                        if currentNode.start_byte > sibling.end_byte:
                            is_dimmed = True
                            break

            for child in reversed(currentNode.children):
                stack.append((child, is_dimmed))

            if currentNode.child_count > 0 and currentNode.type not in {"string", "string_start", "string_content", "string_end"}:
                continue

            opacity = "80" if is_dimmed else "FF"
            alpha   = 128 if is_dimmed else 255

            format = QTextCharFormat()
            format.setFontItalic(False)
            applied = False

            if currentNode.type in VS_CONTROL_FLOW:
                format.setForeground(QColor(f"#{opacity}C586C0"))
                applied = True
            elif currentNode.type in VS_KEYWORDS:
                format.setForeground(QColor(f"#{opacity}569cd6"))
                applied = True
            elif currentNode.type in {"import", "from", "as"}:
                format.setForeground(QColor(f"#{opacity}c586c0"))
                applied = True
            elif currentNode.type in {"def", "class", "lambda"}:
                format.setForeground(QColor(f"#{opacity}fe7b72"))
                applied = True
            elif currentNode.type in {"integer", "float", "complex"}:
                format.setForeground(QColor(f"#{opacity}B5CEA8"))
                applied = True
            elif currentNode.type == "escape_sequence":
                format.setForeground(QColor(f"#{opacity}d7ba7d"))
                applied = True
            elif currentNode.type in {"string", "string_start", "string_content", "string_end"}:
                format.setForeground(QColor(f"#{opacity}a5d6ff"))
                applied = True
            elif currentNode.type == "comment":
                format.setForeground(QColor(f"#{opacity}8b949e")) 
                format.setFontItalic(True)
                applied = True

            elif currentNode.type == "identifier":
                parent = currentNode.parent
                applied = True
                if parent is not None:
                    node_text = currentNode.text.decode('utf-8') if isinstance(currentNode.text, bytes) else currentNode.text
                    if parent.type == "call" and parent.child_by_field_name("function") == currentNode:
                        color = QColor("#d2a8f7")
                        format.setForeground(QColor(f"#{opacity}d2a8f7"))
                    elif parent.type == "function_definition":
                        if parent.child_by_field_name("name") == currentNode:
                            if node_text in DUNDER_METHODS:
                                color = QColor("#dadaa9")
                                format.setForeground(QColor(f"#{opacity}dadaa9"))
                            else:
                                color = QColor("#d2a8f7")
                                format.setForeground(QColor(f"#{opacity}d2a8f7"))
                    elif parent.type in {"parameters", "typed_parameter", "default_parameter", "typed_default_parameter"}:
                        if node_text != 'self':
                            color = QColor("#fda556")
                            format.setForeground(QColor(f"#{opacity}fda556"))
                    elif parent.type == "list_splat_pattern":
                        Superparent = parent.parent
                        if Superparent.type in {"parameters", "typed_parameter", "default_parameter", "typed_default_parameter"}:
                            color = QColor("#fda556")
                            format.setForeground(QColor(f"#{opacity}fda556"))
                    elif parent.type == "type":
                        color = QColor("#4dc1a0")
                        format.setForeground(QColor(f"#{opacity}4dc1a0"))
                    elif parent.type == "class_definition" and parent.child_by_field_name("name") == currentNode:
                        color = QColor("#4dc1a0")
                        format.setForeground(QColor(f"#{opacity}4dc1a0"))
                    elif parent.type == "decorator":
                        color = QColor("#4bc9b0")
                        format.setForeground(QColor(f"#{opacity}4bc9b0"))
                    elif  parent.type == "dotted_name":
                        color = QColor("#4bc9b0")
                        format.setForeground(QColor(f"#{opacity}4bc9b0"))
                    elif parent.type == "argument_list":
                        color = QColor("#4dc1a0")
                        format.setForeground(QColor(f"#{opacity}4dc1a0"))
                    else:
                        if node_text == "self":
                            color = QColor("#FFFFFF")
                            format.setForeground(QColor(f"#{opacity}569cd6"))
                        is_enclosing_param = False
                        ancestor = parent

                        if parent.child_by_field_name("attribute") != currentNode:
                            while ancestor is not None and ancestor.type != "function_definition":
                                ancestor = ancestor.parent
                            if ancestor is not None:
                                params_node = ancestor.child_by_field_name("parameters")
                                if params_node is not None:
                                    for i in range(params_node.child_count):
                                        param = params_node.child(i)
                                        # Handle simple identifiers or typed parameters
                                        if param.type in {"identifier", "typed_parameter", "default_parameter"}:
                                            # If it's a complex parameter, we need to dig one level deeper to the identifier
                                            param_id = param if param.type == "identifier" else param.child(0)
                                            if param_id and param_id.type == "identifier":
                                                p_text = param_id.text.decode('utf-8') if isinstance(param_id.text, bytes) else param_id.text
                                                if p_text == node_text and node_text != "self":
                                                    is_enclosing_param = True
                                                    break
                        if is_enclosing_param:
                                color = QColor("#fda556")
                                format.setForeground(QColor(f"#{opacity}fda556")) # Orange for body parameters
                        else:
                            color = QColor("#FFFFFF")
                            format.setForeground(QColor(f"#{opacity}FFFFFF")) # Default light blue
                        # format.setForeground(QColor(f"#{opacity}FFFFFF"))
                else:
                    color = QColor("#9CDCFE")
                    format.setForeground(QColor(f"#{opacity}9CDCFE"))

            elif currentNode.type in VS_OPERATORS:
                format.setForeground(QColor(f"#{opacity}FFFFFF"))
                applied = True

            elif currentNode.type in {"(", "{", "[", ")", "}", "]"}:
                format.setForeground(QColor(f"#{opacity}FF0000"))
                applied = True

            else:
                format.setForeground(QColor(f"#{opacity}FFFFFF"))
                applied = True

            if applied:
                start_byte_col = currentNode.start_point[1] if start_row == blockNumber else 0
                end_byte_col = currentNode.end_point[1] if end_row == blockNumber else len(line_bytes)
                
                try:
                    startChar = len(line_bytes[:start_byte_col].decode("utf-8").encode("utf-16-le")) // 2
                    endChar = len(line_bytes[:end_byte_col].decode("utf-8").encode("utf-16-le")) // 2
                    
                    length = endChar - startChar
                    if length > 0:
                        self.setFormat(startChar, length, format)
                except UnicodeDecodeError:
                    pass

        dFormat = QTextCharFormat()
        if self.currentBlock().userData():
            for position, data in self.currentBlock().userData().bracketMap.items():
                color = data[1]
                color.setAlpha(alpha)
                dFormat.setForeground(color)
                self.setFormat(position, 1, dFormat)


class readBufferState(Enum):
    HEADER = auto()
    BODY   = auto()


class readBuffer:
    def __init__(self):
        self.Buffer = b""
        self.State  = readBufferState.HEADER


class LSPClient(QObject):
    diagnosticsReady = Signal(object, object, object)

    def __init__(self, parent = None):
        super().__init__(parent)
        self.process      = QProcess()
        self.OutputBuffer = readBuffer()
        self.BodyLength   = 0
        self.ReceivedLen  = 0
        self.Document     = LSPDocument(None, "python", "")

        self.process.readyReadStandardOutput.connect(self.readOutput)
        self.process.readyReadStandardError.connect(self.readError)

        self.startLSP()

        initialize = {
            "jsonrpc"   : "2.0",
            "id"        : 1,
            "method"    : "initialize",
            "params"    : {
                "processId"     : os.getpid(),
                "clientInfo"    : {
                    "name"      : "Sagittarius A*",
                    "version"   : "1.0"
                },
                "rootUri"       : None,
                "capabilities"  : {}

            }
        }
        self.sendMessage(initialize)

        initialized = {
            "jsonrpc": "2.0",
            "method": "initialized",
            "params": {}
        }
        self.sendMessage(initialized)

    def startLSP(self):
        command = "pyright-langserver.cmd" if sys.platform == "win32" else "pyright-langserver"
        self.process.start(
            command,
            ["--stdio"]
        )

        started = self.process.waitForStarted()
        print(f"{BLUE}waiting{RESET}")

        if not started:
            print("Failed to start language server")
            return

        print("Language server started")

    def sendMessage(self, message):
        body = json.dumps(message).encode("utf-8")
        header = (
            f"Content-Length: {len(body)}\r\n"
            f"\r\n"
        ).encode("ascii")

        self.process.write(header + body)

    def didOpenMessage(self):
        message = {
            "jsonrpc"   : "2.0",
            "method"    : "textDocument/didOpen",
            "params"    : {
                "textDocument"  : {
                    "uri"           : self.Document.uri,
                    "languageId"    : self.Document.languageId,
                    "version"       : self.Document.version,
                    "text"          : self.Document.text
                }
            }
        }

        self.sendMessage(message)

    def didChangeMessage(self):
        message = {
            "jsonrpc"   : "2.0",
            "method"    : "textDocument/didChange",
            "params"    : {
                "textDocument"  : {
                    "uri"       : self.Document.uri,
                    "version"   : self.Document.version
                },
                "contentChanges": [
                    {
                        "text"  : self.Document.text
                    }
                ]
            }
        }

        self.sendMessage(message)

    def readOutput(self):
        data = bytes(self.process.readAllStandardOutput())
        self.OutputBuffer.Buffer += data

        self.checkBuffer()

    def checkBuffer(self):
        # print("----------")
        # print("Buffer State =", self.OutputBuffer.State, "\r\n")
        # print(self.OutputBuffer.Buffer.decode("utf-8"), "\r\n\r\n")
        # print("----------")
        while True:
            if self.OutputBuffer.State == readBufferState.HEADER:
                headerEnd = self.OutputBuffer.Buffer.find(b"\r\n\r\n")
                if headerEnd != -1:
                    Header = self.OutputBuffer.Buffer[:headerEnd].decode("utf-8")
                    self.OutputBuffer.Buffer = self.OutputBuffer.Buffer[(headerEnd + 4):]       # <---- "\r\n\r\n" (total 4 bytes)
                    # print("Header =", Header)
                    for line in Header.split("\r\n"):
                        if line.startswith("Content-Length"):
                            self.BodyLength = int(line.split(":")[1].strip())
                            break
                    self.OutputBuffer.State = readBufferState.BODY
                    if len(self.OutputBuffer.Buffer) == 0:
                        break

            if self.OutputBuffer.State == readBufferState.BODY:
                if len(self.OutputBuffer.Buffer) >= self.BodyLength:
                    Body = self.OutputBuffer.Buffer[:self.BodyLength].decode("utf-8")
                    self.OutputBuffer.Buffer = self.OutputBuffer.Buffer[self.BodyLength:]
                    # print("Body =", json.loads(Body))
                    self.readMessage(message = Body)

                    self.OutputBuffer.State = readBufferState.HEADER
                    if self.OutputBuffer.Buffer: continue
                    else: break
                else: break

    def readMessage(self, message):
        message = json.loads(message)
        if "id" in message:
            if "result" in message:
                self.handleResponse(message)
            elif "error" in message:
                self.handleError(message)

        elif "method" in message:
            self.handleNotification(message)

    def handleError(self, message):
        print("Error:\r\n", message, "\r\n\r\n")

    def handleResponse(self, message):
        # print("Response:\r\n", message, "\r\n\r\n")
        pass

    def handleNotification(self, message):
        # print("Notification:\r\n", message, "\r\n\r\n")
        if message["method"] == "textDocument/publishDiagnostics":
            self.handleDiagnostics(message)

    def handleDiagnostics(self, message):
        colorMap = {
            0   : f"{RED}",
            1   : f"{GREEN}",
            2   : f"{YELLOW}",
            3   : f"{BLUE}"
        }
        params  = message["params"]
        uri     = params["uri"]
        version = params["version"]
        diagnostics = params["diagnostics"]
        # print(version, uri)

        self.diagnosticsReady.emit(uri, version, diagnostics)

        for i, diagnostic in enumerate(diagnostics):
            k = i % 4
            # print(colorMap[k], diagnostic)
            # print(f"{RESET}")
        pass

    def readError(self):
        print("Error")


class LSPDocument:
    def __init__(self, uri, languageId, text):
        self.uri        = uri
        self.languageId = languageId
        self.text       = text
        self.version    = 1


class MasterEditor(QWidget):

    def __init__(self, parent):
        super().__init__(parent)
        self.editor = CodeEditor(self)
        self.LayoutConfig()

    def LayoutConfig(self):
        Layout = QHBoxLayout(self)
        Layout.setContentsMargins(0, 0, 0, 0)
        Layout.setSpacing(0)
        Layout.addWidget(self.editor.LineWidget)
        Layout.addWidget(self.editor)


# class  MainWindow(QMainWindow):
#     def __init__(self, parent = None):
#         super().__init__(parent)
#         Main = MasterEditor(self)
#         self.setWindowTitle("anNaylam")
#         self.setCentralWidget(Main)


# app = QApplication([])
# window = MainWindow()

# window.show()

# screen = app.primaryScreen()
# avail = screen.availableGeometry()

# title_bar_height = window.frameGeometry().height() - window.geometry().height()
# border_width = window.frameGeometry().width() - window.geometry().width()

# target_width = (avail.width() // 2) - border_width
# target_height = avail.height() - title_bar_height

# window.resize(target_width, target_height)
# window.move(avail.x() + (avail.width() // 2), avail.y())

# sys.exit(app.exec())
