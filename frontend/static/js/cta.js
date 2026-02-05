const { createApp } = Vue;

const app = createApp({
    data() {
        return {
            logged: false
        };
    },
    mounted() {
        this.checkAuth();
        window.addEventListener('auth:changed', () => {
            this.checkAuth();
        });
    },
    methods: {
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