const { createApp } = Vue;

const app = createApp({
  data() {
    return {
      logged: false,
      isAdmin: false,
      userName: '',
      userEmail: '',
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
      consent: false,
      showInfoTooltip: false
    };
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

    // Listen for auth changes
    window.addEventListener('auth:changed', () => {
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
    });
    
    document.addEventListener('click', (e) => {
      const wrapper = document.querySelector('.info-popover-wrapper');
      if (wrapper && !wrapper.contains(e.target)) {
        this.showInfoTooltip = false;
      }
    });
  },
  methods: {
    async setUserFromToken() {
      const token = window.icp && window.icp.state ? window.icp.state.token : localStorage.getItem("token");
      if (!token) return;
      try {
        const response = await axios.get(window.icp.apiUrl('/api/auth/me'));
        const me = response.data || {};
        this.userName = me.name || 'Guest';
        this.userEmail = me.email || '';
      } catch (_) {
        try {
          const base64Url = token.split('.')[1];
          const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
          const payload = JSON.parse(atob(base64));
          this.userName = payload.name || 'Guest';
          this.userEmail = payload.email || '';
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
        const now = Math.floor(Date.now() / 1000);
        this.sessionTime = Math.max(0, exp - now);
        
        if (this.sessionTime <= 0) {
          clearInterval(this.timerId);
          this.timerId = null;
          localStorage.removeItem('session_expiry_user');
          alert('Your session has expired. Please login again.');
          if (window.icp) window.icp.logout();
          else { localStorage.clear(); window.location.href = "/"; }
        }
      };
      
      updateTimer(); // Run immediately
      this.timerId = setInterval(updateTimer, 1000);
    },

  checkAdmin() {},

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
    },
    
    clearFile() {
      this.fileName = '';
      this.persistedFileName = '';
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

    autoExpand(event) {
      const element = event.target;
      element.style.height = 'auto';
      element.style.height = element.scrollHeight + 'px';
    },

    async uploadResume() {
      const jt = this.targetJobTitle.trim();
      if (!jt) {
        Swal.fire('Error', 'Please enter a target job title', 'error');
        return;
      }
      
      const fileInput = this.$refs.fileInput;
      const file = fileInput.files[0];
      if (!file) {
        Swal.fire('Error', 'Please select a resume file', 'error');
        return;
      }

      // Validation
      const allowedExtensions = ['pdf', 'doc', 'docx'];
      const fileExtension = file.name.split('.').pop().toLowerCase();
      const maxSizeInBytes = 5 * 1024 * 1024; // 5MB

      if (!allowedExtensions.includes(fileExtension)) {
        Swal.fire('Invalid Format', 'Only PDF, DOC, and DOCX files are acceptable.', 'warning');
        return;
      }

      if (file.size > maxSizeInBytes) {
        Swal.fire('File Too Large', 'Resume file size must not exceed 5MB.', 'warning');
        return;
      }

      Swal.fire({
        title: 'Analyzing Resume...',
        text: 'Please wait while our AI evaluates your profile for the ' + jt + ' position.',
        allowOutsideClick: false,
        didOpen: () => { Swal.showLoading() }
      });

      const fd = new FormData();
      fd.append('file', file);
      fd.append('job_title', jt);
      fd.append('consent', this.consent);

      try {
        const r = await axios.post('/api/resume/upload', fd, {
          headers: {
            'Content-Type': 'multipart/form-data'
          }
        });
        
        const res = r.data;
        Swal.close();
        
        this.persistedFileName = file.name;
        localStorage.setItem('resume_filename', this.persistedFileName);
        this.fileName = '';
        fileInput.value = '';

        if (res && res.feedback) {
          this.feedback = res.feedback;
          this.hasAnalyzed = true;
          localStorage.setItem('resume_feedback', JSON.stringify(res.feedback));

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
        Swal.close();
        const errorMsg = (err.response && err.response.data && err.response.data.detail) || err.message || 'Failed to analyze resume';
        const status = err.response ? err.response.status : 0;

        if (status === 429 || errorMsg === 'AI_RATE_LIMIT') {
          Swal.fire({
            title: 'AI is Busy',
            html: `
              <div class="text-center">
                <p class="mb-3">Our AI systems are currently handling high traffic.</p>
                <p class="small text-secondary">Please wait about 30-60 seconds before retrying your upload. Thank you for your patience!</p>
              </div>
            `,
            icon: 'info',
            confirmButtonText: 'Understood',
            confirmButtonColor: '#2563eb'
          });
          return;
        }
        
        if (errorMsg.includes("image-based PDF") || errorMsg.includes("scanned document")) {
          Swal.fire({
            title: 'Extraction Failed',
            html: `
              <div class="text-start">
                <p class="mb-3">${errorMsg}</p>
                <p class="small text-secondary mb-3">Don't worry! You can still use our <strong>Guided Profile Builder</strong> to manually enter your details and get the same quality analysis.</p>
              </div>
            `,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: 'Use Manual Builder',
            cancelButtonText: 'Try Another File',
            confirmButtonColor: '#3b82f6',
          }).then((result) => {
            if (result.isConfirmed) {
              this.openManualBuilder();
            }
          });
        } else {
          Swal.fire('Error', errorMsg, 'error');
        }
        console.error('Upload error:', err);
      }
    },

    openManualBuilder() {
      const modalEl = document.getElementById('manualBuilderModal');
      if (!modalEl) return;
      
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

    async submitManualProfile() {
      if (this.resumeAttempts <= 0) {
        Swal.fire('Limit Reached', 'You have no analysis attempts remaining today.', 'warning');
        return;
      }

      Swal.fire({
        title: 'Generating Profile...',
        text: 'Our AI Coach is analyzing your information.',
        allowOutsideClick: false,
        didOpen: () => { Swal.showLoading() }
      });

      try {
        const response = await axios.post('/api/resume/manual-upload', this.manualData);
        const res = response.data;

        Swal.close();
        const modalElement = document.getElementById('manualBuilderModal');
        const modal = bootstrap.Modal.getInstance(modalElement);
        if (modal) modal.hide();

        this.feedback = res.feedback;
        this.hasAnalyzed = true;
        this.persistedFileName = 'Guided Profile Builder';
        this.targetJobTitle = res.job_title || this.manualData.jobTitle;
        
        localStorage.setItem('resume_feedback', JSON.stringify(res.feedback));
        try { localStorage.removeItem('resume_autoload_disabled'); } catch (_) {}
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
        Swal.close();
        const status = err.response ? err.response.status : 0;
        const detail = (err.response && err.response.data && err.response.data.detail) || err.message;

        if (status === 429) {
          Swal.fire({
            title: 'AI is Busy',
            html: `
              <div class="text-center">
                <p class="mb-3">The AI Coach is currently helping many users at once.</p>
                <p class="small text-secondary">Please wait about 30-60 seconds and try again. We appreciate your patience!</p>
              </div>
            `,
            icon: 'info',
            confirmButtonText: 'Understood',
            confirmButtonColor: '#2563eb'
          });
        } else {
          Swal.fire('Error', detail || 'Failed to analyze profile', 'error');
        }
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
