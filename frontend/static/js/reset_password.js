const { createApp } = Vue;

console.log('reset_password.js loaded');
console.log('Vue available:', !!Vue);
console.log('window.icp available:', !!window.icp);

try {
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
                success: false
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
            console.log('Vue app mounted');
            const urlParams = new URLSearchParams(window.location.search);
            this.token = urlParams.get('token');
            console.log('Token:', this.token);
            
            if (!this.token) {
                console.warn('No token found');
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
                    console.log('Fetching email...');
                    if (!window.icp || !window.icp.apiUrl) {
                        throw new Error('window.icp.apiUrl is missing');
                    }
                    const url = window.icp.apiUrl(`/api/auth/verify-token/${this.token}`);
                    console.log('Verify URL:', url);
                    const response = await axios.get(url);
                    console.log('Email fetched:', response.data.email);
                    this.email = response.data.email;
                } catch (e) {
                    console.error('Fetch email error:', e);
                    Swal.fire({
                        icon: 'error',
                        title: 'Invalid Link',
                        text: 'This reset link is expired or invalid.',
                        confirmButtonText: 'Back to Login'
                    }).then(() => window.location = '/static/pages/login.html');
                }
            },
            handleSuccess() {
                this.success = true;
                Swal.fire({
                    icon: 'success',
                    title: 'Success!',
                    text: 'Your password has been reset successfully. This page will now close.',
                    confirmButtonText: 'OK',
                    allowOutsideClick: false
                }).then(() => {
                    if (window.opener || window.history.length === 1) {
                        window.close();
                    } else {
                        window.location = '/static/pages/login.html';
                    }
                });
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
                    
                    this.handleSuccess();
                } catch (e) {
                    this.submitting = false;
                    Swal.fire({
                        icon: 'error',
                        title: 'Error',
                        text: e.response?.data?.detail || 'Failed to reset password'
                    });
                }
            }
        }
    });

    app.mount('#app');
    console.log('App mounted to #app');
} catch (e) {
    console.error('Critical error in reset_password.js:', e);
}
