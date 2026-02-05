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
                    confirmButtonText: 'Go to Login'
                }).then(() => {
                    window.location = '/static/pages/login.html';
                });
            } catch (e) {
                let msg = 'Verification failed';
                if (e.response && e.response.data && e.response.data.detail) {
                    msg = e.response.data.detail;
                }
                Swal.fire({ icon: 'error', title: 'Error', text: msg });
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
