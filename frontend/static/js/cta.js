const { createApp } = Vue;

const app = createApp({
    data() {
        return {
            logged: false
        };
    },
    mounted() {
        // Small delay to ensure app.js has initialized window.icp
        setTimeout(() => {
            this.checkAuth();
        }, 50);
        
        window.addEventListener('auth:changed', () => {
            this.checkAuth();
        });
    },
    methods: {
        showTerms() { if (window.icp && window.icp.showTerms) window.icp.showTerms(); },
        showPrivacy() { if (window.icp && window.icp.showPrivacy) window.icp.showPrivacy(); },
        checkAuth() {
            this.logged = !!(window.icp && window.icp.state && window.icp.state.token);
        },
        logout() {
            if (window.icp && window.icp.logout) {
                window.icp.logout();
            }
        }
    }
});

app.mount('#app');