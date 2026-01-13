# Project: Python TM Simulator (Standalone)
# Authors: Nicholas Chaudoir, Luis Diaz
# Date Complete: 12/6/2024
# This code borrowed heavily from the technical details available from ~https://morphett.info/turing/turing.html~, so we give thanks to the contributors at Morphett for their work. 

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import random
import re

MOVE = {"l": -1, "r": 1, "*": 0, "s": 0, "n": 0}
BLANK = "_"  # always

DEFAULT_PROGRAM = """; Example 1-tape machine: scan right, then halt
; Format (1-tape): state read write move next

0 0 0 r 0
0 1 1 r 0
0 _ _ * halt
"""

@dataclass
class Instruction:
    cur_state: str
    read: Tuple[str, ...]
    write: Tuple[str, ...]
    move: Tuple[str, ...]
    next_state: str
    breakpoint: bool
    line_no: int


class TMParseError(Exception):
    pass


class Tape:
    def __init__(self, blank: str = BLANK):
        self.blank = blank
        self.cells: Dict[int, str] = {}
        self.head = 0

    def reset(self):
        self.cells.clear()
        self.head = 0

    def read(self) -> str:
        return self.cells.get(self.head, self.blank)

    def write(self, sym: str):
        if sym == self.blank:
            self.cells.pop(self.head, None)
        else:
            self.cells[self.head] = sym

    def move(self, m: str):
        m = m.lower()
        if m not in MOVE:
            raise ValueError(f"Invalid move '{m}'. Expected l/r/*")
        self.head += MOVE[m]

    def load_leftmost(self, s: str):
        # head starts at left-most cell, spaces become blank.
        s = (s or "").replace(" ", self.blank)
        if s == "":
            s = self.blank
        self.reset()
        self.head = 0
        for i, ch in enumerate(s):
            if ch == self.blank:
                continue
            self.cells[i] = ch


class Program:
    """
    file/editor contains ONLY rules (comments with ';' allowed).
    blank character is always '_'.
    tapes and start state come from UI like in Morphett.
    """
    def __init__(self, tapes: int):
        if tapes not in (1, 2):
            raise ValueError("tapes must be 1 or 2")
        self.tapes = tapes
        self.blank = BLANK

        self._map_1: Dict[str, Dict[str, List[Instruction]]] = {}
        self._map_2: Dict[str, Dict[Tuple[str, str], List[Instruction]]] = {}

        self.source_text = ""

    def clear(self):
        self._map_1.clear()
        self._map_2.clear()

    def is_halt_state(self, st: str) -> bool:
        return st.strip().lower().startswith("halt")

    @staticmethod
    def _strip_comment(line: str) -> str:
        return line.split(";", 1)[0].strip()

    def add(self, ins: Instruction):
        if self.tapes == 1:
            self._map_1.setdefault(ins.cur_state, {}).setdefault(ins.read[0], []).append(ins)
        else:
            self._map_2.setdefault(ins.cur_state, {}).setdefault((ins.read[0], ins.read[1]), []).append(ins)

    def _get_1(self, state: str, sym: str) -> List[Instruction]:
        # morphett syntax: (state,sym) then (state,*) then (*,sym) then (*,*)
        if state in self._map_1 and sym in self._map_1[state]:
            return self._map_1[state][sym]
        if state in self._map_1 and "*" in self._map_1[state]:
            return self._map_1[state]["*"]
        if "*" in self._map_1 and sym in self._map_1["*"]:
            return self._map_1["*"][sym]
        if "*" in self._map_1 and "*" in self._map_1["*"]:
            return self._map_1["*"]["*"]
        return []

    def _get_2(self, state: str, r1: str, r2: str) -> List[Instruction]:
        # tiered wildcard matching for 2 tape:
        # prefer exact (r1,r2), then (r1,*) or (*,r2), then (*,*). Same for state, then state="*".
        def pick_for_state(st: str) -> List[Instruction]:
            m = self._map_2.get(st)
            if not m:
                return []
            if (r1, r2) in m:
                return m[(r1, r2)]
            tier2: List[Instruction] = []
            if (r1, "*") in m:
                tier2.extend(m[(r1, "*")])
            if ("*", r2) in m:
                tier2.extend(m[("*", r2)])
            if tier2:
                return tier2
            if ("*", "*") in m:
                return m[("*", "*")]
            return []

        res = pick_for_state(state)
        if res:
            return res
        return pick_for_state("*")

    def get_next(self, state: str, reads: Tuple[str, ...]) -> List[Instruction]:
        if self.tapes == 1:
            return self._get_1(state, reads[0])
        return self._get_2(state, reads[0], reads[1])

    def parse_from_text(self, text: str):
        self.clear()
        self.source_text = text

        lines = text.splitlines()

        # ignore any non-comment lines.
        directive_re = re.compile(r"(?i)^\s*(tapes|blank|start|initial_tape|initial_state|nondet|oneway)\s*:")

        for i, raw in enumerate(lines):
            raw_stripped = raw.strip()
            if directive_re.match(raw_stripped):
                continue

            line = self._strip_comment(raw)
            if not line:
                continue

            toks = line.split()
            if self.tapes == 1:
                # currentState currentSymbol newSymbol direction newState [!]
                if len(toks) not in (5, 6):
                    raise TMParseError(f"Line {i+1}: expected 5 or 6 tokens for 1-tape rule")
                cur, cs, ns, d, st = toks[:5]
                bp = (len(toks) == 6 and toks[5] == "!")
                if len(cs) != 1 or len(ns) != 1:
                    raise TMParseError(f"Line {i+1}: symbols must be single characters")
                if d.lower() not in ("l", "r", "*"):
                    raise TMParseError(f"Line {i+1}: direction must be l, r, or *")
                ins = Instruction(cur, (cs,), (ns,), (d.lower(),), st, bp, i)
                self.add(ins)
            else:
                # currentState r1 r2 w1 w2 d1 d2 newState [!]
                if len(toks) not in (8, 9):
                    raise TMParseError(f"Line {i+1}: expected 8 or 9 tokens for 2-tape rule")
                cur, r1, r2, w1, w2, d1, d2, st = toks[:8]
                bp = (len(toks) == 9 and toks[8] == "!")
                for sym in (r1, r2, w1, w2):
                    if len(sym) != 1:
                        raise TMParseError(f"Line {i+1}: symbols must be single characters")
                if d1.lower() not in ("l", "r", "*") or d2.lower() not in ("l", "r", "*"):
                    raise TMParseError(f"Line {i+1}: direction must be l, r, or *")
                ins = Instruction(cur, (r1, r2), (w1, w2), (d1.lower(), d2.lower()), st, bp, i)
                self.add(ins)


class Machine:
    """
    turing machine file loading block
    handles machine read syntax like Morphett with exception of * for no change
    """

    # start at 0 (default)
    def __init__(self):
        self.prog: Optional[Program] = None
        self.tapes: List[Tape] = []
        self.state = "0"
        self.steps = 0
        self.halted = True
        self.halt_msg = "Load or type a program, then Reset."

    def configure(self, prog: Program):
        self.prog = prog
        self.tapes = [Tape(BLANK) for _ in range(prog.tapes)]

    # re
    def reset(self, input_w: str, initial_state: str):
        if not self.prog:
            self.halted = True
            self.halt_msg = "No program loaded."
            return

        for t in self.tapes:
            t.blank = BLANK
            t.reset()

        self.tapes[0].load_leftmost(input_w)
        if len(self.tapes) == 2:
            self.tapes[1].reset()

        self.state = (initial_state.strip().split() or ["0"])[0]
        self.steps = 0
        self.halted = False
        self.halt_msg = ""

    def reads(self) -> Tuple[str, ...]:
        return tuple(t.read() for t in self.tapes)

    def step(self) -> Optional[Instruction]:
        if self.halted or not self.prog:
            return None

        if self.prog.is_halt_state(self.state):
            self.halted = True
            self.halt_msg = f"Halted (entered state '{self.state}')."
            return None

        reads = self.reads()
        choices = self.prog.get_next(self.state, reads)
        if not choices:
            self.halted = True
            self.halt_msg = f"Halted (no rule for state '{self.state}' reading {reads})."
            return None

        ins = choices[0]  # deterministic like Morphett (but variant handling removed)

        # applying '*' semantics: '*' in write/newState means "no change"
        new_state = self.state if ins.next_state == "*" else ins.next_state

        for i, tape in enumerate(self.tapes):
            w = reads[i] if ins.write[i] == "*" else ins.write[i]
            tape.write(w)

        for i, tape in enumerate(self.tapes):
            tape.move(ins.move[i])

        self.state = new_state
        self.steps += 1

        if ins.breakpoint:
            self.halted = True
            self.halt_msg = f"Paused at breakpoint (line {ins.line_no+1})."

        if self.prog.is_halt_state(self.state):
            self.halted = True
            self.halt_msg = f"Halted (entered state '{self.state}')."

        return ins


# GUI Loader

class TapeCanvas(ttk.Frame):
    """
    does what the name suggests, renders the GUI and tape sim windows.
    """
    def __init__(self, master, title: str, window: int = 33):
        super().__init__(master)
        self.window = window

        header = ttk.Frame(self)
        header.pack(fill="x")
        ttk.Label(header, text=title).pack(side="left")

        self.head_label = ttk.Label(self, text="", padding=(0, 6, 0, 6))
        self.head_label.pack(anchor="w")

        self.canvas = tk.Canvas(self, height=70, highlightthickness=0, background="#ffffff")
        self.canvas.pack(fill="x", expand=True)

    def render(self, tape: Tape):
        self.head_label.configure(text=f"head={tape.head}")
        self.canvas.delete("all")

        # render settings, modify at your own peril 
        w = self.canvas.winfo_width() or 900
        cell_w = max(18, min(28, w // (self.window + 1)))
        cell_h = 40
        pad_x = 8
        y0 = 10

        half = self.window // 2
        start = tape.head - half
        end = tape.head + half

        for idx, pos in enumerate(range(start, end + 1)):
            x0 = pad_x + idx * cell_w
            x1 = x0 + cell_w - 2
            y1 = y0 + cell_h

            sym = tape.cells.get(pos, tape.blank)
            is_head = (pos == tape.head)

            self.canvas.create_rectangle(
                x0, y0, x1, y1,
                outline="#333333",
                fill=("#dff1ff" if is_head else "#f8f8f8")
            )
            self.canvas.create_text(
                (x0 + x1) / 2, y0 + cell_h / 2,
                text=sym, font=("Consolas", 14)
            )
            if is_head:
                self.canvas.create_text((x0 + x1) / 2, y1 + 12, text="^", font=("Consolas", 14))


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Turing Machine Simulator")
        self.geometry("1100x720")

        self.machine = Machine()
        self._job = None
        self._dirty = True

        self._build()
        self._update_ui()

    def _build(self):
        root = ttk.Frame(self, padding=10)
        root.pack(fill="both", expand=True)

        # top buttons
        controls = ttk.Frame(root)
        controls.pack(fill="x")

        ttk.Button(controls, text="Load TM File…", command=self.on_load).pack(side="left")

        ttk.Label(controls, text="  Tapes:").pack(side="left")
        self.tapes_var = tk.StringVar(value="1")
        self.tapes_box = ttk.Combobox(controls, textvariable=self.tapes_var, values=["1", "2"],
                                      width=4, state="readonly")
        self.tapes_box.pack(side="left", padx=(4, 12))
        self.tapes_box.bind("<<ComboboxSelected>>", lambda e: self._mark_dirty())

        ttk.Label(controls, text="Input w:").pack(side="left")
        self.input_var = tk.StringVar(value="")
        ttk.Entry(controls, textvariable=self.input_var, width=26).pack(side="left", padx=(4, 12))

        ttk.Label(controls, text="Initial state:").pack(side="left")
        self.init_state_var = tk.StringVar(value="0")
        ttk.Entry(controls, textvariable=self.init_state_var, width=10).pack(side="left", padx=(4, 12))

        self.btn_run = ttk.Button(controls, text="Run", command=self.on_run_pause)
        self.btn_run.pack(side="left", padx=3)

        self.btn_step = ttk.Button(controls, text="Step", command=self.on_step)
        self.btn_step.pack(side="left", padx=3)

        self.btn_reset = ttk.Button(controls, text="Reset", command=self.on_reset)
        self.btn_reset.pack(side="left", padx=3)

        ttk.Label(controls, text="Speed (ms):").pack(side="left", padx=(16, 0))
        self.speed = tk.IntVar(value=120)
        ttk.Scale(controls, from_=10, to=600, variable=self.speed, orient="horizontal", length=160)\
            .pack(side="left", padx=(6, 0))

        self.status = ttk.Label(root, text="", padding=(0, 10, 0, 6))
        self.status.pack(fill="x")

        # editor and tape windows
        mid = ttk.PanedWindow(root, orient="horizontal")
        mid.pack(fill="both", expand=True)

        # input window
        editor_frame = ttk.Frame(mid, padding=(0, 0, 8, 0))
        mid.add(editor_frame, weight=1)

        ttk.Label(editor_frame, text="Program (rules only; blank is '_' ):").pack(anchor="w")

        editor_box = ttk.Frame(editor_frame)
        editor_box.pack(fill="both", expand=True, pady=(6, 0))

        self.source = tk.Text(editor_box, wrap="none", height=20)
        self.source.pack(side="left", fill="both", expand=True)

        self.source.insert("1.0", DEFAULT_PROGRAM)
        self._dirty = True


        ysb = ttk.Scrollbar(editor_box, orient="vertical", command=self.source.yview)
        ysb.pack(side="right", fill="y")
        self.source.configure(yscrollcommand=ysb.set)

        self.source.bind("<KeyRelease>", lambda e: self._mark_dirty())

        # tapes and log panel
        right = ttk.Frame(mid)
        mid.add(right, weight=1)

        self.tape1_view = TapeCanvas(right, "Tape 1")
        self.tape1_view.pack(fill="x", expand=False)

        self.tape2_view = TapeCanvas(right, "Tape 2")
        self.tape2_view.pack(fill="x", expand=False, pady=(10, 0))

        ttk.Label(right, text="Moves:").pack(anchor="w", pady=(10, 0))
        log_box = ttk.Frame(right)
        log_box.pack(fill="both", expand=True, pady=(6, 0))

        self.log = tk.Text(log_box, wrap="none", state="disabled")
        self.log.pack(side="left", fill="both", expand=True)

        lsb = ttk.Scrollbar(log_box, orient="vertical", command=self.log.yview)
        lsb.pack(side="right", fill="y")
        self.log.configure(yscrollcommand=lsb.set)

    def _mark_dirty(self):
        self._dirty = True

    def _append_log(self, s: str):
        self.log.configure(state="normal")
        self.log.insert("end", s + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _stop(self):
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
        self._job = None
        self.btn_run.configure(text="Run")

    def _compile_if_needed(self) -> bool:
        if not self._dirty and self.machine.prog is not None:
            return True

        text = self.source.get("1.0", "end").rstrip("\n")
        tapes = int(self.tapes_var.get())

        prog = Program(tapes=tapes)
        try:
            prog.parse_from_text(text)
        except TMParseError as e:
            messagebox.showerror("Parse error", str(e))
            return False

        self.machine.configure(prog)
        self._dirty = False
        return True

    def on_load(self):
        path = filedialog.askopenfilename(
            title="Select Turing machine file",
            filetypes=[("Text files", "*.txt *.tm *.machine"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = f.read()
        except Exception as e:
            messagebox.showerror("Load error", str(e))
            return

        self.source.delete("1.0", "end")
        self.source.insert("1.0", data)
        self._mark_dirty()
        self._append_log(f"Loaded file: {path}")

    def on_reset(self):
        self._stop()
        if not self._compile_if_needed():
            return
        self.machine.reset(self.input_var.get(), self.init_state_var.get())
        self._append_log("RESET")
        self._update_ui()

    def on_step(self):
        self._stop()
        if not self._compile_if_needed():
            return
        if self.machine.prog is None or self.machine.halted:
            return
        ins = self.machine.step()
        if ins is None:
            if self.machine.halt_msg:
                self._append_log(self.machine.halt_msg)
            self._update_ui()
            return
        action = f"({ins.cur_state}, {ins.read}) -> write={ins.write} move={ins.move} next={ins.next_state}"
        self._append_log(f"{self.machine.steps:06d}: {action}  [line {ins.line_no+1}]")
        if self.machine.halted and self.machine.halt_msg:
            self._append_log(self.machine.halt_msg)
        self._update_ui()

    def on_run_pause(self):
        if self._job is None:
            if not self._compile_if_needed():
                return
            if self.machine.prog is None:
                return
            if self.machine.halted:
                # if halted, run acts like reset+run
                self.machine.reset(self.input_var.get(), self.init_state_var.get())
                self._append_log("RESET")
            self.btn_run.configure(text="Pause")
            self._run_loop()
        else:
            self._stop()
            self._update_ui()

    def _run_loop(self):
        if self.machine.halted:
            self._stop()
            self._update_ui()
            return

        self.on_step()

        if self.machine.halted:
            self._stop()
            self._update_ui()
            return

        delay = max(1, int(self.speed.get()))
        self._job = self.after(delay, self._run_loop)

    def _render_tapes(self):
        if not self.machine.tapes:
            self.tape2_view.canvas.delete("all")
            self.tape2_view.head_label.configure(text="")
            return

        self.tape1_view.render(self.machine.tapes[0])

        if len(self.machine.tapes) == 2:
            self.tape2_view.render(self.machine.tapes[1])
        else:
            self.tape2_view.canvas.delete("all")
            self.tape2_view.head_label.configure(text="")

    def _update_ui(self):
        if self.machine.prog is None:
            reads = "-"
            tapes = int(self.tapes_var.get())
        else:
            tapes = self.machine.prog.tapes
            reads = self.machine.reads() if not self.machine.halted else "-"

        msg = f"Tapes: {tapes}    State: {self.machine.state}    Steps: {self.machine.steps}    Reads: {reads}    Blank: _"
        if self.machine.halted and self.machine.halt_msg:
            msg += f"    [{self.machine.halt_msg}]"
        self.status.configure(text=msg)

        self._render_tapes()


if __name__ == "__main__":
    App().mainloop()
