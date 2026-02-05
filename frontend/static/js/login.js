const { createApp } = Vue;

const app = createApp({
    data() {
        return {
            username: '',
            password: '',
            showPassword: false,
            loading: false
        };
    },
    mounted() {
        // Clear old session data
        try {
            localStorage.removeItem('resume_feedback');
            localStorage.removeItem('resume_filename');
            localStorage.removeItem('resume_score');
            localStorage.removeItem('target_job_title');
            localStorage.removeItem('target_location');
            localStorage.removeItem('interview_voice_gender');
            localStorage.removeItem('interview_session_id');
        } catch(e) {}
    },
    watch: {},
    methods: {
        async login() {
            if (this.loading) return;
            this.loading = true;

            Swal.fire({
                title: 'Logging in...',
                text: 'Verifying credentials',
                allowOutsideClick: false,
                didOpen: () => Swal.showLoading()
            });

            try {
                const formData = new URLSearchParams();
                formData.append('username', this.username);
                formData.append('password', this.password);

                const response = await axios.post(window.icp.apiUrl('/api/auth/login'), formData, {
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
                });

                const res = response.data;
                window.icp.state.setToken(res.access_token);

                // Check role
                const me = await axios.get(window.icp.apiUrl('/api/auth/me')).then(r => r.data);
                
                if (me.role === 'user') {
                    Swal.fire({
                        icon: 'success',
                        title: 'Login Successful!',
                        text: 'Redirecting to dashboard...',
                        timer: 1500,
                        showConfirmButton: false
                    }).then(() => {
                        window.location = '/static/pages/dashboard.html';
                    });
                } else {
                    window.icp.state.clearToken();
                    Swal.fire({
                        icon: 'error',
                        title: 'Access Denied',
                        text: 'Admin or super_admin cannot use the normal login. Please use the Admin page.',
                    }).then(() => { window.location = '/static/pages/admin.html'; });
                }

            } catch (error) {
                let msg = 'Invalid credentials';
                let showVerifyLink = false;
                
                if (error.response && error.response.data) {
                    msg = error.response.data.detail || msg;
                    if (msg.toLowerCase().includes('verify your email')) {
                        showVerifyLink = true;
                    }
                }

                if (showVerifyLink) {
                    Swal.fire({
                        icon: 'warning',
                        title: 'Email Not Verified',
                        text: msg,
                        showCancelButton: true,
                        confirmButtonText: 'Verify Now',
                        cancelButtonText: 'Close',
                        confirmButtonColor: '#0d6efd'
                    }).then((result) => {
                        if (result.isConfirmed) {
                            window.location = '/static/pages/verify.html?email=' + encodeURIComponent(this.username);
                        }
                    });
                } else {
                    Swal.fire({
                        icon: 'error',
                        title: 'Login Failed',
                        text: msg
                    });
                }
            } finally {
                this.loading = false;
            }
        }
    }
});

app.mount('#app');
