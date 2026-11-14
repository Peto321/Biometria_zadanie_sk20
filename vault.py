"""
Zamykanie a odomykanie priecinka "trezor" cez opravnenia Windows
"""

import csv
import io
import os
import subprocess
import sys

VAULT_DIR = "trezor"
IS_WINDOWS = os.name == "nt"

DENY_RIGHTS = "(OI)(CI)(RD,WD,AD,REA,WEA,X,DC,DE)"

README_TEXT = "Do tohto priecinka vloz tajne subory.\n"


def vault_path():
    return os.path.abspath(VAULT_DIR)


def _run(args):
    """Spusti prikaz, vrati (kod, stdout, stderr) ako text"""
    kwargs = {"creationflags": 0x08000000} if IS_WINDOWS else {}  # CREATE_NO_WINDOW
    r = subprocess.run(args, capture_output=True, **kwargs)
    return (
        r.returncode,
        r.stdout.decode(errors="replace").strip(),
        r.stderr.decode(errors="replace").strip(),
    )


def _current_sid():
    """SID aktualneho pouzivatela"""
    code, out, err = _run(["whoami", "/user", "/fo", "csv", "/nh"])
    if code != 0:
        raise RuntimeError(f"Nepodarilo sa zistit SID pouzivatela: {err or out}")
    row = next(csv.reader(io.StringIO(out)))
    return row[-1].strip()


def ensure_vault():
    """Vytvori priecinok trezoru ak neexistuje"""
    path = vault_path()
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, "README.txt"), "w", encoding="utf-8") as f:
            f.write(README_TEXT)


def status():
    """Vrati 'missing' 'locked' 'unlocked'"""
    path = vault_path()
    if not os.path.isdir(path):
        return "missing"
    try:
        os.listdir(path)
        return "unlocked"
    except PermissionError:
        return "locked"


def lock():
    """Zamkne trezor"""
    if not IS_WINDOWS:
        return False, "Zamykanie funguje len na Windows"
    try:
        ensure_vault()
        if status() == "locked":
            return True, "Trezor je uz zamknuty"
        sid = _current_sid()
        code, out, err = _run(["icacls", vault_path(), "/deny", f"*{sid}:{DENY_RIGHTS}"])
        if code != 0:
            return False, f"Zamknutie zlyhalo: {err or out}"
        return True, "Trezor bol zamknuty"
    except Exception as e:
        return False, f"Zamknutie zlyhalo: {e}"


def unlock():
    """Odomkne trezor"""
    if not IS_WINDOWS:
        return False, "Odomykanie funguje len na Windows"
    try:
        ensure_vault()
        if status() == "unlocked":
            return True, "Trezor je uz odomknuty"
        sid = _current_sid()
        code, out, err = _run(["icacls", vault_path(), "/remove:d", f"*{sid}"])
        if code != 0:
            return False, f"Odomknutie zlyhalo (icacls): {err or out}"
        return True, "Trezor bol odomknuty"
    except Exception as e:
        return False, f"Odomknutie zlyhalo: {e}"


def open_vault():
    """Otvori trezor v Prieskumniku"""
    path = vault_path()
    if hasattr(os, "startfile"):
        os.startfile(path)
    else:
        print(f"Trezor je tu: {path}")


if __name__ == "__main__":
    """Nudzove otvaranie"""
    commands = {"status": lambda: (True, status()), "lock": lock, "unlock": unlock}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        print("Pouzitie: python vault.py status | lock | unlock")
        sys.exit(1)
    ok, msg = commands[sys.argv[1]]()
    print(msg)
    sys.exit(0 if ok else 1)
