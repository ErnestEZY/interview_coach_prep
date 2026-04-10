const { createApp } = Vue;

const app = createApp({
    data() {
        return {
            logged: false,
            role: '',
            userName: '',
            userEmail: '',
            hasAnalyzed: false
        };
    },
    computed: {
        dashboardUrl() {
            if (this.role === 'admin' || this.role === 'super_admin') {
                // Encoded portal path: /static/pages/icp-admin-portal-5e6a1c3d.html
                return atob('L3N0YXRpYy9wYWdlcy9pY3AtYWRtaW4tcG9ydGFsLTVlNmExYzNkLmh0bWw=');
            }
            return '/static/pages/dashboard.html';
        },
        dashboardText() {
            return (this.role === 'admin' || this.role === 'super_admin') 
                ? 'Go to Admin Dashboard' 
                : 'Go to Dashboard';
        },
        isAdmin() {
            return this.role === 'admin' || this.role === 'super_admin';
        }
    },
    mounted() {
        this.checkAuth();
        window.addEventListener('auth:changed', () => {
            this.checkAuth();
        });
    },
    methods: {
        async checkAuth() {
            this.logged = !!(window.icp && window.icp.state && window.icp.state.token);
            if (!this.logged) {
                this.role = '';
                this.userName = '';
                this.userEmail = '';
                this.hasAnalyzed = false;
                return;
            }
            await this.checkRole();
        },
        async checkRole() {
            if (!this.logged) return;
            try {
                const response = await axios.get(window.icp.apiUrl('/api/auth/me'));
                const me = response.data;
                this.role = me.role || '';
                this.userName = me.name || 'Guest';
                this.userEmail = me.email || '';
                this.hasAnalyzed = me.has_analyzed || !!localStorage.getItem('resume_feedback');
            } catch (e) {
                console.error('Error fetching user info:', e);
                const payload = window.icp.decodeToken(window.icp.state.token);
                this.role = payload?.role || '';
            }
        },
        logout() {
            if (window.icp && window.icp.logout) {
                window.icp.logout();
            }
        }
    }
});

app.mount('#app');