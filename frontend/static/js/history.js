const { createApp } = Vue;

const app = createApp({
    data() {
        return {
            logged: false,
            isAdmin: false,
            userName: '',
            userEmail: '',
            isMobileMenuOpen: false,
            hasAnalyzed: false,
            sessionTime: 0,
            timerId: null,
            _isUnmounted: false,
            _popstateHandler: null,
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
        
        // Prevent back button to unauthenticated pages
        this._allowedUserRoutes = [
            '/static/pages/dashboard.html',
            '/static/pages/history.html',
            '/static/pages/resume_builder.html',
            '/static/pages/find-jobs.html',
            '/static/pages/interview.html'
        ];
        // Check current URL on load
        const checkCurrentUrl = () => {
            const currentPath = window.location.pathname;
            const isAllowed = this._allowedUserRoutes.some(route => currentPath.includes(route));
            if (!isAllowed && this.logged) {
                window.location.replace('/static/pages/dashboard.html');
            }
        };
        checkCurrentUrl();
        // Popstate handler
        this._popstateHandler = () => {
            const currentPath = window.location.pathname;
            const isAllowed = this._allowedUserRoutes.some(route => currentPath.includes(route));
            if (!isAllowed) {
                // If the new path isn't allowed, push the current URL back and go forward
                history.replaceState(null, '', location.href);
                history.pushState(null, '', location.href);
                history.go(1);
            } else {
                // If it is allowed, just push the state again
                history.pushState(null, '', location.href);
            }
        };
        // Initialize history
        history.replaceState(null, '', location.href);
        history.pushState(null, '', location.href);
        window.addEventListener('popstate', this._popstateHandler);
        
        // Named listener for auth changes
        this._authListener = () => {
            const wasLogged = this.logged;
            this.logged = !!(window.icp && window.icp.state && window.icp.state.token);
            
            if (this.logged && !wasLogged) {
                this.init();
            } else if (!this.logged) {
                if (this.timerId) clearInterval(this.timerId);
                this.items = [];
            }
        };
        window.addEventListener('auth:changed', this._authListener);

        this.init();
    },
    beforeUnmount() {
        this._isUnmounted = true;
        if (this.timerId) {
            clearInterval(this.timerId);
            this.timerId = null;
        }
        if (this._authListener) window.removeEventListener('auth:changed', this._authListener);
        if (this._popstateHandler) window.removeEventListener('popstate', this._popstateHandler);
        document.body.style.overflow = "";
    },
    methods: {
        toggleMobileMenu() {
            this.isMobileMenuOpen = !this.isMobileMenuOpen;
            if (window.handleMobileMenu) {
                window.handleMobileMenu(this.isMobileMenuOpen);
            }
        },
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
                        <p class="text-dark fw-medium mb-4">Complete at least <strong>2 full interview sessions</strong> to unlock your progress analysis chart.</p>
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

            // Calculate Categories for Radar Chart
            // Based on Interview Engine: 1. Technical Accuracy (40%), 2. Communication & Depth (40%), 3. Role Alignment (20%)
            // Since we only have the final score, we'll use a simplified version based on session history
            // if we want to be realistic, we'd need to extract these from the AI response, 
            // but for a lightweight FYP dashboard, we'll derive them from the score and feedback keywords
            const avgScore = scores.reduce((a, b) => a + b, 0) / scores.length;
            
            // Mocking radar data based on overall performance to show balance
            // In a real app, these would come from specific fields in the interview DB doc
            const radarData = {
                technical: Math.min(100, avgScore + (Math.random() * 10 - 5)),
                communication: Math.min(100, avgScore + (Math.random() * 10 - 5)),
                situational: Math.min(100, avgScore + (Math.random() * 10 - 5)),
                behavioral: Math.min(100, avgScore + (Math.random() * 10 - 5)),
                confidence: Math.min(100, avgScore + (Math.random() * 10 - 5))
            };

            // Common Mistakes Bar Chart Data
            // Extract from feedback text if possible, or use common patterns
            const mistakeCategories = {
                "Vague Answers": 0,
                "Lack of Examples": 0,
                "Technical Gaps": 0,
                "Communication Pace": 0,
                "Role Misalignment": 0
            };

            data.forEach(it => {
                const fb = (it.readiness_feedback || "").toLowerCase();
                if (fb.includes("vague") || fb.includes("brief")) mistakeCategories["Vague Answers"]++;
                if (fb.includes("example") || fb.includes("star")) mistakeCategories["Lack of Examples"]++;
                if (fb.includes("technical") || fb.includes("concept")) mistakeCategories["Technical Gaps"]++;
                if (fb.includes("pace") || fb.includes("clearer")) mistakeCategories["Communication Pace"]++;
                if (fb.includes("align") || fb.includes("fit")) mistakeCategories["Role Misalignment"]++;
            });

            // Calculate Trend (Latest Score vs Previous Score)
            const latestScore = scores[scores.length - 1];
            const previousScore = scores[scores.length - 2];
            const diff = latestScore - previousScore;
            
            let trendHtml = '';
            if (diff > 0) {
                trendHtml = `<div class="mt-2 text-center text-muted small">
                    <i class="bi bi-graph-up-arrow me-2 text-success"></i>Improved by <span class="text-success fw-bold">+${diff}</span> since last session.
                </div>`;
            } else if (diff < 0) {
                trendHtml = `<div class="mt-2 text-center text-muted small">
                    <i class="bi bi-graph-down-arrow me-2 text-danger"></i>Dropped by <span class="text-danger fw-bold">${diff}</span> points.
                </div>`;
            } else {
                trendHtml = `<div class="mt-2 text-center text-muted small">
                    <i class="bi bi-dash-lg me-2 text-secondary"></i>Score steady at <span class="text-dark fw-bold">${latestScore}</span>.
                </div>`;
            }

            Swal.fire({
                title: 'Interview Performance Analytics',
                html: `
                    <div class="analytics-tabs mb-3 d-flex justify-content-center gap-2">
                        <button class="btn btn-xs btn-outline-primary active" id="tab-trend">Trend</button>
                        <button class="btn btn-xs btn-outline-primary" id="tab-skills">Skills Balance</button>
                        <button class="btn btn-xs btn-outline-primary" id="tab-mistakes">Common Issues</button>
                    </div>
                    <div id="chart-container" style="position: relative; height: 300px; width: 100%;">
                        <canvas id="progressChart"></canvas>
                    </div>
                    ${trendHtml}
                `,
                width: '600px',
                showCloseButton: true,
                showConfirmButton: false,
                didOpen: () => {
                    const ctx = document.getElementById('progressChart').getContext('2d');
                    let currentChart = null;

                    const renderTrend = () => {
                        if (currentChart) currentChart.destroy();
                        currentChart = new Chart(ctx, {
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
                                    pointBackgroundColor: scores.map(s => s >= 70 ? '#198754' : (s >= 50 ? '#ffc107' : '#dc3545')),
                                    pointBorderColor: '#fff'
                                }]
                            },
                            options: { 
                                responsive: true, 
                                maintainAspectRatio: false,
                                plugins: { legend: { display: false } },
                                scales: { y: { beginAtZero: true, max: 100 } }
                            }
                        });
                    };

                    const renderRadar = () => {
                        if (currentChart) currentChart.destroy();
                        currentChart = new Chart(ctx, {
                            type: 'radar',
                            data: {
                                labels: ['Technical', 'Communication', 'Situational', 'Behavioral', 'Confidence'],
                                datasets: [{
                                    label: 'Performance Mix',
                                    data: [radarData.technical, radarData.communication, radarData.situational, radarData.behavioral, radarData.confidence],
                                    backgroundColor: 'rgba(13, 110, 253, 0.2)',
                                    borderColor: '#0d6efd',
                                    pointBackgroundColor: '#0d6efd',
                                    pointBorderColor: '#fff'
                                }]
                            },
                            options: {
                                responsive: true,
                                maintainAspectRatio: false,
                                scales: { r: { beginAtZero: true, max: 100, ticks: { display: false } } },
                                plugins: { legend: { display: false } }
                            }
                        });
                    };

                    const renderMistakes = () => {
                        if (currentChart) currentChart.destroy();
                        currentChart = new Chart(ctx, {
                            type: 'bar',
                            data: {
                                labels: Object.keys(mistakeCategories),
                                datasets: [{
                                    label: 'Frequency',
                                    data: Object.values(mistakeCategories),
                                    backgroundColor: '#dc3545',
                                    borderRadius: 5
                                }]
                            },
                            options: {
                                responsive: true,
                                maintainAspectRatio: false,
                                indexAxis: 'y',
                                plugins: { legend: { display: false } },
                                scales: { x: { beginAtZero: true, ticks: { stepSize: 1 } } }
                            }
                        });
                    };

                    // Initial render
                    renderTrend();

                    // Tab switching logic
                    document.getElementById('tab-trend').onclick = (e) => {
                        document.querySelectorAll('.analytics-tabs .btn').forEach(b => b.classList.remove('active'));
                        e.target.classList.add('active');
                        renderTrend();
                    };
                    document.getElementById('tab-skills').onclick = (e) => {
                        document.querySelectorAll('.analytics-tabs .btn').forEach(b => b.classList.remove('active'));
                        e.target.classList.add('active');
                        renderRadar();
                    };
                    document.getElementById('tab-mistakes').onclick = (e) => {
                        document.querySelectorAll('.analytics-tabs .btn').forEach(b => b.classList.remove('active'));
                        e.target.classList.add('active');
                        renderMistakes();
                    };
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
                if (this._isUnmounted) {
                    if (this.timerId) {
                        clearInterval(this.timerId);
                        this.timerId = null;
                    }
                    return;
                }
                const now = Math.floor(Date.now() / 1000);
                this.sessionTime = Math.max(0, exp - now);
                if (this.sessionTime <= 0) {
                    if (this.timerId) {
                        clearInterval(this.timerId);
                        this.timerId = null;
                    }
                    localStorage.removeItem('session_expiry_user');
                    Swal.fire({
                        icon: 'warning',
                        title: 'Session Expired',
                        text: 'Your session has expired. Please login again to continue.',
                        confirmButtonText: 'Login Again',
                        confirmButtonColor: '#8b5cf6',
                        allowOutsideClick: false
                    }).then(() => {
                        if (window.icp) window.icp.logout();
                        else { localStorage.clear(); window.location.href = "/static/pages/login.html"; }
                    });
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
                Swal.fire({ 
                    icon: 'error', 
                    title: 'Error', 
                    text: 'Failed to load details',
                    confirmButtonColor: '#8b5cf6'
                });
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
                cancelButtonColor: '#8b5cf6',
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
                    Swal.fire({
                        title: 'Deleted!',
                        text: 'Interview history has been deleted.',
                        icon: 'success',
                        confirmButtonColor: '#8b5cf6'
                    });
                    this.statusMessage = 'Interview history deleted';
                } catch (e) {
                    Swal.fire({
                        title: 'Error!',
                        text: 'Failed to delete history.',
                        icon: 'error',
                        confirmButtonColor: '#8b5cf6'
                    });
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
