const { createApp } = Vue;

try {
    const app = createApp({
        data() {
            return {
                userName: '',
                userEmail: '',
                logged: false,
                hasAnalyzed: false,
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
                // AI assist loading state per section/index
                assistState: {
                    summary: false,
                    experience: {},   // keyed by entry index
                    projects: {},     // keyed by entry index
                },
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
            
            // Start session timer using JWT exp decode (same pattern as all other pages)
            this.startTimer();

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

            startTimer() {
                if (this.timerId) return;
                const token = (window.icp && window.icp.state && window.icp.state.token)
                              || localStorage.getItem('token');
                if (!token) return;

                let exp = null;
                try {
                    const payload = JSON.parse(
                        atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'))
                    );
                    exp = payload.exp;
                } catch (_) { return; }
                if (!exp) return;

                const updateTimer = () => {
                    if (this._isUnmounted) {
                        if (this.timerId) { clearInterval(this.timerId); this.timerId = null; }
                        return;
                    }
                    const now = Math.floor(Date.now() / 1000);
                    this.sessionTime = Math.max(0, exp - now);

                    if (this.sessionTime <= 0) {
                        if (this.timerId) { clearInterval(this.timerId); this.timerId = null; }
                        Swal.fire({
                            icon: 'warning',
                            title: 'Session Expired',
                            text: 'Your session has expired. Please login again to continue.',
                            confirmButtonText: 'Login Again',
                            confirmButtonColor: '#8b5cf6',
                            allowOutsideClick: false
                        }).then(() => {
                            if (window.icp) window.icp.logout();
                            else { localStorage.clear(); window.location.href = '/static/pages/login.html'; }
                        });
                    }
                };

                updateTimer();
                this.timerId = setInterval(updateTimer, 1000);
            },
            async checkAnalysisImport() {
                const feedbackStr = localStorage.getItem('resume_feedback');
                const hidePrompt = localStorage.getItem('resume_builder_hide_import_prompt') === 'true';

                // Only offer import if has_analyzed is true (backend confirms user has analysed)
                // AND there's actual feedback data in localStorage.
                // This prevents stale or injected localStorage data from triggering the prompt.
                if (!this.hasAnalyzed) return;
                
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
                    // Use has_analyzed from backend OR session flag set after upload
                    this.hasAnalyzed = !!me.has_analyzed || localStorage.getItem('session_has_analyzed') === 'true';
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
                        this.hasAnalyzed = !!payload.has_analyzed || localStorage.getItem('session_has_analyzed') === 'true';
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
                if (type === 'education') {
                    if (this.resume.education.length >= 3) return;
                    this.resume.education.push({ school: '', degree: '', date: '', gpa: '', location: '' });
                }
                if (type === 'experience') {
                    if (this.resume.experience.length >= 3) return;
                    this.resume.experience.push({ company: '', position: '', date: '', bullets: [''] });
                }
                if (type === 'projects') {
                    if (this.resume.projects.length >= 3) return;
                    this.resume.projects.push({ name: '', tech: '', bullets: [''] });
                }
                if (type === 'certifications') {
                    if (this.resume.certifications.length >= 4) return;
                    this.resume.certifications.push({ name: '' });
                }
                if (type === 'languages') {
                    if (this.resume.languages.length >= 4) return;
                    this.resume.languages.push({ name: '' });
                }
                if (type === 'extra_info') {
                    if (!Array.isArray(this.resume.extra_info)) this.resume.extra_info = [];
                    if (this.resume.extra_info.length >= 4) return;
                    this.resume.extra_info.push({ content: '' });
                }
                if (type === 'skills_tech') {
                    if (this.resume.skills_tech.length >= 6) return;
                    this.resume.skills_tech.push('');
                }
                if (type === 'skills_tools') {
                    if (this.resume.skills_tools.length >= 6) return;
                    this.resume.skills_tools.push('');
                }
                if (type === 'skills_soft') {
                    if (this.resume.skills_soft.length >= 6) return;
                    this.resume.skills_soft.push('');
                }
                if (type === 'skills_other') {
                    if (this.resume.skills_other.length >= 6) return;
                    this.resume.skills_other.push('');
                }
            },
            removeItem(type, index) {
                this.resume[type].splice(index, 1);
            },
            addBullet(type, index) {
                if (!this.resume[type][index].bullets) {
                    this.resume[type][index].bullets = [];
                }
                if (this.resume[type][index].bullets.length >= 4) return;
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
                const el = document.getElementById('resume-template');
                if (!el) return;

                // Ask user which download type they want
                const result = await Swal.fire({
                    title: 'Download Resume',
                    html: `
                        <div class="text-start">
                            <p class="text-secondary small mb-3">Choose your preferred format:</p>
                            <div class="d-flex flex-column gap-2">
                                <div class="p-3 rounded" style="border: 1px solid #93c5fd; background: #eff6ff;">
                                    <div class="fw-bold small mb-1" style="color: #1d4ed8;">&#9733; Save as PDF — ATS Friendly</div>
                                    <div class="small" style="color: #374151;">Text-based PDF. Selectable, copyable and scannable by ATS systems. Recommended for job applications.</div>
                                </div>
                                <div class="p-3 rounded" style="border: 1px solid #d1d5db; background: #f9fafb;">
                                    <div class="fw-bold small mb-1" style="color: #374151;">Direct Download — Image Based</div>
                                    <div class="small" style="color: #4b5563;">Renders resume as an image. Looks pixel-perfect but text cannot be selected or scanned by ATS.</div>
                                </div>
                            </div>
                        </div>
                    `,
                    showCancelButton: true,
                    showCloseButton: true,
                    confirmButtonText: '&#8681; Save as PDF (ATS)',
                    cancelButtonText: '&#8681; Direct Download',
                    confirmButtonColor: '#2563eb',
                    cancelButtonColor: '#6b7280',
                    reverseButtons: false
                });

                // Only bail out if the user closed/escaped — not if they clicked cancel (Direct Download)
                if (result.isDismissed && result.dismiss !== Swal.DismissReason.cancel) return;

                const rawName = this.resume.name || 'Resume';
                const themeClass = this.currentTheme.className;
                const fileName = rawName.replace(/\s+/g, '_') + '_Resume';

                // ── ATS Path: clean popup print ─────────────────────────────────────────
                if (result.isConfirmed) {
                    const resumeHTML = el.innerHTML;

                    const printDoc = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>${fileName}</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    html, body { background: white; font-family: 'Times New Roman', Times, serif; color: #333; font-size: 11pt; line-height: 1.5; }
    @page { size: A4 portrait; margin: 0; }
    body { padding: 12mm 14mm; }
    #resume-template { width: 100%; }
    .resume-header { border-bottom: 2px solid #333; padding-bottom: 10px; margin-bottom: 15px; text-align: center; }
    .resume-name { font-size: 22pt; font-weight: bold; color: #333; text-transform: uppercase; letter-spacing: 2px; overflow-wrap: break-word; word-break: break-word; margin-bottom: 5px; }
    .resume-title { font-size: 12pt; color: #555; font-weight: 500; margin-bottom: 10px; }
    .resume-contact { font-size: 10pt; color: #444; display: flex; gap: 15px; flex-wrap: wrap; justify-content: center; }
    .section-title { font-size: 14pt; font-weight: bold; color: #333; border-bottom: 1px solid #ccc; padding-bottom: 5px; margin-top: 20px; margin-bottom: 10px; text-transform: uppercase; page-break-after: avoid; break-after: avoid; }
    .resume-item { margin-bottom: 15px; page-break-inside: avoid; break-inside: avoid; }
    .item-header { display: flex; justify-content: space-between; font-weight: bold; }
    .item-sub { font-style: italic; color: #555; font-size: 10pt; margin-bottom: 5px; }
    .item-desc { font-size: 10pt; line-height: 1.4; color: #444; }
    .skills-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px 20px; margin-top: 5px; }
    .skill-group-title { font-weight: bold; font-size: 10pt; margin-bottom: 2px; }
    .skills-list { font-size: 10pt; color: #444; }
    .cert-lang-row { display: flex; gap: 20px; }
    .cert-lang-col-left, .cert-lang-col-right { flex: 1; }
    .cert-lang-item { page-break-inside: avoid; break-inside: avoid; }
    #resume-template::after { display: none !important; }
    .bi::before { content: '' }
    .theme-classic { font-family: 'Times New Roman', Times, serif; }
    .theme-classic .resume-name { color: #333; }
    .theme-classic .section-title { border-bottom-color: #ccc; color: #333; }
    .theme-modern { font-family: Arial, Helvetica, sans-serif; }
    .theme-modern .resume-header { border-bottom-color: #007BFF; }
    .theme-modern .resume-name { color: #007BFF; letter-spacing: 1px; }
    .theme-modern .section-title { border-bottom: 2px solid #007BFF; color: #333; text-transform: uppercase; font-size: 13pt; }
    .theme-modern .item-header span:first-child { color: #007BFF; }
    .theme-kendall { font-family: 'Garamond', 'Times New Roman', serif; }
    .theme-kendall .resume-name { font-family: 'Garamond', serif; font-weight: bold; text-align: center; letter-spacing: 4px; font-size: 24pt; }
    .theme-kendall .section-title { font-family: 'Garamond', serif; text-align: center; font-size: 14pt; letter-spacing: 2px; border-top: 1px solid #000; border-bottom: 1px solid #000; padding-top: 5px; padding-bottom: 5px; margin-top: 15px; }
    .theme-flat { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; }
    .theme-flat .section-title { background-color: #f2f2f2; padding: 5px 10px; font-size: 12pt; font-weight: bold; border-left: 4px solid #333; }
    .theme-flat .item-header span:first-child { font-weight: bold; }
    .theme-gov { font-family: 'Times New Roman', Times, serif; }
    .theme-gov .resume-name { font-size: 18pt; font-weight: bold; }
    .theme-gov .section-title { font-weight: bold; border-bottom: 2px solid #000; padding-bottom: 2px; margin-bottom: 8px; text-transform: uppercase; }
    .theme-gov .item-header { font-weight: normal; }
    .theme-gov .item-header span:first-child { font-weight: bold; }
    * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  </style>
</head>
<body>
  <div id="resume-template" class="${themeClass}">
    ${resumeHTML}
  </div>
  <script>
    window.onload = function() {
      setTimeout(function() {
        window.print();
        window.onafterprint = function() { window.close(); };
      }, 250);
    };
  <\/script>
</body>
</html>`;

                    const printWin = window.open('', '_blank', 'width=900,height=700,scrollbars=yes,toolbar=no,menubar=no,location=no,status=no');
                    if (!printWin) {
                        Swal.fire({
                            icon: 'warning',
                            title: 'Popup Blocked',
                            html: 'Please allow popups for this site, then try again.',
                            confirmButtonColor: '#8b5cf6'
                        });
                        return;
                    }
                    printWin.document.write(printDoc);
                    printWin.document.close();
                    return;
                }

                // ── Direct Download Path: jsPDF image-based ─────────────────────────────
                if (result.dismiss === Swal.DismissReason.cancel) {
                    Swal.fire({
                        title: 'Generating PDF...',
                        text: 'Please wait while we prepare your file.',
                        allowOutsideClick: false,
                        showCloseButton: false,
                        didOpen: () => { Swal.showLoading(); }
                    });

                    try {
                        const savedPage = this.currentPage;
                        this.currentPage = 1;
                        await this.$nextTick();
                        await new Promise(r => setTimeout(r, 150));

                        const offscreen = document.createElement('div');
                        // Use position:absolute top:-9999px (NOT fixed + negative z-index)
                        // so html2canvas can capture the element. Fixed + z-index:-9999
                        // causes html2canvas to render a blank canvas on some browsers.
                        offscreen.style.cssText = [
                            'position:absolute',
                            'top:-9999px',
                            'left:0',
                            'width:794px',
                            'height:auto',
                            'overflow:visible',
                            'background:white',
                            'pointer-events:none',
                        ].join(';');
                        document.body.appendChild(offscreen);

                        const clone = el.cloneNode(true);
                        // Ensure the theme class from the live element is on the clone.
                        // el already has it, but explicitly set it to be safe.
                        clone.className = el.className;
                        clone.style.cssText = [
                            'width:794px',
                            'min-height:auto',
                            'padding:57px',     // ≈15mm at 96dpi
                            'box-sizing:border-box',
                            'transform:none',
                            'box-shadow:none',
                            'background:white',
                            'position:static',
                            'display:block',
                        ].join(';');
                        clone.removeAttribute('data-pdf-export');
                        clone.setAttribute('data-pdf-export', 'true');
                        offscreen.appendChild(clone);

                        await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
                        await new Promise(r => setTimeout(r, 80));

                        const canvas = await html2canvas(clone, {
                            scale: 2, useCORS: true, letterRendering: true,
                            backgroundColor: '#ffffff',
                            scrollX: 0, scrollY: 0, x: 0, y: 0,
                            width: clone.scrollWidth, height: clone.scrollHeight,
                            windowWidth: clone.scrollWidth, windowHeight: clone.scrollHeight,
                            ignoreElements: (node) =>
                                node.tagName === 'NAV' ||
                                node.classList.contains('resume-preview-actions') ||
                                node.classList.contains('resume-pagination') ||
                                node.classList.contains('session-timer-badge'),
                        });

                        document.body.removeChild(offscreen);
                        this.currentPage = savedPage;

                        let JsPDF = (window.jspdf && window.jspdf.jsPDF) ? window.jspdf.jsPDF : window.jsPDF;
                        if (!JsPDF) throw new Error('jsPDF library not found.');

                        const pdf     = new JsPDF({ unit: 'mm', format: 'a4', orientation: 'portrait' });
                        const pageW   = pdf.internal.pageSize.getWidth();
                        const pageH   = pdf.internal.pageSize.getHeight();
                        const cW      = canvas.width;
                        const cH      = canvas.height;
                        const pxPerMm = cW / pageW;
                        const pageHpx = pageH * pxPerMm;

                        let pageNum = 0, srcY = 0;
                        while (srcY < cH) {
                            if (pageNum > 0) pdf.addPage();
                            const sliceH = Math.min(pageHpx, cH - srcY);
                            const slice = document.createElement('canvas');
                            slice.width  = cW;
                            slice.height = Math.ceil(sliceH);
                            slice.getContext('2d').drawImage(canvas, 0, srcY, cW, sliceH, 0, 0, cW, Math.ceil(sliceH));
                            pdf.addImage(slice.toDataURL('image/jpeg', 0.98), 'JPEG', 0, 0, pageW, sliceH / pxPerMm);
                            srcY += pageHpx;
                            pageNum++;
                        }

                        pdf.save(`${rawName.replace(/\s+/g, '_')}_Resume.pdf`);
                        Swal.close();
                    } catch (err) {
                        console.error('PDF Export Error:', err);
                        const leftover = document.querySelector('div[style*="top:-9999px"]');
                        if (leftover) document.body.removeChild(leftover);
                        Swal.fire({ icon: 'error', title: 'Export Failed', text: err.message || 'Please try again.', confirmButtonColor: '#8b5cf6' });
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
            },

            // ── AI Writing Assist Methods ──────────────────────────────────

            async assistSummary() {
                const text = this.resume.summary;
                if (!text || !text.trim()) {
                    Swal.fire({
                        icon: 'info',
                        title: 'Nothing to enhance yet',
                        text: 'Please write your summary first before using AI assist.',
                        confirmButtonColor: '#8b5cf6',
                        timer: 3000,
                        showConfirmButton: false,
                    });
                    return;
                }
                this.assistState.summary = true;
                try {
                    const token = localStorage.getItem('token');
                    const apiUrl = window.icp ? window.icp.apiUrl('/api/assist/summary') : '/api/assist/summary';
                    const res = await axios.post(
                        apiUrl,
                        { text: text.trim(), job_title: this.resume.title || '', char_limit: 250 },
                        { headers: { Authorization: `Bearer ${token}` } }
                    );
                    const improved = this._stripMarkdown(res.data?.result || '');
                    if (improved) this.resume.summary = improved;
                } catch (err) {
                    const msg = err.response?.data?.detail || 'AI assist failed. Please try again.';
                    Swal.fire({ icon: 'error', title: 'Assist Failed', text: msg, confirmButtonColor: '#8b5cf6' });
                } finally {
                    this.assistState.summary = false;
                }
            },

            async assistBullets(section, index) {
                const entry = this.resume[section][index];
                const bullets = (entry?.bullets || []).filter(b => b && b.trim());
                if (!bullets.length) {
                    Swal.fire({
                        icon: 'info',
                        title: 'Nothing to enhance yet',
                        text: 'Please write at least one bullet point before using AI assist.',
                        confirmButtonColor: '#8b5cf6',
                        timer: 3000,
                        showConfirmButton: false,
                    });
                    return;
                }

                // Mark this specific entry as loading
                this.assistState[section] = { ...this.assistState[section], [index]: true };

                try {
                    const token = localStorage.getItem('token');
                    const apiUrl = window.icp ? window.icp.apiUrl('/api/assist/bullets') : '/api/assist/bullets';

                    // Build context string: for experience use company+position, for projects use name+tech
                    const roleContext = section === 'experience'
                        ? [entry.position, entry.company].filter(Boolean).join(' at ')
                        : [entry.name, entry.tech].filter(Boolean).join(' — ');

                    const res = await axios.post(
                        apiUrl,
                        {
                            bullets,
                            role_context: roleContext,
                            section,
                            char_limit: 250,
                        },
                        { headers: { Authorization: `Bearer ${token}` } }
                    );

                    const improved = (res.data?.result || []).map(b => this._stripMarkdown(b));
                    if (improved.length) {
                        // Replace bullets, padding with empty strings to retain array length
                        const updated = [...improved];
                        while (updated.length < entry.bullets.length) updated.push('');
                        this.resume[section][index].bullets = updated.slice(0, entry.bullets.length);
                    }
                } catch (err) {
                    const msg = err.response?.data?.detail || 'AI assist failed. Please try again.';
                    Swal.fire({ icon: 'error', title: 'Assist Failed', text: msg, confirmButtonColor: '#8b5cf6' });
                } finally {
                    this.assistState[section] = { ...this.assistState[section], [index]: false };
                }
            },

            /** Strip all markdown formatting and wrapping quotes from a string (client-side safety net) */
            _stripMarkdown(text) {
                if (!text) return '';
                // Remove bold/italic: **x**, *x*, __x__, _x_
                text = text.replace(/\*{1,3}([^*\n]+)\*{1,3}/g, '$1');
                text = text.replace(/_{1,3}([^_\n]+)_{1,3}/g, '$1');
                // Remove stray lone asterisks
                text = text.replace(/(?<!\w)\*+(?!\w)/g, '');
                text = text.trim();
                // Strip wrapping quotes the model sometimes adds
                if ((text.startsWith('"') && text.endsWith('"')) ||
                    (text.startsWith("'") && text.endsWith("'"))) {
                    text = text.slice(1, -1).trim();
                }
                return text;
            },
        }
    });
    
    app.mount('#app');
    console.log("Vue App Instance Created and Mounted to #app");
} catch (error) {
    console.error("Critical Error during Vue initialization:", error);
}