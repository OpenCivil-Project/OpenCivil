from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QMessageBox

SERVER_NAME = "opencivil_ipc_v1"

class IPCManager(QObject):
    raise_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._server  = None   
        self._clients = []     
        self._socket  = None   

    def start_server(self):
        """Register this process as the primary. Call once, early in main()."""
        self._server = QLocalServer(self)
        QLocalServer.removeServer(SERVER_NAME)        
        self._server.listen(SERVER_NAME)
        self._server.newConnection.connect(self._on_new_connection)

    def _on_new_connection(self):
        sock = self._server.nextPendingConnection()
        self._clients.append(sock)
        sock.readyRead.connect(lambda: self._on_client_data(sock))
        sock.disconnected.connect(
            lambda: self._clients.remove(sock) if sock in self._clients else None
        )

    def send_secondary_ready(self):
        """Notify primary that we are a new secondary window (not a raise request)."""
        if self._socket:
            self._socket.write(b"SECONDARY_READY\n")
            self._socket.flush()
            self._socket.waitForBytesWritten(400)

    def _on_client_data(self, sock):
        data = bytes(sock.readAll()).decode("utf-8", errors="ignore").strip()
        if data == "RAISE":
            self.raise_requested.emit()

    def broadcast_logout(self):
        """Tell every connected secondary window that a logout happened."""
        for sock in list(self._clients):
            try:
                sock.write(b"LOGOUT\n")
                sock.flush()
            except Exception:
                pass

    def connect_to_primary(self) -> bool:
        """
        Try to reach an already-running instance.
        Returns True when a primary is found (caller should send_raise + exit).
        """
        sock = QLocalSocket(self)
        sock.connectToServer(SERVER_NAME)
        if sock.waitForConnected(500):
            self._socket = sock
            return True
        return False

    def send_raise(self):
        """Ask the primary to bring itself to the foreground."""
        if self._socket:
            self._socket.write(b"RAISE\n")
            self._socket.flush()
            self._socket.waitForBytesWritten(400)

    def listen_as_secondary(self, window):
        """
        Wire the logout listener for a window that connected as a secondary.
        'window' is the MainWindow instance.
        """
        def _on_data():
            raw = bytes(self._socket.readAll()).decode("utf-8", errors="ignore")
            if "LOGOUT" in raw:
                _handle_remote_logout(window)

        self._socket.readyRead.connect(_on_data)

def _handle_remote_logout(window):
    """
    Called when a secondary window receives a LOGOUT broadcast.
    Auto-saves if possible, asks for a path if not, then closes.
    """
    has_unsaved = window.model and not window.undo_stack.isClean()

    if not has_unsaved:
        window.close()
        return

    file_path = getattr(window.model, "file_path", None)

    if file_path:
        saved = window.on_save_model()
        msg = "Your work has been saved." if saved else "Auto-save failed — please check the file manually."
    else:
        saved = window.on_save_model()
        msg = (
            "Your work has been saved."
            if saved
            else "Your unsaved work was NOT saved (dialog was cancelled)."
        )

    box = QMessageBox(window)
    box.setWindowTitle("Session Ended")
    box.setText(
        f"You have been logged out from another window.\n\n"
        f"{msg}\n\n"
        f"This window will now close."
    )
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    box.exec()
    window.close()
