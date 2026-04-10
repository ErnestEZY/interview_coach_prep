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
        showTerms() { window.icp.showTerms(); },
        showPrivacy() { window.icp.showPrivacy(); },
        promptFields() {
            if (!this.username || !this.password) {
                Swal.fire({
                    icon: 'info',
                    title: 'Incomplete Fields',
                    text: 'Please enter both your email address and password to sign in.',
                    confirmButtonColor: '#8b5cf6'
                });
            }
        },
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
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    validateStatus: (status) => status < 500
                });

                const res = response.data;

                if (response.status !== 200) {
                    let msg = res.detail || 'Invalid credentials';
                    let showVerifyLink = typeof msg === 'string' && msg.toLowerCase().includes('verify your email');

                    if (showVerifyLink) {
                        Swal.fire({
                            icon: 'warning',
                            title: 'Email Not Verified',
                            html: msg.replace(/\n/g, '<br>'),
                            showCancelButton: true,
                            confirmButtonText: 'Verify Now',
                            cancelButtonText: 'Close',
                            confirmButtonColor: '#8b5cf6'
                        }).then((result) => {
                            if (result.isConfirmed) {
                                window.location = '/static/pages/verify.html?email=' + encodeURIComponent(this.username);
                            }
                        });
                    } else {
                        Swal.fire({
                            icon: 'error',
                            title: 'Login Failed',
                            html: typeof msg === 'string' ? msg.replace(/\n/g, '<br>') : JSON.stringify(msg),
                            confirmButtonColor: '#8b5cf6'
                        });
                    }
                    return;
                }

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
                } else if (me.role === 'admin' || me.role === 'super_admin') {
                    window.icp.state.clearToken();
                    Swal.fire({
                        icon: 'error',
                        title: 'Restricted Access',
                        text: 'This account is registered as an Administrator. Please use the secure admin portal to sign in.',
                        confirmButtonColor: '#8b5cf6'
                    });
                } else {
                    window.icp.state.clearToken();
                    Swal.fire({
                        icon: 'error',
                        title: 'Unknown Role',
                        text: 'Your account role is not recognized. Please contact support.',
                        confirmButtonColor: '#8b5cf6'
                    });
                }

            } catch (error) {
                console.error('Login Error details:', error);
                let msg = 'Invalid credentials';
                
                if (error.response) {
                    msg = (error.response.data && error.response.data.detail) || msg;
                } else if (error.request) {
                    msg = 'Network error: Cannot reach the server. Please check your internet connection or if the backend is down.';
                    if (window.icp.state.isTauri) {
                      msg += ' (Tauri CORS check failed?)';
                    }
                } else {
                    msg = error.message;
                }

                Swal.fire({
                    icon: 'error',
                    title: 'Login Failed',
                    html: typeof msg === 'string' ? msg.replace(/\n/g, '<br>') : JSON.stringify(msg),
                    confirmButtonColor: '#8b5cf6'
                });
            } finally {
                this.loading = false;
            }
        }
    }
});

app.mount('#app');
