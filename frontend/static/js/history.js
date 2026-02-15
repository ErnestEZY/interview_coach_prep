const { createApp } = Vue;

const app = createApp({
    data() {
        return {
            logged: false,
            isAdmin: false,
            userName: '',
            userEmail: '',
            hasAnalyzed: false,
            sessionTime: 0,
            timerId: null,
            items: [],
            allItems: [],
            sortOrder: 'desc',
            loading: false,
            detailsLoading: false,
            expandedId: null,
            expandedDetails: null,
            statusMessage: ''
        };
    },
    mounted() {
        this.logged = !!(window.icp && window.icp.state && window.icp.state.token);
        
        window.addEventListener('auth:changed', () => {
            const wasLogged = this.logged;
            this.logged = !!(window.icp && window.icp.state && window.icp.state.token);
            
            if (this.logged && !wasLogged) {
                this.init();
            } else if (!this.logged) {
                if (this.timerId) clearInterval(this.timerId);
                this.items = [];
            }
        });

        this.init();
        
        // Mobile menu handler
        window.handleMobileMenu = function() {
            const sidebar = document.getElementById('mobileSidebar');
            const overlay = document.getElementById('sidebarOverlay');
            if (sidebar && overlay) {
                sidebar.classList.toggle('active');
                overlay.classList.toggle('active');
            }
        };
    },
    methods: {
        showProgressChart() {
            // Filter logic:
            // 1. Only include items that have a valid numeric readiness_score (not null, not undefined)
            // 2. This automatically excludes "N/A" (null) scores and "Paused/In Progress" sessions (null)
            // 3. Sort by created_at ascending so the line flows correctly over time
            const data = this.allItems
                .filter(it => typeof it.readiness_score === 'number')
                .sort((a, b) => new Date(a.created_at) - new Date(b.created_at));

            if (data.length < 2) {
                Swal.fire({
                    icon: 'info',
                    title: 'Not Enough Data',
                    html: `
                        <p class="text-secondary mb-4">Complete at least <strong>2 full interview sessions</strong> to unlock your progress analysis chart.</p>
                        <div class="d-grid gap-2 col-8 mx-auto">
                            <a href="/static/pages/interview.html" class="btn btn-primary">
                                <i class="bi bi-play-circle me-2"></i>Start Mock Interview
                            </a>
                        </div>
                    `,
                    showConfirmButton: false,
                    showCloseButton: true
                });
                return;
            }

            const labels = data.map(it => {
                const date = new Date(it.created_at);
                return `${date.getDate()}/${date.getMonth() + 1}`;
            });
            const scores = data.map(it => it.readiness_score);

            // Calculate Trend (Latest Score vs Previous Score)
            const latestScore = scores[scores.length - 1];
            const previousScore = scores[scores.length - 2];
            const diff = latestScore - previousScore;
            
            let trendHtml = '';
            if (diff > 0) {
                trendHtml = `<div class="mt-3 text-center text-muted" style="font-size: 1rem;">
                    <i class="bi bi-graph-up-arrow me-2 text-success"></i>You improved by <span class="text-success fw-bold">+${diff}</span> points since your last session!
                </div>`;
            } else if (diff < 0) {
                trendHtml = `<div class="mt-3 text-center text-muted" style="font-size: 1rem;">
                    <i class="bi bi-graph-down-arrow me-2 text-danger"></i>Score dropped by <span class="text-danger fw-bold">${diff}</span> points. Keep practicing!
                </div>`;
            } else {
                trendHtml = `<div class="mt-3 text-center text-muted" style="font-size: 1rem;">
                    <i class="bi bi-dash-lg me-2 text-secondary"></i>Your score remained steady at <span class="text-dark fw-bold">${latestScore}</span>.
                </div>`;
            }

            // Dynamic Point Colors based on score
            const pointColors = scores.map(s => {
                if (s >= 75) return '#198754'; // Success Green
                if (s >= 50) return '#ffc107'; // Warning Yellow
                return '#dc3545'; // Danger Red
            });

            Swal.fire({
                title: 'Interview Readiness Progress',
                // Wrap canvas in a relative container with fixed height to prevent Chart.js from expanding indefinitely
                html: `<div style="position: relative; height: 300px; width: 100%;">
                        <canvas id="progressChart"></canvas>
                       </div>
                       ${trendHtml}`,
                width: 800,
                showCloseButton: true,
                showConfirmButton: false,
                didOpen: () => {
                    const ctx = document.getElementById('progressChart').getContext('2d');
                    new Chart(ctx, {
                        type: 'line',
                        data: {
                            labels: labels,
                            datasets: [{
                                label: 'Readiness Score',
                                data: scores,
                                borderColor: '#0d6efd',
                                backgroundColor: 'rgba(13, 110, 253, 0.1)',
                                tension: 0.3,
                                fill: true,
                                pointRadius: 6,
                                pointHoverRadius: 8,
                                pointBackgroundColor: pointColors,
                                pointBorderColor: '#fff',
                                spanGaps: true
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            scales: {
                                y: {
                                    beginAtZero: true,
                                    max: 100,
                                    grid: {
                                        color: 'rgba(0, 0, 0, 0.05)' // Light grey for white bg
                                    },
                                    ticks: { color: '#6c757d' } // Darker grey for white bg
                                },
                                x: {
                                    grid: { display: false },
                                    ticks: { color: '#6c757d' } // Darker grey for white bg
                                }
                            },
                            plugins: {
                                legend: { display: false },
                                tooltip: {
                                    mode: 'index',
                                    intersect: false,
                                    callbacks: {
                                        title: (tooltipItems) => {
                                            const index = tooltipItems[0].dataIndex;
                                            const item = data[index];
                                            return this.toMalaysiaTime(item.created_at);
                                        },
                                        label: (context) => {
                                            let label = context.dataset.label || '';
                                            if (label) {
                                                label += ': ';
                                            }
                                            if (context.parsed.y !== null) {
                                                label += context.parsed.y;
                                            }
                                            return label;
                                        }
                                    }
                                },
                                annotation: {
                                    annotations: {
                                        line1: {
                                            type: 'line',
                                            yMin: 70,
                                            yMax: 70,
                                            borderColor: 'rgba(25, 135, 84, 0.5)', // Transparent Green
                                            borderWidth: 2,
                                            borderDash: [5, 5],
                                            label: {
                                                content: 'Target Goal (70)',
                                                enabled: true,
                                                position: 'end',
                                                backgroundColor: 'rgba(25, 135, 84, 0.8)',
                                                color: 'white',
                                                font: { size: 10 }
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        plugins: [{
                            id: 'customAnnotation',
                            beforeDraw: (chart) => {
                                const { ctx, chartArea: { top, right, bottom, left, width, height }, scales: { y } } = chart;
                                const yVal = y.getPixelForValue(70);
                                
                                if (yVal >= top && yVal <= bottom) {
                                    ctx.save();
                                    ctx.beginPath();
                                    ctx.strokeStyle = 'rgba(25, 135, 84, 0.6)'; // Dashed Green Line
                                    ctx.lineWidth = 2;
                                    ctx.setLineDash([5, 5]);
                                    ctx.moveTo(left, yVal);
                                    ctx.lineTo(right, yVal);
                                    ctx.stroke();
                                    
                                    // Label
                                    ctx.fillStyle = 'rgba(25, 135, 84, 1)';
                                    ctx.font = '10px sans-serif';
                                    ctx.fillText('Target Goal (70)', right - 80, yVal - 5);
                                    ctx.restore();
                                }
                            }
                        }]
                    });
                }
            });
        },
        async setUserFromToken() {
            const token = window.icp && window.icp.state ? window.icp.state.token : localStorage.getItem("token");
            if (!token) return;
            try {
                const response = await axios.get(window.icp.apiUrl('/api/auth/me'));
                const me = response.data || {};
                this.userName = me.name || 'Guest';
                this.userEmail = me.email || '';
                this.hasAnalyzed = !!me.has_analyzed || !!localStorage.getItem('resume_feedback');
            } catch (_) {
                try {
                    const base64Url = token.split('.')[1];
                    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
                    const payload = JSON.parse(atob(base64));
                    this.userName = payload.name || 'Guest';
                    this.userEmail = payload.email || '';
                    this.hasAnalyzed = !!payload.has_analyzed || !!localStorage.getItem('resume_feedback');
                } catch (e) {}
            }
        },
        formatTime(seconds) {
            if (isNaN(seconds) || seconds === null || seconds === undefined) return '0:00';
            const totalSeconds = Math.max(0, Math.floor(seconds));
            const m = Math.floor(totalSeconds / 60);
            const s = totalSeconds % 60;
            return `${m}:${s.toString().padStart(2, '0')}`;
        },
        toMalaysiaTime(utcString) {
            if (!utcString) return 'Unknown';
            const date = new Date(utcString);
            return new Intl.DateTimeFormat('en-MY', {
                timeZone: 'Asia/Kuala_Lumpur',
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: false
            }).format(date);
        },
        startTimer() {
            if (this.timerId) return;
            const token = window.icp.state.token;
            if (!token) return;
            
            const payload = window.icp.decodeToken(token);
            if (!payload || !payload.exp) return;
            
            const exp = payload.exp;
            localStorage.setItem('session_expiry_user', exp);
            
            const updateTimer = () => {
                const now = Math.floor(Date.now() / 1000);
                this.sessionTime = Math.max(0, exp - now);
                if (this.sessionTime <= 0) {
                    clearInterval(this.timerId);
                    this.timerId = null;
                    localStorage.removeItem('session_expiry_user');
                    alert('Your session has expired. Please login again.');
                    window.icp.logout();
                }
            };
            
            updateTimer();
            this.timerId = setInterval(updateTimer, 1000);
        },
        async checkAdmin() {},
        async fetchHistory() {
            if (!this.logged) return;
            this.loading = true;
            
            try {
                const items = await axios.get(window.icp.apiUrl('/api/interview/history')).then(r => r.data);
                this.allItems = items;
                this.applySort();
            } catch (e) {
                console.error('Failed to fetch history', e);
                this.statusMessage = 'Failed to fetch history';
                if (e.response && e.response.status === 401) {
                    window.location.href = '/static/pages/login.html';
                }
            } finally {
                this.loading = false;
            }
        },
        applySort() {
            const sorted = [...this.allItems];
            sorted.sort((a, b) => {
                const da = new Date(a.created_at);
                const db = new Date(b.created_at);
                return this.sortOrder === 'desc' ? db - da : da - db;
            });
            this.items = sorted;
        },
        async toggleDetails(id) {
            if (this.expandedId === id) {
                this.expandedId = null;
                this.expandedDetails = null;
                return;
            }
            
            this.expandedId = id;
            this.detailsLoading = true;
            this.expandedDetails = null;
            
            try {
                const d = await axios.get(window.icp.apiUrl(`/api/interview/${id}`)).then(r => r.data);
                
                // Process transcript
                const t = Array.isArray(d.transcript) ? d.transcript : [];
                const pairs = [];
                for (let i = 0; i < t.length; i++) {
                    if (t[i].role === 'assistant') {
                        const q = t[i].text;
                        // Skip readiness feedback and score if they appear in transcript
                        if (d.readiness_feedback && q.includes(d.readiness_feedback.substring(0, 20))) continue;
                        if (q.includes("Interview Readiness Score")) continue;
                        
                        let a = '';
                        if (i + 1 < t.length && t[i + 1].role === 'user') { a = t[i + 1].text; }
                        pairs.push({ q, a });
                    }
                }
                
                d.pairs = pairs;
                
                // Format readiness feedback
                if (d.readiness_feedback) {
                    const parts = d.readiness_feedback.split('\n\n');
                    if (parts.length >= 2) {
                        d.formattedFeedback = parts.slice(1).join('\n\n').trim();
                    } else {
                        d.formattedFeedback = d.readiness_feedback;
                    }
                }
                
                this.expandedDetails = d;
            } catch (e) {
                console.error('Failed to load details', e);
                this.statusMessage = 'Failed to load details';
                Swal.fire({ icon: 'error', title: 'Error', text: 'Failed to load details' });
            } finally {
                this.detailsLoading = false;
            }
        },
        async deleteInterview(id) {
            const result = await Swal.fire({
                title: 'Delete History?',
                text: "You won't be able to revert this!",
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#d33',
                cancelButtonColor: '#3085d6',
                confirmButtonText: 'Yes, delete it!'
            });
            
            if (result.isConfirmed) {
                try {
                    await axios.delete(window.icp.apiUrl(`/api/interview/${id}`));
                    this.allItems = this.allItems.filter(it => it.id !== id);
                    this.applySort();
                    if (this.expandedId === id) {
                        this.expandedId = null;
                        this.expandedDetails = null;
                    }
                    Swal.fire('Deleted!', 'Interview history has been deleted.', 'success');
                    this.statusMessage = 'Interview history deleted';
                } catch (e) {
                    Swal.fire('Error!', 'Failed to delete history.', 'error');
                    this.statusMessage = 'Failed to delete history';
                }
            }
        },
        init() {
            if (this.logged) {
                this.startTimer();
                this.setUserFromToken();
                this.fetchHistory();
                
                // Hide global loader
                setTimeout(() => { 
                    const loader = document.getElementById('global-loader');
                    if(loader) loader.style.display = 'none'; 
                }, 500);
            } else {
                window.location.href = '/static/pages/login.html';
            }
        },
        logout() {
            window.icp.logout();
        }
    },
    watch: {
        sortOrder() {
            this.applySort();
        }
    }
});

app.mount('#app');
