from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from app.services.scanner_prefs import ScannerDevice

# WIA image format GUIDs
_WIA_FORMAT_BMP = "{B96B3CAB-0728-11D3-9D7B-0000F81EF32E}"
_WIA_FORMAT_JPEG = "{B96B3CAE-0728-11D3-9D7B-0000F81EF32E}"
_WIA_FORMAT_PNG = "{B96B3CAF-0728-11D3-9D7B-0000F81EF32E}"
_WIA_FORMAT_TIFF = "{B96B3CB1-0728-11D3-9D7B-0000F81EF32E}"

# Item property IDs
_WIA_IPS_CUR_INTENT = 6146  # 1=Color, 2=Grayscale, 4=Text
_WIA_IPS_XRES = 6147
_WIA_IPS_YRES = 6148


def list_scanners() -> list[ScannerDevice]:
    if sys.platform != "win32":
        return []
    try:
        import pythoncom
        import win32com.client
    except ImportError:
        return []

    devices: list[ScannerDevice] = []
    pythoncom.CoInitialize()
    try:
        manager = win32com.client.Dispatch("WIA.DeviceManager")
        for info in manager.DeviceInfos:
            if info.Type != 1:
                continue
            device_id = str(info.DeviceID)
            name = str(info.Properties("Name").Value)
            devices.append(ScannerDevice(device_id=device_id, name=name))
    except Exception:
        return []
    finally:
        pythoncom.CoUninitialize()
    return devices


def _set_prop(item, prop_id: int, value) -> None:
    try:
        item.Properties(prop_id).Value = value
    except Exception:
        pass


def _extension_for_format(format_id: str) -> str:
    fmt = (format_id or "").upper()
    if "B96B3CAE" in fmt:
        return ".jpg"
    if "B96B3CAF" in fmt:
        return ".png"
    if "B96B3CB1" in fmt:
        return ".tif"
    return ".bmp"


def _transfer_image(item, dialog) -> object:
    """Acquire one page; prefer JPEG for smaller files and reliable PIL convert."""
    errors: list[str] = []
    for fmt in (_WIA_FORMAT_JPEG, _WIA_FORMAT_BMP, _WIA_FORMAT_PNG, _WIA_FORMAT_TIFF, None):
        try:
            if dialog is not None and fmt is not None:
                return dialog.ShowTransfer(item, fmt, False)
            if fmt is not None:
                return item.Transfer(fmt)
            return item.Transfer()
        except Exception as exc:
            errors.append(str(exc))
            continue
    detail = "; ".join(errors[:3]) if errors else "unknown error"
    raise RuntimeError(f"Scanner transfer failed ({detail})")


def scan_images(device_id: str) -> list[Path]:
    if sys.platform != "win32":
        raise RuntimeError("Direct scanner capture is only supported on Windows.")

    try:
        import pythoncom
        import win32com.client
    except ImportError as exc:
        raise RuntimeError(
            "Scanner support requires pywin32. Use 'Add from File' after scanning to disk."
        ) from exc

    pythoncom.CoInitialize()
    try:
        manager = win32com.client.Dispatch("WIA.DeviceManager")
        device = None
        for info in manager.DeviceInfos:
            if str(info.DeviceID) == device_id:
                device = info.Connect()
                break
        if device is None:
            raise RuntimeError(
                "Selected scanner was not found. Click Select Scanner and choose it again."
            )

        if device.Items.Count < 1:
            raise RuntimeError("Scanner has no scan source. Check the device is powered on.")

        item = device.Items[1]
        _set_prop(item, _WIA_IPS_CUR_INTENT, 1)  # Color
        _set_prop(item, _WIA_IPS_XRES, 200)
        _set_prop(item, _WIA_IPS_YRES, 200)

        try:
            dialog = win32com.client.Dispatch("WIA.CommonDialog")
        except Exception:
            dialog = None

        image = _transfer_image(item, dialog)
        if image is None:
            raise RuntimeError("Scan cancelled or returned no image.")

        format_id = ""
        try:
            format_id = str(image.FormatID)
        except Exception:
            format_id = ""
        ext = _extension_for_format(format_id)
        temp_dir = Path(tempfile.mkdtemp(prefix="hms_scan_"))
        output = temp_dir / f"scan_001{ext}"
        image.SaveFile(str(output))
        if not output.exists() or output.stat().st_size <= 0:
            raise RuntimeError("Scanner saved an empty file.")
        return [output]
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Scan failed: {exc}") from exc
    finally:
        pythoncom.CoUninitialize()
