const { createApp } = Vue;

/** Reads the token and its role synchronously; app.min.js has already run. */
function readSession() {
    const token = (window.icp && window.icp.state && window.icp.state.token)
        || localStorage.getItem('token');
    const payload = token && window.icp && window.icp.decodeToken
        ? window.icp.decodeToken(token)
        : null;
    return { logged: !!token, role: (payload && payload.role) || '' };
}

const app = createApp({
    data() {
        // Same reasoning as the home page: the session is resolved before the
        // first paint so an admin never sees the candidate controls.
        const session = readSession();
        return {
            logged: session.logged,
            role: session.role,
            userName: '',
            userEmail: ''
        };
    },
    computed: {
        isAdmin() {
            return this.role === 'admin' || this.role === 'super_admin';
        },
        dashboardUrl() {
            if (this.role === 'admin' || this.role === 'super_admin') {
                // Encoded portal path: /static/pages/icp-admin-portal-5e6a1c3d.html
                return atob('L3N0YXRpYy9wYWdlcy9pY3AtYWRtaW4tcG9ydGFsLTVlNmExYzNkLmh0bWw=');
            }
            return '/static/pages/dashboard.html';
        },
        dashboardText() {
            // Same rule as the home page: an admin gets a route back to the
            // portal, never one into the candidate dashboard.
            return this.isAdmin ? 'Back to Admin Portal' : 'Go to Dashboard';
        }
    },
    mounted() {
        // Prevent back button to unauthenticated pages when logged out
        this._popstateHandler = () => {
            history.pushState(null, '', window.location.href);
        };
        window.addEventListener('popstate', this._popstateHandler);
        history.pushState(null, '', window.location.href);

        // Small delay to ensure app.js has initialized window.icp
        setTimeout(() => {
            this.checkAuth();
        }, 50);
        
        this._authListener = () => {
            this.checkAuth();
        };
        window.addEventListener('auth:changed', this._authListener);
    },
    beforeUnmount() {
        if (this._authListener) window.removeEventListener('auth:changed', this._authListener);
        if (this._popstateHandler) window.removeEventListener('popstate', this._popstateHandler);
    },
    methods: {
        showTerms() { if (window.icp && window.icp.showTerms) window.icp.showTerms(); },
        showPrivacy() { if (window.icp && window.icp.showPrivacy) window.icp.showPrivacy(); },
        async checkAuth() {
            this.logged = !!(window.icp && window.icp.state && window.icp.state.token);
            if (!this.logged) {
                this.role = '';
                this.userName = '';
                this.userEmail = '';
                return;
            }
            // Same reasoning as the home page: the JWT already carries the
            // role, so the admin link is correct on the first paint instead of
            // after /api/auth/me answers.
            this.roleFromToken();
            await this.checkRole();
        },
        roleFromToken() {
            const session = readSession();
            if (session.role) this.role = session.role;
        },
        async checkRole() {
            if (!this.logged) return;
            try {
                const response = await axios.get(window.icp.apiUrl('/api/auth/me'));
                const me = response.data;
                this.role = me.role || '';
                this.userName = me.name || 'Guest';
                this.userEmail = me.email || '';
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
