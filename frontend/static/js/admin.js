const { createApp } = Vue;

const app = createApp({
    data() {
        return {
            email: '',
            password: '',
            showPassword: false,
            loading: false,
            logged: false
        };
    },
    mounted() {
        this.checkAuth();
        window.addEventListener('auth:changed', this.checkAuth);
    },
    methods: {
        checkAuth() {
            this.logged = !!(window.icp && window.icp.state && window.icp.state.token);
        },
        togglePassword() {
            this.showPassword = !this.showPassword;
        },
        async login() {
            if (this.loading) return;
            this.loading = true;

            Swal.fire({
                title: 'Authenticating...',
                allowOutsideClick: false,
                didOpen: () => Swal.showLoading()
            });

            try {
                const formData = new URLSearchParams();
                formData.append('username', this.email);
                formData.append('password', this.password);

                const response = await axios.post(window.icp.apiUrl('/api/auth/admin_login'), formData, {
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
                });

                const res = response.data;
                window.icp.state.setToken(res.access_token);

                // Trigger security alert if anomaly detected
                if (res.is_anomaly && res.admin_emails && res.admin_emails.length > 0) {
                    if (window.sendSecurityAlertEmail) {
                        window.sendSecurityAlertEmail(res.admin_emails, this.email, 'Detected IP', res.alert_reason)
                            .then(result => console.log('Admin Security Alert:', result))
                            .catch(err => console.error('Admin Security Alert Error:', err));
                    }
                }

                Swal.fire({
                    icon: 'success',
                    title: 'Access Granted',
                    text: 'Redirecting to portal...',
                    timer: 1500,
                    showConfirmButton: false
                }).then(() => {
                    window.location = '/static/pages/admin_panel.html';
                });

            } catch (error) {
                let msg = 'Invalid admin credentials';
                if (error.response && error.response.data) {
                    msg = error.response.data.detail || msg;
                }
                Swal.fire({
                    icon: 'error',
                    title: 'Login Failed',
                    text: msg
                });
            } finally {
                this.loading = false;
            }
        },
        logout() {
            window.icp.logout();
        }
    }
});

app.mount('#app');
