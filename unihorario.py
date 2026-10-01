import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import random
import copy
import threading
import math
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

@dataclass
class Subject:
    id: str
    name: str
    hours_per_week: int
    semester: int = 8

@dataclass
class Professor:
    id: str
    name: str
    subject_ids: List[str]
    unavailable: List[Tuple[int, int]] = field(default_factory=list)

@dataclass
class Group:
    id: str
    name: str
    semester: int
    subject_ids: List[str]

class Schedule:
    def __init__(self, groups, subjects_dict, professors_dict, days=5, slots=8):
        self.groups        = groups
        self.subjects      = subjects_dict
        self.professors    = professors_dict
        self.days          = days
        self.slots         = slots
        self.grid: Dict[str, List[List[Optional[str]]]] = {
            g.id: [[None]*slots for _ in range(days)] for g in groups
        }
        self.fitness: float = 0.0
        self.details: Dict  = {}

    def clone(self) -> 'Schedule':
        s = Schedule.__new__(Schedule)
        s.groups     = self.groups
        s.subjects   = self.subjects
        s.professors = self.professors
        s.days       = self.days
        s.slots      = self.slots
        s.grid       = {gid: [row[:] for row in grid]
                        for gid, grid in self.grid.items()}
        s.fitness    = self.fitness
        s.details    = dict(self.details)
        return s

class GeneticAlgorithm:
    def __init__(self, cfg):
        self.groups      = cfg['groups']
        self.subjects    = {s.id: s for s in cfg['subjects']}
        self.professors  = {p.id: p for p in cfg['professors']}
        self.days        = cfg.get('days', 5)
        self.slots       = cfg.get('slots', 8)
        self.pop_size    = cfg.get('pop_size', 100)
        self.generations = cfg.get('generations', 300)
        self.mut_rate    = cfg.get('mut_rate', 0.15)
        self.elite       = cfg.get('elite', 5)
        self.tourn_k     = cfg.get('tourn_k', 3)

        self.sub2prof: Dict[str, str] = {}
        for p in cfg['professors']:
            for sid in p.subject_ids:
                self.sub2prof[sid] = p.id

        self.blocked: Dict[str, Set[Tuple[int,int]]] = {
            p.id: set(p.unavailable) for p in cfg['professors']
        }

        self.best_hist: List[float] = []
        self.avg_hist:  List[float] = []

    def _random_schedule(self) -> Schedule:
        sched = Schedule(self.groups, self.subjects, self.professors,
                         self.days, self.slots)
        for g in self.groups:
            self._fill_group(sched, g)
        return sched

    def _fill_group(self, sched: Schedule, group: Group):
        grid = sched.grid[group.id]

        sub_hours = {}
        for sid in group.subject_ids:
            sub_hours[sid] = sub_hours.get(sid, 0) + self.subjects[sid].hours_per_week

        sessions = []
        for sid, total in sub_hours.items():
            remaining = total
            while remaining > 0:
                dur = min(2, remaining) if remaining > 1 else 1
                if remaining >= 2:
                    dur = random.choice([1, 2])
                sessions.append((sid, dur))
                remaining -= dur
        random.shuffle(sessions)

        subject_days: Dict[str, Set[int]] = {sid: set() for sid in sub_hours}

        for sid, dur in sessions:
            placed = False

            candidates = [(d, s) for d in range(self.days)
                          for s in range(self.slots - dur + 1)]
            random.shuffle(candidates)

            for d, s in candidates:
                if d in subject_days.get(sid, set()):
                    continue

                if any(grid[d][s+i] is not None for i in range(dur)):
                    continue

                pid = self.sub2prof.get(sid)
                if pid and any((d, s+i) in self.blocked.get(pid, set())
                               for i in range(dur)):
                    continue

                for i in range(dur):
                    grid[d][s+i] = sid
                subject_days[sid].add(d)
                placed = True
                break

            if not placed:

                for d in range(self.days):
                    for s in range(self.slots - dur + 1):
                        if all(grid[d][s+i] is None for i in range(dur)):
                            for i in range(dur):
                                grid[d][s+i] = sid
                            subject_days[sid].add(d)
                            placed = True
                            break
                    if placed:
                        break

            if not placed:

                for d in range(self.days):
                    for s in range(self.slots):
                        if grid[d][s] is None:
                            grid[d][s] = sid
                            placed = True
                            break
                    if placed:
                        break

    def evaluate(self, sched: Schedule) -> float:
        pen = 0.0
        det = {}

        pc = self._prof_conflicts(sched)
        pen += pc * 1000
        det['prof_conflicts'] = pc

        av = self._avail_violations(sched)
        pen += av * 500
        det['avail_violations'] = av

        sg = self._student_gaps(sched)
        pen += sg * 10
        det['student_gaps'] = sg

        ls = self._long_sessions(sched)
        pen += ls * 60
        det['long_sessions'] = ls

        rs = self._repeated_subject_day(sched)
        pen += rs * 35
        det['repeated_subjects'] = rs

        di = self._daily_imbalance(sched)
        pen += di * 5
        det['imbalance'] = round(di, 2)

        pd = self._prof_dispersion(sched)
        pen += pd * 8
        det['prof_dispersion'] = pd

        pg = self._prof_gaps(sched)
        pen += pg * 12
        det['prof_gaps'] = pg

        fit = 1000.0 / (1.0 + pen)
        sched.fitness = fit
        sched.details  = det
        return fit

    def _prof_conflicts(self, s: Schedule) -> int:
        slot_use: Dict[Tuple, int] = {}
        for g in self.groups:
            for d in range(self.days):
                for sl in range(self.slots):
                    sid = s.grid[g.id][d][sl]
                    if sid:
                        pid = self.sub2prof.get(sid)
                        if pid:
                            k = (d, sl, pid)
                            slot_use[k] = slot_use.get(k, 0) + 1
        return sum(v-1 for v in slot_use.values() if v > 1)

    def _avail_violations(self, s: Schedule) -> int:
        v = 0
        for g in self.groups:
            for d in range(self.days):
                for sl in range(self.slots):
                    sid = s.grid[g.id][d][sl]
                    if sid:
                        pid = self.sub2prof.get(sid)
                        if pid and (d, sl) in self.blocked.get(pid, set()):
                            v += 1
        return v

    def _student_gaps(self, s: Schedule) -> int:
        gaps = 0
        for g in self.groups:
            for d in range(self.days):
                row = s.grid[g.id][d]
                first = next((i for i,x in enumerate(row) if x), None)
                last  = next((i for i,x in enumerate(reversed(row)) if x), None)
                if first is None:
                    continue
                last_i = self.slots - 1 - last
                gaps += sum(1 for i in range(first, last_i+1) if row[i] is None)
        return gaps

    def _long_sessions(self, s: Schedule) -> int:
        v = 0
        for g in self.groups:
            for d in range(self.days):
                row = s.grid[g.id][d]
                run = 1
                for sl in range(1, self.slots):
                    if row[sl] and row[sl] == row[sl-1]:
                        run += 1
                        if run > 2:
                            v += 1
                    else:
                        run = 1
        return v

    def _repeated_subject_day(self, s: Schedule) -> int:
        v = 0
        for g in self.groups:
            for d in range(self.days):
                row = s.grid[g.id][d]
                seen: Dict[str, int] = {}
                prev = None
                for sl in range(self.slots):
                    cur = row[sl]
                    if cur and cur != prev:
                        seen[cur] = seen.get(cur, 0) + 1
                    prev = cur
                v += sum(c-1 for c in seen.values() if c > 1)
        return v

    def _daily_imbalance(self, s: Schedule) -> float:
        total = 0.0
        for g in self.groups:
            hours = [sum(1 for sl in range(self.slots)
                         if s.grid[g.id][d][sl]) for d in range(self.days)]
            if hours:
                mu = sum(hours)/len(hours)
                total += sum((h-mu)**2 for h in hours)/len(hours)
        return total

    def _prof_dispersion(self, s: Schedule) -> int:
        pdays: Dict[str, Set[int]] = {}
        for g in self.groups:
            for d in range(self.days):
                for sl in range(self.slots):
                    sid = s.grid[g.id][d][sl]
                    if sid:
                        pid = self.sub2prof.get(sid)
                        if pid:
                            pdays.setdefault(pid, set()).add(d)
        return sum(len(ds) for ds in pdays.values())

    def _prof_gaps(self, s: Schedule) -> int:

        ps: Dict[str, List[List[bool]]] = {}
        for g in self.groups:
            for d in range(self.days):
                for sl in range(self.slots):
                    sid = s.grid[g.id][d][sl]
                    if sid:
                        pid = self.sub2prof.get(sid)
                        if pid:
                            if pid not in ps:
                                ps[pid] = [[False]*self.slots for _ in range(self.days)]
                            ps[pid][d][sl] = True
        gaps = 0
        for pid, grid in ps.items():
            for d in range(self.days):
                row = grid[d]
                first = next((i for i,x in enumerate(row) if x), None)
                last  = next((i for i,x in enumerate(reversed(row)) if x), None)
                if first is None:
                    continue
                last_i = self.slots - 1 - last
                gaps += sum(1 for i in range(first, last_i+1) if not row[i])
        return gaps

    def _tournament(self, pop):
        sample = random.sample(pop, min(self.tourn_k, len(pop)))
        return max(sample, key=lambda x: x.fitness)

    def _crossover(self, p1: Schedule, p2: Schedule):
        c1, c2 = p1.clone(), p2.clone()
        gids = [g.id for g in self.groups]
        if len(gids) >= 2:
            pt = random.randint(1, len(gids)-1)
            for gid in gids[pt:]:
                c1.grid[gid] = [r[:] for r in p2.grid[gid]]
                c2.grid[gid] = [r[:] for r in p1.grid[gid]]
        return c1, c2

    def _mutate(self, sched: Schedule) -> Schedule:
        m = sched.clone()
        for g in self.groups:
            if random.random() >= self.mut_rate:
                continue
            grid = m.grid[g.id]
            kind = random.choice(['swap', 'move', 'day_swap', 'refill'])

            if kind == 'swap':
                d1 = random.randrange(self.days);  s1 = random.randrange(self.slots)
                d2 = random.randrange(self.days);  s2 = random.randrange(self.slots)
                grid[d1][s1], grid[d2][s2] = grid[d2][s2], grid[d1][s1]

            elif kind == 'move':
                filled = [(d, sl) for d in range(self.days)
                          for sl in range(self.slots) if grid[d][sl]]
                empty  = [(d, sl) for d in range(self.days)
                          for sl in range(self.slots) if not grid[d][sl]]
                if filled and empty:
                    d1, s1 = random.choice(filled)
                    d2, s2 = random.choice(empty)
                    grid[d2][s2] = grid[d1][s1]
                    grid[d1][s1] = None

            elif kind == 'day_swap':
                d1, d2 = random.sample(range(self.days), 2)
                grid[d1], grid[d2] = grid[d2][:], grid[d1][:]

            elif kind == 'refill':

                m.grid[g.id] = [[None]*self.slots for _ in range(self.days)]
                self._fill_group(m, g)

        return m

    def run(self, callback=None, stop_event=None):
        self.best_hist = []
        self.avg_hist  = []

        pop = [self._random_schedule() for _ in range(self.pop_size)]
        for s in pop:
            self.evaluate(s)

        best_ever = max(pop, key=lambda x: x.fitness).clone()

        for gen in range(self.generations):
            if stop_event and stop_event.is_set():
                break

            pop.sort(key=lambda x: x.fitness, reverse=True)

            bf  = pop[0].fitness
            avg = sum(x.fitness for x in pop) / len(pop)
            self.best_hist.append(bf)
            self.avg_hist.append(avg)

            if pop[0].fitness > best_ever.fitness:
                best_ever = pop[0].clone()

            if callback:
                callback(gen+1, bf, avg, pop[0])

            if bf >= 990:
                break

            new_pop = [s.clone() for s in pop[:self.elite]]

            while len(new_pop) < self.pop_size:
                p1 = self._tournament(pop)
                p2 = self._tournament(pop)
                if random.random() < 0.80:
                    c1, c2 = self._crossover(p1, p2)
                else:
                    c1, c2 = p1.clone(), p2.clone()
                c1 = self._mutate(c1);  self.evaluate(c1)
                c2 = self._mutate(c2);  self.evaluate(c2)
                new_pop += [c1, c2]

            pop = new_pop[:self.pop_size]

        pop.sort(key=lambda x: x.fitness, reverse=True)
        return pop[:3], self.best_hist, self.avg_hist

DAY_NAMES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]

SUBJECT_PALETTE = [
    "#E63946", "#457B9D", "#2A9D8F", "#E9C46A", "#F4A261",
    "#A8DADC", "#6D6875", "#B5E48C", "#F72585", "#4CC9F0",
    "#8338EC", "#06D6A0",
]

COLORS = {
    'bg':        '#0D0D1A',
    'surface':   '#141428',
    'panel':     '#1A1A35',
    'border':    '#2A2A50',
    'accent':    '#4F46E5',
    'accent2':   '#7C3AED',
    'highlight': '#06D6A0',
    'warn':      '#F59E0B',
    'danger':    '#EF4444',
    'text':      '#E2E8F0',
    'muted':     '#94A3B8',
    'white':     '#FFFFFF',
}

class UnihorarioApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("UNIHORARIO  ·  Algoritmos Genéticos para Horarios Académicos")
        self.root.geometry("1280x850")
        self.root.minsize(1000, 700)
        self.root.configure(bg=COLORS['bg'])

        self.subjects_data:   List[Subject]   = []
        self.professors_data: List[Professor] = []
        self.groups_data:     List[Group]     = []
        self.results:         List[Schedule]  = []
        self.best_hist:       List[float]     = []
        self.avg_hist:        List[float]     = []
        self.ga_thread:       Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self._cfg_start = 8
        self._cfg_slots = 8
        self._cfg_days  = 5

        self._load_defaults()
        self._apply_ttk_style()
        self._build_ui()

    def _load_defaults(self):
        names = ["Matemáticas","Física","Programación","Base de Datos",
                 "Inglés","Redes","Álgebra Lineal"]
        self.subjects_data = [Subject(f"S{i+1}", n, 5) for i, n in enumerate(names)]

        prof_names = ["Dr. Ramírez","Mtra. López","Ing. García","Dr. Martínez",
                      "Mtra. Sánchez","Ing. Torres","Dr. Herrera"]
        self.professors_data = [
            Professor(f"P{i+1}", pn, [f"S{i+1}"])
            for i, pn in enumerate(prof_names)
        ]

        self.groups_data = [
            Group("8A", "8° A", 8, [f"S{i+1}" for i in range(7)]),
            Group("8B", "8° B", 8, [f"S{i+1}" for i in range(7)]),
        ]

    def _apply_ttk_style(self):
        s = ttk.Style()
        s.theme_use('clam')

        s.configure('TNotebook',     background=COLORS['bg'],      borderwidth=0)
        s.configure('TNotebook.Tab', background=COLORS['panel'],
                    foreground=COLORS['muted'],   padding=[18, 10],
                    font=('Courier New', 10, 'bold'))
        s.map('TNotebook.Tab',
              background=[('selected', COLORS['accent'])],
              foreground=[('selected', COLORS['white'])])

        s.configure('Treeview', background=COLORS['surface'],
                    foreground=COLORS['text'],   rowheight=28,
                    fieldbackground=COLORS['surface'],
                    font=('Courier New', 9))
        s.configure('Treeview.Heading', background=COLORS['accent'],
                    foreground=COLORS['white'],
                    font=('Courier New', 9, 'bold'))
        s.map('Treeview', background=[('selected', COLORS['accent2'])])

        s.configure('Vertical.TScrollbar',
                    background=COLORS['panel'], troughcolor=COLORS['surface'],
                    arrowcolor=COLORS['muted'])

        s.configure('TProgressbar', troughcolor=COLORS['surface'],
                    background=COLORS['highlight'], bordercolor=COLORS['border'],
                    lightcolor=COLORS['highlight'], darkcolor=COLORS['highlight'])

    def _build_ui(self):

        hdr = tk.Frame(self.root, bg=COLORS['accent'], height=56)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)
        tk.Label(hdr, text="⬡  UNIHORARIO",
                 font=('Courier New', 16, 'bold'),
                 bg=COLORS['accent'], fg=COLORS['white']).pack(side='left', padx=20)
        tk.Label(hdr, text="Sistema Inteligente · Algoritmos Genéticos · Horarios Académicos",
                 font=('Courier New', 9),
                 bg=COLORS['accent'], fg='#C7D2FE').pack(side='left')

        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill='both', expand=True, padx=8, pady=8)

        self.tab_cfg     = tk.Frame(self.nb, bg=COLORS['bg'])
        self.tab_run     = tk.Frame(self.nb, bg=COLORS['bg'])
        self.tab_results = tk.Frame(self.nb, bg=COLORS['bg'])
        self.tab_graph   = tk.Frame(self.nb, bg=COLORS['bg'])

        self.nb.add(self.tab_cfg,     text='  ⚙  Config  ')
        self.nb.add(self.tab_run,     text='  ▶  Ejecutar  ')
        self.nb.add(self.tab_results, text='  ◈  Resultados  ')
        self.nb.add(self.tab_graph,   text='  ∿  Convergencia  ')

        self._build_config_tab()
        self._build_run_tab()
        self._build_results_tab()
        self._build_graph_tab()

    def _lbl(self, parent, text, size=9, bold=False, color=None):
        return tk.Label(parent, text=text,
                        font=('Courier New', size, 'bold' if bold else 'normal'),
                        bg=parent.cget('bg'),
                        fg=color or COLORS['text'])

    def _btn(self, parent, text, cmd, color=None, width=14):
        c = color or COLORS['accent']
        b = tk.Button(parent, text=text, command=cmd,
                      bg=c, fg=COLORS['white'],
                      font=('Courier New', 9, 'bold'),
                      relief='flat', bd=0, padx=8, pady=7,
                      width=width, cursor='hand2',
                      activebackground=COLORS['accent2'],
                      activeforeground=COLORS['white'])
        return b

    def _entry(self, parent, var, width=14):
        return tk.Entry(parent, textvariable=var, width=width,
                        bg=COLORS['panel'], fg=COLORS['text'],
                        insertbackground=COLORS['text'],
                        font=('Courier New', 9),
                        relief='flat', bd=4)

    def _section(self, parent, title):
        f = tk.LabelFrame(parent, text=f'  {title}  ',
                          bg=COLORS['surface'],
                          fg=COLORS['highlight'],
                          font=('Courier New', 10, 'bold'),
                          bd=1, relief='solid',
                          highlightbackground=COLORS['border'])
        return f

    def _tree(self, parent, cols, widths, height=7):
        frm = tk.Frame(parent, bg=COLORS['surface'])
        t = ttk.Treeview(frm, columns=cols, show='headings', height=height)
        for col, w in zip(cols, widths):
            t.heading(col, text=col)
            t.column(col, width=w, anchor='center')
        sb = ttk.Scrollbar(frm, orient='vertical', command=t.yview)
        t.configure(yscrollcommand=sb.set)
        t.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        return frm, t

    def _build_config_tab(self):
        pane = tk.PanedWindow(self.tab_cfg, orient='horizontal',
                              bg=COLORS['bg'], sashwidth=6,
                              sashpad=3, sashrelief='flat')
        pane.pack(fill='both', expand=True, padx=8, pady=8)

        left  = tk.Frame(pane, bg=COLORS['bg'])
        right = tk.Frame(pane, bg=COLORS['bg'])
        pane.add(left,  minsize=400)
        pane.add(right, minsize=380)

        inst = self._section(left, "🏫 Jornada Institucional")
        inst.pack(fill='x', pady=(0,8))

        ig = tk.Frame(inst, bg=COLORS['surface'])
        ig.pack(fill='x', padx=12, pady=10)

        labels  = ["Hora inicio (24h):", "Hora fin (24h):", "Días semana:"]
        defs    = ["8", "16", "5"]
        keys    = ['start','end','days']
        self.iv = {}
        for i, (l, d, k) in enumerate(zip(labels, defs, keys)):
            self._lbl(ig, l).grid(row=i, column=0, sticky='w', pady=4, padx=4)
            v = tk.StringVar(value=d)
            self.iv[k] = v
            self._entry(ig, v, 8).grid(row=i, column=1, padx=8, pady=4)

        sf = self._section(left, "📚 Materias")
        sf.pack(fill='both', expand=True, pady=(0,8))

        sfrm, self.stree = self._tree(sf,
            ('ID','Nombre','Hrs/Sem'), (60,200,80), height=8)
        sfrm.pack(fill='both', expand=True, padx=8, pady=8)
        self._refresh_stree()

        sc = tk.Frame(sf, bg=COLORS['surface'])
        sc.pack(fill='x', padx=8, pady=(0,8))
        self._lbl(sc, "Nombre:").grid(row=0, column=0, padx=4)
        self.snv = tk.StringVar()
        self._entry(sc, self.snv, 18).grid(row=0, column=1, padx=4)
        self._lbl(sc, "Horas:").grid(row=0, column=2, padx=4)
        self.shv = tk.StringVar(value="5")
        self._entry(sc, self.shv, 5).grid(row=0, column=3, padx=4)
        self._btn(sc, "+ Agregar", self._add_subject,
                  COLORS['highlight'], 9).grid(row=0, column=4, padx=4)
        self._btn(sc, "✕ Quitar",  self._del_subject,
                  COLORS['danger'], 8).grid(row=0, column=5, padx=4)

        gf = self._section(right, "👥 Grupos")
        gf.pack(fill='x', pady=(0,8))

        gfrm, self.gtree = self._tree(gf,
            ('ID','Nombre','Sem'), (70,160,60), height=5)
        gfrm.pack(fill='x', padx=8, pady=8)
        self._refresh_gtree()

        gc = tk.Frame(gf, bg=COLORS['surface'])
        gc.pack(fill='x', padx=8, pady=(0,8))
        self._lbl(gc, "ID:").grid(row=0, column=0, padx=4)
        self.gnid = tk.StringVar()
        self._entry(gc, self.gnid, 7).grid(row=0, column=1, padx=4)
        self._lbl(gc, "Nombre:").grid(row=0, column=2, padx=4)
        self.gnnm = tk.StringVar()
        self._entry(gc, self.gnnm, 12).grid(row=0, column=3, padx=4)
        self._btn(gc, "+ Agregar", self._add_group,
                  COLORS['highlight'], 9).grid(row=0, column=4, padx=4)
        self._btn(gc, "✕ Quitar",  self._del_group,
                  COLORS['danger'], 8).grid(row=0, column=5, padx=4)

        pf = self._section(right, "👨‍🏫 Personal Académico")
        pf.pack(fill='both', expand=True)

        pfrm, self.ptree = self._tree(pf,
            ('ID','Nombre','Materia','Bloqueados'), (50,140,130,90), height=8)
        pfrm.pack(fill='both', expand=True, padx=8, pady=8)
        self._refresh_ptree()

        pc = tk.Frame(pf, bg=COLORS['surface'])
        pc.pack(fill='x', padx=8, pady=(0,8))
        self._btn(pc, "✏ Editar Disponibilidad", self._edit_avail,
                  COLORS['accent2'], 22).pack(side='left', padx=6)
        self._btn(pc, "🔄 Asignar Todas las Materias", self._auto_assign,
                  COLORS['accent'], 24).pack(side='left', padx=6)

    def _refresh_stree(self):
        self.stree.delete(*self.stree.get_children())
        for s in self.subjects_data:
            self.stree.insert('', 'end', values=(s.id, s.name, s.hours_per_week))

    def _refresh_gtree(self):
        self.gtree.delete(*self.gtree.get_children())
        for g in self.groups_data:
            self.gtree.insert('', 'end', values=(g.id, g.name, g.semester))

    def _refresh_ptree(self):
        self.ptree.delete(*self.ptree.get_children())
        for p in self.professors_data:
            sn = ', '.join(
                s.name for s in self.subjects_data if s.id in p.subject_ids
            ) or '—'
            bl = len(p.unavailable)
            self.ptree.insert('', 'end', values=(p.id, p.name, sn, f"{bl} slots"))

    def _add_subject(self):
        name = self.snv.get().strip()
        if not name:
            messagebox.showwarning("Error", "Ingresa el nombre de la materia.")
            return
        try:
            h = int(self.shv.get())
        except ValueError:
            messagebox.showwarning("Error", "Las horas deben ser un entero.")
            return
        nid = f"S{len(self.subjects_data)+1}"
        self.subjects_data.append(Subject(nid, name, h))
        pid = f"P{len(self.professors_data)+1}"
        self.professors_data.append(Professor(pid, f"Profesor {name[:12]}", [nid]))

        for g in self.groups_data:
            if nid not in g.subject_ids:
                g.subject_ids.append(nid)
        self._refresh_stree(); self._refresh_ptree()
        self.snv.set('')

    def _del_subject(self):
        sel = self.stree.selection()
        if not sel:
            return
        sid = self.stree.item(sel[0])['values'][0]
        self.subjects_data   = [s for s in self.subjects_data if s.id != sid]
        self.professors_data = [p for p in self.professors_data
                                if sid not in p.subject_ids or len(p.subject_ids) > 1]
        for p in self.professors_data:
            if sid in p.subject_ids:
                p.subject_ids.remove(sid)
        for g in self.groups_data:
            if sid in g.subject_ids:
                g.subject_ids.remove(sid)
        self._refresh_stree(); self._refresh_ptree()

    def _add_group(self):
        gid = self.gnid.get().strip(); gn = self.gnnm.get().strip()
        if not gid or not gn:
            messagebox.showwarning("Error", "Completa ID y Nombre del grupo.")
            return
        if any(g.id == gid for g in self.groups_data):
            messagebox.showwarning("Error", f"El grupo '{gid}' ya existe.")
            return
        self.groups_data.append(Group(gid, gn, 8,
                                      [s.id for s in self.subjects_data]))
        self._refresh_gtree()
        self.gnid.set(''); self.gnnm.set('')

    def _del_group(self):
        sel = self.gtree.selection()
        if not sel:
            return
        gid = self.gtree.item(sel[0])['values'][0]
        self.groups_data = [g for g in self.groups_data if g.id != gid]
        self._refresh_gtree()

    def _auto_assign(self):
        all_ids = [s.id for s in self.subjects_data]
        for g in self.groups_data:
            g.subject_ids = all_ids[:]
        messagebox.showinfo("Listo", "Todas las materias asignadas a todos los grupos.")

    def _edit_avail(self):
        sel = self.ptree.selection()
        if not sel:
            messagebox.showinfo("Info", "Selecciona un profesor primero.")
            return
        pid  = self.ptree.item(sel[0])['values'][0]
        prof = next((p for p in self.professors_data if p.id == pid), None)
        if not prof:
            return

        try:
            start = int(self.iv['start'].get())
            end   = int(self.iv['end'].get())
            days  = int(self.iv['days'].get())
        except ValueError:
            start, end, days = 8, 16, 5
        slots = end - start

        dlg = tk.Toplevel(self.root)
        dlg.title(f"Disponibilidad — {prof.name}")
        dlg.geometry("560x460")
        dlg.configure(bg=COLORS['surface'])
        dlg.grab_set()

        tk.Label(dlg, text=f"Marcar slots NO disponibles  ·  {prof.name}",
                 font=('Courier New', 11, 'bold'),
                 bg=COLORS['surface'], fg=COLORS['highlight']).pack(pady=12)

        frm = tk.Frame(dlg, bg=COLORS['surface'])
        frm.pack(fill='both', expand=True, padx=12)

        dn = DAY_NAMES[:days]
        tk.Label(frm, text="Hora", width=8,
                 bg=COLORS['accent'], fg='white',
                 font=('Courier New', 8, 'bold')).grid(row=0, column=0, padx=2, pady=2)
        for c, d in enumerate(dn):
            tk.Label(frm, text=d, width=10,
                     bg=COLORS['accent'], fg='white',
                     font=('Courier New', 8, 'bold')).grid(row=0, column=c+1, padx=2, pady=2)

        cvars = {}
        for sl in range(slots):
            tk.Label(frm, text=f"{start+sl:02d}:00", width=8,
                     bg=COLORS['panel'], fg=COLORS['muted'],
                     font=('Courier New', 8)).grid(row=sl+1, column=0, padx=2, pady=1)
            for d in range(days):
                v = tk.BooleanVar(value=(d, sl) in prof.unavailable)
                cvars[(d, sl)] = v
                cb = tk.Checkbutton(frm, variable=v,
                                    bg=COLORS['surface'],
                                    activebackground=COLORS['surface'],
                                    selectcolor=COLORS['danger'])
                cb.grid(row=sl+1, column=d+1, padx=2, pady=1)

        def save():
            prof.unavailable = [(d, sl) for (d, sl), v in cvars.items() if v.get()]
            self._refresh_ptree()
            dlg.destroy()

        self._btn(dlg, "💾  Guardar", save, COLORS['highlight'], 14).pack(pady=12)

    def _build_run_tab(self):
        main = tk.Frame(self.tab_run, bg=COLORS['bg'])
        main.pack(fill='both', expand=True, padx=14, pady=14)

        pf = self._section(main, "🧬 Parámetros del Algoritmo Genético")
        pf.pack(fill='x', pady=(0,10))

        pg = tk.Frame(pf, bg=COLORS['surface'])
        pg.pack(padx=14, pady=12)

        param_defs = [
            ("Población:", 'pop',  '100'),
            ("Generaciones:", 'gen', '300'),
            ("Tasa mutación:", 'mut', '0.15'),
            ("Élite:", 'elite', '5'),
            ("Torneo k:", 'tourn', '3'),
        ]
        self.pv = {}
        for i, (lbl, key, val) in enumerate(param_defs):
            r, c = divmod(i, 3)
            self._lbl(pg, lbl).grid(row=r, column=c*2, sticky='e', padx=8, pady=6)
            v = tk.StringVar(value=val)
            self.pv[key] = v
            self._entry(pg, v, 10).grid(row=r, column=c*2+1, padx=6, pady=6)

        bf = tk.Frame(main, bg=COLORS['bg'])
        bf.pack(pady=10)
        self.run_btn  = self._btn(bf, "▶  Ejecutar AG",   self._run_ga,
                                   COLORS['highlight'], 18)
        self.run_btn.pack(side='left', padx=10)
        self.stop_btn = self._btn(bf, "⏹  Detener",       self._stop_ga,
                                   COLORS['danger'], 12)
        self.stop_btn.pack(side='left', padx=10)
        self.stop_btn.config(state='disabled')

        prgf = self._section(main, "📊 Progreso")
        prgf.pack(fill='x', pady=(0,10))
        self.pvar = tk.DoubleVar()
        ttk.Progressbar(prgf, variable=self.pvar, maximum=100,
                        length=700, style='TProgressbar').pack(
                            fill='x', padx=14, pady=8)
        self.stat_str = tk.StringVar(value="Listo para ejecutar...")
        tk.Label(prgf, textvariable=self.stat_str,
                 bg=COLORS['surface'], fg=COLORS['warn'],
                 font=('Courier New', 10)).pack(pady=(0,8))

        sf = tk.Frame(main, bg=COLORS['bg'])
        sf.pack(fill='x', pady=(0,10))
        self._stat_vars = {}
        for lbl, key, clr in [
            ("Generación",     'gen',  COLORS['text']),
            ("Mejor Fitness",  'best', COLORS['highlight']),
            ("Fitness Prom.",  'avg',  COLORS['warn']),
            ("Conflictos Prof","conf", COLORS['danger']),
            ("Huecos Alumnos", 'gaps', '#60A5FA'),
        ]:
            box = tk.Frame(sf, bg=COLORS['panel'], bd=1, relief='solid')
            box.pack(side='left', expand=True, fill='x', padx=5)
            self._lbl(box, lbl, 8, color=COLORS['muted']).pack(pady=(6,0))
            v = tk.StringVar(value="—")
            self._stat_vars[key] = v
            tk.Label(box, textvariable=v, font=('Courier New', 15, 'bold'),
                     bg=COLORS['panel'], fg=clr).pack(pady=(2,8))

        lf = self._section(main, "📝 Log de Ejecución")
        lf.pack(fill='both', expand=True)
        self.log = scrolledtext.ScrolledText(lf, height=10,
                                              bg=COLORS['bg'],
                                              fg='#A5F3FC',
                                              font=('Courier New', 8),
                                              insertbackground='white',
                                              selectbackground=COLORS['accent'])
        self.log.pack(fill='both', expand=True, padx=8, pady=8)

    def _log_write(self, msg):
        self.log.insert('end', msg + '\n')
        self.log.see('end')

    def _run_ga(self):
        if not self.groups_data:
            messagebox.showwarning("Error", "No hay grupos configurados.")
            return
        if not self.subjects_data:
            messagebox.showwarning("Error", "No hay materias configuradas.")
            return
        try:
            start = int(self.iv['start'].get())
            end   = int(self.iv['end'].get())
            days  = int(self.iv['days'].get())
            if end <= start or days < 1:
                raise ValueError
            slots = end - start
            pop   = int(self.pv['pop'].get())
            gens  = int(self.pv['gen'].get())
            mut   = float(self.pv['mut'].get())
            elite = int(self.pv['elite'].get())
            tourn = int(self.pv['tourn'].get())
        except ValueError:
            messagebox.showerror("Error", "Parámetro inválido.")
            return

        self._cfg_start = start
        self._cfg_slots = slots
        self._cfg_days  = days

        all_sids = [s.id for s in self.subjects_data]
        for g in self.groups_data:
            if not g.subject_ids:
                g.subject_ids = all_sids[:]

        cfg = dict(
            groups=self.groups_data, subjects=self.subjects_data,
            professors=self.professors_data,
            days=days, slots=slots,
            pop_size=pop, generations=gens,
            mut_rate=mut, elite=elite, tourn_k=tourn,
        )

        self.stop_event.clear()
        self.run_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self.log.delete('1.0', 'end')
        self._log_write("╔══════════════════════════════════════════╗")
        self._log_write("║    UNIHORARIO  ·  Algoritmo Genético     ║")
        self._log_write("╚══════════════════════════════════════════╝")
        self._log_write(f"  Grupos: {len(self.groups_data)}  |  Materias: {len(self.subjects_data)}")
        self._log_write(f"  Jornada: {start}:00-{end}:00  |  {days} días  |  {slots} slots/día")
        self._log_write(f"  Población: {pop}  |  Generaciones: {gens}  |  Mutación: {mut}")
        self._log_write("─"*44)

        ga = GeneticAlgorithm(cfg)

        def thread_fn():
            def cb(gen, best, avg, best_s):
                self.root.after(0, lambda: self._update(gen, best, avg, best_s, gens))
            res, bh, ah = ga.run(callback=cb, stop_event=self.stop_event)
            self.root.after(0, lambda: self._on_done(res, bh, ah))

        self.ga_thread = threading.Thread(target=thread_fn, daemon=True)
        self.ga_thread.start()

    def _update(self, gen, best, avg, best_s, total):
        pct = gen / total * 100
        self.pvar.set(pct)
        self.stat_str.set(f"Generación {gen}/{total}  —  Mejor Fitness: {best:.4f}")
        self._stat_vars['gen'].set(str(gen))
        self._stat_vars['best'].set(f"{best:.3f}")
        self._stat_vars['avg'].set(f"{avg:.3f}")
        self._stat_vars['conf'].set(str(best_s.details.get('prof_conflicts', '?')))
        self._stat_vars['gaps'].set(str(best_s.details.get('student_gaps', '?')))
        if gen % 20 == 0:
            c = best_s.details.get('prof_conflicts', '?')
            self._log_write(f"  Gen {gen:4d}  best={best:.4f}  avg={avg:.4f}  conf={c}")

    def _stop_ga(self):
        self.stop_event.set()

    def _on_done(self, results, bh, ah):
        self.run_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
        self.pvar.set(100)
        self.results   = results
        self.best_hist = bh
        self.avg_hist  = ah
        self._log_write("─"*44)
        self._log_write(f"  ✓ Completado  |  {len(bh)} generaciones")
        if bh:
            self._log_write(f"  Mejor fitness: {bh[-1]:.4f}")
        self._display_results()
        self._draw_graph()
        if results:
            self.nb.select(2)
            messagebox.showinfo("✓ Completado",
                f"Algoritmo terminado.\nMejor fitness: {results[0].fitness:.4f}\n"
                f"Conflictos de profesor: {results[0].details.get('prof_conflicts',0)}")

    def _build_results_tab(self):
        self.rnb = ttk.Notebook(self.tab_results)
        self.rnb.pack(fill='both', expand=True, padx=8, pady=8)
        self.r_frames = []
        for i in range(3):
            f = tk.Frame(self.rnb, bg=COLORS['bg'])
            self.rnb.add(f, text=f'  #{i+1}  ')
            self.r_frames.append(f)
            tk.Label(f, text="Ejecuta el Algoritmo Genético\npara ver los resultados aquí.",
                     bg=COLORS['bg'], fg=COLORS['muted'],
                     font=('Courier New', 13)).pack(expand=True)

    def _display_results(self):
        for i, (sched, frm) in enumerate(zip(self.results, self.r_frames)):
            for w in frm.winfo_children():
                w.destroy()

            det = sched.details
            pct = min(100, sched.fitness / 10)

            hb = tk.Frame(frm, bg=COLORS['panel'])
            hb.pack(fill='x', padx=8, pady=6)
            medals = ['🥇','🥈','🥉']
            tk.Label(hb, text=f"{medals[i]}  #{i+1}  Fitness: {sched.fitness:.4f}  ({pct:.1f}%)",
                     font=('Courier New', 12, 'bold'),
                     bg=COLORS['panel'], fg=COLORS['highlight']).pack(side='left', padx=12)
            info = (f"Conflictos: {det.get('prof_conflicts',0)}  |  "
                    f"Huecos: {det.get('student_gaps',0)}  |  "
                    f"Sesiones>2h: {det.get('long_sessions',0)}  |  "
                    f"RepetDía: {det.get('repeated_subjects',0)}")
            tk.Label(hb, text=info,
                     font=('Courier New', 8),
                     bg=COLORS['panel'], fg=COLORS['warn']).pack(side='left', padx=16)

            gnb = ttk.Notebook(frm)
            gnb.pack(fill='both', expand=True, padx=8, pady=4)
            for g in self.groups_data:
                gf = tk.Frame(gnb, bg=COLORS['bg'])
                gnb.add(gf, text=f'  {g.name}  ')
                self._draw_schedule_grid(gf, sched, g)

            self.rnb.tab(i, text=f"  {medals[i]} #{i+1} ({pct:.0f}%)  ")

    def _draw_schedule_grid(self, parent, sched: Schedule, group: Group):
        start = self._cfg_start
        slots = self._cfg_slots
        days  = self._cfg_days

        scol = {s.id: SUBJECT_PALETTE[j % len(SUBJECT_PALETTE)]
                for j, s in enumerate(self.subjects_data)}

        can = tk.Canvas(parent, bg=COLORS['bg'], highlightthickness=0)
        vsb = ttk.Scrollbar(parent, orient='vertical', command=can.yview)
        hsb = ttk.Scrollbar(parent, orient='horizontal', command=can.xview)
        sf  = tk.Frame(can, bg=COLORS['bg'])
        sf.bind("<Configure>",
                lambda e: can.configure(scrollregion=can.bbox('all')))
        can.create_window((0,0), window=sf, anchor='nw')
        can.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side='right', fill='y')
        hsb.pack(side='bottom', fill='x')
        can.pack(fill='both', expand=True)

        CW = 130
        CH = 34

        dn = DAY_NAMES[:days]

        tk.Label(sf, text="HORA", width=8, height=2,
                 bg=COLORS['accent'], fg='white',
                 font=('Courier New', 8, 'bold'),
                 relief='flat').grid(row=0, column=0, padx=1, pady=1, sticky='nsew')
        for ci, d in enumerate(dn):
            tk.Label(sf, text=d, width=CW//8, height=2,
                     bg=COLORS['accent'], fg='white',
                     font=('Courier New', 9, 'bold'),
                     relief='flat').grid(row=0, column=ci+1, padx=1, pady=1, sticky='nsew')

        grid = sched.grid[group.id]
        for sl in range(slots):
            tk.Label(sf, text=f"{start+sl:02d}:00", width=8, height=2,
                     bg=COLORS['panel'], fg=COLORS['muted'],
                     font=('Courier New', 8, 'bold'),
                     relief='flat').grid(row=sl+1, column=0, padx=1, pady=1, sticky='nsew')
            for ci in range(days):
                sid = grid[ci][sl]
                if sid:
                    sub  = next((s for s in self.subjects_data if s.id == sid), None)
                    name = (sub.name[:14]+'…' if sub and len(sub.name)>14 else
                            (sub.name if sub else sid))
                    color = scol.get(sid, '#888')
                    tk.Label(sf, text=name, width=CW//8, height=2,
                             bg=color, fg='#0D0D1A',
                             font=('Courier New', 7, 'bold'),
                             relief='flat', wraplength=120,
                             justify='center').grid(row=sl+1, column=ci+1,
                                                    padx=1, pady=1, sticky='nsew')
                else:
                    tk.Label(sf, text='', width=CW//8, height=2,
                             bg=COLORS['bg'], fg=COLORS['text'],
                             relief='flat').grid(row=sl+1, column=ci+1,
                                                  padx=1, pady=1, sticky='nsew')

        lf = tk.Frame(parent, bg=COLORS['surface'])
        lf.pack(fill='x', padx=8, pady=4)
        tk.Label(lf, text="Leyenda:", bg=COLORS['surface'],
                 fg=COLORS['muted'],
                 font=('Courier New', 8, 'bold')).pack(side='left', padx=6)
        for j, s in enumerate(self.subjects_data):
            c = SUBJECT_PALETTE[j % len(SUBJECT_PALETTE)]
            tk.Label(lf, text=f' {s.name[:10]} ',
                     bg=c, fg='#0D0D1A',
                     font=('Courier New', 7, 'bold'),
                     relief='raised', padx=2).pack(side='left', padx=3, pady=4)

    def _build_graph_tab(self):
        self.fig = Figure(figsize=(11, 6), dpi=100)
        self.fig.patch.set_facecolor(COLORS['bg'])
        self.ax  = self.fig.add_subplot(111)
        self._style_ax()
        self.ax.text(0.5, 0.5, "Ejecuta el Algoritmo Genético\npara ver la curva de convergencia",
                     transform=self.ax.transAxes, ha='center', va='center',
                     color=COLORS['muted'], fontsize=13,
                     fontfamily='Courier New')
        self.fig_canvas = FigureCanvasTkAgg(self.fig, master=self.tab_graph)
        self.fig_canvas.draw()
        self.fig_canvas.get_tk_widget().pack(fill='both', expand=True, padx=8, pady=8)

    def _style_ax(self):
        ax = self.ax
        ax.set_facecolor(COLORS['surface'])
        for sp in ax.spines.values():
            sp.set_color(COLORS['border'])
        ax.tick_params(colors=COLORS['muted'], labelsize=9)
        ax.set_title("Curva de Convergencia — Algoritmo Genético",
                     color=COLORS['text'], fontsize=13,
                     fontweight='bold', fontfamily='Courier New', pad=14)
        ax.set_xlabel("Generación", color=COLORS['muted'],
                      fontfamily='Courier New')
        ax.set_ylabel("Fitness", color=COLORS['muted'],
                      fontfamily='Courier New')

    def _draw_graph(self):
        self.ax.clear()
        self._style_ax()
        bh = self.best_hist
        ah = self.avg_hist
        if not bh:
            self.fig_canvas.draw()
            return

        xs = range(1, len(bh)+1)
        self.ax.plot(xs, bh, color=COLORS['highlight'], lw=2.2,
                     label='Mejor Fitness', zorder=3)
        self.ax.plot(xs, ah, color=COLORS['warn'],      lw=1.5,
                     linestyle='--', alpha=0.85,
                     label='Fitness Promedio', zorder=2)
        self.ax.fill_between(xs, ah, bh,
                              color=COLORS['highlight'], alpha=0.08)

        best_i = bh.index(max(bh))
        self.ax.annotate(
            f" {bh[best_i]:.4f}",
            xy=(best_i+1, bh[best_i]),
            color=COLORS['highlight'],
            fontsize=9, fontfamily='Courier New',
            arrowprops=dict(arrowstyle='->', color=COLORS['highlight'], lw=1.2),
            xytext=(best_i+1 + max(1, len(bh)*0.04), bh[best_i]*0.97),
        )
        self.ax.grid(True, color=COLORS['border'], alpha=0.4, linestyle=':')
        leg = self.ax.legend(facecolor=COLORS['panel'],
                              labelcolor=COLORS['text'],
                              fontsize=9, framealpha=0.9)
        leg.get_frame().set_edgecolor(COLORS['border'])
        self.fig.tight_layout()
        self.fig_canvas.draw()

if __name__ == '__main__':
    root = tk.Tk()
    app  = UnihorarioApp(root)
    root.mainloop()
