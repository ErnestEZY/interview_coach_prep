const { createApp } = Vue;

const app = createApp({
    data() {
        return {
            token: '',
            email: 'Loading...',
            password: '',
            confirmPassword: '',
            showPassword: false,
            showConfirmPassword: false,
            submitting: false,
            success: false,
            countdown: 5
        };
    },
    computed: {
        passwordCriteria() {
            return {
                length: this.password.length >= 8,
                upper: /[A-Z]/.test(this.password),
                lower: /[a-z]/.test(this.password),
                number: /[0-9]/.test(this.password),
                special: /[!@#$%^&*(),.?":{}|<>]/.test(this.password)
            };
        },
        passwordStrength() {
            if (!this.password) return { label: 'None', color: 'text-secondary', width: '0%', class: 'bg-secondary' };
            const criteria = this.passwordCriteria;
            const metCount = Object.values(criteria).filter(Boolean).length;
            if (metCount <= 2) return { label: 'Weak', color: 'text-danger', width: '33%', class: 'bg-danger' };
            if (metCount <= 4) return { label: 'Medium', color: 'text-warning', width: '66%', class: 'bg-warning' };
            return { label: 'Strong', color: 'text-success', width: '100%', class: 'bg-success' };
        },
        passwordsMatch() {
            return this.password && this.confirmPassword && this.password === this.confirmPassword;
        }
    },
    mounted() {
        const urlParams = new URLSearchParams(window.location.search);
        this.token = urlParams.get('token');
        
        if (!this.token) {
            Swal.fire({
                icon: 'error',
                title: 'Invalid Link',
                text: 'This reset link is missing or invalid.',
                confirmButtonText: 'Back to Login'
            }).then(() => window.location = '/static/pages/login.html');
        } else {
            this.fetchEmail();
        }
    },
    methods: {
        async fetchEmail() {
            try {
                const response = await axios.get(window.icp.apiUrl(`/api/auth/verify-token/${this.token}`));
                this.email = response.data.email;
            } catch (e) {
                Swal.fire({
                    icon: 'error',
                    title: 'Invalid Link',
                    text: 'This reset link is expired or invalid.',
                    confirmButtonText: 'Back to Login'
                }).then(() => window.location = '/static/pages/login.html');
            }
        },
        startCountdown() {
            const timer = setInterval(() => {
                this.countdown--;
                if (this.countdown <= 0) {
                    clearInterval(timer);
                    // Close the window if possible, otherwise redirect
                    if (window.opener || window.history.length === 1) {
                        window.close();
                    } else {
                        window.location = '/static/pages/login.html';
                    }
                }
            }, 1000);
        },
        async submit() {
            if (this.password !== this.confirmPassword) {
                Swal.fire({ icon: 'error', title: 'Error', text: 'Passwords do not match' });
                return;
            }
            if (!Object.values(this.passwordCriteria).every(Boolean)) {
                Swal.fire({ icon: 'error', title: 'Weak Password', text: 'Please meet all password criteria.' });
                return;
            }
            
            this.submitting = true;
            try {
                await axios.post(window.icp.apiUrl('/api/auth/reset-password'), {
                    token: this.token,
                    password: this.password
                });
                
                this.success = true;
                this.startCountdown();
            } catch (e) {
                let msg = 'Failed to update password';
                if (e.response && e.response.data && e.response.data.detail) {
                    msg = e.response.data.detail;
                }
                Swal.fire({ icon: 'error', title: 'Update Failed', text: msg });
            } finally {
                this.submitting = false;
            }
        }
    }
});

app.mount('#app');
