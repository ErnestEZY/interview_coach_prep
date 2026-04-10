const { createApp } = Vue;

const app = createApp({
    data() {
        return {
            email: '',
            otp: '',
            submitting: false
        };
    },
    mounted() {
        const urlParams = new URLSearchParams(window.location.search);
        this.email = (urlParams.get('email') || '').trim();
    },
    methods: {
        promptFields() {
            if (this.otp.length < 6) {
                Swal.fire({
                    icon: 'info',
                    title: 'Verification Code',
                    text: 'Please enter the full 6-digit verification code sent to your email.',
                    confirmButtonColor: '#8b5cf6'
                });
            }
        },
        async submit() {
            this.submitting = true;
            Swal.fire({
                title: 'Verifying...',
                allowOutsideClick: false,
                didOpen: () => Swal.showLoading()
            });

            try {
                await axios.post(window.icp.apiUrl('/api/auth/verify-email'), {
                    email: this.email,
                    otp: this.otp
                });
                
                Swal.fire({
                    icon: 'success',
                    title: 'Email Verified!',
                    text: 'You can now login to your account.',
                    confirmButtonText: 'Go to Login',
                    confirmButtonColor: '#8b5cf6'
                }).then(() => {
                    window.location = '/static/pages/login.html';
                });
            } catch (e) {
                let msg = 'Verification failed';
                if (e.response && e.response.data && e.response.data.detail) {
                    msg = e.response.data.detail;
                }
                Swal.fire({ 
                    icon: 'error', 
                    title: 'Error', 
                    html: msg.replace(/\n/g, '<br>'),
                    confirmButtonColor: '#8b5cf6'
                });
            } finally {
                this.submitting = false;
            }
        },
        validateOtp(event) {
             this.otp = event.target.value.replace(/[^0-9]/g, '');
        },
        focusOtp() {
            if (this.$refs && this.$refs.otpInput) {
                this.$refs.otpInput.focus();
            }
        }
    }
});

app.mount('#app');
