const { createApp } = Vue;

try {
    const app = createApp({
        data() {
            return {
                userName: '',
                userEmail: '',
                logged: false,
                sessionTime: 0,
                isLoading: true,
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
            const token = localStorage.getItem('token');
            this.logged = !!token;
            
            if (!this.logged) {
                window.location.href = '/static/pages/login.html';
                return;
            }

            // Load user info
            await this.setUserFromToken();
            
            // Setup session timer if app.js is loaded
            if (window.setupSessionTimer) {
                try {
                    window.setupSessionTimer(this);
                } catch (e) {
                    console.error("Error setting up session timer:", e);
                }
            }

            // Add a small delay to ensure app.js checks are done
            setTimeout(() => {
                this.isLoading = false;
                console.log("Loading complete, state:", this.resume);
            }, 200);

            // Initialize with one empty item for main sections if they are empty
            if (this.resume.education.length === 0) this.addItem('education');
            if (this.resume.experience.length === 0) this.addItem('experience');
        },
        methods: {
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
            downloadPDF() {
                const element = document.getElementById('resume-template');
                element.classList.add(this.currentTheme.className);

                if (!element) {
                    console.error("Resume template element not found");
                    return;
                }

                const opt = {
                    margin: 0,
                    filename: `${this.resume.name.replace(/\s+/g, '_')}_Resume.pdf`,
                    image: { type: 'jpeg', quality: 0.98 },
                    html2canvas: { scale: 3, useCORS: true, letterRendering: true },
                    jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
                };

                if (typeof html2pdf !== 'undefined') {
                    html2pdf().set(opt).from(element).save();
                } else {
                    Swal.fire('Error', 'PDF library not loaded. Please refresh the page.', 'error');
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
            getGuidance(bullet) {
                if (!bullet || bullet.trim().length === 0) return '';
                if (bullet.trim().length < 10) return 'Expand on this point for more impact.';
                const startsWithVerb = this.actionVerbs.some(verb => bullet.trim().toLowerCase().startsWith(verb.toLowerCase()));
                if (!startsWithVerb) return 'Start with a strong action verb (e.g., Developed, Managed).';
                if (!/\d/.test(bullet)) return 'Quantify your achievement with numbers or data if possible.';
                return '';
            }
        }
    });
    
    app.mount('#app');
    console.log("Vue App Instance Created and Mounted to #app");
} catch (error) {
    console.error("Critical Error during Vue initialization:", error);
}
