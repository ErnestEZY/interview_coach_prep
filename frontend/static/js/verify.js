const { createApp } = Vue;

const RESEND_COOLDOWN = 30; // seconds
const MAX_ATTEMPTS   = 3;

const app = createApp({
    data() {
        return {
            email: '',
            otp: '',
            submitting: false,

            // Resend cooldown
            resendCooldown: 0,      // seconds remaining
            _cooldownTimer: null,

            // Attempt tracking
            attemptsLeft: MAX_ATTEMPTS,
            MAX_ATTEMPTS,           // expose constant to template
            locked: false           // true after 3 wrong attempts
        };
    },
    computed: {
        resendDisabled() {
            return this.resendCooldown > 0 || this.locked;
        }
    },
    mounted() {
        const urlParams = new URLSearchParams(window.location.search);
        this.email = (urlParams.get('email') || '').trim();

        // Start the initial 30-second cooldown so users can't spam resend
        // immediately after landing on the page (OTP was just sent on register)
        this.startCooldown();
    },
    beforeUnmount() {
        clearInterval(this._cooldownTimer);
    },
    methods: {
        startCooldown() {
            clearInterval(this._cooldownTimer);
            this.resendCooldown = RESEND_COOLDOWN;
            this._cooldownTimer = setInterval(() => {
                if (this.resendCooldown > 0) {
                    this.resendCooldown--;
                } else {
                    clearInterval(this._cooldownTimer);
                }
            }, 1000);
        },

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

        async resendOtp() {
            if (this.resendDisabled) return;

            try {
                const res = await axios.post(window.icp.apiUrl('/api/auth/resend-otp'), {
                    email: this.email
                });

                const newOtp = res.data.otp;

                // Calculate expiry time (MYT) for the email template
                const now = new Date();
                const utc = now.getTime() + (now.getTimezoneOffset() * 60000);
                const mytTime = new Date(utc + (3600000 * 8));
                mytTime.setMinutes(mytTime.getMinutes() + 15);
                const expiryTime = mytTime.toLocaleTimeString('en-GB', {
                    hour: '2-digit', minute: '2-digit', hour12: false
                });

                // Send via the same EmailJS helper used by register.js
                const result = await sendVerificationEmail(this.email, newOtp, expiryTime);

                // Reset attempt counter on successful resend
                this.attemptsLeft = MAX_ATTEMPTS;
                this.startCooldown();

                if (result.success) {
                    Swal.fire({
                        icon: 'success',
                        title: 'Code Resent',
                        html: `A new verification code has been sent to:<br><strong class="text-primary">${this.email}</strong>`,
                        confirmButtonColor: '#8b5cf6',
                        timer: 3000,
                        showConfirmButton: false
                    });
                } else {
                    // OTP was regenerated in DB but email failed ΓÇö warn the user
                    Swal.fire({
                        icon: 'warning',
                        title: 'Email Not Delivered',
                        text: `A new code was generated but the email could not be sent: ${result.error}. Please try again.`,
                        confirmButtonColor: '#8b5cf6'
                    });
                }
            } catch (e) {
                let msg = 'Failed to resend code. Please try again.';
                if (e.response?.data?.detail) msg = e.response.data.detail;
                Swal.fire({
                    icon: 'error',
                    title: 'Resend Failed',
                    text: msg,
                    confirmButtonColor: '#8b5cf6'
                });
            }
        },

        async submit() {
            if (this.locked) return;

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
                if (e.response?.data?.detail) msg = e.response.data.detail;

                // Detect "too many attempts" from backend
                if (msg.toLowerCase().includes('too many') || msg.toLowerCase().includes('register again')) {
                    this.locked = true;
                    this.attemptsLeft = 0;
                    clearInterval(this._cooldownTimer);

                    Swal.fire({
                        icon: 'error',
                        title: 'Too Many Attempts',
                        html: 'You have exceeded the maximum number of OTP attempts.<br><br>Please register again.',
                        confirmButtonText: 'Register Again',
                        confirmButtonColor: '#8b5cf6',
                        allowOutsideClick: false
                    }).then(() => {
                        window.location = '/static/pages/register.html';
                    });
                } else {
                    // Parse remaining attempts from backend message if present
                    const match = msg.match(/(\d+) attempt/);
                    if (match) this.attemptsLeft = parseInt(match[1]);

                    this.otp = '';
                    Swal.fire({
                        icon: 'error',
                        title: 'Invalid Code',
                        html: msg.replace(/\n/g, '<br>'),
                        confirmButtonColor: '#8b5cf6'
                    });
                }
            } finally {
                this.submitting = false;
            }
        },

        validateOtp(event) {
            this.otp = event.target.value.replace(/[^0-9]/g, '');
        },
        focusOtp() {
            if (this.$refs?.otpInput) {
                this.$refs.otpInput.focus();
            }
        }
    }
});

app.mount('#app');
