function interview() {
  return {
    logged: !!icp.state.token,
    isAdmin: false,
    hasAnalyzed: false,
    sessionId: null,
    questionLimit: 10,
    difficulty: "Intermediate",
    transcript: [],
    answer: "",
    speaker: localStorage.getItem('interview_speaker_enabled') !== 'false',
    voiceGender: localStorage.getItem('interview_voice_gender') || 'female',
    mic: localStorage.getItem('interview_mic_enabled') === 'true',
    recording: false,
    thinking: false,
    speaking: false,
    recognition: null,
    hasResume: false,
    jobTitle: "",
    resumeFeedback: null,
    interviewAttempts: 0,
    maxInterviewAttempts: 3,
    readinessScore: null,
    feedbackExplanation: "",
    getScoreColorClass() {
      if (!this.readinessScore) return '';
      const score = parseInt(this.readinessScore);
      if (score >= 80) return 'score-high';
      if (score >= 50) return 'score-medium';
      return 'score-low';
    },
    sessionTime: 0,
    timerId: null,
    interviewTime: 1200, // 20 minutes default
    interviewTimerId: null,
    inactivityTimer: null,
    lastInteractionTime: Date.now(),
    useCamera: localStorage.getItem('interview_camera_enabled') === 'true',
    cameraStream: null,
    faceDetectionTimer: null,
    faceAbsentTimer: null,
    isFaceDetected: false,
    
    resetInactivityTimer() {
      this.lastInteractionTime = Date.now();
      if (this.inactivityTimer) clearTimeout(this.inactivityTimer);
      if (!this.sessionId) return;
      
      this.inactivityTimer = setTimeout(() => {
        if (this.sessionId) {
          this.pauseInterview("Inactivity Timeout", "You haven't responded for 5 minutes. The interview has been paused.");
        }
      }, 5 * 60 * 1000); // 5 minutes
    },
    
    pauseInterview(title, text) {
      this.stopInterviewTimer();
      if (this.inactivityTimer) clearTimeout(this.inactivityTimer);
      this.stopCamera();
      
      const currentSid = this.sessionId;
      this.sessionId = null; // Mark as inactive locally
      
      Swal.fire({
        icon: 'info',
        title: title,
        text: text,
        showCancelButton: true,
        confirmButtonText: 'Continue Now',
        cancelButtonText: 'Close & Resume Later',
        confirmButtonColor: '#2563eb',
        cancelButtonColor: '#64748b'
      }).then((result) => {
        if (result.isConfirmed) {
          // Resume immediately
          this.sessionId = currentSid;
          this.startInterviewTimer();
          this.resetInactivityTimer();
          if (this.useCamera) this.startCamera();
        } else {
          // Go to history
          window.location.href = '/static/pages/history.html';
        }
      });
    },
    formatTime(seconds) {
      if (isNaN(seconds) || seconds === null || seconds === undefined) return '0:00';
      const totalSeconds = Math.max(0, Math.floor(seconds));
      const m = Math.floor(totalSeconds / 60);
      const s = totalSeconds % 60;
      return `${m}:${s.toString().padStart(2, '0')}`;
    },
    checkAdmin() {
      if (!this.logged) return;
      fetch('/api/auth/me', {
        headers: { 'Authorization': 'Bearer ' + icp.state.token }
      })
        .then(r => r.json())
        .then(me => {
          this.isAdmin = me.role === 'admin' || me.role === 'super_admin';
          const localFeedback = localStorage.getItem('resume_feedback');
          const hasLocal = localFeedback && localFeedback !== 'null' && localFeedback !== 'undefined';
          this.hasAnalyzed = me.has_analyzed || hasLocal;
        })
        .catch(() => { this.isAdmin = false; });
    },
    startTimer() {
      if (this.timerId) return;
      const token = icp.state.token;
      if (!token) return;
      const payload = icp.decodeToken(token);
      if (!payload || !payload.exp) return;
      const exp = payload.exp;
      localStorage.setItem('session_expiry_user', exp);
      const now = Math.floor(Date.now() / 1000);
      this.sessionTime = Math.max(0, exp - now);
      this.timerId = setInterval(() => {
        if (this.sessionTime > 0) {
          this.sessionTime--;
        } else {
          clearInterval(this.timerId);
          this.timerId = null;
          localStorage.removeItem('session_expiry_user');
          alert('Your session has expired. Please login again.');
          icp.logout();
        }
      }, 1000);
    },
    startInterviewTimer() {
      this.stopInterviewTimer();
      
      // Calculate time based on question limit
      // 10 -> 15 min (900s), 15 -> 25 min (1500s), 20 -> 35 min (2100s)
      const limit = parseInt(this.questionLimit);
      if (limit === 10) this.interviewTime = 900;
      else if (limit === 15) this.interviewTime = 1500;
      else if (limit === 20) this.interviewTime = 2100;
      else this.interviewTime = 1200; // fallback

      this.interviewTimerId = setInterval(() => {
        if (this.interviewTime > 0) {
          this.interviewTime--;
        } else {
          this.stopInterviewTimer();
          this.pauseInterview('Time is Up', 'Your interview time has ended. The session is paused, but you can still continue.');
        }
      }, 1000);
    },
    stopInterviewTimer() {
      if (this.interviewTimerId) {
        clearInterval(this.interviewTimerId);
        this.interviewTimerId = null;
      }
    },
    async startCamera() {
      if (!this.useCamera) return;
      
      try {
        // Load face-api models if not already loaded
        if (!this.modelsLoaded) {
          const MODEL_URL = 'https://cdn.jsdelivr.net/gh/justadudewhohacks/face-api.js@master/weights';
          await Promise.all([
            faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL),
          ]);
          this.modelsLoaded = true;
        }

        const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 320, height: 240 } });
        this.cameraStream = stream;
        
        // Setup video element
        let video = document.getElementById('interviewVideo');
        if (!video) {
          // Create video element if it doesn't exist
          const container = document.createElement('div');
          container.id = 'cameraContainer';
          container.className = 'camera-preview-container';
          container.innerHTML = `
            <div class="camera-header">
              <span class="small fw-bold"><i class="bi bi-camera-video-fill me-1"></i> Live Preview</span>
              <span id="faceStatus" class="badge bg-danger">Initializing...</span>
            </div>
            <video id="interviewVideo" autoplay muted playsinline></video>
          `;
          document.body.appendChild(container);
          video = document.getElementById('interviewVideo');
        }
        video.srcObject = stream;
        
        Swal.fire({
          icon: 'info',
          title: 'Camera Active',
          text: 'Please ensure you have good lighting and your face is clearly visible for the best experience.',
          timer: 3000,
          showConfirmButton: false
        });

        this.startFaceDetection();
      } catch (err) {
        console.error("Camera error:", err);
        this.useCamera = false;
        localStorage.setItem('interview_camera_enabled', 'false');
        Swal.fire('Camera Error', 'Could not access camera or load detection models. Please check permissions.', 'error');
      }
    },
    stopCamera() {
      if (this.cameraStream) {
        this.cameraStream.getTracks().forEach(track => track.stop());
        this.cameraStream = null;
      }
      if (this.faceDetectionTimer) clearInterval(this.faceDetectionTimer);
      if (this.faceAbsentTimer) clearTimeout(this.faceAbsentTimer);
      
      const container = document.getElementById('cameraContainer');
      if (container) container.remove();
    },
    async startFaceDetection() {
      if (this.faceDetectionTimer) clearInterval(this.faceDetectionTimer);
      
      const video = document.getElementById('interviewVideo');
      const statusBadge = document.getElementById('faceStatus');
      
      this.faceDetectionTimer = setInterval(async () => {
        if (!this.sessionId || !video || video.paused || video.ended) return;
        
        try {
          // Use tiny face detector for performance
          const detections = await faceapi.detectSingleFace(video, new faceapi.TinyFaceDetectorOptions());
          
          if (detections) {
            this.isFaceDetected = true;
            if (statusBadge) {
              statusBadge.className = 'badge bg-success';
              statusBadge.innerText = 'Face Detected';
            }
            if (this.faceAbsentTimer) {
              clearTimeout(this.faceAbsentTimer);
              this.faceAbsentTimer = null;
            }
          } else {
            this.isFaceDetected = false;
            if (statusBadge) {
              statusBadge.className = 'badge bg-danger';
              statusBadge.innerText = 'Face Not Detected';
            }
            
            if (!this.faceAbsentTimer) {
              this.faceAbsentTimer = setTimeout(() => {
                if (this.sessionId && !this.isFaceDetected) {
                  // 15 seconds passed
                  if (window.Toaster) window.Toaster.postMessage('Presence check: Are you still there?');
                  
                  // Show a small non-blocking toast first
                  const Toast = Swal.mixin({
                    toast: true,
                    position: 'top-end',
                    showConfirmButton: false,
                    timer: 15000,
                    timerProgressBar: true
                  });
                  
                  Toast.fire({
                    icon: 'warning',
                    title: 'Are you still there?',
                    text: 'Face not detected for 15 seconds.'
                  });

                  // Set 30s timeout for full pause
                  setTimeout(() => {
                    if (this.sessionId && !this.isFaceDetected) {
                      this.pauseInterview('Presence Timeout', 'You were away for too long. The interview has been paused.');
                    }
                  }, 15000); // 15s + 15s = 30s
                }
              }, 15000);
            }
          }
        } catch (e) {
          console.error("Face detection error:", e);
        }
      }, 1000); // Check every second for better responsiveness
    },
    init() {
      this.startTimer();
      this.checkAdmin();

      // Request permissions from Flutter if running in mobile app
      if (window.PermissionHandler) {
        if (this.useCamera) window.PermissionHandler.postMessage('camera');
        if (this.mic) window.PermissionHandler.postMessage('microphone');
      }

      // Watchers for permissions
      this.$watch('useCamera', (val) => {
        if (val && window.PermissionHandler) {
          window.PermissionHandler.postMessage('camera');
        }
      });
      this.$watch('mic', (val) => {
        if (val && window.PermissionHandler) {
          window.PermissionHandler.postMessage('microphone');
        }
      });

      // Pre-load voices for TTS and warm up the engine
      if ('speechSynthesis' in window) {
        // Some mobile browsers need a small utterance to "unlock" the audio context
        const warmUp = new SpeechSynthesisUtterance("");
        warmUp.volume = 0;
        window.speechSynthesis.speak(warmUp);

        window.speechSynthesis.getVoices();
        if (window.speechSynthesis.onvoiceschanged !== undefined) {
          window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
        }
      }

      // Watch transcript for changes and scroll to bottom
      this.$watch('transcript', () => {
        this.$nextTick(() => {
          const box = this.$refs.transcriptBox;
          if (box) {
            box.scrollTo({
              top: box.scrollHeight,
              behavior: 'smooth'
            });
          }
        });
      });

      // Fetch limits
      try {
        fetch('/api/interview/limits', {
          headers: { 'Authorization': 'Bearer ' + icp.state.token }
        })
          .then(r => {
            if (r.status === 200) return r.json();
            return null;
          })
          .then(j => {
            if (j) {
              this.interviewAttempts = j.remaining;
              this.maxInterviewAttempts = j.limit;
            }
          })
          .catch(() => { });
      } catch (e) { }

      const feedback = localStorage.getItem("resume_feedback");
      const title = localStorage.getItem("target_job_title");
      if (feedback && title) {
        try {
          this.resumeFeedback = JSON.parse(feedback);
          this.jobTitle = title;
          this.hasResume = true;
          this.hasAnalyzed = true;
        } catch (e) {
          console.error("Error parsing resume feedback", e);
        }
      } else {
        // If not in local storage, try to fetch the latest from backend
        fetch('/api/resume/my', {
          headers: { 'Authorization': 'Bearer ' + icp.state.token }
        })
        .then(r => r.ok ? r.json() : [])
        .then(items => {
          if (items && items.length > 0) {
            // Sort by created_at desc and take the first
            const latest = items.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))[0];
            if (latest && latest.feedback) {
              this.resumeFeedback = latest.feedback;
                      this.jobTitle = latest.job_title;
                      this.hasResume = true;
                      this.hasAnalyzed = true;
                      localStorage.setItem('resume_feedback', JSON.stringify(latest.feedback));
              localStorage.setItem('target_job_title', latest.job_title);
            }
          }
        })
        .catch(() => {});
      }
    },
    get iconClass() { if (this.thinking) return 'icon thinking'; if (this.speaking) return 'icon speaking'; return 'icon idle'; },
    get transcriptHtml() {
      return this.transcript.map(t => `<div><strong>${t.role === 'assistant' ? 'Interviewer' : 'You'}:</strong> ${t.text}</div>`).join('');
    },
    tts(text) {
      if (!this.speaker) return;

      // Try native Flutter TTS first if available
      if (window.TTSHandler) {
        window.TTSHandler.postMessage(JSON.stringify({
          text: text,
          gender: this.voiceGender
        }));
        return;
      }

      if (!('speechSynthesis' in window)) {
        console.error('Speech Synthesis not supported in this browser.');
        return;
      }
      
      // Log for debugging in WebView
      if (window.Toaster) {
        window.Toaster.postMessage('Speaking: ' + text.substring(0, 30) + '...');
      }
      
      // Ensure voices are loaded
      let voices = window.speechSynthesis.getVoices();
      if (voices.length === 0) {
        window.speechSynthesis.getVoices();
        voices = window.speechSynthesis.getVoices();
      }
      
      if (window.Toaster) {
        window.Toaster.postMessage('Available voices: ' + voices.length);
        if (voices.length > 0) {
          window.Toaster.postMessage('First voice: ' + voices[0].name);
        }
      }
      
      // Cancel any ongoing speech
      window.speechSynthesis.cancel();

      const u = new SpeechSynthesisUtterance(text);
      u.lang = 'en-US'; // Default lang
      
      // Priority for smoother male voices
      let selectedVoice = null;

      if (voices.length > 0) {
        if (this.voiceGender === 'male') {
          selectedVoice = voices.find(v => v.lang.startsWith('en') && (
            v.name.toLowerCase().includes('natural') && v.name.toLowerCase().includes('male') ||
            v.name.toLowerCase().includes('guy') || 
            v.name.toLowerCase().includes('google uk english male') ||
            v.name.toLowerCase().includes('microsoft james') ||
            v.name.toLowerCase().includes('david')
          )) || voices.find(v => v.name.toLowerCase().includes('male') && v.lang.startsWith('en'));
        } else {
          selectedVoice = voices.find(v => v.lang.startsWith('en') && (
            v.name.toLowerCase().includes('natural') && v.name.toLowerCase().includes('female') ||
            v.name.toLowerCase().includes('aria') ||
            v.name.toLowerCase().includes('google uk english female') ||
            v.name.toLowerCase().includes('microsoft zira') ||
            v.name.toLowerCase().includes('samantha')
          )) || voices.find(v => v.name.toLowerCase().includes('female') && v.lang.startsWith('en'));
        }

        // If no gender-specific voice found, pick any English voice
        if (!selectedVoice) {
          selectedVoice = voices.find(v => v.lang.startsWith('en'));
        }

        if (selectedVoice) {
          u.voice = selectedVoice;
          u.lang = selectedVoice.lang;
        }
      }

      u.rate = 0.95;
      u.pitch = 1.0;
      u.volume = 1.0;

      u.onstart = () => { 
        this.speaking = true;
      };
      u.onend = () => { 
        this.speaking = false;
      };
      u.onerror = (e) => { 
        console.error('Speech error:', e);
        this.speaking = false;
        if (window.Toaster) {
          window.Toaster.postMessage('Speech error: ' + e.error);
        }
      };
      
      window.speechSynthesis.speak(u);
    },
    extractFeedback(text) {
      // Regular expression to find score (e.g., 85/100 or Score: 85)
      const scoreMatch = text.match(/(\d{1,3})\s?\/\s?100/) || text.match(/Score:\s?(\d{1,3})/i);
      if (scoreMatch) {
        this.readinessScore = scoreMatch[1];
        // The rest of the message is the explanation
        this.feedbackExplanation = text.replace(scoreMatch[0], "").replace(/Interview Readiness Score/i, "").trim();
      } else if (text.includes("accuracy") || text.includes("incomplete") || text.includes("early")) {
        // Case for early exit
        this.readinessScore = "N/A";
        this.feedbackExplanation = text;
      }
    },
    initRecognition() {
      const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SR) return null;
      const rec = new SR();
      rec.lang = 'en-US';
      rec.interimResults = false;
      rec.maxAlternatives = 1;
      return rec;
    },
    record() {
      if (!this.sessionId) return;
      if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
        Swal.fire({ icon: 'info', title: 'Mic not supported', text: 'Your browser does not support Speech Recognition. Please type your answer.' });
        return;
      }
      if (!this.recognition) this.recognition = this.initRecognition();
      if (!this.recognition) return;

      this.recognition.onstart = () => {
        this.recording = true;
      };
      
      this.recognition.onresult = (e) => {
        const t = Array.from(e.results).map(r => r[0].transcript).join(' ').trim();
        if (t) this.answer = t;
      };
      this.recognition.onerror = (event) => {
        this.recording = false;
        console.error('Speech Recognition Error:', event.error);
        let message = 'Please try recording again or type your answer.';
        if (event.error === 'not-allowed') {
          message = 'Microphone access denied. Please check your app permissions.';
        } else if (event.error === 'no-speech') {
          message = 'No speech detected. Please try speaking again.';
        } else if (event.error === 'network') {
          message = 'Network error during speech recognition.';
        }
        Swal.fire({ icon: 'error', title: 'Mic error', text: message });
      };
      this.recognition.onend = () => {
        this.recording = false;
      };
      this.recognition.start();
    },
    async start() {
      if (!this.hasResume) {
        Swal.fire('Error', 'Please upload your resume in the dashboard first.', 'error');
        return;
      }
      if (this.interviewAttempts <= 0) {
        Swal.fire({
          icon: 'warning',
          title: 'Daily Limit Reached',
          text: 'You have used all 3 interview sessions for today. Please wait until 00:00 Malaysia Time for the reset.',
          confirmButtonColor: '#ffc107'
        });
        return;
      }

      // Aggressive unlock for TTS on mobile - must be in direct user gesture
      if (this.speaker && 'speechSynthesis' in window) {
        const unlock = new SpeechSynthesisUtterance(" ");
        unlock.volume = 0;
        window.speechSynthesis.speak(unlock);
        if (window.Toaster) {
          window.Toaster.postMessage('TTS unlocked via user gesture');
        }
      }

      this.thinking = true;
      this.transcript = [];
      this.readinessScore = null;
      this.feedbackExplanation = "";
      const fd = new FormData();
      if (this.jobTitle) fd.append('job_title', this.jobTitle);
      if (this.resumeFeedback) fd.append('resume_feedback', JSON.stringify(this.resumeFeedback));
      fd.append('questions_limit', this.questionLimit);
      fd.append('difficulty', this.difficulty);

      fetch('/api/interview/start', {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + icp.state.token },
        body: fd
      })
        .then(r => {
          if (r.status === 401) return null;
          if (!r.ok) {
            return r.json().then(j => {
              if ((r.status === 429 || r.status === 400) && j.detail && j.detail.includes("Daily interview session limit")) {
                this.interviewAttempts = 0;
                Swal.fire({
                  title: 'Limit Reached',
                  html: `
                        <div class='mb-3'>${j.detail}</div>
                        <div class='small text-secondary reset-info-text'>Resets at 00:00 Malaysia Time (GMT+8)</div>
                      `,
                  icon: 'warning',
                  confirmButtonColor: '#3085d6'
                });
              } else {
                Swal.fire('Error', j.detail || 'Failed to start interview', 'error');
              }
              return null;
            });
          }
          return r.json();
        })
        .then(j => {
          if (!j) return;
          this.sessionId = j.session_id;
          this.transcript.push({ role: 'assistant', text: j.message });
          this.tts(j.message);
          this.interviewAttempts = Math.max(0, this.interviewAttempts - 1);
          this.startInterviewTimer();
          this.resetInactivityTimer();
          if (this.useCamera) this.startCamera();
        })
        .finally(() => { this.thinking = false });
    },
    end() {
      if (!this.sessionId) return;
      
      Swal.fire({
        title: 'End Interview?',
        text: "Ending now will stop the session immediately. You won't receive a score for this partial attempt.",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#ef4444',
        cancelButtonColor: '#64748b',
        confirmButtonText: 'Yes, end it'
      }).then((result) => {
        if (result.isConfirmed) {
          fetch('/api/interview/' + this.sessionId + '/end', { method: 'POST', headers: { 'Authorization': 'Bearer ' + icp.state.token } })
            .then(r => {
              if (r.status === 401) return null;
              return r.json();
            })
            .then(j => {
              this.sessionId = null;
              this.stopInterviewTimer();
              if (this.inactivityTimer) clearTimeout(this.inactivityTimer);
              this.stopCamera();
              
              Swal.fire({
                icon: 'info',
                title: 'Interview Ended',
                text: 'Unfortunately, the interview ended too early, and a score cannot be provided. You can start a new session when you are ready.',
                confirmButtonColor: '#2563eb'
              });
            });
        }
      });
    },
    async send() {
      const text = this.answer.trim();
      if (!text) return;
      this.answer = "";
      this.transcript.push({ role: 'user', text });
      this.thinking = true;
      this.resetInactivityTimer();
      
      fetch('/api/interview/' + this.sessionId + '/reply', { method: 'POST', headers: { 'Authorization': 'Bearer ' + icp.state.token, 'Content-Type': 'application/x-www-form-urlencoded' }, body: new URLSearchParams({ user_text: text }).toString() })
        .then(r => { if (r.status === 401) return null; return r.json() })
        .then(j => {
          if (!j) return;
          if (j.message) {
            this.transcript.push({ role: 'assistant', text: j.message });
            this.tts(j.message);
          }
          if (j.ended) {
            this.extractFeedback(j.message);
            this.stopInterviewTimer();
            if (this.inactivityTimer) clearTimeout(this.inactivityTimer);
            this.stopCamera();
            
            Swal.fire({
              icon: 'success',
              title: 'Interview Completed',
              text: 'Great job! You have completed the interview session. You can now view your history or start a new one.',
              confirmButtonColor: '#2563eb'
            });
            this.sessionId = null;
          }
        })
        .finally(() => { this.thinking = false });
    },
    async resetQuota() {
      if (!confirm('Are you sure you want to reset your quotas? (This is for development/testing only)')) return;
      try {
        const r = await fetch('/api/interview/reset-quota', {
          method: 'POST',
          headers: { 'Authorization': 'Bearer ' + icp.state.token }
        });
        if (r.ok) {
          Swal.fire('Success', 'Quotas have been reset. Please refresh the page or wait for limits to update.', 'success');
          // Refresh limits
          const res = await fetch('/api/interview/limits', {
            headers: { 'Authorization': 'Bearer ' + icp.state.token }
          });
          if (res.ok) {
            const j = await res.json();
            this.interviewAttempts = j.remaining;
            this.maxInterviewAttempts = j.limit;
          }
        } else {
          Swal.fire('Error', 'Failed to reset quotas.', 'error');
        }
      } catch (e) {
        Swal.fire('Error', 'Something went wrong.', 'error');
      }
    }
  }
}