#!/usr/bin/env python3
"""
J.A.R.V.I.S. — tworzy skrót na pulpicie Windows.

Uruchomienie (jednorazowo):
  python training/utworz_skrot.py

Tworzy ikonę "J.A.R.V.I.S." na pulpicie, która cicho uruchamia
serwer Ollama i interfejs graficzny (bez okna konsoli).
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
TRAINING = ROOT / "training"


def make_icon(ico_path: Path) -> bool:
    """Generuje ikonę w stylu arc reactor. Wymaga Pillow."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return False

    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = cy = size // 2

    d.ellipse([6, 6, size - 6, size - 6], fill=(18, 24, 44, 255))
    d.ellipse([6, 6, size - 6, size - 6], outline=(60, 140, 230, 255), width=12)
    d.ellipse([cx - 64, cy - 64, cx + 64, cy + 64], outline=(90, 170, 245, 255), width=7)
    d.ellipse([cx - 32, cy - 32, cx + 32, cy + 32], fill=(120, 200, 255, 255))

    img.save(ico_path, format="ICO",
             sizes=[(256, 256), (64, 64), (48, 48), (32, 32), (16, 16)])
    return True


def main() -> None:
    if sys.platform != "win32":
        print("[INFO] Ten skrypt tworzy skrót tylko na Windows.")
        return

    launcher = TRAINING / "jarvis_launch.vbs"
    if not launcher.exists():
        print(f"[BŁĄD] Brak launchera: {launcher}")
        print("       Pobierz najnowszą wersję: git pull")
        return

    ico = TRAINING / "jarvis.ico"
    has_icon = make_icon(ico)
    icon_line = f"$sc.IconLocation = '{ico}'" if has_icon else ""

    ps = f"""
$ws = New-Object -ComObject WScript.Shell
$desktop = $ws.SpecialFolders('Desktop')
$sc = $ws.CreateShortcut((Join-Path $desktop 'J.A.R.V.I.S..lnk'))
$sc.TargetPath = 'wscript.exe'
$sc.Arguments = '"{launcher}"'
$sc.WorkingDirectory = '{ROOT}'
{icon_line}
$sc.Description = 'J.A.R.V.I.S. - Osobisty Asystent AI'
$sc.Save()
"""

    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"[BŁĄD] Nie udało się utworzyć skrótu: {e.stderr}")
        return
    except FileNotFoundError:
        print("[BŁĄD] PowerShell niedostępny.")
        return

    print("[OK] Skrót 'J.A.R.V.I.S.' utworzony na pulpicie.")
    if has_icon:
        print(f"[OK] Ikona: {ico}")
    else:
        print("[INFO] Użyto ikony domyślnej.")
        print("       Dla własnej ikony: pip install pillow  (i uruchom ponownie)")


if __name__ == "__main__":
    main()
