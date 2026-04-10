const { createApp } = Vue;

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
            },
            allCriteriaMet() {
                return Object.values(this.passwordCriteria).every(Boolean);
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
            promptFields() {
                if (!this.password || !this.confirmPassword) {
                    Swal.fire({
                        icon: 'info',
                        title: 'Incomplete Fields',
                        text: 'Please enter and confirm your new password to proceed.',
                        confirmButtonColor: '#8b5cf6'
                    });
                } else if (!this.passwordsMatch) {
                    Swal.fire({
                        icon: 'error',
                        title: 'Passwords do not match',
                        text: 'The confirmation password does not match the new password. Please try again.',
                        confirmButtonColor: '#8b5cf6'
                    });
                } else if (!this.allCriteriaMet) {
                    const criteria = this.passwordCriteria;
                    Swal.fire({
                        icon: 'warning',
                        iconHtml: 'i',
                        title: 'Invalid Password Format',
                        html: `
                            <div class="text-start small">
                                <p class="mb-2">Your password must meet all the following security criteria:</p>
                                <ul class="list-unstyled mb-0">
                                    <li class="mb-1" style="color: ${criteria.length ? '#22c55e' : '#ef4444'} !important;">
                                        <i class="bi ${criteria.length ? 'bi-check-circle-fill' : 'bi-x-circle-fill'} me-2"></i>
                                        At least 8 characters
                                    </li>
                                    <li class="mb-1" style="color: ${criteria.upper ? '#22c55e' : '#ef4444'} !important;">
                                        <i class="bi ${criteria.upper ? 'bi-check-circle-fill' : 'bi-x-circle-fill'} me-2"></i>
                                        At least 1 uppercase letter
                                    </li>
                                    <li class="mb-1" style="color: ${criteria.lower ? '#22c55e' : '#ef4444'} !important;">
                                        <i class="bi ${criteria.lower ? 'bi-check-circle-fill' : 'bi-x-circle-fill'} me-2"></i>
                                        At least 1 lowercase letter
                                    </li>
                                    <li class="mb-1" style="color: ${criteria.number ? '#22c55e' : '#ef4444'} !important;">
                                        <i class="bi ${criteria.number ? 'bi-check-circle-fill' : 'bi-x-circle-fill'} me-2"></i>
                                        At least 1 number
                                    </li>
                                    <li class="mb-1" style="color: ${criteria.special ? '#22c55e' : '#ef4444'} !important;">
                                        <i class="bi ${criteria.special ? 'bi-check-circle-fill' : 'bi-x-circle-fill'} me-2"></i>
                                        At least 1 special character
                                    </li>
                                </ul>
                            </div>
                        `,
                        confirmButtonColor: '#8b5cf6'
                    });
                }
            },
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
                        confirmButtonText: 'Back to Login',
                        confirmButtonColor: '#8b5cf6'
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
                    confirmButtonColor: '#8b5cf6',
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
                    this.promptFields();
                    return;
                }
                if (!this.allCriteriaMet) {
                    this.promptFields();
                    return;
                }
                
                this.submitting = true;
                Swal.fire({
                    title: 'Resetting Password...',
                    text: 'Please wait while we secure your account',
                    allowOutsideClick: false,
                    didOpen: () => Swal.showLoading()
                });

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
                        title: 'Reset Failed',
                        text: e.response?.data?.detail || 'Failed to reset password. Please try again.'
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
