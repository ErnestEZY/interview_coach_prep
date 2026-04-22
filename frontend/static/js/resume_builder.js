const { createApp } = Vue;

try {
    const app = createApp({
        data() {
            return {
                userName: '',
                userEmail: '',
                logged: false,
                isMobileMenuOpen: false,
                sessionTime: 0,
                timerId: null,
                isLoading: true,
                _isUnmounted: false,
                totalPages: 1,
                currentPage: 1,
                themes: [
                    { name: 'Classic', className: 'theme-classic' },
                    { name: 'Modern', className: 'theme-modern' },
                    { name: 'Kendall', className: 'theme-kendall' },
                    { name: 'Flat', className: 'theme-flat' },
                    { name: 'Gov-Standard', className: 'theme-gov' },
                ],
                currentTheme: { name: 'Classic', className: 'theme-classic' },
                actionVerbs: [
                    'Developed', 'Implemented', 'Designed', 'Optimized', 'Led', 'Managed', 'Created', 'Improved', 'Increased', 'Reduced', 'Analyzed', 'Engineered', 'Launched', 'Collaborated'
                ],
                resume: {
                    name: 'FULL NAME',
                    title: 'Professional Title',
                    email: 'ernest@example.com',
                    phone: '+60 12-345 6789',
                    location: 'Kuala Lumpur, MY',
                    website: 'linkedin.com/in/ernestezy',
                    summary: 'Passionate software engineer with expertise in building AI-powered web applications and mobile solutions. Dedicated to bridging the experience gap through innovative technology.',
                    education: [
                        { school: 'Asia Pacific University (APU)', degree: 'BSc (Hons) in Computer Science (Intelligent Systems)', date: '2022 - 2025', gpa: '3.85/4.00', location: 'Kuala Lumpur, MY' }
                    ],
                    experience: [
                        {
                            company: 'Tech Innovators Corp',
                            position: 'Software Engineering Intern',
                            date: 'June 2024 - August 2024',
                            bullets: [
                                'Engineered and launched a key feature for a web application, resulting in a 15% increase in user engagement.',
                                'Reduced server response time by 25% through strategic query optimization and caching.',
                                'Collaborated with a cross-functional team of 5 to design and deploy a new microservice.'
                            ]
                        }
                    ],
                    projects: [
                        {
                            name: 'E-commerce Recommendation Engine',
                            tech: 'Python, TensorFlow, Scikit-learn, Flask',
                            bullets: [
                                'Increased average order value by 15% by developing a collaborative filtering model that suggested relevant products to users.',
                                'Improved user retention by 10% by implementing a real-time, personalized product recommendation API.'
                            ]
                        }
                    ],
                    skills_tech: ['Python', 'JavaScript', 'TypeScript'],
                    skills_tools: ['Docker', 'AWS', 'Git'],
                    skills_soft: ['Leadership', 'Communication'],
                    skills_other: ['Agile Methodologies'],
                    certifications: [{ name: 'AWS Certified Cloud Practitioner (2024)' }],
                    languages: [{ name: 'English (Fluent)' }, { name: 'Malay (Native)' }],
                    extra_info: [
                        { content: 'Available for relocation.' },
                        { content: 'Active member of the Open Source community.' }
                    ]
                }
            };
        },
        watch: {
            resume: {
            handler(val) {
                localStorage.setItem('resume_builder_session', JSON.stringify(val));
                this.$nextTick(() => {
                    this.updatePageCount();
                });
            },
            deep: true
        }
    },
    computed: {
        nameFontSize() {
            const length = this.resume.name.length;
            if (length > 30) return '12pt';
            if (length > 20) return '14pt';
            return '16pt';
        }
    },
        async mounted() {
        console.log("Resume Builder Mounted");
        
        // Listen for auth changes
        this._authListener = () => {
            const token = localStorage.getItem('token');
            this.logged = !!token;
            if (!this.logged) {
                window.location.href = '/static/pages/login.html';
            }
        };
        window.addEventListener('auth:changed', this._authListener);
        
        // Initialize page count after loading state
        this.$nextTick(() => {
            setTimeout(() => {
                this.updatePageCount();
            }, 500);
        });

        const token = localStorage.getItem('token');
            this.logged = !!token;
            
            if (!this.logged) {
                window.location.href = '/static/pages/login.html';
                return;
            }

            // Load session data if available
            const savedResume = localStorage.getItem('resume_builder_session');
            if (savedResume) {
                try {
                    this.resume = JSON.parse(savedResume);
                    console.log("Session data restored");
                } catch (e) {
                    console.error("Error restoring session:", e);
                }
            }

            // Load user info
            await this.setUserFromToken();
            
            // Setup session timer if app.js is loaded
            if (window.setupSessionTimer) {
                try {
                    this.timerId = window.setupSessionTimer(this);
                } catch (e) {
                    console.error("Error setting up session timer:", e);
                }
            }

            // Add a small delay to ensure app.js checks are done
            setTimeout(() => {
                this.isLoading = false;
                console.log("Loading complete, state:", this.resume);
                this.checkAnalysisImport();
            }, 200);

            // Initialize with one empty item for main sections if they are empty
            if (this.resume.education.length === 0) this.addItem('education');
            if (this.resume.experience.length === 0) this.addItem('experience');
        },
        beforeUnmount() {
            this._isUnmounted = true;
            if (this.timerId) {
                clearInterval(this.timerId);
                this.timerId = null;
            }
            if (this._authListener) window.removeEventListener('auth:changed', this._authListener);
            document.body.style.overflow = "";
        },
        methods: {
            toggleMobileMenu() {
                this.isMobileMenuOpen = !this.isMobileMenuOpen;
                if (window.handleMobileMenu) {
                    window.handleMobileMenu(this.isMobileMenuOpen);
                }
            },
            async checkAnalysisImport() {
                const feedbackStr = localStorage.getItem('resume_feedback');
                const hidePrompt = localStorage.getItem('resume_builder_hide_import_prompt') === 'true';
                
                if (feedbackStr && !hidePrompt) {
                    const result = await Swal.fire({
                        title: 'Import AI-Polished Data?',
                        html: `
                            <p>We found your recently analyzed resume. Would you like to pre-fill the builder with polished, AI-extracted information?</p>
                            <div class="form-check d-flex justify-content-center mt-3">
                                <input class="form-check-input me-2" type="checkbox" id="dontAskAgain">
                                <label class="form-check-label small text-secondary" for="dontAskAgain" style="cursor: pointer;">
                                    Don't remind me again until logout
                                </label>
                            </div>
                        `,
                        icon: 'question',
                        showCancelButton: true,
                        confirmButtonText: 'Yes, Import',
                        cancelButtonText: 'No, Thanks',
                        confirmButtonColor: '#0d6efd',
                        cancelButtonColor: '#6c757d',
                        allowOutsideClick: false
                    });

                    const dontAskAgainChecked = document.getElementById('dontAskAgain')?.checked;
                    
                    if (dontAskAgainChecked) {
                        localStorage.setItem('resume_builder_hide_import_prompt', 'true');
                    }

                    if (result.isConfirmed) {
                        try {
                            const feedback = JSON.parse(feedbackStr);
                            
                            // 1. Basics
                            const targetJobTitle = localStorage.getItem('target_job_title');
                            if (targetJobTitle) {
                                this.resume.title = targetJobTitle;
                            } else if (feedback.DetectedJobTitle) {
                                this.resume.title = feedback.DetectedJobTitle;
                            }
                            
                            if (feedback.Location) this.resume.location = feedback.Location;
                            if (feedback.Email) this.resume.email = feedback.Email;
                            if (feedback.Phone) this.resume.phone = feedback.Phone;
                            if (feedback.Website) this.resume.website = feedback.Website;
                            if (feedback.ProfessionalSummary || feedback.Summary) {
                                this.resume.summary = feedback.ProfessionalSummary || feedback.Summary;
                            }
                            
                            // 2. Education
                            if (feedback.Education && Array.isArray(feedback.Education) && feedback.Education.length > 0) {
                                this.resume.education = feedback.Education.map(edu => ({
                                    school: edu.Institution || edu.school || edu.School || '',
                                    degree: edu.Degree || edu.degree || '',
                                    date: edu.Date || edu.date || edu.Period || '',
                                    location: edu.Location || edu.location || '',
                                    gpa: edu.GPA || edu.gpa || edu.Grade || ''
                                }));
                            }

                            // 3. Experience
                            if (feedback.Experience && Array.isArray(feedback.Experience) && feedback.Experience.length > 0) {
                                this.resume.experience = feedback.Experience.map(exp => {
                                    let bullets = [''];
                                    if (exp.Bullets && Array.isArray(exp.Bullets)) {
                                        bullets = exp.Bullets;
                                    } else if (exp.Description) {
                                        bullets = exp.Description.split('\n')
                                            .filter(b => b.trim())
                                            .map(b => b.replace(/^[•\-\*]\s*/, '').trim());
                                    }
                                    return {
                                        company: exp.Company || exp.company || '',
                                        position: exp.Position || exp.position || exp.Role || '',
                                        date: exp.Date || exp.date || exp.Period || '',
                                        bullets: bullets.length > 0 ? bullets : ['']
                                    };
                                });
                            }

                            // 4. Projects
                            if (feedback.Projects && Array.isArray(feedback.Projects) && feedback.Projects.length > 0) {
                                this.resume.projects = feedback.Projects.map(proj => {
                                    let bullets = [''];
                                    if (proj.Bullets && Array.isArray(proj.Bullets)) {
                                        bullets = proj.Bullets;
                                    } else if (proj.Description) {
                                        bullets = proj.Description.split('\n')
                                            .filter(b => b.trim())
                                            .map(b => b.replace(/^[•\-\*]\s*/, '').trim());
                                    }
                                    return {
                                        name: proj.Name || proj.name || '',
                                        tech: proj.Tech || proj.tech || proj.Technologies || '',
                                        bullets: bullets.length > 0 ? bullets : ['']
                                    };
                                });
                            }

                            // 5. Skills
                            if (feedback.SkillsTech) {
                                this.resume.skills_tech = Array.isArray(feedback.SkillsTech) ? feedback.SkillsTech : feedback.SkillsTech.split(/[,\n]/).map(s => s.trim()).filter(s => s);
                            }
                            if (feedback.SkillsTools) {
                                this.resume.skills_tools = Array.isArray(feedback.SkillsTools) ? feedback.SkillsTools : feedback.SkillsTools.split(/[,\n]/).map(s => s.trim()).filter(s => s);
                            }
                            if (feedback.SkillsSoft) {
                                this.resume.skills_soft = Array.isArray(feedback.SkillsSoft) ? feedback.SkillsSoft : feedback.SkillsSoft.split(/[,\n]/).map(s => s.trim()).filter(s => s);
                            }
                            
                            // 6. Others
                            if (feedback.Certifications && Array.isArray(feedback.Certifications)) {
                                this.resume.certifications = feedback.Certifications.map(c => ({ 
                                    name: typeof c === 'string' ? c : (c.name || c.Name || '') 
                                })).filter(c => c.name);
                            }
                            if (feedback.Languages && Array.isArray(feedback.Languages)) {
                                this.resume.languages = feedback.Languages.map(l => ({ 
                                    name: typeof l === 'string' ? l : (l.name || l.Name || '') 
                                })).filter(l => l.name);
                            }

                            // 7. Extra
                            if (feedback.AdditionalInfo && Array.isArray(feedback.AdditionalInfo)) {
                                this.resume.extra_info = feedback.AdditionalInfo.map(i => ({ 
                                    content: typeof i === 'string' ? i : (i.content || i.Content || '') 
                                })).filter(i => i.content);
                            } else if (feedback.ExtraInfo && typeof feedback.ExtraInfo === 'string') {
                                this.resume.extra_info = feedback.ExtraInfo.split('\n')
                                    .filter(line => line.trim())
                                    .map(line => ({ content: line.trim() }));
                            }
                            
                            // Trigger immediate save to session
                            localStorage.setItem('resume_builder_session', JSON.stringify(this.resume));
                            
                            Swal.fire({
                                icon: 'success',
                                title: 'Full Import Complete',
                                text: 'Your AI-polished sections have been pre-filled.',
                                timer: 2000,
                                showConfirmButton: false
                            });
                        } catch (e) {
                            console.error("Error importing feedback:", e);
                        }
                    }
                }
            },
            async setUserFromToken() {
                const token = localStorage.getItem('token');
                if (!token) return;
                
                try {
                    // Try backend first
                    const apiUrl = (window.icp && window.icp.apiUrl) ? window.icp.apiUrl('/api/auth/me') : '/api/auth/me';
                    const response = await axios.get(apiUrl);
                    const me = response.data || {};
                    this.userName = me.name || 'Guest';
                    this.userEmail = me.email || '';
                    // Update resume name if it was default
                    if (this.resume.name === 'FULL NAME') {
                        this.resume.name = this.userName;
                    }
                    if (this.resume.email === 'ernest@example.com') {
                        this.resume.email = this.userEmail;
                    }
                } catch (_) {
                    // Fallback to decode token
                    try {
                        const base64Url = token.split('.')[1];
                        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
                        const payload = JSON.parse(atob(base64));
                        this.userName = payload.name || 'Guest';
                        this.userEmail = payload.email || '';
                        if (this.resume.name === 'FULL NAME') {
                            this.resume.name = this.userName;
                        }
                        if (this.resume.email === 'ernest@example.com') {
                            this.resume.email = this.userEmail;
                        }
                    } catch (e) {
                        console.error("Error decoding token:", e);
                    }
                }
            },
            addItem(type) {
                if (type === 'education') this.resume.education.push({ school: '', degree: '', date: '', gpa: '', location: '' });
                if (type === 'experience') this.resume.experience.push({ company: '', position: '', date: '', bullets: [''] });
                if (type === 'projects') this.resume.projects.push({ name: '', tech: '', bullets: [''] });
                if (type === 'certifications') this.resume.certifications.push({ name: '' });
                if (type === 'languages') this.resume.languages.push({ name: '' });
                if (type === 'extra_info') {
                    if (!Array.isArray(this.resume.extra_info)) this.resume.extra_info = [];
                    this.resume.extra_info.push({ content: '' });
                }
                if (type === 'skills_tech') this.resume.skills_tech.push('');
                if (type === 'skills_tools') this.resume.skills_tools.push('');
                if (type === 'skills_soft') this.resume.skills_soft.push('');
                if (type === 'skills_other') this.resume.skills_other.push('');
            },
            removeItem(type, index) {
                this.resume[type].splice(index, 1);
            },
            addBullet(type, index) {
                if (!this.resume[type][index].bullets) {
                    this.resume[type][index].bullets = [];
                }
                this.resume[type][index].bullets.push('');
            },
            removeBullet(type, itemIndex, bulletIndex) {
                this.resume[type][itemIndex].bullets.splice(bulletIndex, 1);
            },
            addVerbToLastBullet(type, itemIndex, verb) {
                const bullets = this.resume[type][itemIndex].bullets;
                if (bullets.length > 0) {
                    const lastBullet = bullets[bullets.length - 1];
                    bullets[bullets.length - 1] = lastBullet ? `${verb} ${lastBullet}` : verb;
                } else {
                    this.addBullet(type, itemIndex);
                    this.resume[type][itemIndex].bullets[0] = verb;
                }
            },
            async downloadPDF() {
                const element = document.getElementById('resume-template');
                if (!element) return;

                // 1. Show instruction alert for ATS-Friendly PDF
                const result = await Swal.fire({
                    title: 'Download ATS-Friendly PDF',
                    text: 'For the best results (selectable text & ATS-friendly), we recommend using "Save as PDF" in the print dialog.',
                    icon: 'info',
                    showCancelButton: true,
                    showCloseButton: true, // Added Close Button
                    confirmButtonText: 'Open Print Dialog',
                    cancelButtonText: 'Direct Download',
                    confirmButtonColor: '#0d6efd',
                    cancelButtonColor: '#6c757d'
                });

                // If user closed the alert or clicked outside
                if (result.isDismissed && result.dismiss === Swal.DismissReason.close || result.dismiss === Swal.DismissReason.esc) {
                    return;
                }

                // Capture original state to restore later
                const originalPage = this.currentPage;
                
                if (result.isConfirmed) {
                    // RESET TO PAGE 1 BEFORE PRINTING (Fixes "Blank Page" issue)
                    this.currentPage = 1;
                    
                    // Wait for Vue to update the DOM and use a longer delay for security
                    await this.$nextTick();
                    
                    // Add a tiny delay to ensure the browser has repainted for printing
                    setTimeout(() => {
                        window.print();
                        // Restore page after a short delay
                        this.currentPage = originalPage;
                    }, 500);
                    return;
                }

                // 2. Direct Download Fallback (if they clicked "Direct Download")
                if (result.dismiss === Swal.DismissReason.cancel) {
                    Swal.fire({
                        title: 'Generating PDF...',
                        text: 'Please wait while we prepare your file.',
                        allowOutsideClick: false,
                        showCloseButton: true, // Allow cancelling during direct download
                        didOpen: () => {
                            Swal.showLoading();
                        }
                    });

                    try {
                        // Create a COMPLETELY NEW element for capture to avoid transform/pagination issues
                        const captureContainer = document.createElement('div');
                        captureContainer.id = 'temp-capture-container';
                        captureContainer.style.position = 'absolute';
                        captureContainer.style.left = '-9999px';
                        captureContainer.style.top = '0';
                        captureContainer.style.width = '210mm';
                        captureContainer.style.background = 'white';
                        
                        // Clone the template but STRIP the Vue-driven transforms
                        const clone = element.cloneNode(true);
                        clone.style.transform = 'none';
                        clone.style.padding = '0'; // Remove inner padding, let html2pdf handle margins
                        clone.style.margin = '0';
                        clone.style.width = '170mm'; // 210mm - 40mm (left+right margins)
                        clone.style.boxShadow = 'none';
                        clone.style.minHeight = 'auto'; 
                        
                        captureContainer.appendChild(clone);
                        document.body.appendChild(captureContainer);

                        const opt = {
                            margin: [20, 20, 20, 20], // Strict 20mm margins on all sides for EVERY page
                            filename: `${this.resume.name.replace(/\s+/g, '_')}_Resume.pdf`,
                            image: { type: 'jpeg', quality: 0.98 },
                            html2canvas: { 
                                scale: 2, 
                                useCORS: true, 
                                letterRendering: true,
                                backgroundColor: '#ffffff',
                                scrollY: 0
                            },
                            jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' },
                            pagebreak: { mode: ['avoid-all', 'css', 'legacy'] }
                        };

                        await html2pdf().set(opt).from(clone).save();
                        
                        if (document.getElementById('temp-capture-container')) {
                            document.body.removeChild(captureContainer);
                        }
                        Swal.close();
                    } catch (err) {
                        console.error("PDF Export Error:", err);
                        Swal.fire('Error', 'Failed to generate PDF. Please try again.', 'error');
                    }
                }
            },
            logout() {
                if (window.logout) {
                    window.logout();
                } else {
                    localStorage.clear();
                    window.location.href = '/static/pages/login.html';
                }
            },
            formatTime(seconds) {
                const mins = Math.floor(seconds / 60);
                const secs = seconds % 60;
                return `${mins}:${secs.toString().padStart(2, '0')}`;
            },
            setTheme(theme) {
                this.currentTheme = theme;
                this.$nextTick(() => {
                    this.updatePageCount();
                });
            },
            updatePageCount() {
                // Calculate total pages based on 297mm height per page
                // We use a slightly more robust calculation by looking at the actual rendered height
                const element = document.getElementById('resume-template');
                if (element) {
                    // 297mm is approximately 1122.5 pixels at 96 DPI
                    // However, since we work in mm, let's keep it in mm logic
                    const totalHeightMm = element.offsetHeight * (25.4 / 96); 
                    this.totalPages = Math.max(1, Math.ceil(totalHeightMm / 297));
                    
                    if (this.currentPage > this.totalPages) {
                        this.currentPage = this.totalPages;
                    }
                }
            },
            prevPage() {
                if (this.currentPage > 1) {
                    this.currentPage--;
                    this.scrollToPreviewTop();
                }
            },
            nextPage() {
                if (this.currentPage < this.totalPages) {
                    this.currentPage++;
                    this.scrollToPreviewTop();
                }
            },
            scrollToPreviewTop() {
                const wrapper = document.querySelector('.resume-preview-wrapper');
                if (wrapper) {
                    wrapper.scrollTop = 0;
                }
            },
            getGuidance(bullet) {
                if (!bullet || bullet.trim().length === 0) return '';
                if (bullet.trim().length < 10) return 'Expand on this point for more impact.';
                const startsWithVerb = this.actionVerbs.some(verb => bullet.trim().toLowerCase().startsWith(verb.toLowerCase()));
                if (!startsWithVerb) return ''; // Removed as requested
                return '';
            }
        }
    });
    
    app.mount('#app');
    console.log("Vue App Instance Created and Mounted to #app");
} catch (error) {
    console.error("Critical Error during Vue initialization:", error);
}