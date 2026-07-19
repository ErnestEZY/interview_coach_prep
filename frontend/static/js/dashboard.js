const { createApp } = Vue;

const app = createApp({
  data() {
    return {
      logged: false,
      isAdmin: false,
      userName: '',
      userEmail: '',
      isMobileMenuOpen: false,
      hasAnalyzed: false,
      sessionTime: 0,
      timerId: null,
      isLoading: true,
      feedback: null,
      uploading: false,
      hasHistory: false,
      fileName: '',
      targetJobTitle: localStorage.getItem('target_job_title') || '',
      resumeAttempts: 0,
      maxResumeAttempts: 5,
      persistedFileName: '',
      manualData: {
        jobTitle: '',
        experience: '',
        summary: '',
        skills: '',
        achievement: ''
      },
      assistLoading: {
        summary: false,
        skills: false,
        achievement: false,
      },
      consent: false,
      showInfoTooltip: false,
      isSubmitted: false,
      selectedFile: null,
      _isUnmounted: false,
      showAnalysisProgress: false,
      analysisProgress: 0,
      analysisStatus: 'Preparing analysis...',
      progressInterval: null
    };
  },
  computed: {
    hasResume() {
      return !!this.feedback || !!this.hasAnalyzed;
    }
  },
  mounted() {
        // Check initial token
        const token = window.icp && window.icp.state ? window.icp.state.token : localStorage.getItem("token");
        this.logged = !!token;

        if (this.logged) {
            this.startTimer();
            this.setUserFromToken();
            this.initDashboard();
        } else {
            this.isLoading = false;
            // Reset state if not logged in
            this.targetJobTitle = '';
            this.feedback = null;
            this.hasAnalyzed = false;
            this.fileName = '';
            this.persistedFileName = '';
        }

        // Prevent back button to unauthenticated pages
        this._allowedUserRoutes = [
            '/static/pages/dashboard.html',
            '/static/pages/history.html',
            '/static/pages/resume_builder.html',
            '/static/pages/find-jobs.html',
            '/static/pages/interview.html'
        ];
        // Check current URL on load
        const checkCurrentUrl = () => {
            const currentPath = window.location.pathname;
            const isAllowed = this._allowedUserRoutes.some(route => currentPath.includes(route));
            if (!isAllowed && this.logged) {
                window.location.replace('/static/pages/dashboard.html');
            }
        };
        checkCurrentUrl();
        // Popstate handler
        this._handlePopState = () => {
            const currentPath = window.location.pathname;
            const isAllowed = this._allowedUserRoutes.some(route => currentPath.includes(route));
            if (!isAllowed) {
                // If the new path isn't allowed, push the current URL back and go forward
                history.replaceState(null, '', location.href);
                history.pushState(null, '', location.href);
                history.go(1);
            } else {
                // If it is allowed, just push the state again
                history.pushState(null, '', location.href);
            }
        };
        // Initialize history
        history.replaceState(null, '', location.href);
        history.pushState(null, '', location.href);
        window.addEventListener('popstate', this._handlePopState);

        // Named listener for auth changes
        this._authListener = () => {
            const newToken = window.icp && window.icp.state ? window.icp.state.token : null;
            this.logged = !!newToken;
            if (this.logged) {
                this.startTimer();
                this.setUserFromToken();
                this.initDashboard();
            } else {
                this.isLoading = false;
                this.targetJobTitle = '';
                this.feedback = null;
                this.hasAnalyzed = false;
                this.fileName = '';
                this.persistedFileName = '';
                if (this.timerId) {
                    clearInterval(this.timerId);
                    this.timerId = null;
                }
            }
        };
        window.addEventListener('auth:changed', this._authListener);
        
        // Named listener for tooltip
        this._tooltipListener = (e) => {
            const wrapper = document.querySelector('.info-popover-wrapper');
            if (wrapper && !wrapper.contains(e.target)) {
                this.showInfoTooltip = false;
            }
        };
        document.addEventListener('click', this._tooltipListener);
    },
    beforeUnmount() {
        this._isUnmounted = true;
        if (this.timerId) clearInterval(this.timerId);
        if (this._authListener) window.removeEventListener('auth:changed', this._authListener);
        if (this._tooltipListener) document.removeEventListener('click', this._tooltipListener);
        if (this._handlePopState) window.removeEventListener('popstate', this._handlePopState);
        document.body.style.overflow = "";
    },
  methods: {
    toggleMobileMenu() {
      this.isMobileMenuOpen = !this.isMobileMenuOpen;
      if (window.handleMobileMenu) {
        window.handleMobileMenu(this.isMobileMenuOpen);
      }
    },
    async setUserFromToken() {
      const token = window.icp && window.icp.state.token ? window.icp.state.token : localStorage.getItem("token");
      if (!token) return;
      try {
        const response = await axios.get(window.icp.apiUrl('/api/auth/me'));
        const me = response.data || {};
        this.userName = me.name || 'Guest';
        this.userEmail = me.email || '';
        this.isAdmin = (me.role === 'admin' || me.role === 'super_admin');
      } catch (_) {
        try {
          const base64Url = token.split('.')[1];
          const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
          const payload = JSON.parse(atob(base64));
          this.userName = payload.name || 'Guest';
          this.userEmail = payload.email || '';
          this.isAdmin = (payload.role === 'admin' || payload.role === 'super_admin');
        } catch (e) {}
      }
    },
    formatTime(seconds) {
      if (isNaN(seconds) || seconds === null || seconds === undefined) return '0:00';
      const totalSeconds = Math.max(0, Math.floor(seconds));
      const m = Math.floor(totalSeconds / 60);
      const s = totalSeconds % 60;
      return `${m}:${s.toString().padStart(2, '0')}`;
    },
    
    startTimer() {
      if (this.timerId) return;
      const token = window.icp && window.icp.state ? window.icp.state.token : localStorage.getItem("token");
      if (!token) return;

      const decode = (t) => {
        try {
          const base64Url = t.split('.')[1];
          const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
          return JSON.parse(atob(base64));
        } catch (e) { return null; }
      };

      const payload = decode(token);
      if (!payload || !payload.exp) return;
      
      const exp = payload.exp;
      localStorage.setItem('session_expiry_user', exp);
      
      const updateTimer = () => {
        if (this._isUnmounted) {
          if (this.timerId) {
            clearInterval(this.timerId);
            this.timerId = null;
          }
          return;
        }
        const now = Math.floor(Date.now() / 1000);
        const newSessionTime = Math.max(0, exp - now);
        
        if (this.sessionTime !== newSessionTime) {
          this.sessionTime = newSessionTime;
        }
        
        if (this.sessionTime <= 0) {
          if (this.timerId) {
            clearInterval(this.timerId);
            this.timerId = null;
          }
          localStorage.removeItem('session_expiry_user');
          Swal.fire({
            icon: 'warning',
            title: 'Session Expired',
            text: 'Your session has expired. Please login again to continue.',
            confirmButtonText: 'Login Again',
            confirmButtonColor: '#8b5cf6',
            allowOutsideClick: false
          }).then(() => {
            if (window.icp) window.icp.logout();
            else { 
              localStorage.clear(); 
              window.location.href = "/static/pages/login.html"; 
            }
          });
        }
      };
      
      updateTimer(); // Run immediately
      this.timerId = setInterval(updateTimer, 1000);
    },

  checkAdmin() {},

    async clearBrowserCache() {
      const result = await Swal.fire({
        title: 'Clear Cache & Restart?',
        text: 'This will wipe saved session data and reload the application to fix persistent issues.',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d33',
        cancelButtonColor: '#3085d6',
        confirmButtonText: 'Yes, clear it!'
      });

      if (result.isConfirmed) {
        // Clear all storage
        localStorage.clear();
        sessionStorage.clear();
        
        // Unregister service workers
        if ('serviceWorker' in navigator) {
          try {
            const registrations = await navigator.serviceWorker.getRegistrations();
            for (let registration of registrations) {
              await registration.unregister();
            }
          } catch (e) {
            console.error('SW unregistration failed:', e);
          }
        }
        
        // Force reload without cache if possible
        window.location.href = '/static/pages/login.html?reset=' + new Date().getTime();
      }
    },

    async initDashboard() {
      try {
        this.isLoading = true;
        const autoloadDisabled = localStorage.getItem('resume_autoload_disabled') === 'true';
        if (autoloadDisabled) {
          try {
            localStorage.removeItem('resume_feedback');
            localStorage.removeItem('resume_filename');
            localStorage.removeItem('resume_score');
            localStorage.removeItem('target_job_title');
            localStorage.removeItem('target_location');
          } catch (_) {}
          this.feedback = null;
          this.hasAnalyzed = false;
          this.persistedFileName = '';
          this.targetJobTitle = '';
        }
        // Load from local storage first
        const stored = localStorage.getItem('resume_feedback');
        if (stored && stored !== 'null' && stored !== 'undefined') {
          this.feedback = JSON.parse(stored);
          this.hasAnalyzed = true;
        }
        this.persistedFileName = localStorage.getItem('resume_filename') || '';
        this.isSubmitted = localStorage.getItem('resume_submitted') === 'true';
        
        // If no local feedback but logged in, fetch from server
        if (!autoloadDisabled && !this.feedback && this.logged) {
          try {
            const r = await axios.get('/api/resume/my');
            const items = r.data || [];
            if (items && items.length > 0) {
              const latest = items.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))[0];
              if (latest && latest.feedback) {
                this.feedback = latest.feedback;
                this.hasAnalyzed = true;
                
                localStorage.setItem('resume_feedback', JSON.stringify(latest.feedback));
                localStorage.setItem('resume_filename', latest.filename || '');
                if (latest.feedback && typeof latest.feedback.Score !== 'undefined') {
                  localStorage.setItem('resume_score', String(latest.feedback.Score));
                } else {
                  localStorage.removeItem('resume_score');
                }
                this.persistedFileName = latest.filename || '';
              }
            }
          } catch (e) {
            console.error('Error fetching resume history:', e);
          }
        }
      } catch (e) {
        console.error('Error in initDashboard:', e);
      } finally {
        await new Promise(r => setTimeout(r, 300));
        this.isLoading = false;
      }

      await Promise.allSettled([
        (async () => {
          try {
            const r = await axios.get('/api/interview/history');
            if (r.status === 200) {
              const j = r.data;
              this.hasHistory = Array.isArray(j) && j.length > 0;
            }
          } catch (e) {}
        })(),
        (async () => {
          try {
            const r = await axios.get('/api/resume/limits');
            if (r.status === 200) {
              const j = r.data;
              this.resumeAttempts = j.remaining;
              this.maxResumeAttempts = j.limit;
            }
          } catch (e) {}
        })()
      ]);
    },

    handleFileChange(event) {
      const file = event.target.files[0];
      this.fileName = file ? file.name : '';
      this.selectedFile = file || null;
    },
    
    clearFile() {
      this.fileName = '';
      this.persistedFileName = '';
      this.selectedFile = null;
      if (this.$refs.fileInput) {
        this.$refs.fileInput.value = '';
      }
    },

    saveJobTitle(value) {
      this.targetJobTitle = value;
      localStorage.setItem('target_job_title', value);
    },

    toggleInfoTooltip() {
      this.showInfoTooltip = !this.showInfoTooltip;
    },

    promptResumeFields() {
      if (!this.targetJobTitle || (!this.fileName && !this.persistedFileName)) {
        let missing = [];
        if (!this.targetJobTitle) missing.push("Target Job Title");
        if (!this.fileName && !this.persistedFileName) missing.push("Resume File");
        
        Swal.fire({
          icon: 'info',
          title: 'Missing Information',
          text: `Please provide the following to continue: ${missing.join(' and ')}.`,
          confirmButtonColor: '#8b5cf6'
        });
      }
    },

    promptManualFields() {
      const data = this.manualData;
      if (!data.jobTitle || !data.experience || !data.summary || !data.skills || !data.achievement) {
        Swal.fire({
          icon: 'info',
          title: 'Incomplete Profile',
          text: 'Please fill in all the fields in the Guided Profile Builder to generate your analysis.',
          confirmButtonColor: '#8b5cf6'
        });
      }
    },

    async submitApplication() {
      const jt = this.targetJobTitle.trim();

      if (window.strictGuard && window.strictGuard.isGibberish(jt)) {
        Swal.fire({
          icon: 'warning',
          iconHtml: 'i',
          title: 'Invalid Job Title',
          text: 'The job title you entered appears to be invalid or gibberish. Please provide a real job title before saving your profile.',
          confirmButtonColor: '#8b5cf6'
        });
        return;
      }
      
      const { value: confirmed } = await Swal.fire({
        title: 'Save Profile for Review?',
        html: `
          <div class="text-start small" style="color: #475569; font-weight: 500;">
            <p>By saving your profile, you agree to our <strong>Data Consent Policy</strong>:</p>
            <ul class="mb-3" style="list-style-type: disc; padding-left: 1.25rem; color: #64748b;">
              <li>Your resume file and job title will be securely stored in our system.</li>
              <li>We will use this data to provide accurate analysis and improve future mock interview questions.</li>
              <li>Your information will only be accessible to authorized administrators for professional review.</li>
            </ul>
            <p class="mb-0">Do you wish to proceed and save your profile for review?</p>
          </div>
        `,
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: 'Yes, I Consent',
        cancelButtonText: 'Not Now',
        confirmButtonColor: '#8b5cf6',
        cancelButtonColor: '#475569'
      });

      if (!confirmed) return;

      const file = this.selectedFile || (this.$refs.fileInput ? this.$refs.fileInput.files[0] : null);
      
      if (!file) {
        Swal.fire({
          icon: 'error',
          title: 'File Not Found',
          text: 'Please re-upload your resume file to save your profile for review.',
          confirmButtonColor: '#8b5cf6'
        });
        return;
      }

      Swal.fire({
        title: 'Saving Profile...',
        text: 'Your data is being securely stored.',
        allowOutsideClick: false,
        didOpen: () => { Swal.showLoading() }
      });

      const fd = new FormData();
      fd.append('file', file);
      fd.append('job_title', jt);
      fd.append('consent', 'true');
      fd.append('skip_analysis', 'true');
      if (this.feedback) {
        fd.append('existing_feedback', JSON.stringify(this.feedback));
      }

      try {
        await axios.post('/api/resume/upload', fd, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
        
        this.isSubmitted = true;
        localStorage.setItem('resume_submitted', 'true');
        
        Swal.fire({
          title: 'Profile Saved!',
          text: 'Your resume has been successfully saved for review.',
          icon: 'success',
          timer: 2000,
          showConfirmButton: false
        });
      } catch (e) {
        console.error('Submission error:', e);
        Swal.fire({
          title: 'Error',
          text: e.response?.data?.detail || 'Failed to save profile',
          icon: 'error',
          confirmButtonColor: '#8b5cf6'
        });
      }
    },

    autoExpand(event) {
      const element = event.target;
      element.style.height = 'auto';
      element.style.height = element.scrollHeight + 'px';
    },

    startAnalysisProgress(isManual = false) {
      this.showAnalysisProgress = true;
      this.analysisProgress = 0;
      this.analysisStatus = isManual ? 'Initializing profile builder...' : 'Uploading resume...';

      const stages = isManual ? [
        { threshold: 5,  status: 'Initializing profile builder...' },
        { threshold: 12, status: 'Extracting profile data...' },
        { threshold: 20, status: 'Scanning profile for completeness...' },
        { threshold: 25, status: 'Retrieving career knowledge base...' },
        { threshold: 30, status: 'AI is reviewing your profile...' },
        { threshold: 40, status: 'Analysing target role requirements...' },
        { threshold: 50, status: 'Evaluating your technical skills...' },
        { threshold: 58, status: 'Assessing experience and achievements...' },
        { threshold: 66, status: 'Identifying strengths and weaknesses...' },
        { threshold: 74, status: 'Generating improvement suggestions...' },
        { threshold: 82, status: 'Personalising career coaching advice...' },
        { threshold: 88, status: 'Cross-referencing industry standards...' },
        { threshold: 94, status: 'Finalising analysis...' },
      ] : [
        { threshold: 5,  status: 'Uploading resume...' },
        { threshold: 12, status: 'Extracting resume content...' },
        { threshold: 20, status: 'Scanning document for ATS compatibility...' },
        { threshold: 25, status: 'Retrieving career knowledge base...' },
        { threshold: 30, status: 'AI is reviewing your profile...' },
        { threshold: 40, status: 'Analysing target role requirements...' },
        { threshold: 50, status: 'Evaluating your technical skills...' },
        { threshold: 58, status: 'Assessing work experience and projects...' },
        { threshold: 66, status: 'Reviewing academic background...' },
        { threshold: 74, status: 'Identifying strengths and weaknesses...' },
        { threshold: 82, status: 'Generating improvement suggestions...' },
        { threshold: 88, status: 'Personalising career coaching advice...' },
        { threshold: 94, status: 'Cross-referencing industry standards...' },
      ];

      const holdingMessages = [
        'Almost there...',
        'Polishing your feedback...',
        'Organising results...',
        'Wrapping up the analysis...',
      ];

      // Speed zones (single 200ms interval, probabilistic skipping):
      //   0–12%  : no skip   → ~200ms/step  (fast — real upload/extraction)
      //  12–30%  : ~33% skip → ~300ms/step  (medium — OCR + RAG + prompt build)
      //  30–94%  : ~55% skip → ~450ms/step  (slow crawl — Mistral thinking)
      let currentStage = 0;
      let holdingIndex = 0;

      this.progressInterval = setInterval(() => {
        if (this.analysisProgress < 95) {
          const p = this.analysisProgress;
          const skip =
            p >= 30 ? (Math.random() > 0.45) :   // ~55% skip → ~450ms/step
            p >= 12 ? (Math.random() > 0.67) :    // ~33% skip → ~300ms/step
                       false;                      // no skip   → ~200ms/step
          if (skip) return;

          this.analysisProgress = Math.min(94, this.analysisProgress + 1);

          while (
            currentStage < stages.length &&
            this.analysisProgress >= stages[currentStage].threshold
          ) {
            this.analysisStatus = stages[currentStage].status;
            currentStage++;
          }
        } else {
          // ── Soft wait zones ──────────────────────────────────────────────
          // If backend is not done yet, we use two soft checkpoints:
          //   95% → hold for ~4s, then slowly creep to 97%
          //   97% → hold for ~4s, then stay there until backend returns
          // Each step in the creep zone has a high skip rate to move slowly.

          const p = this.analysisProgress;

          if (p < 97) {
            // Creep slowly from 95 → 97 (~8s for 2 steps, ~4s each)
            if (Math.random() > 0.98) {   // ~2% chance per 200ms tick → ~10s per step
              this.analysisProgress += 1;
              if (this.analysisProgress === 96) {
                this.analysisStatus = 'Almost there...';
              } else if (this.analysisProgress === 97) {
                this.analysisStatus = 'Polishing your feedback...';
              }
            }
          } else {
            // Stuck at 97 — rotate messages softly, wait for backend
            if (Math.random() > 0.96) {
              this.analysisStatus = holdingMessages[holdingIndex % holdingMessages.length];
              holdingIndex++;
            }
          }
        }
      }, 200);
    },

    stopAnalysisProgress(success = true) {
      // Stop the holding loop — backend has returned
      if (this.progressInterval) {
        clearInterval(this.progressInterval);
        this.progressInterval = null;
      }

      if (success) {
        return new Promise(resolve => {
          // Set the completion message regardless of where the bar is
          this.analysisStatus = 'Generating your feedback report...';

          // Animate from current position to 100% at a natural human pace (~200ms/step)
          // This ensures the bar never jumps — it always finishes smoothly even if
          // the backend returned early while the bar was only at 40%.
          const finalInterval = setInterval(() => {
            if (this.analysisProgress < 100) {
              this.analysisProgress += 1;

              if (this.analysisProgress >= 99) {
                this.analysisStatus = 'Analysis complete';
              } else if (this.analysisProgress === 97) {
                this.analysisStatus = 'Preparing your career insights...';
              } else if (this.analysisProgress <= 96) {
                this.analysisStatus = 'Generating your feedback report...';
              }
            } else {
              clearInterval(finalInterval);
              setTimeout(() => {
                this.showAnalysisProgress = false;
                resolve();
              }, 600);
            }
          }, 200);
        });
      } else {
        this.showAnalysisProgress = false;
        return Promise.resolve();
      }
    },

    async uploadResume() {
      if (this.resumeAttempts <= 0) {
        Swal.fire({
          title: 'Limit Reached',
          text: 'You have no analysis attempts remaining today.',
          icon: 'warning',
          confirmButtonColor: '#8b5cf6'
        });
        return;
      }

      const jt = this.targetJobTitle.trim();
      if (!jt) {
        Swal.fire({
          title: 'Error',
          text: 'Please enter a target job title',
          icon: 'error',
          confirmButtonColor: '#8b5cf6'
        });
        return;
      }

      if (window.strictGuard && window.strictGuard.isGibberish(jt)) {
        Swal.fire({
          icon: 'warning',
          iconHtml: 'i',
          title: 'Invalid Job Title',
          text: 'The job title you entered appears to be invalid or gibberish. Please provide a real job title (e.g., "Software Engineer") to get an accurate analysis.',
          confirmButtonColor: '#8b5cf6'
        });
        return;
      }
      
      const fileInput = this.$refs.fileInput;
      const file = this.selectedFile || (fileInput ? fileInput.files[0] : null);
      
      if (!file) {
        if (this.persistedFileName) {
          Swal.fire({
            icon: 'info',
            title: 'Re-upload Required',
            text: 'To analyze your profile for a new role or to re-run the analysis, please re-upload your resume file.',
            confirmButtonColor: '#8b5cf6'
          });
        } else {
          Swal.fire({
            title: 'Error',
            text: 'Please select a resume file',
            icon: 'error',
            confirmButtonColor: '#8b5cf6'
          });
        }
        return;
      }

      // Validation
      const allowedExtensions = ['pdf', 'doc', 'docx'];
      const fileExtension = file.name.split('.').pop().toLowerCase();
      const maxSizeInBytes = 5 * 1024 * 1024; // 5MB

      if (!allowedExtensions.includes(fileExtension)) {
        Swal.fire({
          title: 'Invalid Format',
          text: 'Only PDF, DOC, and DOCX files are acceptable.',
          icon: 'warning',
          confirmButtonColor: '#8b5cf6'
        });
        return;
      }

      if (file.size > maxSizeInBytes) {
        Swal.fire({
          title: 'File Too Large',
          text: 'Resume file size must not exceed 5MB.',
          icon: 'warning',
          confirmButtonColor: '#8b5cf6'
        });
        return;
      }

      this.uploading = true;
      this.startAnalysisProgress(false);

      const fd = new FormData();
      fd.append('file', file);
      fd.append('job_title', jt);
      fd.append('consent', this.consent);

      try {
        this.isSubmitted = false;
        localStorage.removeItem('resume_submitted');
        const r = await axios.post('/api/resume/upload', fd, {
          headers: {
            'Content-Type': 'multipart/form-data'
          }
        });
        
        const res = r.data;
        
        // Wait for progress bar to hit 100% and overlay to hide
        await this.stopAnalysisProgress(true);
        this.uploading = false;
        
        // Handle Rejection (Not a resume)
        if (res && res.feedback && res.feedback.IsResume === false) {
            Swal.fire({
                icon: 'error',
                title: 'Invalid Document',
                text: res.feedback.Disadvantages?.[0] || 'The uploaded file does not appear to be a valid professional resume. Please upload a real resume to get an analysis.',
                confirmButtonColor: '#8b5cf6'
            });
            // Do not show the feedback section if rejected
            this.hasAnalyzed = false;
            this.feedback = null;
            return;
        }

        this.persistedFileName = file.name;
        this.selectedFile = file; // Ensure selectedFile is preserved for subsequent Save Profile for Review
        localStorage.setItem('resume_filename', this.persistedFileName);
        this.fileName = '';
        if (fileInput) fileInput.value = '';

        if (res && res.feedback) {
          // Clean feedback lists of any "rejection" or "safety" messages
          const cleanList = (list) => (list || []).filter(item => 
            !/safety|rejected|rejection|guardrail|check failed|invalid document/i.test(item)
          );
          
          res.feedback.Advantages = cleanList(res.feedback.Advantages);
          res.feedback.Disadvantages = cleanList(res.feedback.Disadvantages);
          res.feedback.Suggestions = cleanList(res.feedback.Suggestions);

          this.feedback = res.feedback;
          this.hasAnalyzed = true;
          localStorage.setItem('resume_feedback', JSON.stringify(res.feedback));
          localStorage.setItem('session_has_analyzed', 'true');

          const finalTitle = res.job_title || jt;
          this.targetJobTitle = finalTitle;
          localStorage.setItem('target_job_title', finalTitle);

          if (res.feedback.Location) {
            localStorage.setItem('target_location', res.feedback.Location);
          }
          try { localStorage.removeItem('resume_autoload_disabled'); } catch (_) {}
          this.resumeAttempts = Math.max(0, this.resumeAttempts - 1);

          Swal.fire({
            icon: 'success',
            title: 'Analysis Complete',
            text: 'Your profile has been successfully analyzed!',
            timer: 2000,
            showConfirmButton: false
          });
        } else {
          throw new Error('Invalid response from server');
        }
      } catch (err) {
        await this.stopAnalysisProgress(false);
        this.uploading = false;
        const errorMsg = (err.response && err.response.data && err.response.data.detail) || err.message || 'Failed to analyze resume';
        const status = err.response ? err.response.status : 0;

        if (status === 429 || errorMsg === 'AI_RATE_LIMIT') {
          Swal.fire({
            title: 'AI is Busy',
            html: `
              <div class="text-center">
                <p class="mb-3">Our AI systems are currently handling high traffic.</p>
                <p class="small" style="color: #475569; font-weight: 500;">Please wait about 30-60 seconds before retrying your upload. Thank you for your patience!</p>
              </div>
            `,
            icon: 'info',
            confirmButtonText: 'Understood',
            confirmButtonColor: '#8b5cf6'
          });
          return;
        }
        
        if (errorMsg.includes("image-based PDF") || errorMsg.includes("scanned document")) {
          Swal.fire({
            title: 'Extraction Failed',
            html: `
              <div class="text-start">
                <p class="mb-3">${errorMsg}</p>
                <p class="small mb-3" style="color: #475569; font-weight: 500;">Don't worry! You can still use our <strong>Guided Profile Builder</strong> to manually enter your details and get the same quality analysis.</p>
              </div>
            `,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: 'Use Manual Builder',
            cancelButtonText: 'Try Another File',
            confirmButtonColor: '#8b5cf6',
          }).then((result) => {
            if (result.isConfirmed) {
              this.openManualBuilder();
            }
          });
        } else {
          Swal.fire({
            title: 'Error',
            text: errorMsg,
            icon: 'error',
            confirmButtonColor: '#8b5cf6'
          });
        }
        console.error('Upload error:', err);
      }
    },

    openManualBuilder() {
      const modalEl = document.getElementById('manualBuilderModal');
      if (!modalEl) return;

      // Pre-fill from existing AI analysis if available
      const feedbackStr = localStorage.getItem('resume_feedback');
      if (feedbackStr) {
        try {
          const fb = JSON.parse(feedbackStr);

          // Job title: use stored target first, fallback to AI detected
          if (!this.manualData.jobTitle) {
            this.manualData.jobTitle = localStorage.getItem('target_job_title') || fb.DetectedJobTitle || '';
          }

          // Experience: derive from first Experience entry date range, or leave blank
          if (!this.manualData.experience && fb.Experience && fb.Experience.length > 0) {
            const firstExp = fb.Experience[0];
            this.manualData.experience = firstExp.Date || firstExp.date || '';
          }

          // Professional summary
          if (!this.manualData.summary) {
            this.manualData.summary = fb.ProfessionalSummary || fb.Summary || '';
          }

          // Skills: join tech + tools + soft skills into a comma list
          if (!this.manualData.skills) {
            const skillParts = [
              fb.SkillsTech || '',
              fb.SkillsTools || '',
              fb.SkillsSoft || ''
            ].filter(Boolean).join(', ');
            // Deduplicate and trim to 300 chars
            const uniqueSkills = [...new Set(
              skillParts.split(/[,\n]/).map(s => s.trim()).filter(s => s)
            )].join(', ');
            this.manualData.skills = uniqueSkills.slice(0, 300);
          }

          // Achievement: use first experience bullet as the key achievement
          if (!this.manualData.achievement) {
            if (fb.Experience && fb.Experience.length > 0) {
              const bullets = fb.Experience[0].Bullets || [];
              this.manualData.achievement = bullets.length > 0 ? bullets[0] : '';
            }
          }
        } catch (e) {
          // silently ignore parse errors — fields stay blank
        }
      }

      try {
        let modal = bootstrap.Modal.getInstance(modalEl);
        if (!modal) {
          modal = new bootstrap.Modal(modalEl);
        }
        modal.show();
      } catch (e) {
        console.error("Error showing modal:", e);
      }
    },

    async assistManualField(field) {
      // Char limits matching the HTML maxlength values
      const charLimits = { summary: 500, skills: 300, achievement: 500 };
      const currentText = this.manualData[field];

      if (!currentText || !currentText.trim()) {
        Swal.fire({
          icon: 'info',
          title: 'Nothing to enhance yet',
          text: 'Please type something in the field first before using AI assist.',
          confirmButtonColor: '#8b5cf6',
          timer: 3000,
          showConfirmButton: false,
        });
        return;
      }

      this.assistLoading[field] = true;
      try {
        const token = localStorage.getItem('token');
        const apiUrl = window.icp ? window.icp.apiUrl('/api/assist/manual-field') : '/api/assist/manual-field';
        const response = await axios.post(
          apiUrl,
          {
            field,
            text: currentText.trim(),
            job_title: this.manualData.jobTitle || '',
            char_limit: charLimits[field],
          },
          { headers: { Authorization: `Bearer ${token}` } }
        );
        const improved = this._stripMarkdown(response.data?.result || '');
        if (improved) {
          this.manualData[field] = improved;
        }
      } catch (err) {
        const msg = err.response?.data?.detail || 'AI assist failed. Please try again.';
        Swal.fire({ icon: 'error', title: 'Assist Failed', text: msg, confirmButtonColor: '#8b5cf6' });
      } finally {
        this.assistLoading[field] = false;
      }
    },

    /** Strip all markdown formatting and wrapping quotes from a string (client-side safety net) */
    _stripMarkdown(text) {
      if (!text) return '';
      text = text.replace(/\*{1,3}([^*\n]+)\*{1,3}/g, '$1');
      text = text.replace(/_{1,3}([^_\n]+)_{1,3}/g, '$1');
      text = text.replace(/(?<!\w)\*+(?!\w)/g, '');
      text = text.trim();
      // Strip wrapping quotes the model sometimes adds
      if ((text.startsWith('"') && text.endsWith('"')) ||
          (text.startsWith("'") && text.endsWith("'"))) {
        text = text.slice(1, -1).trim();
      }
      return text;
    },

    async submitManualProfile() {
      if (this.resumeAttempts <= 0) {
        Swal.fire({
          title: 'Limit Reached',
          text: 'You have no analysis attempts remaining today.',
          icon: 'warning',
          confirmButtonColor: '#8b5cf6'
        });
        return;
      }

      // Gibberish checks for all fields
      const fields = [
        { key: 'jobTitle', label: 'Job Title' },
        { key: 'experience', label: 'Experience' },
        { key: 'summary', label: 'Professional Summary' },
        { key: 'skills', label: 'Top Skills' },
        { key: 'achievement', label: 'Key Achievement' }
      ];

      const gibberishFields = fields.filter(f => {
        if (window.strictGuard) return window.strictGuard.isGibberish(this.manualData[f.key]);
        return window.icp.isGibberish(this.manualData[f.key]);
      });

      if (gibberishFields.length > 0) {
        const labels = gibberishFields.map(f => f.label);
        let message = '';
        if (labels.length === 1) {
          message = `The ${labels[0]} you entered appears to be invalid or gibberish.`;
        } else {
          message = `The following fields appear to have invalid or gibberish text: ${labels.join(', ')}.`;
        }

        Swal.fire({
          icon: 'warning',
          iconHtml: 'i',
          title: 'Invalid Input Detected',
          html: `
            <div class="text-center">
              <p class="mb-3">${message}</p>
              <p class="small" style="color: #475569; font-weight: 500;">Please provide real, professional information to ensure our AI Coach can help you effectively.</p>
            </div>
          `,
          confirmButtonColor: '#8b5cf6'
        });
        return;
      }

      const { value: confirmedConsent } = await Swal.fire({
        title: 'Save Profile for Review?',
        html: `
          <div class="text-start small" style="color: #475569; font-weight: 500;">
            <p>By generating this profile, you agree to our <strong>Data Consent Policy</strong>:</p>
            <ul class="mb-3" style="list-style-type: disc; padding-left: 1.25rem; color: #64748b;">
              <li>Your profile details will be securely stored in our system.</li>
              <li>We will use this data to provide accurate analysis and improve future mock interview questions.</li>
              <li>Your information will only be accessible to authorized administrators for professional review.</li>
            </ul>
            <p class="mb-0">Do you wish to proceed and save your profile for review?</p>
          </div>
        `,
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: 'Yes, I Consent',
        cancelButtonText: 'Not Now',
        confirmButtonColor: '#8b5cf6',
        cancelButtonColor: '#475569'
      });

      if (!confirmedConsent) return;

      this.uploading = true;
      this.startAnalysisProgress(true);

      try {
        const response = await axios.post('/api/resume/manual-upload', {
          ...this.manualData,
          consent: true
        });
        const res = response.data;

        await this.stopAnalysisProgress(true);
        this.uploading = false;

        const modalElement = document.getElementById('manualBuilderModal');
        const modal = bootstrap.Modal.getInstance(modalElement);
        if (modal) modal.hide();

        if (res && res.feedback && res.feedback.IsResume === false) {
            Swal.fire({
                icon: 'error',
                title: 'Analysis Failed',
                text: res.feedback.Disadvantages?.[0] || 'The AI could not generate a professional profile from the provided details. Please ensure the information is realistic.',
                confirmButtonColor: '#8b5cf6'
            });
            this.hasAnalyzed = false;
            this.feedback = null;
            return;
        }

        // Clean feedback lists of any "rejection" or "safety" messages
        const cleanList = (list) => (list || []).filter(item => 
          !/safety|rejected|rejection|guardrail|check failed|invalid document/i.test(item)
        );
        
        res.feedback.Advantages = cleanList(res.feedback.Advantages);
        res.feedback.Disadvantages = cleanList(res.feedback.Disadvantages);
        res.feedback.Suggestions = cleanList(res.feedback.Suggestions);

        this.feedback = res.feedback;
        this.hasAnalyzed = true;
        this.persistedFileName = 'Guided Profile Builder';
        this.targetJobTitle = res.job_title || this.manualData.jobTitle;
        
        localStorage.setItem('resume_feedback', JSON.stringify(res.feedback));
        try { localStorage.removeItem('resume_autoload_disabled'); } catch (_) {}
        localStorage.setItem('session_has_analyzed', 'true');
        localStorage.setItem('resume_filename', 'Guided Profile Builder');
        localStorage.setItem('target_job_title', this.targetJobTitle);
        
        if (res.feedback.Location) {
          localStorage.setItem('target_location', res.feedback.Location);
        }
        
        this.resumeAttempts = Math.max(0, this.resumeAttempts - 1);

        Swal.fire({
          icon: 'success',
          title: 'Profile Created!',
          text: 'Your guided profile is ready for interviews.',
          timer: 2000,
          showConfirmButton: false
        });
        
        // Reset manual data
        this.manualData = { jobTitle: '', experience: '', summary: '', skills: '', achievement: '' };
        
      } catch (err) {
        this.stopAnalysisProgress(false);
        const status = err.response ? err.response.status : 0;
        const detail = (err.response && err.response.data && err.response.data.detail) || err.message;

        if (status === 429) {
          Swal.fire({
            title: 'AI is Busy',
            html: `
              <div class="text-center">
                <p class="mb-3">The AI Coach is currently helping many users at once.</p>
                <p class="small" style="color: #475569; font-weight: 500;">Please wait about 30-60 seconds and try again. We appreciate your patience!</p>
              </div>
            `,
            icon: 'info',
            confirmButtonColor: '#8b5cf6'
          });
        } else {
          Swal.fire({
            title: 'Error',
            text: detail,
            icon: 'error',
            confirmButtonColor: '#8b5cf6'
          });
        }
        console.error('Manual builder error:', err);
      } finally {
        this.uploading = false;
      }
    },

    exportToPDF() {
      const { jsPDF } = window.jspdf;
      const doc = new jsPDF();
      doc.setFontSize(22);
      doc.setTextColor(37, 99, 235);
      doc.text('Resume Analysis Report', 20, 20);
      doc.setFontSize(10);
      doc.setTextColor(100, 116, 139);
      const date = new Date().toLocaleDateString('en-MY', { timeZone: 'Asia/Kuala_Lumpur' });
      const job = localStorage.getItem('target_job_title') || 'Not specified';
      doc.text(`Date: ${date}`, 20, 30);
      doc.text(`Target Role: ${job}`, 20, 35);
      doc.text(`Score: ${this.feedback.Score}/100`, 20, 40);
      let yPos = 55;
      const drawSection = (title, items, color) => {
        doc.setFontSize(14);
        doc.setTextColor(color[0], color[1], color[2]);
        doc.text(title, 20, yPos);
        yPos += 8;
        doc.setFontSize(11);
        doc.setTextColor(51, 65, 85);
        items.forEach(item => {
          const lines = doc.splitTextToSize(`• ${item}`, 170);
          if (yPos + (lines.length * 7) > 280) {
            doc.addPage();
            yPos = 20;
          }
          doc.text(lines, 20, yPos);
          yPos += lines.length * 7;
        });
        yPos += 5;
      };
      if (this.feedback.Advantages && this.feedback.Advantages.length > 0) {
        drawSection('Advantages', this.feedback.Advantages, [22, 163, 74]);
      }
      if (this.feedback.Disadvantages && this.feedback.Disadvantages.length > 0) {
        drawSection('Disadvantages', this.feedback.Disadvantages, [220, 38, 38]);
      }
      if (this.feedback.Suggestions && this.feedback.Suggestions.length > 0) {
        drawSection('Suggestions', this.feedback.Suggestions, [202, 138, 4]);
      }
      
      // Add Disclaimer at the bottom
      if (yPos + 20 > 280) {
        doc.addPage();
        yPos = 20;
      } else {
        yPos += 10;
      }
      doc.setFontSize(8);
      doc.setTextColor(148, 163, 184);
      doc.text('Disclaimer: This report is generated by AI for professional guidance purposes only. Please verify critical information.', 20, yPos);

      doc.save('Resume_Analysis_Report.pdf');
    },

    logout() {
      if (window.icp) window.icp.logout();
    }
  }
});

app.mount('#app');
