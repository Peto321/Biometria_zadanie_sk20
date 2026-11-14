import os
import sys
import tkinter as tk
from tkinter import messagebox

import vault

FACE_PATH = os.path.join("reference_faces", "owner.jpg")
KEYSTROKE_PROFILE_PATH = "keystroke_profile.json"

STEP_NAMES = [
    "1. Overenie tváre",
    "2. Liveness: úsmev / žmurknutie",
    "3. Heslo + rytmus písania",
]
SYMBOLS = {"idle": "–", "run": "…", "ok": "✔", "fail": "✘"}
COLORS = {"idle": "gray", "run": "#b8860b", "ok": "#1a8f3c", "fail": "#c0392b"}


def profile_exists():
    return os.path.exists(FACE_PATH) and os.path.exists(KEYSTROKE_PROFILE_PATH)


class App:
    def __init__(self, root):
        self.root = root
        root.title("Biometrický trezor")
        root.geometry("400x500")
        root.resizable(False, False)

        tk.Label(root, text="Biometrický trezor", font=("Segoe UI", 16, "bold")).pack(pady=(15, 2))

        self.btn_add = tk.Button(root, text="Pridať profil", width=26, height=2,
                                 command=self.add_profile)
        self.btn_add.pack(pady=(15, 5))
        self.btn_unlock = tk.Button(root, text="Odomknúť trezor", width=26, height=2,
                                    command=self.unlock)
        self.btn_unlock.pack(pady=5)
        self.btn_lock = tk.Button(root, text="Zamknúť trezor", width=26, height=2,
                                  command=self.lock_vault)
        self.btn_lock.pack(pady=5)
        self.vault_state_var = tk.StringVar()
        tk.Label(root, textvariable=self.vault_state_var,
                 font=("Segoe UI", 10, "bold")).pack(pady=(4, 0))

        tester_frame = tk.Frame(root)
        tester_frame.pack(pady=(8, 0))
        tk.Label(tester_frame, text="Používateľ:", fg="gray").pack(side="left")
        self.tester_var = tk.StringVar(value="owner")
        tk.Entry(tester_frame, textvariable=self.tester_var, width=14).pack(side="left", padx=5)

        steps_frame = tk.LabelFrame(root, text="Priebeh odomykania", padx=10, pady=5)
        steps_frame.pack(fill="x", padx=20, pady=12)
        self.step_labels = []
        for name in STEP_NAMES:
            row = tk.Frame(steps_frame)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=name, anchor="w").pack(side="left")
            sym = tk.Label(row, text=SYMBOLS["idle"], fg=COLORS["idle"],
                           font=("Segoe UI", 12, "bold"))
            sym.pack(side="right")
            self.step_labels.append(sym)

        self.status_var = tk.StringVar(value="Pripravený.")
        tk.Label(root, textvariable=self.status_var, wraplength=360, fg="#333").pack(pady=5)

        if not profile_exists():
            self.status_var.set("Profil neexistuje klikni na „Pridať profil“")
        else:
            vault.lock()  
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.refresh_vault_state()


    def set_busy(self, busy):
        state = "disabled" if busy else "normal"
        self.btn_add.config(state=state)
        self.btn_unlock.config(state=state)
        self.btn_lock.config(state=state)
        self.root.update()

    def set_status(self, text):
        self.status_var.set(text)
        self.root.update()

    def set_step(self, index, state):
        self.step_labels[index].config(text=SYMBOLS[state], fg=COLORS[state])
        self.root.update()

    def reset_steps(self):
        for i in range(len(self.step_labels)):
            self.set_step(i, "idle")

    def refresh_vault_state(self):
        text = {
            "locked": "Trezor zamknutý",
            "unlocked": "Trezor Odomknutý",
            "missing": "Trezor sa vytvorí prihlásením",
        }[vault.status()]
        self.vault_state_var.set(text)

    def lock_vault(self):
        if not profile_exists():
            messagebox.showwarning("Chýba profil",
                                   parent=self.root)
            return
        ok, msg = vault.lock()
        self.set_status(msg)
        self.refresh_vault_state()
        if not ok:
            messagebox.showwarning("Zamknutie zlyhalo", msg, parent=self.root)

    def on_close(self):
        if profile_exists():
            ok, msg = vault.lock()
            if not ok:
                messagebox.showwarning("Trezor sa nepodarilo zamknúť", msg, parent=self.root)
        self.root.destroy()

    
    def add_profile(self):
        if profile_exists():
            if not messagebox.askyesno("Profil už existuje",
                                       "Profil už existuje. Chceš ho prepísať novým?",
                                       parent=self.root):
                return

        old_face = None
        if os.path.exists(FACE_PATH):
            with open(FACE_PATH, "rb") as f:
                old_face = f.read()

        self.reset_steps()
        self.set_busy(True)
        success = False
        try:
            self.set_status("Krok 1/2: snímanie tváre")
            import register_face
            if not register_face.main():
                self.set_status("Registrácia tváre zrušená")
                return

            self.set_status("Krok 2/2: vytvor heslo a napíš ho 10-krát")
            import keystroke
            if not keystroke.enroll(master=self.root):
                self.set_status("Registrácia hesla zrušená, profil nebol vytvorený")
                return

            success = True
            self.set_status("Profil bol úspešne vytvorený")
            messagebox.showinfo("Info","Profil bol vytvorený", parent=self.root)
        except Exception as e:
            self.set_status(f"Chyba: {e}")
        finally:
            if not success:  
                if old_face is not None:
                    with open(FACE_PATH, "wb") as f:
                        f.write(old_face)
                elif os.path.exists(FACE_PATH):
                    os.remove(FACE_PATH)
            self.set_busy(False)

    
    def unlock(self):
        if not profile_exists():
            messagebox.showwarning("Chýba profil", "Najprv pridaj profil", parent=self.root)
            return

        if vault.status() == "unlocked":
            self.set_status("Trezor už je odomknutý")
            vault.open_vault()
            return

        tester = self.tester_var.get().strip() or "owner"
        self.reset_steps()
        self.set_busy(True)
        try:
            # Krok 1: tvar
            self.set_step(0, "run")
            self.set_status("Krok 1: pozri sa do kamery")
            import access_control
            ok = access_control.verify_identity(tester=tester)
            self.set_step(0, "ok" if ok else "fail")
            if not ok:
                self.set_status("tvár nezodpovedá profilu")
                return

            
            self.set_step(1, "run")
            self.set_status("Krok 2: splň výzvu v okne kamery")
            import liveness
            ok = liveness.run_liveness_check()
            self.set_step(1, "ok" if ok else "fail")
            if not ok:
                self.set_status("liveness test zlyhal")
                return

            
            self.set_step(2, "run")
            self.set_status("Krok 3: napíš heslo")
            import keystroke
            ok = keystroke.verify_keystroke(tester=tester, master=self.root)
            self.set_step(2, "ok" if ok else "fail")
            if not ok:
                self.set_status("heslo alebo rytmus písania nesedí")
                return

            ok, msg = vault.unlock()
            if not ok:
                self.set_status(msg)
                messagebox.showwarning("Odomknutie zlyhalo", msg, parent=self.root)
                return
            vault.open_vault()
            self.set_status("Trezor je odomknutý")
        except Exception as e:
            self.set_status(f"Chyba: {e}")
        finally:
            self.set_busy(False)
            self.refresh_vault_state()


def setup_runtime():
    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)

    if getattr(sys, "frozen", False) or sys.stdout is None or sys.stderr is None:
        log = open(os.path.join(base_dir, "app.log"), "a", buffering=1, encoding="utf-8")
        sys.stdout = log
        sys.stderr = log


def main():
    setup_runtime()
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
