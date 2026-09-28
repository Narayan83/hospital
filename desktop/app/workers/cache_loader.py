from PySide6.QtCore import QThread, Signal

from app.api_client.client import ApiClient
from app.services.master_cache import load_master_cache


class CacheLoaderThread(QThread):
    finished_ok = Signal()
    failed = Signal(str)

    def __init__(self, api: ApiClient):
        super().__init__()
        self._api = api

    def run(self) -> None:
        error = load_master_cache(self._api)
        if error:
            self.failed.emit(error)
        else:
            self.finished_ok.emit()
