"""
Biometria cez dynamiku pisania na klavesnici
"""

import argparse
import csv
import hashlib
import hmac
import json
import os
import time
from datetime import datetime

import numpy as np

# --- Nastavenia ---
PROFILE_PATH = "keystroke_profile.json"
LOG_PATH = "keystroke_attempts_log.csv"
N_SAMPLES = 10          # kolko krat sa pise heslo pri registracii
THRESHOLD_K = 2.0       # prah = priemer + K * smerodajna odchylka z leave-one-out
MIN_SD = 0.01           # spodny limit smerodajnej odchylky, proti deleniu ~0
MIN_PASSWORD_LEN = 8
PBKDF2_ITERATIONS = 200_000


def hash_password(password, salt=None, iterations=PBKDF2_ITERATIONS):
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return {"salt": salt.hex(), "hash": digest.hex(), "iterations": iterations}


def check_password(password, record):
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(record["salt"]),
        record["iterations"],
    )
    return hmac.compare_digest(digest.hex(), record["hash"])


def extract_features(seq):
    presses = [k["press"] for k in seq]
    dwell = [k["release"] - k["press"] for k in seq]
    flight = [presses[i + 1] - presses[i] for i in range(len(seq) - 1)]
    return dwell + flight


def scaled_distance(x, mean, sd):
    x, mean, sd = np.asarray(x), np.asarray(mean), np.asarray(sd)
    return float(np.mean(np.abs(x - mean) / np.maximum(sd, MIN_SD)))


def build_profile(samples, k=THRESHOLD_K):
    X = np.asarray(samples, dtype=float)
    n = len(X)
    if n < 3:
        raise ValueError("Potrebne su aspon 3 vzorky")

    mean = X.mean(axis=0)
    sd = X.std(axis=0, ddof=1)

    loo = []
    for i in range(n):
        others = np.delete(X, i, axis=0)
        loo.append(scaled_distance(X[i], others.mean(axis=0), others.std(axis=0, ddof=1)))
    loo = np.array(loo)

    threshold = float(loo.mean() + k * loo.std(ddof=1))
    return {
        "mean": mean.tolist(),
        "sd": sd.tolist(),
        "n_samples": n,
        "k": k,
        "loo_mean": float(loo.mean()),
        "loo_std": float(loo.std(ddof=1)),
        "threshold": threshold,
    }


def score_attempt(profile, features):
    return scaled_distance(features, profile["mean"], profile["sd"])


def run_capture_window(title, instruction, samples_needed=1, expected=None, master=None):
    
    """Otvori okno s polom na heslo a zaznamenava casy klaves."""
    
    import tkinter as tk

    root = tk.Toplevel(master) if master is not None else tk.Tk()
    root.title(title)
    root.geometry("480x250")
    root.resizable(False, False)

    tk.Label(root, text=instruction, wraplength=440, justify="left").pack(pady=(15, 5))
    progress_var = tk.StringVar(value="")
    status_var = tk.StringVar(value="Napis heslo a stlac Enter")
    tk.Label(root, textvariable=progress_var, font=("Segoe UI", 11, "bold")).pack()
    entry = tk.Entry(root, show="*", width=40, font=("Segoe UI", 12))
    entry.pack(pady=10)
    tk.Label(root, textvariable=status_var, fg="gray", wraplength=440).pack()

    state = {"seq": [], "down": {}, "corrected": False}
    results = []
    cancelled = {"value": False}

    if expected is not None:
        progress_var.set(f"Vzorka 0 / {samples_needed}")

    def reset():
        entry.delete(0, "end")
        state["seq"] = []
        state["down"] = {}
        state["corrected"] = False

    def finish():
        text = entry.get()
        seq = state["seq"]
        valid = (
            not state["corrected"]
            and len(text) > 0
            and len(seq) == len(text)
            and all(item["release"] is not None for item in seq)
        )
        features = extract_features(seq) if valid else None
        reset()

        if expected is None:  # rezim overenia
            results.append({"text": text, "features": features})
            root.destroy()
            return

        # rezim registracie
        if text == expected and features is not None:
            results.append({"text": text, "features": features})
            progress_var.set(f"Vzorka {len(results)} / {samples_needed}")
            status_var.set("OK, pis dalej.")
            if len(results) >= samples_needed:
                root.destroy()
        else:
            status_var.set(
                "Neplatny pokus"
                "Skus znova"
            )

    def on_press(event):
        if event.keysym in ("Return", "KP_Enter"):
            finish()
            return "break"
        keycode = event.keycode
        if keycode in state["down"]:  
            return
        now = time.perf_counter()
        if event.keysym in ("BackSpace", "Delete", "Left", "Right", "Home", "End"):
            state["corrected"] = True
        if len(event.char) == 1 and event.char.isprintable():
            item = {"press": now, "release": None}
            state["seq"].append(item)
            state["down"][keycode] = item
        else:  
            state["down"][keycode] = None

    def on_release(event):
        item = state["down"].pop(event.keycode, None)
        if item is not None and item["release"] is None:
            item["release"] = time.perf_counter()

    def on_cancel():
        cancelled["value"] = True
        root.destroy()

    entry.bind("<KeyPress>", on_press)
    entry.bind("<KeyRelease>", on_release)
    entry.bind("<<Paste>>", lambda e: "break")  
    entry.bind("<Control-v>", lambda e: "break")
    root.protocol("WM_DELETE_WINDOW", on_cancel)
    entry.focus_force()
    if master is not None:
        root.transient(master)
        root.wait_visibility()
        root.grab_set()
        master.wait_window(root)
    else:
        root.mainloop()

    return None if cancelled["value"] else results


def ask_new_password(master=None):
    """Dialog na vytvorenie hesla 2 krat"""
    import tkinter as tk
    from tkinter import messagebox, simpledialog

    owns_root = master is None
    if owns_root:
        root = tk.Tk()
        root.withdraw()
    else:
        root = master
    try:
        while True:
            pw = simpledialog.askstring(
                "Vytvorenie hesla",
                f"Zadaj nove heslo min. {MIN_PASSWORD_LEN} znakov\n",
                show="*",
                parent=root,
            )
            if pw is None:
                return None
            if len(pw) < MIN_PASSWORD_LEN:
                messagebox.showwarning("Slabe heslo", f"Minimalne {MIN_PASSWORD_LEN} znakov.", parent=root)
                continue
            pw2 = simpledialog.askstring("Vytvorenie hesla", "Zopakuj heslo:", show="*", parent=root)
            if pw2 is None:
                return None
            if pw != pw2:
                messagebox.showwarning("Nezhoda", "Hesla sa nezhoduju skus znova.", parent=root)
                continue
            return pw
    finally:
        if owns_root:
            root.destroy()


def enroll(n_samples=N_SAMPLES, k=THRESHOLD_K, master=None):
    password = ask_new_password(master)
    if password is None:
        print("Registracia zrusena")
        return False

    samples = run_capture_window(
        title="Registracia - dynamika pisania",
        instruction=(
            f"Napis svoje heslo {n_samples}-krat"
        ),
        samples_needed=n_samples,
        expected=password,
        master=master,
    )
    if samples is None or len(samples) < n_samples:
        print("Registracia zrusena - nedostatok vzoriek")
        return False

    profile = build_profile([s["features"] for s in samples], k=k)
    profile["password"] = hash_password(password)

    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)

    print(f"Profil ulozeny do {PROFILE_PATH}")
    print(f"  pocet vzoriek:   {profile['n_samples']}")
    print(f"  pocet priznakov: {len(profile['mean'])}")
    print(f"  leave-one-out:   priemer {profile['loo_mean']:.3f}, sd {profile['loo_std']:.3f}")
    print(f"  prah (K={k}):     {profile['threshold']:.3f}")
    return True


def log_attempt(tester, password_ok, score, threshold, accepted):
    new_file = not os.path.exists(LOG_PATH)
    with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["timestamp", "tester", "password_ok", "score", "threshold", "accepted"])
        w.writerow([
            datetime.now().isoformat(timespec="seconds"),
            tester,
            int(password_ok),
            "" if score is None else f"{score:.4f}",
            f"{threshold:.4f}",
            int(accepted),
        ])


def verify_keystroke(tester="owner", log=True, master=None):
    if not os.path.exists(PROFILE_PATH):
        print("Profil neexistuje")
        return False

    with open(PROFILE_PATH, encoding="utf-8") as f:
        profile = json.load(f)

    attempts = run_capture_window(
        title="Overenie - dynamika pisania",
        instruction="Napis heslo a zatlac Enter",
        samples_needed=1,
        expected=None,
        master=master,
    )
    if not attempts:
        print("Overenie zrusene")
        return False

    attempt = attempts[0]
    threshold = profile["threshold"]

    if not check_password(attempt["text"], profile["password"]):
        print("Nespravne heslo.")
        if log:
            log_attempt(tester, False, None, threshold, False)
        return False

    if attempt["features"] is None:
        print("Neplatny pokus skus znova.")
        return False

    score = score_attempt(profile, attempt["features"])
    accepted = score <= threshold
    print(f"[Keystroke] skore: {score:.3f}  (prah: {threshold:.3f})")
    print("Heslo aj rytmus pisania sedia" if accepted
          else "Rytmus pisania nezodpoveda profilu")
    if log:
        log_attempt(tester, True, score, threshold, accepted)
    return accepted


def main():
    parser = argparse.ArgumentParser(description="Keystroke dynamics")
    parser.add_argument("command", choices=["enroll", "verify"])
    parser.add_argument("--tester", default="owner",
                        help="meno osoby ktora sa prihlasuje")
    parser.add_argument("--samples", type=int, default=N_SAMPLES)
    parser.add_argument("--k", type=float, default=THRESHOLD_K)
    args = parser.parse_args()

    if args.command == "enroll":
        if args.samples < 5:
            parser.error("--samples musi byt aspon 5")
        enroll(args.samples, args.k)
    else:
        verify_keystroke(args.tester)


if __name__ == "__main__":
    main()
