const { createApp } = Vue;

const app = createApp({
    data() {
        return {
            email: localStorage.getItem('forgot_email') || '',
            submitting: false
        };
    },
    watch: {
        email(newVal) {
            localStorage.setItem('forgot_email', newVal);
        }
    },
    methods: {
        promptFields() {
            if (!this.email) {
                Swal.fire({
                    icon: 'info',
                    title: 'Incomplete Field',
                    text: 'Please enter your email address to receive a reset link.',
                    confirmButtonColor: '#8b5cf6'
                });
            }
        },
        async submit() {
            if (!this.email) return;
            this.submitting = true;
            
            Swal.fire({
                title: 'Sending Link...',
                text: 'Please wait while we process your request',
                allowOutsideClick: false,
                didOpen: () => Swal.showLoading()
            });

            try {
                await axios.post(window.icp.apiUrl('/api/auth/forgot-password'), { email: this.email });
                
                Swal.fire({
                    icon: 'success',
                    title: 'Check your email',
                    text: 'We have sent a password reset link to your email address.',
                    confirmButtonText: 'OK',
                    confirmButtonColor: '#8b5cf6'
                });
            } catch (e) {
                console.error('Forgot password error', e);
                const msg = e.response?.data?.detail || 'Failed to send reset link. Please try again.';
                Swal.fire({
                    icon: 'error',
                    title: 'Error',
                    text: msg,
                    confirmButtonColor: '#8b5cf6'
                });
            } finally {
                this.submitting = false;
            }
        }
    }
});

app.mount('#app');
