const { createApp } = Vue;

const app = createApp({
    data() {
        return {
            logged: false,
            id: null,
            detail: null,
            fileUrl: '',
            errorMsg: '',
            sessionTime: 0,
            timerId: null
        };
    },
    mounted() {
        this.init();
        window.addEventListener('auth:changed', () => {
            this.logged = !!(window.icp && window.icp.state && window.icp.state.token);
            if (this.logged) this.startTimer();
        });
        window.addEventListener('beforeunload', () => {
            if (this.fileUrl) URL.revokeObjectURL(this.fileUrl);
        });
    },
    methods: {
        formatTime(seconds) {
            if (isNaN(seconds) || seconds === null || seconds === undefined) return '0:00';
            const totalSeconds = Math.max(0, Math.floor(seconds));
            const m = Math.floor(totalSeconds / 60);
            const s = totalSeconds % 60;
            return `${m}:${s.toString().padStart(2, '0')}`;
        },
        startTimer() {
            if (this.timerId) return;
            const token = window.icp.state.token;
            if (!token) return;
            
            const payload = window.icp.decodeToken(token);
            if (!payload || !payload.exp) return;
            
            const exp = payload.exp;
            localStorage.setItem('session_expiry_admin', exp);
            
            const updateTimer = () => {
                const now = Math.floor(Date.now() / 1000);
                this.sessionTime = Math.max(0, exp - now);
                if (this.sessionTime <= 0) {
                    clearInterval(this.timerId);
                    this.timerId = null;
                    localStorage.removeItem('session_expiry_admin');
                    alert('Admin session has expired. Please login again.');
                    window.icp.logout();
                }
            };
            
            updateTimer();
            this.timerId = setInterval(updateTimer, 1000);
        },
        async init() {
            const urlParams = new URLSearchParams(window.location.search);
            this.id = urlParams.get('id');
            
            this.logged = !!(window.icp && window.icp.state && window.icp.state.token);
            
            if (!this.logged) {
                window.location.href = '/static/pages/admin.html';
                return;
            }
            
            this.startTimer();
            
            try {
                const me = await axios.get(window.icp.apiUrl('/api/auth/me')).then(r => r.data);
                if (!(me.role === 'admin' || me.role === 'super_admin')) {
                    window.location.href = '/static/pages/admin.html';
                    return;
                }
            } catch (e) {
                window.location.href = '/static/pages/admin.html';
                return;
            }
            
            if (!this.id) {
                Swal.fire({ icon: 'error', title: 'Missing resume id' });
                return;
            }
            
            try {
                const response = await axios.get(window.icp.apiUrl(`/api/admin/resumes/${this.id}`));
                this.detail = response.data;
                
                // Fetch file
                try {
                    const fileResponse = await axios.get(window.icp.apiUrl(`/api/admin/resumes/${this.id}/file`), {
                        responseType: 'blob'
                    });
                    this.fileUrl = URL.createObjectURL(fileResponse.data);
                } catch (err) {
                    console.error('File fetch error:', err);
                    if (err.response && err.response.status === 404) {
                        this.errorMsg = 'No file available for this resume.';
                    } else {
                        // Fallback
                        this.fileUrl = window.icp.apiUrl(`/api/admin/resumes/${this.id}/file_open?token=${encodeURIComponent(window.icp.state.token)}`);
                    }
                }
            } catch (err) {
                console.error(err);
                if (err.response && err.response.status === 401) {
                    window.location.href = '/static/pages/admin.html';
                }
            }
        },
        logout() {
            window.icp.logout();
        }
    }
});

app.mount('#app');
