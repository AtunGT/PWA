document.addEventListener('DOMContentLoaded', () => {
    // === TAB MANAGEMENT ===
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(btn.dataset.tab).classList.add('active');
        });
    });

    // === STATE MANAGEMENT ===
    let subjects = [
        { id: "S1", name: "Matemáticas", hours_per_week: 5 },
        { id: "S2", name: "Física", hours_per_week: 5 },
        { id: "S3", name: "Programación", hours_per_week: 5 },
        { id: "S4", name: "Base de Datos", hours_per_week: 5 },
        { id: "S5", name: "Inglés", hours_per_week: 5 },
        { id: "S6", name: "Redes", hours_per_week: 5 },
        { id: "S7", name: "Álgebra Lineal", hours_per_week: 5 }
    ];

    let professors = [
        { id: "P1", name: "Dr. Ramírez", subject_ids: ["S1"], unavailable: [] },
        { id: "P2", name: "Mtra. López", subject_ids: ["S2"], unavailable: [] },
        { id: "P3", name: "Ing. García", subject_ids: ["S3"], unavailable: [] },
        { id: "P4", name: "Dr. Martínez", subject_ids: ["S4"], unavailable: [] },
        { id: "P5", name: "Mtra. Sánchez", subject_ids: ["S5"], unavailable: [] },
        { id: "P6", name: "Ing. Torres", subject_ids: ["S6"], unavailable: [] },
        { id: "P7", name: "Dr. Herrera", subject_ids: ["S7"], unavailable: [] }
    ];

    let groups = [
        { id: "8A", name: "8° A", semester: 8, subject_ids: ["S1", "S2", "S3", "S4", "S5", "S6", "S7"] },
        { id: "8B", name: "8° B", semester: 8, subject_ids: ["S1", "S2", "S3", "S4", "S5", "S6", "S7"] }
    ];

    // === UI RENDERERS ===
    function setupTable(tableId, data, renderRow, onDelete) {
        const tbody = document.querySelector(`#${tableId} tbody`);
        tbody.innerHTML = '';
        data.forEach(item => {
            const tr = document.createElement('tr');
            tr.innerHTML = renderRow(item);
            tr.addEventListener('click', () => {
                const selected = tbody.querySelector('.selected');
                if (selected) selected.classList.remove('selected');
                tr.classList.add('selected');
                tr.dataset.id = item.id;
            });
            tbody.appendChild(tr);
        });
    }

    function refreshAllTables() {
        setupTable('subjects-table', subjects, s => `<td>${s.id}</td><td>${s.name}</td><td>${s.hours_per_week}</td>`);
        setupTable('groups-table', groups, g => `<td>${g.id}</td><td>${g.name}</td><td>${g.semester}</td>`);
        setupTable('profs-table', professors, p => {
            const subNames = p.subject_ids.map(sid => subjects.find(s => s.id === sid)?.name).join(', ') || '—';
            return `<td>${p.id}</td><td>${p.name}</td><td>${subNames}</td><td>${p.unavailable.length} slots</td>`;
        });
    }
    
    refreshAllTables();

    // === ADD/DEL LOGIC ===
    document.getElementById('btn-add-subj').addEventListener('click', () => {
        const name = document.getElementById('subj-name').value.trim();
        const hrs = parseInt(document.getElementById('subj-hrs').value);
        if (!name || isNaN(hrs)) return alert("Completa Nombre y Horas.");
        
        const id = `S${subjects.length + 1}`;
        subjects.push({ id, name, hours_per_week: hrs });
        
        const pid = `P${professors.length + 1}`;
        professors.push({ id: pid, name: `Profesor ${name.substring(0, 10)}`, subject_ids: [id], unavailable: [] });
        
        groups.forEach(g => g.subject_ids.push(id));
        refreshAllTables();
    });

    document.getElementById('btn-del-subj').addEventListener('click', () => {
        const tr = document.querySelector('#subjects-table tbody tr.selected');
        if (!tr) return alert("Selecciona una materia primero.");
        const id = tr.dataset.id;
        subjects = subjects.filter(s => s.id !== id);
        professors.forEach(p => p.subject_ids = p.subject_ids.filter(sid => sid !== id));
        groups.forEach(g => g.subject_ids = g.subject_ids.filter(sid => sid !== id));
        refreshAllTables();
    });

    document.getElementById('btn-add-group').addEventListener('click', () => {
        const id = document.getElementById('group-id').value.trim();
        const name = document.getElementById('group-name').value.trim();
        if (!id || !name) return alert("Completa ID y Nombre.");
        if (groups.find(g => g.id === id)) return alert("ID de grupo ya existe.");
        groups.push({ id, name, semester: 8, subject_ids: subjects.map(s => s.id) });
        refreshAllTables();
    });

    document.getElementById('btn-del-group').addEventListener('click', () => {
        const tr = document.querySelector('#groups-table tbody tr.selected');
        if (!tr) return alert("Selecciona un grupo primero.");
        groups = groups.filter(g => g.id !== tr.dataset.id);
        refreshAllTables();
    });

    document.getElementById('btn-auto-assign').addEventListener('click', () => {
        groups.forEach(g => g.subject_ids = subjects.map(s => s.id));
        refreshAllTables();
        alert("Todas las materias asignadas a todos los grupos.");
    });


    // === GA RUNNER LOGIC ===
    let worker = null;
    let convergenceData = { bests: [], avgs: [] };

    function drawChart() {
        const canvas = document.getElementById('convergence-chart');
        const ctx = canvas.getContext('2d');
        const w = canvas.width;
        const h = canvas.height;
        
        ctx.clearRect(0, 0, w, h);
        
        if (convergenceData.bests.length === 0) return;
        
        const pad = 40;
        const maxFit = Math.max(100, ...convergenceData.bests);
        const steps = convergenceData.bests.length;
        
        // Draw axes
        ctx.strokeStyle = '#2A2A50';
        ctx.beginPath();
        ctx.moveTo(pad, pad); ctx.lineTo(pad, h - pad); ctx.lineTo(w - pad, h - pad);
        ctx.stroke();

        function plotLine(data, color) {
            ctx.strokeStyle = color;
            ctx.lineWidth = 2;
            ctx.beginPath();
            data.forEach((val, i) => {
                const x = pad + (i / Math.max(1, steps - 1)) * (w - 2*pad);
                const y = h - pad - (val / maxFit) * (h - 2*pad);
                if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
            });
            ctx.stroke();
        }

        plotLine(convergenceData.avgs, '#F59E0B'); // Warn (Average)
        plotLine(convergenceData.bests, '#06D6A0'); // Highlight (Best)
    }

    function renderSchedule(schedule) {
        const container = document.getElementById('schedule-container');
        container.innerHTML = '';
        
        const days = 5;
        const slots = 8;
        const dayNames = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"];

        for (const [groupId, grid] of Object.entries(schedule.grid)) {
            const gTitle = document.createElement('h3');
            gTitle.className = 'group-title';
            gTitle.textContent = `Grupo: ${groupId}`;
            container.appendChild(gTitle);

            const gridDiv = document.createElement('div');
            gridDiv.className = 'schedule-grid';

            const corner = document.createElement('div');
            corner.className = 'schedule-header';
            corner.textContent = 'Hora';
            gridDiv.appendChild(corner);

            dayNames.forEach(d => {
                const dh = document.createElement('div');
                dh.className = 'schedule-header';
                dh.textContent = d;
                gridDiv.appendChild(dh);
            });

            for (let s = 0; s < slots; s++) {
                const tc = document.createElement('div');
                tc.className = 'schedule-header';
                tc.textContent = `${8 + s}:00`;
                gridDiv.appendChild(tc);

                for (let d = 0; d < days; d++) {
                    const cell = document.createElement('div');
                    cell.className = 'schedule-cell';
                    const subject = grid[d][s];
                    if (subject) {
                        const subjName = subjects.find(su => su.id === subject)?.name || subject;
                        cell.textContent = subjName;
                        cell.classList.add('filled');
                    } else {
                        cell.textContent = '-';
                    }
                    gridDiv.appendChild(cell);
                }
            }
            container.appendChild(gridDiv);
        }
    }

    const startBtn = document.getElementById('start-btn');
    const cancelBtn = document.getElementById('cancel-btn');
    const progressBar = document.getElementById('progress-bar');
    const statusText = document.getElementById('status-text');
    const fitnessText = document.getElementById('fitness-text');

    startBtn.addEventListener('click', () => {
        const generations = parseInt(document.getElementById('gen-count').value) || 100;
        const popSize = parseInt(document.getElementById('pop-size').value) || 50;

        if (worker) worker.terminate();
        worker = new Worker('js/worker.js');
        
        startBtn.disabled = true;
        cancelBtn.disabled = false;
        progressBar.style.width = '0%';
        convergenceData = { bests: [], avgs: [] };
        drawChart();
        document.getElementById('schedule-container').innerHTML = '<p style="text-align: center; color: var(--muted);">Procesando...</p>';
        statusText.textContent = 'Iniciando optimización...';
        
        // Pass dynamic state
        worker.postMessage({
            command: 'start',
            config: {
                generations, popSize, days: 5, slots: 8,
                subjects, professors, groups
            }
        });

        worker.onmessage = (e) => {
            const data = e.data;
            if (data.type === 'progress') {
                progressBar.style.width = Math.round((data.generation / generations) * 100) + '%';
                statusText.textContent = `Generación ${data.generation} de ${generations}...`;
                fitnessText.textContent = `Mejor Fitness: ${data.bestFitness.toFixed(2)}`;
                
                convergenceData.bests.push(data.bestFitness);
                convergenceData.avgs.push(data.avgFitness || (data.bestFitness * 0.8)); // Approx if worker doesn't send avg
                drawChart();
            } else if (data.type === 'done') {
                statusText.textContent = 'Procesamiento completado.';
                progressBar.style.width = '100%';
                startBtn.disabled = false;
                cancelBtn.disabled = true;
                if (data.bestSchedule) renderSchedule(data.bestSchedule);
                
                // Switch to results tab automatically
                document.querySelector('.tab-btn[data-tab="tab-results"]').click();

                if (Notification.permission === 'granted') {
                    new Notification('UNIHORARIO Web', { body: `Cálculo finalizado. Mejor fitness: ${data.bestFitness.toFixed(2)}` });
                }
            }
        };
    });

    cancelBtn.addEventListener('click', () => {
        if (worker) {
            worker.terminate();
            worker = null;
            statusText.textContent = 'Procesamiento cancelado.';
            startBtn.disabled = false;
            cancelBtn.disabled = true;
            progressBar.style.width = '0%';
        }
    });

    if ('Notification' in window) Notification.requestPermission();
    
    // Draw empty chart initially
    drawChart();
});
