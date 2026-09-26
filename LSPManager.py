from pathlib import Path
from typing import Dict, List, Optional
from PySide6.QtCore import QObject, Signal
from anNaylam import *

class WorkSpaceRegistry:
    def __init__(self):
        self.workSpace : Dict[Path : List[Path]] = {}

    def addWorkSpace(self, root : str, linked : List[str] = None):
        rootPath = Path(root).resolve()
        linkedPaths = [Path(p).resolve() for p in (linked or [])]
        self.workSpace.update({rootPath : linkedPaths})

    def findWorkSpace(self, filePath : str) -> Optional[Path]:
        if not filePath:
            return None
        absPath = Path(filePath).resolve()
        for root, linked in self.workSpace.items():
            if root == absPath.parent or root in absPath.parents:
                return root
            for lp in linked:
                if lp == absPath.parent or lp in absPath.parents:
                    return root

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
            rootURI =  None
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
            client = LSPClient()
            client.diagnosticsReady.connect(self.diagnosticsReady.emit)
            self.servers.update({workSpace : client})

        server = self.servers[workSpace]
        if filePath:
            self.fileToserver.update({Path(filePath).as_uri() : server})

        return server
