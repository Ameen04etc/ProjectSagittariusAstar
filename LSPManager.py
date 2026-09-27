from pathlib import Path
from importlib.resources import path
from typing import Dict, List, Optional
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
    QEasingCurve, QUrl)
from PySide6.QtGui import (QPainter, QColor, QPen,
    QPixmap, QFont, QMouseEvent,
    QImage, QCursor, QPainterPath,
    QStandardItemModel, QStandardItem,
    QFontMetrics, QKeySequence, QTextFormat,
    QTextCursor, QTextBlock, QShortcut,
    QTextCharFormat, QSyntaxHighlighter, QGuiApplication,
    QTextBlockUserData, QFontMetricsF, QWheelEvent,
    QAbstractTextDocumentLayout, QMouseEvent)
from enum import Enum, auto
from typing import cast
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

class WorkSpaceRegistry:
    EDITOR_MARKERS = {
            ".sagittarius",       # Custom folder
            ".vscode",            # VS Code config directory
        }

    # 2. Project / Tooling configuration indicators
    PROJECT_MARKERS = {
        # Python-specific
        "pyproject.toml",
        "pyrightconfig.json",
        "setup.py",
        "setup.cfg",
        "requirements.txt",
        "Pipfile",
        # Language agnostic / Monorepos
        "package.json",
        "Cargo.toml",
        "CMakeLists.txt",
    }

    # 3. Version control marker (strongest boundary indicator)
    VCS_MARKERS = {
        ".git",
        ".hg",
    }
    

    def __init__(self):
        self.workSpace : Dict[Path, List[Path]] = {}

    def addWorkSpace(self, root : str, linked : List[str] = None):
        rootPath = Path(root).resolve()
        linkedPaths = [Path(p).resolve() for p in (linked or [])]
        self.workSpace.update({rootPath : linkedPaths})

    def findWorkSpace(self, filePath : str) -> Optional[Path]:
        if not filePath:
            return None
        absPath = Path(filePath).resolve()
        parentDirs = list(absPath.parents)
        for parent in parentDirs:
            if parent in self.workSpace:
                return parent

            for root, linkedDirs in self.workSpace.items():
                for linked in linkedDirs:
                    if parent == linked:
                        return root

        home = Path.home()
        stopDirs = {
            home,
            home / "Desktop",
            home / "Downloads",
            home / "Documents",
            home / "Pictures",
            home / "Videos",
            home / "Music"
        }

        for parent in parentDirs:
            if parent in stopDirs or parent == parent.parent:
                break

        return None


class LSPManager(QObject):
    diagnosticsReady = Signal(str, object, list)    # uri, version, diagnostics

    def __init__(self, parent = None):
        super().__init__(parent)
        self.workSpaceRegistry = WorkSpaceRegistry()
        self.servers : Dict[str, LSPClient] = {}
        self.fileToserver : Dict[str, LSPClient] = {}

    def serverConfig(self, filePath : Optional[str]) -> LSPClient:
        if not filePath:
            workSpace = "__STANDALONE__"
            workSpaceURI =  None
            folders = None
        else:
            workSpace = self.workSpaceRegistry.findWorkSpace(filePath = filePath)
            if workSpace:
                workSpaceURI = workSpace.as_uri()
                folders = [{
                    "uri" : workSpaceURI,
                    "name" : workSpace.name
                }]

                for linked in self.workSpaceRegistry.workSpace.get(workSpace, []):
                    folders.append({
                        "uri" : linked.as_uri(),
                        "name" : linked.name
                    })

            else:
                workSpace = "__STANDALONE__"
                workSpaceURI = None
                folders = None

        if workSpace not in self.servers:
            client = LSPClient(parent = self, rootURI = workSpaceURI, workSpaceFolders = folders)
            client.diagnosticsReady.connect(self.diagnosticsReady.emit)
            self.servers.update({workSpace : client})

        server = self.servers[workSpace]
        if filePath:
            self.fileToserver.update({Path(filePath).as_uri() : server})

        return server


class LSPClient(QObject):
    diagnosticsReady = Signal(str, object, list)    # uri, version, diagnostics

    def __init__(self, parent = None, rootURI = None, workSpaceFolders = None):
        super().__init__(parent)
        self.process      = QProcess(self)
        self.OutputBuffer = readBuffer()
        self.BodyLength   = 0

        self.rootURI       = rootURI
        self.parentFolders = workSpaceFolders

        self.process.readyReadStandardOutput.connect(self.readOutput)
        self.process.readyReadStandardError.connect(self.readError)

        self.startLSP()
        self.sendInitialize()

    def startLSP(self):
        command = "pyright-langserver.cmd" if sys.platform == "win32" else "pyright-langserver"
        self.process.start(
            command,
            ["--stdio"]
        )

        started = self.process.waitForStarted()

        if not started:
            print("Failed to start language server")
            return
        print(f"{RED}Lang Srever Started{RESET}")

    def sendMessage(self, message):
        body = json.dumps(message).encode("utf-8")
        header = (
            f"Content-Length: {len(body)}\r\n"
            f"\r\n"
        ).encode("ascii")

        self.process.write(header + body)

    def sendInitialize(self):
        initialize = {
            "jsonrpc" : "2.0",
            "id"      : 1,
            "method"  : "initialize",
            "params"  : {
                "processId"   : os.getpid(),
                "clientInfo"  : {
                    "name"    : "Sagittarius A*",
                    "version" : "1.0"
                },
                "rootUri"         : self.rootURI,
                "workspaceFolders": self.parentFolders,
                "capabilities"    : {
                    "workspace" : {
                        "workspaceFolders" : True
                    }
                }
            }
        }
        self.sendMessage(initialize)

        initialized = {
            "jsonrpc": "2.0",
            "method": "initialized",
            "params": {}
        }
        self.sendMessage(initialized)

    def didOpenMessage(self, uri: str, languageId: str, version: int, text: str):
        message = {
            "jsonrpc"   : "2.0",
            "method"    : "textDocument/didOpen",
            "params"    : {
                "textDocument"  : {
                    "uri"           : uri,
                    "languageId"    : languageId,
                    "version"       : version,
                    "text"          : text
                }
            }
        }
        self.sendMessage(message)

    def didChangeMessage(self, uri: str, version: int, text: str):
        message = {
            "jsonrpc"   : "2.0",
            "method"    : "textDocument/didChange",
            "params"    : {
                "textDocument"  : {
                    "uri"       : uri,
                    "version"   : version
                },
                "contentChanges": [
                    {
                        "text"  : text
                    }
                ]
            }
        }
        self.sendMessage(message)

    def didCloseMessage(self, uri: str):
        message = {
            "jsonrpc": "2.0",
            "method": "textDocument/didClose",
            "params": {
                "textDocument": {"uri": uri}
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



class readBufferState(Enum):
    HEADER = auto()
    BODY   = auto()


class readBuffer:
    def __init__(self):
        self.Buffer = b""
        self.State  = readBufferState.HEADER
