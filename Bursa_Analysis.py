"""
Bursa Malaysia Stock Screener — GUI Edition
Double-click to run. No terminal needed.
"""

import threading
import time
import datetime
import queue
import sys
import os
import tkinter as tk
from tkinter import ttk, font
import pandas as pd
import yfinance as yf

from bursa_tickers import BURSA_TICKERS, search_bursa

# ── Colour palette (dark terminal aesthetic) ─────────────────────────────────
BG          = "#0d1117"
BG2         = "#161b22"
BG3         = "#21262d"
ACCENT      = "#f0b429"   # amber
ACCENT2     = "#58a6ff"   # blue
GREEN       = "#3fb950"
RED         = "#f85149"
TEXT        = "#e6edf3"
TEXT_DIM    = "#8b949e"
BORDER      = "#30363d"


# ═════════════════════════════════════════════════════════════════════════════
# Worker — runs in background thread, posts updates via queue
# ═════════════════════════════════════════════════════════════════════════════

def check_shariah(info):
    non_shariah = ["gambling","casino","brewery","distillery","tobacco",
                   "alcohol","liquor","wine","beer","betting"]
    industry = (info.get("industry") or "").lower()
    sector   = (info.get("sector")   or "").lower()
    for kw in non_shariah:
        if kw in industry or kw in sector:
            return "N"
    return ""

def compute_sma(hist, period):
    if hist is None or len(hist) < period:
        return None
    return round(hist["Close"].rolling(window=period).mean().iloc[-1], 4)

def compute_adr(hist, days=20):
    if hist is None or len(hist) < days:
        return None
    recent = hist.tail(days)
    return round(((recent["High"] - recent["Low"]) / recent["Low"] * 100).mean(), 2)

def compute_performance(hist, days):
    if hist is None or len(hist) < days:
        return None
    cur, past = hist["Close"].iloc[-1], hist["Close"].iloc[-days]
    return round(((cur - past) / past) * 100, 2) if past else None

def fetch_one(code, name, retries=2):
    symbol = f"{code}.KL"
    for attempt in range(retries):
        try:
            stock = yf.Ticker(symbol)
            hist  = stock.history(period="1y")
            if hist.empty:
                return None
            latest = hist.iloc[-1]
            info   = stock.info or {}
            c = round(latest.get("Close", 0), 4)
            return {
                "Code": code,
                "Name": info.get("shortName", name),
                "Sector": info.get("sector", ""),
                "Open":  round(latest.get("Open", 0), 4),
                "High":  round(latest.get("High", 0), 4),
                "Low":   round(latest.get("Low",  0), 4),
                "Close": c,
                "SMA20":  compute_sma(hist, 20),
                "SMA50":  compute_sma(hist, 50),
                "SMA200": compute_sma(hist, 200),
                "Shariah": check_shariah(info),
                "Price":   c,
                "ADR%":    compute_adr(hist, 20),
                "Perf 5D%":  compute_performance(hist, 5),
                "Perf 1M%":  compute_performance(hist, 20),
                "Perf 3M%":  compute_performance(hist, 60),
                "EPS":     info.get("trailingEps", ""),
                "P/E":     info.get("trailingPE", info.get("forwardPE", "")),
                "Volume":  int(latest.get("Volume", 0)),
                "Mkt Cap": info.get("marketCap", ""),
            }
        except Exception:
            if attempt < retries - 1:
                time.sleep(2)
    return None

def worker(tickers, q, stop_event):
    total   = len(tickers)
    results = []
    failed  = []
    start   = time.time()

    q.put(("total", total))

    for i, (code, name) in enumerate(tickers, 1):
        if stop_event.is_set():
            q.put(("stopped", len(results), len(failed), time.time() - start))
            return

        q.put(("progress", i, code, name))

        data = fetch_one(code, name)
        if data:
            results.append(data)
            q.put(("log", "ok", f"{code}  {name[:30]}  →  RM {data['Close']}"))
        else:
            failed.append(code)
            q.put(("log", "fail", f"{code}  {name[:30]}  →  no data"))

        if i % 5 == 0:
            time.sleep(1)

    # Save CSV
    df = pd.DataFrame(results)
    df["Mkt Cap"] = pd.to_numeric(df["Mkt Cap"], errors="coerce")
    df = df.sort_values("Mkt Cap", ascending=False, na_position="last")

    ts       = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"bursa_screener_{ts}.csv"

    # Save next to the executable / script
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    filepath = os.path.join(os.path.dirname(base) if getattr(sys, 'frozen', False)
                            else base, filename)
    df.to_csv(filepath, index=False, encoding="utf-8-sig")

    elapsed = time.time() - start
    q.put(("done", results, failed, elapsed, filepath, df))


# ═════════════════════════════════════════════════════════════════════════════
# GUI
# ═════════════════════════════════════════════════════════════════════════════

class BursaApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Bursa Screener")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(780, 580)

        self._q          = queue.Queue()
        self._stop       = threading.Event()
        self._running    = False
        self._total      = 0

        self._build_ui()
        self.after(100, self._poll)

    # ── UI Layout ────────────────────────────────────────────────────────────
    def _build_ui(self):
        # Fonts
        try:
            mono = font.Font(family="JetBrains Mono", size=10)
            head = font.Font(family="JetBrains Mono", size=13, weight="bold")
        except Exception:
            mono = font.Font(family="Courier", size=10)
            head = font.Font(family="Courier", size=13, weight="bold")

        # ── Header ───────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=BG2, pady=14)
        hdr.pack(fill="x")

        tk.Label(hdr, text="BURSA SCREENER",
                 bg=BG2, fg=ACCENT,
                 font=head).pack(side="left", padx=20)

        self._lbl_time = tk.Label(hdr, text="", bg=BG2, fg=TEXT_DIM,
                                  font=mono)
        self._lbl_time.pack(side="right", padx=20)
        self._tick_clock()

        # ── Controls ─────────────────────────────────────────────────────────
        ctrl = tk.Frame(self, bg=BG, pady=10, padx=16)
        ctrl.pack(fill="x")

        tk.Label(ctrl, text="Limit (0 = all):", bg=BG, fg=TEXT_DIM,
                 font=mono).grid(row=0, column=0, sticky="w")
        self._entry_limit = tk.Entry(ctrl, width=8, bg=BG3, fg=TEXT,
                                     insertbackground=ACCENT,
                                     relief="flat", font=mono,
                                     highlightthickness=1,
                                     highlightbackground=BORDER,
                                     highlightcolor=ACCENT)
        self._entry_limit.insert(0, "0")
        self._entry_limit.grid(row=0, column=1, padx=(6, 20), pady=2)

        tk.Label(ctrl, text="Search:", bg=BG, fg=TEXT_DIM,
                 font=mono).grid(row=0, column=2, sticky="w")
        self._entry_search = tk.Entry(ctrl, width=16, bg=BG3, fg=TEXT,
                                      insertbackground=ACCENT,
                                      relief="flat", font=mono,
                                      highlightthickness=1,
                                      highlightbackground=BORDER,
                                      highlightcolor=ACCENT)
        self._entry_search.grid(row=0, column=3, padx=(6, 20), pady=2)

        self._btn_run = tk.Button(ctrl, text="  ▶  RUN  ",
                                  bg=ACCENT, fg="#0d1117",
                                  activebackground="#d4991f",
                                  activeforeground="#0d1117",
                                  relief="flat", font=head,
                                  cursor="hand2",
                                  command=self._start)
        self._btn_run.grid(row=0, column=4, padx=(0, 10))

        self._btn_stop = tk.Button(ctrl, text="  ■  STOP  ",
                                   bg=BG3, fg=RED,
                                   activebackground=BG2,
                                   activeforeground=RED,
                                   relief="flat", font=head,
                                   cursor="hand2",
                                   state="disabled",
                                   command=self._stop_run)
        self._btn_stop.grid(row=0, column=5)

        # ── Progress bar ─────────────────────────────────────────────────────
        prog_frame = tk.Frame(self, bg=BG, padx=16)
        prog_frame.pack(fill="x", pady=(4, 0))

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Bursa.Horizontal.TProgressbar",
                        troughcolor=BG3,
                        background=ACCENT,
                        bordercolor=BG,
                        lightcolor=ACCENT,
                        darkcolor=ACCENT)

        self._progressbar = ttk.Progressbar(prog_frame, style="Bursa.Horizontal.TProgressbar",
                                            orient="horizontal", mode="determinate",
                                            length=400)
        self._progressbar.pack(fill="x", pady=4)

        # ── Status row ───────────────────────────────────────────────────────
        stat = tk.Frame(self, bg=BG, padx=16)
        stat.pack(fill="x")

        self._lbl_current = tk.Label(stat, text="Ready.", bg=BG, fg=ACCENT2,
                                     font=mono, anchor="w")
        self._lbl_current.pack(side="left")

        self._lbl_eta = tk.Label(stat, text="", bg=BG, fg=TEXT_DIM,
                                 font=mono, anchor="e")
        self._lbl_eta.pack(side="right")

        # ── Log box ──────────────────────────────────────────────────────────
        log_frame = tk.Frame(self, bg=BG, padx=16, pady=8)
        log_frame.pack(fill="both", expand=True)

        tk.Label(log_frame, text="LOG", bg=BG, fg=TEXT_DIM,
                 font=mono).pack(anchor="w", pady=(0, 4))

        txt_frame = tk.Frame(log_frame, bg=BORDER, padx=1, pady=1)
        txt_frame.pack(fill="both", expand=True)

        self._log = tk.Text(txt_frame, bg=BG2, fg=TEXT,
                            font=mono, relief="flat",
                            state="disabled", wrap="none",
                            selectbackground=BG3)
        scroll_y = tk.Scrollbar(txt_frame, orient="vertical",
                                command=self._log.yview, bg=BG3)
        self._log.configure(yscrollcommand=scroll_y.set)
        scroll_y.pack(side="right", fill="y")
        self._log.pack(fill="both", expand=True)

        self._log.tag_config("ok",   foreground=GREEN)
        self._log.tag_config("fail", foreground=RED)
        self._log.tag_config("info", foreground=ACCENT2)
        self._log.tag_config("done", foreground=ACCENT)
        self._log.tag_config("dim",  foreground=TEXT_DIM)

        # ── Footer ───────────────────────────────────────────────────────────
        foot = tk.Frame(self, bg=BG2, pady=8)
        foot.pack(fill="x", side="bottom")

        self._lbl_status = tk.Label(foot, text="Idle",
                                    bg=BG2, fg=TEXT_DIM, font=mono)
        self._lbl_status.pack(side="left", padx=16)

        tk.Button(foot, text="✕  Close",
                  bg=BG2, fg=TEXT_DIM,
                  activebackground=BG3, activeforeground=RED,
                  relief="flat", font=mono,
                  cursor="hand2",
                  command=self._on_close).pack(side="right", padx=16)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Helpers ──────────────────────────────────────────────────────────────
    def _tick_clock(self):
        self._lbl_time.config(
            text=datetime.datetime.now().strftime("%Y-%m-%d  %H:%M:%S"))
        self.after(1000, self._tick_clock)

    def _log_write(self, msg, tag=""):
        self._log.configure(state="normal")
        self._log.insert("end", msg + "\n", tag)
        self._log.see("end")
        self._log.configure(state="disabled")

    def _log_clear(self):
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")

    # ── Start / Stop ─────────────────────────────────────────────────────────
    def _start(self):
        if self._running:
            return

        limit  = int(self._entry_limit.get() or 0)
        search = self._entry_search.get().strip()

        tickers = search_bursa(search) if search else list(BURSA_TICKERS)
        if limit > 0:
            tickers = tickers[:limit]

        self._log_clear()
        self._log_write(f"  Starting scan — {len(tickers)} tickers", "info")
        self._log_write(f"  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "dim")
        self._log_write("  " + "─" * 55, "dim")

        self._running = True
        self._stop.clear()
        self._progressbar["value"] = 0
        self._progressbar["maximum"] = len(tickers)
        self._btn_run.config(state="disabled")
        self._btn_stop.config(state="normal")
        self._lbl_status.config(text="Running…", fg=ACCENT)
        self._start_time = time.time()

        t = threading.Thread(target=worker,
                             args=(tickers, self._q, self._stop),
                             daemon=True)
        t.start()

    def _stop_run(self):
        self._stop.set()
        self._lbl_status.config(text="Stopping…", fg=RED)

    # ── Queue polling ─────────────────────────────────────────────────────────
    def _poll(self):
        try:
            while True:
                msg = self._q.get_nowait()
                kind = msg[0]

                if kind == "total":
                    self._total = msg[1]

                elif kind == "progress":
                    _, i, code, name = msg
                    self._progressbar["value"] = i
                    elapsed = time.time() - self._start_time
                    eta     = (elapsed / i) * (self._total - i) if i else 0
                    eta_str = f"{int(eta//60)}m {int(eta%60)}s"
                    self._lbl_current.config(
                        text=f"  [{i}/{self._total}]  {code}  {name[:30]}")
                    self._lbl_eta.config(text=f"ETA  {eta_str}  ")

                elif kind == "log":
                    _, tag, text = msg
                    prefix = "  ✓  " if tag == "ok" else "  ✗  "
                    self._log_write(prefix + text, tag)

                elif kind == "done":
                    _, results, failed, elapsed, filepath, df = msg
                    self._on_done(results, failed, elapsed, filepath, df)

                elif kind == "stopped":
                    _, fetched, fail_count, elapsed = msg
                    self._log_write("\n  " + "─" * 55, "dim")
                    self._log_write(f"  ■  Stopped by user.", "fail")
                    self._log_write(f"  Fetched so far: {fetched}  |  Failed: {fail_count}", "info")
                    self._log_write(f"  Elapsed: {int(elapsed//60)}m {int(elapsed%60)}s", "dim")
                    self._reset_controls()

        except queue.Empty:
            pass
        self.after(80, self._poll)

    def _on_done(self, results, failed, elapsed, filepath, df):
        self._progressbar["value"] = self._total
        elapsed_str = f"{int(elapsed//60)}m {int(elapsed%60)}s"

        self._log_write("\n  " + "─" * 55, "dim")
        self._log_write(f"  ✓  DONE!", "done")
        self._log_write(f"  Fetched : {len(results)} / {self._total}", "done")
        self._log_write(f"  Failed  : {len(failed)}"
                        + (f"  ({', '.join(failed[:5])}{'…' if len(failed)>5 else ''})" if failed else ""),
                        "fail" if failed else "dim")
        self._log_write(f"  Time    : {elapsed_str}", "info")
        self._log_write(f"  Saved   : {filepath}", "info")
        self._log_write("\n  Top 5 by Market Cap:", "done")

        for _, row in df.head(5).iterrows():
            mkt = f"{row['Mkt Cap']/1e9:.2f}B" if pd.notna(row.get("Mkt Cap")) else "-"
            self._log_write(
                f"    {str(row['Code']):<8}  {str(row['Name'])[:25]:<25}  RM {row['Close']:<8}  MktCap {mkt}",
                "ok")

        self._lbl_current.config(text="  Scan complete!")
        self._lbl_eta.config(text="")
        self._lbl_status.config(text=f"Done — {len(results)} counters saved", fg=GREEN)
        self._reset_controls()

    def _reset_controls(self):
        self._running = False
        self._btn_run.config(state="normal")
        self._btn_stop.config(state="disabled")

    def _on_close(self):
        self._stop.set()
        self.destroy()


# ═════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = BursaApp()
    app.geometry("900x640")
    app.mainloop()