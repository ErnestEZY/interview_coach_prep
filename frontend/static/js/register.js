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
            loading: false,
            termsAccepted: false,
            privacyAccepted: false,
            showTermsButtons: false,
            showPrivacyButtons: false,
            legalHighlighted: false
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
        scrollToLegal() {
            const el = document.getElementById('legal-section');
            if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            this.legalHighlighted = true;
            setTimeout(() => { this.legalHighlighted = false; }, 3500);
        },
        expandTerms() {
            Swal.fire({
                title: 'Terms & Conditions',
                html: `
                  <div id="terms-scroll" class="text-start small overflow-auto px-2" style="max-height: 400px; line-height: 1.6;">
                    <h6 class="fw-bold">1. Acceptance of Terms</h6>
                    <p>By accessing or using ICP (Interview Coach Prep), you agree to be bound by these Terms and Conditions. These terms apply to all visitors, users, and others who access the service.</p>
                    <h6 class="fw-bold">2. Service Description</h6>
                    <p>ICP provides an AI-powered platform for interview preparation, including mock interviews, resume analysis, and career guidance. The service is provided "as is" and "as available".</p>
                    <h6 class="fw-bold">3. User Accounts</h6>
                    <p>You must provide accurate and complete information when creating an account. You are solely responsible for the activity that occurs on your account and must keep your password secure.</p>
                    <h6 class="fw-bold">4. User Conduct</h6>
                    <p>You agree not to use the service for any unlawful purpose or to conduct any activity that would violate the rights of others.</p>
                    <h6 class="fw-bold">5. Intellectual Property</h6>
                    <p>The Service and its original content, features, and functionality are and will remain the exclusive property of ICP and its licensors.</p>
                    <h6 class="fw-bold">6. Limitation of Liability</h6>
                    <p>In no event shall ICP be liable for any indirect, incidental, special, or consequential damages. AI feedback is for educational purposes only.</p>
                    <h6 class="fw-bold">7. Termination</h6>
                    <p>We may terminate or suspend access to our Service immediately, without prior notice, for any reason whatsoever.</p>
                    <h6 class="fw-bold">8. Changes</h6>
                    <p>We reserve the right to modify or replace these Terms at any time with at least 30 days' notice.</p>
                  </div>
                `,
                showCloseButton: true,
                showCancelButton: true,
                confirmButtonText: '<i class="bi bi-check-lg me-1"></i> Accept',
                cancelButtonText: '<i class="bi bi-x-lg me-1"></i> Decline',
                confirmButtonColor: '#22c55e',
                cancelButtonColor: '#ef4444',
                reverseButtons: false,
                didOpen: () => {
                    const confirmBtn = Swal.getConfirmButton();
                    confirmBtn.disabled = true;
                    confirmBtn.style.opacity = '0.5';
                    const scrollEl = document.getElementById('terms-scroll');
                    if (scrollEl) {
                        scrollEl.addEventListener('scroll', function onScroll() {
                            if (scrollEl.scrollTop + scrollEl.clientHeight >= scrollEl.scrollHeight - 5) {
                                confirmBtn.disabled = false;
                                confirmBtn.style.opacity = '1';
                                scrollEl.removeEventListener('scroll', onScroll);
                            }
                        });
                    }
                }
            }).then((res) => {
                if (res.isConfirmed) {
                    this.termsAccepted = true;
                    if (!this.privacyAccepted) {
                        setTimeout(() => { this.expandPrivacy(); }, 300);
                    } else {
                        this.form.agreed = true;
                    }
                } else if (res.isDismissed && res.dismiss === Swal.DismissReason.cancel) {
                    this.termsAccepted = false;
                    this.form.agreed = false;
                }
            });
        },
        expandPrivacy() {
            Swal.fire({
                title: 'Privacy Policy',
                html: `
                  <div id="privacy-scroll" class="text-start small overflow-auto px-2" style="max-height: 400px; line-height: 1.6;">
                    <h6 class="fw-bold">1. Information We Collect</h6>
                    <p><strong>Personal Data:</strong> We collect your name and email address for account management and security.</p>
                    <p><strong>Professional Data:</strong> We collect resume files and interview responses that you voluntarily upload or provide to our AI engine.</p>
                    <h6 class="fw-bold">2. How We Use Your Data</h6>
                    <p>We use the collected data to provide AI-driven feedback, personalize your experience, maintain account security, and improve our services.</p>
                    <h6 class="fw-bold">3. Data Sharing & Third Parties</h6>
                    <p>We do not sell your personal data. We share necessary information with AI Services, Email Services, and Database Services only to provide the service.</p>
                    <h6 class="fw-bold">4. Data Security</h6>
                    <p>We implement technical and organizational security measures including encryption for passwords and secure API communication.</p>
                    <h6 class="fw-bold">5. Your Rights</h6>
                    <p>You have the right to access, correct, or delete your personal data at any time through your profile settings.</p>
                    <h6 class="fw-bold">6. Cookies</h6>
                    <p>We use local storage and essential cookies to maintain your session. We do not use tracking cookies for third-party advertising.</p>
                    <h6 class="fw-bold">7. Children's Privacy</h6>
                    <p>Our Service does not address anyone under the age of 15.</p>
                  </div>
                `,
                showCloseButton: true,
                showCancelButton: true,
                confirmButtonText: '<i class="bi bi-check-lg me-1"></i> Accept',
                cancelButtonText: '<i class="bi bi-x-lg me-1"></i> Decline',
                confirmButtonColor: '#22c55e',
                cancelButtonColor: '#ef4444',
                reverseButtons: false,
                didOpen: () => {
                    const confirmBtn = Swal.getConfirmButton();
                    confirmBtn.disabled = true;
                    confirmBtn.style.opacity = '0.5';
                    const scrollEl = document.getElementById('privacy-scroll');
                    if (scrollEl) {
                        scrollEl.addEventListener('scroll', function onScroll() {
                            if (scrollEl.scrollTop + scrollEl.clientHeight >= scrollEl.scrollHeight - 5) {
                                confirmBtn.disabled = false;
                                confirmBtn.style.opacity = '1';
                                scrollEl.removeEventListener('scroll', onScroll);
                            }
                        });
                    }
                }
            }).then((res) => {
                if (res.isConfirmed) {
                    this.privacyAccepted = true;
                    if (this.termsAccepted) {
                        this.form.agreed = true;
                    }
                } else if (res.isDismissed && res.dismiss === Swal.DismissReason.cancel) {
                    this.privacyAccepted = false;
                    this.form.agreed = false;
                }
            });
        },
        async showTermsPrompt() { this.expandTerms(); },
        async showPrivacyPrompt() { this.expandPrivacy(); },
        promptFields() {
            if (!this.form.email || !this.form.password || !this.form.confirmPassword || !this.form.agreed) {
                Swal.fire({
                    icon: 'info',
                    title: 'Incomplete Registration',
                    text: 'Please fill in all required fields (Email, Password, Confirm Password) and agree to the terms to create your account.',
                    confirmButtonColor: '#8b5cf6'
                });
            } else if (!this.passwordsMatch) {
                Swal.fire({
                    icon: 'error',
                    title: 'Passwords do not match',
                    text: 'Please ensure both passwords are the same.',
                    confirmButtonColor: '#8b5cf6'
                });
            } else if (!Object.values(this.passwordCriteria).every(Boolean)) {
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
                Swal.fire({ 
                    icon: 'warning', 
                    iconHtml: 'i',
                    title: 'Agreement Required', 
                    text: 'Please agree to the Terms & Conditions and Privacy Policy to continue.', 
                    confirmButtonColor: '#8b5cf6' 
                });
                return;
            }
            
            // Validation
            if (this.form.name && !/^[A-Za-z\s]*$/.test(this.form.name)) {
                Swal.fire({ icon: 'error', title: 'Invalid Name', text: 'Name can only contain alphabets and spaces.', confirmButtonColor: '#8b5cf6' });
                return;
            }
            
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(this.form.email)) {
                Swal.fire({ icon: 'error', title: 'Invalid Email', text: 'Please enter a valid email address.', confirmButtonColor: '#8b5cf6' });
                return;
            }
            
            const domain = this.form.email.split('@')[1];
            if (!domain || !domain.includes('.')) {
                Swal.fire({ icon: 'error', title: 'Invalid Domain', text: 'The email domain seems invalid.', confirmButtonColor: '#8b5cf6' });
                return;
            }
            
            if (this.form.password !== this.form.confirmPassword) {
                Swal.fire({ icon: 'error', title: 'Passwords do not match', text: 'Please ensure both passwords are the same.', confirmButtonColor: '#8b5cf6' });
                return;
            }
            
            const criteria = this.passwordCriteria;
            
            if (!Object.values(criteria).every(Boolean)) {
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
                    confirmButtonText: 'Try Again',
                    confirmButtonColor: '#8b5cf6'
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
                              <p class='small' style="color: #475569; font-weight: 500;">Please check your inbox (and spam folder) to complete your registration.</p>
                            </div>
                        `,
                        confirmButtonText: 'Enter OTP',
                        confirmButtonColor: '#8b5cf6'
                    }).then(() => {
                        window.location = '/static/pages/verify.html?email=' + encodeURIComponent(email);
                    });
                } else {
                    Swal.fire({
                        icon: 'warning',
                        iconHtml: 'i',
                        title: 'Email Sending Failed',
                        text: 'Account created, but we couldn\'t send the email: ' + result.error + '. Please contact support.',
                        confirmButtonText: 'I understand',
                        confirmButtonColor: '#8b5cf6'
                    }).then(() => {
                        window.location = '/static/pages/verify.html?email=' + encodeURIComponent(email);
                    });
                }
                
            } catch (error) {
                let msg = 'Registration failed';
                if (error.response && error.response.data) {
                    msg = error.response.data.detail || msg;
                }
                Swal.fire({ icon: 'error', title: 'Registration Failed', html: msg.replace(/\n/g, '<br>'), confirmButtonColor: '#8b5cf6' });
            } finally {
                this.loading = false;
            }
        }
    }
});

app.mount('#app');
