const { createApp } = Vue;

const app = createApp({
    data() {
        return {
            form: {
                name: localStorage.getItem('reg_name') || '',
                email: localStorage.getItem('reg_email') || '',
                password: '',
                confirmPassword: '',
                agreed: false
            },
            showPassword: false,
            showConfirmPassword: false,
            loading: false
        };
    },
    computed: {
        passwordCriteria() {
            const pwd = this.form.password;
            return {
                length: pwd.length >= 8,
                upper: /[A-Z]/.test(pwd),
                lower: /[a-z]/.test(pwd),
                number: /[0-9]/.test(pwd),
                special: /[!@#$%^&*(),.?":{}|<>]/.test(pwd)
            };
        },
        passwordStrength() {
            if (!this.form.password) return { label: 'None', color: 'text-secondary', width: '0%', class: 'bg-secondary' };
            const criteria = this.passwordCriteria;
            const metCount = Object.values(criteria).filter(Boolean).length;
            if (metCount <= 2) return { label: 'Weak', color: 'text-danger', width: '33%', class: 'bg-danger' };
            if (metCount <= 4) return { label: 'Medium', color: 'text-warning', width: '66%', class: 'bg-warning' };
            return { label: 'Strong', color: 'text-success', width: '100%', class: 'bg-success' };
        },
        passwordsMatch() {
            return this.form.password === this.form.confirmPassword;
        }
    },
    methods: {
        showTerms() { window.icp.showTerms(); },
        showPrivacy() { window.icp.showPrivacy(); },
        saveForm() {
            localStorage.setItem('reg_name', this.form.name);
            localStorage.setItem('reg_email', this.form.email);
        },
        validateName() {
            this.form.name = this.form.name.replace(/[^A-Za-z\s]/g, '');
            this.saveForm();
        },
        async register() {
            if (this.loading) return;

            if (!this.form.agreed) {
                Swal.fire({ icon: 'warning', title: 'Agreement Required', text: 'Please agree to the Terms & Conditions and Privacy Policy to continue.' });
                return;
            }
            
            // Validation
            if (this.form.name && !/^[A-Za-z\s]*$/.test(this.form.name)) {
                Swal.fire({ icon: 'error', title: 'Invalid Name', text: 'Name can only contain alphabets and spaces.' });
                return;
            }
            
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(this.form.email)) {
                Swal.fire({ icon: 'error', title: 'Invalid Email', text: 'Please enter a valid email address.' });
                return;
            }
            
            const domain = this.form.email.split('@')[1];
            if (!domain || !domain.includes('.')) {
                Swal.fire({ icon: 'error', title: 'Invalid Domain', text: 'The email domain seems invalid.' });
                return;
            }
            
            if (this.form.password !== this.form.confirmPassword) {
                Swal.fire({ icon: 'error', title: 'Passwords do not match', text: 'Please ensure both passwords are the same.' });
                return;
            }
            
            const criteria = this.passwordCriteria;
            const validLength = this.form.password.length >= 8 && this.form.password.length <= 12;
            
            if (!criteria.upper || !criteria.lower || !criteria.number || !criteria.special || !validLength) {
                Swal.fire({
                    icon: 'error',
                    title: 'Invalid Password Format',
                    html: `
                        <div class='text-start small'>
                          <p class='mb-2 fw-bold text-danger'>Password must include:</p>
                          <ul class='list-unstyled'>
                            <li class='${validLength ? 'text-success' : 'text-danger'}'>
                              <i class='bi ${validLength ? 'bi-check-circle-fill' : 'bi-x-circle-fill'} me-2'></i>At least 8 characters
                            </li>
                            <li class='${criteria.upper ? 'text-success' : 'text-danger'}'>
                              <i class='bi ${criteria.upper ? 'bi-check-circle-fill' : 'bi-x-circle-fill'} me-2'></i>Contains uppercase letter
                            </li>
                            <li class='${criteria.lower ? 'text-success' : 'text-danger'}'>
                              <i class='bi ${criteria.lower ? 'bi-check-circle-fill' : 'bi-x-circle-fill'} me-2'></i>Contains lowercase letter
                            </li>
                            <li class='${criteria.number ? 'text-success' : 'text-danger'}'>
                              <i class='bi ${criteria.number ? 'bi-check-circle-fill' : 'bi-x-circle-fill'} me-2'></i>Contains number
                            </li>
                            <li class='${criteria.special ? 'text-success' : 'text-danger'}'>
                              <i class='bi ${criteria.special ? 'bi-check-circle-fill' : 'bi-x-circle-fill'} me-2'></i>Contains special character
                            </li>
                          </ul>
                        </div>
                    `
                });
                return;
            }
            
            this.loading = true;
            Swal.fire({
                title: 'Creating Account...',
                text: 'Please wait',
                allowOutsideClick: false,
                didOpen: () => Swal.showLoading()
            });
            
            try {
                const response = await axios.post(window.icp.apiUrl('/api/auth/register'), {
                    email: this.form.email,
                    password: this.form.password,
                    name: this.form.name
                });
                
                const res = response.data;
                const email = res.email;
                const otp = res.otp;
                
                // Calculate expiry time (MYT)
                const now = new Date();
                const utc = now.getTime() + (now.getTimezoneOffset() * 60000);
                const mytTime = new Date(utc + (3600000 * 8));
                mytTime.setMinutes(mytTime.getMinutes() + 15);
                const expiryTime = mytTime.toLocaleTimeString('en-GB', { 
                  hour: '2-digit', 
                  minute: '2-digit',
                  hour12: false 
                });
                
                const result = await sendVerificationEmail(email, otp, expiryTime);
                
                localStorage.removeItem('reg_name');
                localStorage.removeItem('reg_email');
                
                if (result.success) {
                    Swal.fire({
                        icon: 'success',
                        title: 'OTP Sent Successfully',
                        html: `
                            <div class='text-center'>
                              <p>A verification code has been sent to:</p>
                              <p class='fw-bold text-primary'>${email}</p>
                              <p class='small text-secondary'>Please check your inbox (and spam folder) to complete your registration.</p>
                            </div>
                        `,
                        confirmButtonText: 'Enter OTP'
                    }).then(() => {
                        window.location = '/static/pages/verify.html?email=' + encodeURIComponent(email);
                    });
                } else {
                    Swal.fire({
                        icon: 'warning',
                        title: 'Email Sending Failed',
                        text: 'Account created, but we couldn\'t send the email: ' + result.error + '. Please contact support.',
                        confirmButtonText: 'I understand'
                    }).then(() => {
                        window.location = '/static/pages/verify.html?email=' + encodeURIComponent(email);
                    });
                }
                
            } catch (error) {
                let msg = 'Registration failed';
                if (error.response && error.response.data) {
                    msg = error.response.data.detail || msg;
                }
                Swal.fire({ icon: 'error', title: 'Registration Failed', text: msg });
            } finally {
                this.loading = false;
            }
        }
    }
});

app.mount('#app');
