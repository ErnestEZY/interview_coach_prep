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
