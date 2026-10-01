
const subjectsData = [
    { id: "S1", name: "Matemáticas", hours_per_week: 5 },
    { id: "S2", name: "Física", hours_per_week: 5 },
    { id: "S3", name: "Programación", hours_per_week: 5 },
    { id: "S4", name: "Base de Datos", hours_per_week: 5 },
    { id: "S5", name: "Inglés", hours_per_week: 5 },
    { id: "S6", name: "Redes", hours_per_week: 5 },
    { id: "S7", name: "Álgebra Lineal", hours_per_week: 5 }
];

const professorsData = [
    { id: "P1", name: "Dr. Ramírez", subject_ids: ["S1"], unavailable: [] },
    { id: "P2", name: "Mtra. López", subject_ids: ["S2"], unavailable: [] },
    { id: "P3", name: "Ing. García", subject_ids: ["S3"], unavailable: [] },
    { id: "P4", name: "Dr. Martínez", subject_ids: ["S4"], unavailable: [] },
    { id: "P5", name: "Mtra. Sánchez", subject_ids: ["S5"], unavailable: [] },
    { id: "P6", name: "Ing. Torres", subject_ids: ["S6"], unavailable: [] },
    { id: "P7", name: "Dr. Herrera", subject_ids: ["S7"], unavailable: [] }
];

const groupsData = [
    { id: "8A", name: "8° A", semester: 8, subject_ids: ["S1", "S2", "S3", "S4", "S5", "S6", "S7"] },
    { id: "8B", name: "8° B", semester: 8, subject_ids: ["S1", "S2", "S3", "S4", "S5", "S6", "S7"] }
];

class Schedule {
    constructor(groups, subjects, professors, days = 5, slots = 8) {
        this.groups = groups;
        this.subjects = subjects;
        this.professors = professors;
        this.days = days;
        this.slots = slots;
        this.fitness = 0.0;
        
        this.grid = {};
        for (let g of groups) {
            this.grid[g.id] = [];
            for (let d = 0; d < days; d++) {
                this.grid[g.id].push(new Array(slots).fill(null));
            }
        }
    }

    clone() {
        let s = new Schedule(this.groups, this.subjects, this.professors, this.days, this.slots);
        s.fitness = this.fitness;
        for (let gid in this.grid) {
            for (let d = 0; d < this.days; d++) {
                s.grid[gid][d] = [...this.grid[gid][d]];
            }
        }
        return s;
    }
}

class GeneticAlgorithm {
    constructor(cfg) {
        this.groups = cfg.groups;
        
        this.subjects = {};
        cfg.subjects.forEach(s => this.subjects[s.id] = s);
        
        this.professors = {};
        cfg.professors.forEach(p => this.professors[p.id] = p);
        
        this.days = cfg.days || 5;
        this.slots = cfg.slots || 8;
        this.popSize = cfg.popSize || 100;
        this.generations = cfg.generations || 300;
        this.mutRate = cfg.mutRate || 0.15;
        this.elite = cfg.elite || 5;
        this.tournK = cfg.tournK || 3;

        this.sub2prof = {};
        cfg.professors.forEach(p => {
            p.subject_ids.forEach(sid => {
                this.sub2prof[sid] = p.id;
            });
        });

        this.blocked = {};
        cfg.professors.forEach(p => {
            this.blocked[p.id] = p.unavailable.map(u => `${u[0]},${u[1]}`);
        });
    }

    randomSchedule() {
        let sched = new Schedule(this.groups, this.subjects, this.professors, this.days, this.slots);
        for (let g of this.groups) {
            this.fillGroup(sched, g);
        }
        return sched;
    }

    fillGroup(sched, group) {
        let grid = sched.grid[group.id];
        let subHours = {};
        
        for (let sid of group.subject_ids) {
            subHours[sid] = (subHours[sid] || 0) + this.subjects[sid].hours_per_week;
        }

        let sessions = [];
        for (let sid in subHours) {
            let remaining = subHours[sid];
            while (remaining > 0) {
                let dur = remaining > 1 ? Math.min(2, remaining) : 1;
                if (remaining >= 2) {
                    dur = Math.random() < 0.5 ? 1 : 2;
                }
                sessions.push([sid, dur]);
                remaining -= dur;
            }
        }
        
        
        sessions.sort(() => Math.random() - 0.5);

        let subjectDays = {};
        for (let sid in subHours) subjectDays[sid] = new Set();

        for (let [sid, dur] of sessions) {
            let placed = false;
            let candidates = [];
            for (let d = 0; d < this.days; d++) {
                for (let s = 0; s < this.slots - dur + 1; s++) {
                    candidates.push([d, s]);
                }
            }
            candidates.sort(() => Math.random() - 0.5);

            for (let [d, s] of candidates) {
                if (subjectDays[sid].has(d)) continue;

                let overlap = false;
                for (let i = 0; i < dur; i++) {
                    if (grid[d][s+i] !== null) overlap = true;
                }
                if (overlap) continue;

                let pid = this.sub2prof[sid];
                if (pid) {
                    let blocked = false;
                    for (let i = 0; i < dur; i++) {
                        if (this.blocked[pid].includes(`${d},${s+i}`)) blocked = true;
                    }
                    if (blocked) continue;
                }

                for (let i = 0; i < dur; i++) grid[d][s+i] = sid;
                subjectDays[sid].add(d);
                placed = true;
                break;
            }

            if (!placed) {
                
                for (let d = 0; d < this.days; d++) {
                    for (let s = 0; s < this.slots - dur + 1; s++) {
                        let empty = true;
                        for (let i = 0; i < dur; i++) {
                            if (grid[d][s+i] !== null) empty = false;
                        }
                        if (empty) {
                            for (let i = 0; i < dur; i++) grid[d][s+i] = sid;
                            subjectDays[sid].add(d);
                            placed = true;
                            break;
                        }
                    }
                    if (placed) break;
                }
            }
            
            if (!placed) {
                
                for (let d = 0; d < this.days; d++) {
                    for (let s = 0; s < this.slots; s++) {
                        if (grid[d][s] === null) {
                            grid[d][s] = sid;
                            placed = true;
                            break;
                        }
                    }
                    if (placed) break;
                }
            }
        }
    }

    evaluate(sched) {
        let pen = 0.0;
        pen += this.profConflicts(sched) * 1000;
        pen += this.availViolations(sched) * 500;
        pen += this.studentGaps(sched) * 10;
        pen += this.longSessions(sched) * 60;
        pen += this.repeatedSubjectDay(sched) * 35;
        pen += this.dailyImbalance(sched) * 5;
        
        let fit = 1000.0 / (1.0 + pen);
        sched.fitness = fit;
        return fit;
    }

    profConflicts(s) {
        let slotUse = {};
        for (let g of this.groups) {
            for (let d = 0; d < this.days; d++) {
                for (let sl = 0; sl < this.slots; sl++) {
                    let sid = s.grid[g.id][d][sl];
                    if (sid) {
                        let pid = this.sub2prof[sid];
                        if (pid) {
                            let k = `${d},${sl},${pid}`;
                            slotUse[k] = (slotUse[k] || 0) + 1;
                        }
                    }
                }
            }
        }
        let conf = 0;
        for (let k in slotUse) {
            if (slotUse[k] > 1) conf += slotUse[k] - 1;
        }
        return conf;
    }

    availViolations(s) { return 0; } 

    studentGaps(s) {
        let gaps = 0;
        for (let g of this.groups) {
            for (let d = 0; d < this.days; d++) {
                let row = s.grid[g.id][d];
                let first = row.findIndex(x => x !== null);
                if (first === -1) continue;
                let last = -1;
                for (let i = this.slots - 1; i >= 0; i--) {
                    if (row[i] !== null) { last = i; break; }
                }
                for (let i = first; i <= last; i++) {
                    if (row[i] === null) gaps++;
                }
            }
        }
        return gaps;
    }

    longSessions(s) { return 0; } 

    repeatedSubjectDay(s) {
        let v = 0;
        for (let g of this.groups) {
            for (let d = 0; d < this.days; d++) {
                let row = s.grid[g.id][d];
                let seen = {};
                let prev = null;
                for (let sl = 0; sl < this.slots; sl++) {
                    let cur = row[sl];
                    if (cur && cur !== prev) {
                        seen[cur] = (seen[cur] || 0) + 1;
                    }
                    prev = cur;
                }
                for (let c in seen) {
                    if (seen[c] > 1) v += seen[c] - 1;
                }
            }
        }
        return v;
    }

    dailyImbalance(s) { return 0; }

    tournament(pop) {
        let best = null;
        for (let i = 0; i < this.tournK; i++) {
            let cand = pop[Math.floor(Math.random() * pop.length)];
            if (!best || cand.fitness > best.fitness) best = cand;
        }
        return best;
    }

    crossover(p1, p2) {
        let c1 = p1.clone();
        let c2 = p2.clone();
        let gids = this.groups.map(g => g.id);
        if (gids.length >= 2) {
            let pt = Math.floor(Math.random() * (gids.length - 1)) + 1;
            for (let i = pt; i < gids.length; i++) {
                let gid = gids[i];
                c1.grid[gid] = p2.grid[gid].map(r => [...r]);
                c2.grid[gid] = p1.grid[gid].map(r => [...r]);
            }
        }
        return [c1, c2];
    }

    mutate(sched) {
        let m = sched.clone();
        for (let g of this.groups) {
            if (Math.random() >= this.mutRate) continue;
            let grid = m.grid[g.id];
            let kind = Math.random();
            
            if (kind < 0.33) {
                
                let d1 = Math.floor(Math.random() * this.days), s1 = Math.floor(Math.random() * this.slots);
                let d2 = Math.floor(Math.random() * this.days), s2 = Math.floor(Math.random() * this.slots);
                let temp = grid[d1][s1];
                grid[d1][s1] = grid[d2][s2];
                grid[d2][s2] = temp;
            } else if (kind < 0.66) {
                
                let d1 = Math.floor(Math.random() * this.days);
                let d2 = Math.floor(Math.random() * this.days);
                let temp = grid[d1];
                grid[d1] = grid[d2];
                grid[d2] = temp;
            } else {
                
                for(let i = 0; i < this.days; i++) {
                    grid[i] = new Array(this.slots).fill(null);
                }
                this.fillGroup(m, g);
            }
        }
        return m;
    }
}


self.onmessage = function(e) {
    if (e.data.command === 'start') {
        const config = e.data.config;
        const ga = new GeneticAlgorithm({
            groups: groupsData,
            subjects: subjectsData,
            professors: professorsData,
            generations: config.generations,
            popSize: config.popSize,
            days: config.days,
            slots: config.slots
        });

        let pop = [];
        for (let i = 0; i < ga.popSize; i++) {
            let s = ga.randomSchedule();
            ga.evaluate(s);
            pop.push(s);
        }

        let gen = 0;
        
        function processNextChunk() {
            let endGen = Math.min(gen + 10, ga.generations); 
            
            for (; gen < endGen; gen++) {
                pop.sort((a, b) => b.fitness - a.fitness);
                
                let newPop = pop.slice(0, ga.elite).map(s => s.clone());
                while (newPop.length < ga.popSize) {
                    let p1 = ga.tournament(pop);
                    let p2 = ga.tournament(pop);
                    let c1, c2;
                    if (Math.random() < 0.8) {
                        [c1, c2] = ga.crossover(p1, p2);
                    } else {
                        c1 = p1.clone(); c2 = p2.clone();
                    }
                    c1 = ga.mutate(c1); ga.evaluate(c1);
                    c2 = ga.mutate(c2); ga.evaluate(c2);
                    newPop.push(c1, c2);
                }
                pop = newPop.slice(0, ga.popSize);
            }
            
            pop.sort((a, b) => b.fitness - a.fitness);

            self.postMessage({
                type: 'progress',
                generation: gen,
                bestFitness: pop[0].fitness
            });

            if (gen < ga.generations) {
                
                setTimeout(processNextChunk, 0);
            } else {
                self.postMessage({
                    type: 'done',
                    bestSchedule: pop[0],
                    bestFitness: pop[0].fitness
                });
            }
        }
        
        processNextChunk();
    }
};
