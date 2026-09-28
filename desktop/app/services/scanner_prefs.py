from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSettings

ORG = "HospitalManagement"
APP = "Desktop"


@dataclass(frozen=True)
class ScannerDevice:
    device_id: str
    name: str


class ScannerPreferences:
    def __init__(self) -> None:
        self._settings = QSettings(ORG, APP)

    def get_default(self) -> ScannerDevice | None:
        device_id = self._settings.value("scanner/device_id", "")
        name = self._settings.value("scanner/device_name", "")
        if device_id and name:
            return ScannerDevice(str(device_id), str(name))
        return None

    def set_default(self, device: ScannerDevice) -> None:
        self._settings.setValue("scanner/device_id", device.device_id)
        self._settings.setValue("scanner/device_name", device.name)
        self._settings.sync()
