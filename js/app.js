document.addEventListener('DOMContentLoaded', () => {
    const startBtn = document.getElementById('start-btn');
    const cancelBtn = document.getElementById('cancel-btn');
    const progressBar = document.getElementById('progress-bar');
    const statusText = document.getElementById('status-text');
    const fitnessText = document.getElementById('fitness-text');
    const scheduleContainer = document.getElementById('schedule-container');
    const genCountInput = document.getElementById('gen-count');
    const popSizeInput = document.getElementById('pop-size');

    let worker = null;

    function renderSchedule(schedule) {
        scheduleContainer.innerHTML = '';
        
        
        const days = 5;
        const slots = 8;
        const dayNames = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"];

        
        for (const [groupId, grid] of Object.entries(schedule.grid)) {
            const groupTitle = document.createElement('h3');
            groupTitle.className = 'group-title';
            groupTitle.textContent = `Grupo: ${groupId}`;
            scheduleContainer.appendChild(groupTitle);

            const gridDiv = document.createElement('div');
            gridDiv.className = 'schedule-grid';

            
            const corner = document.createElement('div');
            corner.className = 'schedule-header';
            corner.textContent = 'Hora';
            gridDiv.appendChild(corner);

            
            dayNames.forEach(d => {
                const dayHeader = document.createElement('div');
                dayHeader.className = 'schedule-header';
                dayHeader.textContent = d;
                gridDiv.appendChild(dayHeader);
            });

            
            for (let s = 0; s < slots; s++) {
                const timeCell = document.createElement('div');
                timeCell.className = 'schedule-header';
                timeCell.textContent = `${8 + s}:00`;
                gridDiv.appendChild(timeCell);

                for (let d = 0; d < days; d++) {
                    const cell = document.createElement('div');
                    cell.className = 'schedule-cell';
                    const subject = grid[d][s];
                    if (subject) {
                        cell.textContent = subject;
                        cell.classList.add('filled');
                    } else {
                        cell.textContent = '-';
                    }
                    gridDiv.appendChild(cell);
                }
            }

            scheduleContainer.appendChild(gridDiv);
        }
    }

    startBtn.addEventListener('click', () => {
        const generations = parseInt(genCountInput.value) || 100;
        const popSize = parseInt(popSizeInput.value) || 50;

        if (worker) {
            worker.terminate();
        }

        
        worker = new Worker('js/worker.js');
        
        startBtn.disabled = true;
        cancelBtn.disabled = false;
        progressBar.style.width = '0%';
        scheduleContainer.innerHTML = '';
        statusText.textContent = 'Iniciando procesamiento en segundo plano...';

        worker.postMessage({
            command: 'start',
            config: {
                generations,
                popSize,
                days: 5,
                slots: 8
            }
        });

        worker.onmessage = (e) => {
            const data = e.data;
            
            if (data.type === 'progress') {
                const percent = Math.round((data.generation / generations) * 100);
                progressBar.style.width = percent + '%';
                statusText.textContent = `Generación ${data.generation} de ${generations}...`;
                fitnessText.textContent = `Mejor Fitness: ${data.bestFitness.toFixed(2)}`;
                
                
            } else if (data.type === 'done') {
                statusText.textContent = 'Procesamiento completado.';
                progressBar.style.width = '100%';
                startBtn.disabled = false;
                cancelBtn.disabled = true;
                
                if (data.bestSchedule) {
                    renderSchedule(data.bestSchedule);
                }
                
                
                if (Notification.permission === 'granted') {
                    new Notification('UNIHORARIO Web', {
                        body: `Cálculo finalizado. Mejor fitness: ${data.bestFitness.toFixed(2)}`,
                        icon: './'
                    });
                }
            }
        };

        worker.onerror = (err) => {
            console.error('Worker error:', err);
            statusText.textContent = 'Error en el procesamiento.';
            startBtn.disabled = false;
            cancelBtn.disabled = true;
        };
    });

    cancelBtn.addEventListener('click', () => {
        if (worker) {
            worker.terminate();
            worker = null;
            statusText.textContent = 'Procesamiento cancelado por el usuario.';
            startBtn.disabled = false;
            cancelBtn.disabled = true;
            progressBar.style.width = '0%';
        }
    });

    
    if ('Notification' in window) {
        Notification.requestPermission();
    }
});
