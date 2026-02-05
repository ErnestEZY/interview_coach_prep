const { createApp } = Vue;

// Immediate Global Sidebar Logic
window.handleMobileMenu = function() {
    const sidebar = document.getElementById('mobileSidebar');
    const overlay = document.getElementById('sidebarOverlay');
    if (sidebar && overlay) {
        const isActive = sidebar.classList.contains("active");
        if (isActive) {
            sidebar.classList.remove("active");
            overlay.classList.remove("active");
        } else {
            sidebar.classList.add("active");
            overlay.classList.add("active");
        }
    }
};

const app = createApp({
    data() {
        return {
            logged: false,
            isAdmin: false,
            userName: '',
            userEmail: '',
            hasAnalyzed: false,
            
            // Session Config
            sessionId: null,
            currentQuestion: 0,
            questionLimit: 10,
            difficulty: "Intermediate",
            
            // Interview State
            transcript: [],
            answer: "",
            speaker: localStorage.getItem('interview_speaker_enabled') !== 'false',
            voiceGender: localStorage.getItem('interview_voice_gender') || 'female',
            mic: localStorage.getItem('interview_mic_enabled') === 'true',
            recording: false,
            thinking: false,
            speaking: false,
            recognition: null,
            
            // Resume/Job Context
            hasResume: false,
            jobTitle: "",
            resumeFeedback: null,
            
            // Results
            interviewAttempts: 0,
            maxInterviewAttempts: 3,
            readinessScore: null,
            feedbackExplanation: "",
            
            // Timers
            sessionTime: 0,
            timerId: null,
            interviewTime: 1200, // 20 minutes default
            interviewTimerId: null,
            inactivityTimer: null,
            lastInteractionTime: Date.now(),
            invalidLocalAttempts: 0,
            
            // Camera / Face API
            useCamera: localStorage.getItem('interview_camera_enabled') === 'true',
            cameraStream: null,
            faceDetectionTimer: null,
            faceAbsentTimer: null,
            isFaceDetected: false,
            isStarting: false,
            modelsLoaded: false,
            videoDevices: [],
            selectedCameraId: localStorage.getItem('interview_camera_device_id') || '',
            
            // Audio Devices
            audioDevices: [],
            selectedMicId: localStorage.getItem('interview_mic_device_id') || '',
            
            // Loading States
            loading: true,
            submitting: false,
            faceWarningShown: false,
            faceConfirmTimer: null,
            selectedFemaleVoiceId: null,
            selectedMaleVoiceId: null,
            isPaused: false
        };
    },
    computed: {
        scoreColorClass() {
            if (!this.readinessScore) return '';
            const score = parseInt(this.readinessScore);
            if (score >= 80) return 'score-high';
            if (score >= 50) return 'score-medium';
            return 'score-low';
        }
    },
    watch: {
        selectedCameraId(newVal) {
            try { localStorage.setItem('interview_camera_device_id', newVal || ''); } catch (_) {}
        },
        selectedMicId(newVal) {
            try { localStorage.setItem('interview_mic_device_id', newVal || ''); } catch (_) {}
        },
        useCamera(newVal) {
            localStorage.setItem('interview_camera_enabled', newVal);
            if (newVal) {
                this.loadVideoDevices().then(() => this.startCamera());
            } else {
                this.stopCamera();
            }
        },
        mic(newVal) {
            localStorage.setItem('interview_mic_enabled', newVal);
        },
        speaker(newVal) {
            localStorage.setItem('interview_speaker_enabled', newVal);
        },
        voiceGender(newVal) {
            localStorage.setItem('interview_voice_gender', newVal);
        },
        interviewTime(newVal) {
            try { localStorage.setItem('interview_remaining_time', newVal); } catch (_) {}
        }
    },
    mounted() {
        // Check initial auth
        this.logged = !!(window.icp && window.icp.state && window.icp.state.token);
        
        // Listen for auth changes
        window.addEventListener('auth:changed', () => {
            const wasLogged = this.logged;
            this.logged = !!(window.icp && window.icp.state && window.icp.state.token);
            if (this.logged && !wasLogged) {
                this.init();
            } else if (!this.logged) {
                try {
                    localStorage.removeItem('resume_feedback');
                    localStorage.removeItem('resume_filename');
                    localStorage.removeItem('resume_score');
                    localStorage.removeItem('target_job_title');
                    localStorage.removeItem('target_location');
                    localStorage.removeItem('interview_session_id');
                } catch (_) {}
                this.sessionId = null;
                this.currentQuestion = 0;
                this.transcript = [];
                this.readinessScore = null;
                this.feedbackExplanation = "";
            }
        });

        // Initialize
        this.init();

        // Mobile menu handler
        window.handleMobileMenu = function() {
            const sidebar = document.getElementById('mobileSidebar');
            const overlay = document.getElementById('sidebarOverlay');
            if (sidebar && overlay) {
                sidebar.classList.toggle('active');
                overlay.classList.toggle('active');
            }
        };

        // Global click listener for inactivity
        document.addEventListener('click', () => this.resetInactivityTimer());
        document.addEventListener('keypress', () => this.resetInactivityTimer());
    },
    methods: {
        async loadVideoDevices() {
            try {
                await this.ensureCameraPermissions();
                const devices = await this.getVideoDevices();
                this.videoDevices = devices;
                if (!this.selectedCameraId) {
                    const stored = localStorage.getItem('interview_camera_device_id') || '';
                    this.selectedCameraId = stored || (devices[0] && devices[0].deviceId) || '';
                }
            } catch (e) {}
        },
        onCameraDeviceChange() {
            if (this.cameraStream) {
                this.stopCamera();
                this.startCamera();
            }
        },
        async loadAudioDevices() {
            try {
                await this.ensureAudioPermissions();
                const devices = await this.getAudioDevices();
                this.audioDevices = devices;
                if (!this.selectedMicId) {
                    const stored = localStorage.getItem('interview_mic_device_id') || '';
                    this.selectedMicId = stored || (devices[0] && devices[0].deviceId) || '';
                }
            } catch (e) {}
        },
        async ensureAudioPermissions() {
            try {
                await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
            } catch (e) {}
        },
        async getAudioDevices() {
            if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return [];
            const all = await navigator.mediaDevices.enumerateDevices();
            return all.filter(d => d.kind === 'audioinput');
        },
        onAudioDeviceChange() {
            console.log("Audio device changed:", this.selectedMicId);
            // webkitSpeechRecognition uses system default, but we track choice for UI consistency
        },
        async init() {
            try {
                this.loading = true;
                if (this.logged) {
                    this.setUserFromToken();
                    this.startTimer();
                    this.computeResumeStatus();
                    this.loadAudioDevices();
                }
                if (this.logged) {
                    try {
                        const r = await axios.get(window.icp.apiUrl('/api/interview/limits'));
                        if (r && r.data) {
                            this.interviewAttempts = r.data.remaining ?? this.interviewAttempts;
                            this.maxInterviewAttempts = r.data.limit ?? this.maxInterviewAttempts;
                        }
                    } catch (e) {}
                }
                
                // Initialize speech recognition if supported
                if ('webkitSpeechRecognition' in window) {
                    this.recognition = new webkitSpeechRecognition();
                    this.recognition.continuous = true;
                    this.recognition.interimResults = true;
                    this.recognition.lang = 'en-US';
                    
                    this.recognition.onresult = (event) => {
                        let finalTranscript = '';
                        for (let i = event.resultIndex; i < event.results.length; ++i) {
                            if (event.results[i].isFinal) {
                                finalTranscript += event.results[i][0].transcript;
                            }
                        }
                        if (finalTranscript) {
                            this.answer += (this.answer ? ' ' : '') + finalTranscript;
                            this.resetInactivityTimer();
                        }
                    };

                    this.recognition.onerror = (event) => {
                        console.error('Speech recognition error', event.error);
                        this.recording = false;
                    };
                    
                    this.recognition.onend = () => {
                        if (this.recording) {
                            this.recognition.start();
                        }
                    };
                }
                
                // Start camera if enabled and faceapi is available
                if (this.useCamera) {
                    if (window.faceapi) {
                        this.startCamera();
                    } else {
                        console.warn("face-api.js not loaded, skipping camera init");
                        this.useCamera = false;
                    }
                }
                
                await this.restoreSessionIfAny();
            } catch (e) {
                console.error("Interview initialization failed", e);
                Swal.fire('Error', 'Failed to initialize interview session. Please refresh.', 'error');
            } finally {
                const hasLocalResume = !!(localStorage.getItem('resume_feedback') || localStorage.getItem('resume_filename') || localStorage.getItem('target_job_title'));
                const delay = hasLocalResume ? 200 : 700;
                await new Promise(r => setTimeout(r, delay));
                this.loading = false;
            }
        },

        async setUserFromToken() {
            const token = window.icp && window.icp.state ? window.icp.state.token : localStorage.getItem("token");
            if (!token) return;
            try {
                const response = await axios.get(window.icp.apiUrl('/api/auth/me'));
                const me = response.data || {};
                this.userName = me.name || 'Guest';
                this.userEmail = me.email || '';
                this.hasAnalyzed = !!me.has_analyzed;
            } catch (_) {
                try {
                    const base64Url = token.split('.')[1];
                    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
                    const payload = JSON.parse(atob(base64));
                    this.userName = payload.name || 'Guest';
                    this.userEmail = payload.email || '';
                    this.hasAnalyzed = !!payload.has_analyzed;
                } catch (e) {}
            }
        },

        computeResumeStatus() {
            const localFeedbackStr = localStorage.getItem('resume_feedback');
            const localFilename = localStorage.getItem('resume_filename');
            const storedJobTitle = localStorage.getItem('target_job_title');
            
            let parsedFeedback = null;
            if (localFeedbackStr && localFeedbackStr !== 'null' && localFeedbackStr !== 'undefined') {
                try { parsedFeedback = JSON.parse(localFeedbackStr); } catch (_) { parsedFeedback = null; }
            }
            
            if (parsedFeedback || localFilename || storedJobTitle || this.hasAnalyzed) {
                this.hasResume = true;
                this.resumeFeedback = parsedFeedback || this.resumeFeedback;
                const detectedTitle = (parsedFeedback && parsedFeedback.DetectedJobTitle) || '';
                this.jobTitle = storedJobTitle || detectedTitle || this.jobTitle || '';
            } else {
                this.hasResume = false;
                this.jobTitle = '';
                this.resumeFeedback = null;
            }
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
            
            const updateTimer = () => {
                const now = Math.floor(Date.now() / 1000);
                this.sessionTime = Math.max(0, exp - now);
                
                if (this.sessionTime <= 0) {
                    clearInterval(this.timerId);
                    this.timerId = null;
                    Swal.fire('Session Ended', 'Your session has expired. Please login again.', 'warning')
                        .then(() => {
                            if (window.icp) window.icp.logout();
                            else { localStorage.clear(); window.location.href = "/"; }
                        });
                }
            };
            
            updateTimer();
            this.timerId = setInterval(updateTimer, 1000);
        },

        formatTime(seconds) {
            if (isNaN(seconds) || seconds === null) return '0:00';
            const m = Math.floor(seconds / 60);
            const s = seconds % 60;
            return `${m}:${s.toString().padStart(2, '0')}`;
        },

        async startInterview() {
            if (!this.logged) {
                Swal.fire('Authentication Required', 'Please login to start an interview.', 'warning');
                return;
            }
            if (this.interviewAttempts <= 0) {
                Swal.fire('Limit Reached', 'You have no interview sessions remaining today.', 'warning');
                return;
            }
            
            if (!this.hasResume) {
                Swal.fire({
                    title: 'Resume Required',
                    text: 'Please upload your resume in the dashboard before starting an interview.',
                    icon: 'warning',
                    confirmButtonText: 'Go to Dashboard'
                }).then((result) => {
                    if (result.isConfirmed) {
                        window.location.href = '/static/pages/dashboard.html';
                    }
                });
                return;
            }

            this.isStarting = true;
            try {
                const fd = new FormData();
                const localFeedbackStr = localStorage.getItem('resume_feedback');
                const storedJobTitle = localStorage.getItem('target_job_title') || '';
                fd.append('difficulty', this.difficulty);
                fd.append('questions_limit', String(parseInt(this.questionLimit)));
                if (storedJobTitle) fd.append('job_title', storedJobTitle);
                if (localFeedbackStr) fd.append('resume_feedback', localFeedbackStr);
                
                const response = await axios.post(window.icp.apiUrl('/api/interview/start'), fd);
                
                this.sessionId = response.data.session_id;
                try { localStorage.setItem('interview_session_id', String(this.sessionId)); } catch (_) {}
                this.currentQuestion = 1;
                this.transcript = [];
                this.transcript.push({ role: 'ai', content: response.data.message });
                
                // Start interview timer
                this.startInterviewTimer();

                // Start inactivity timer
                this.resetInactivityTimer();

                // Speak the first question (ensure voices ready and gender applied)
                if (this.speaker) {
                    await this.ensureVoicesReady();
                    await this.initVoices();
                    this.speak(response.data.message);
                }

            } catch (e) {
                console.error('Failed to start interview', e);
                Swal.fire('Error', 'Failed to start interview session.', 'error');
            } finally {
                this.isStarting = false;
            }
        },

        async submitAnswer() {
            if (!this.answer.trim()) return;
            
            this.submitting = true;
            const userAnswer = this.answer;
            this.transcript.push({ role: 'user', content: userAnswer });
            this.answer = "";
            
            // Stop recording if active
            if (this.recording) {
                this.toggleMic();
            }

            this.thinking = true;
            
            try {
                // Client-side invalid handler using strict InvalidGuard
                const isInvalid = window.InvalidGuard ? window.InvalidGuard.isInvalid(userAnswer) : this.isLikelyGibberish(userAnswer);
                
                if (isInvalid) {
                    if (window.InvalidGuard) {
                        window.InvalidGuard.increment();
                        const attempts = window.InvalidGuard.getAttempts();
                        if (attempts >= 3) {
                            await window.InvalidGuard.endSession(this);
                            // Clear state to ensure no further processing
                            this.submitting = false;
                            this.thinking = false;
                            this.sessionId = null;
                            return;
                        }
                    } else {
                        this.invalidLocalAttempts++;
                        if (this.invalidLocalAttempts >= 3) {
                            try {
                                const sid = this.sessionId;
                                if (this.interviewTimerId) clearInterval(this.interviewTimerId);
                                await axios.post(window.icp.apiUrl(`/api/interview/${sid}/end`));
                            } catch (_) {}
                            const endMsg = "Session ended due to repeated invalid responses. Readiness Score: N/A.";
                            this.transcript.push({ role: 'ai', content: endMsg });
                            this.readinessScore = null;
                            this.feedbackExplanation = "We received multiple responses that looked like random characters or non-words. The session is now closed. Readiness Score is N/A.";
                            if (this.speaker) this.speak(this.feedbackExplanation);
                            this.interviewAttempts = Math.max(0, this.interviewAttempts - 1);
                            this.sessionId = null;
                            this.currentQuestion = 0;
                            try { localStorage.removeItem('interview_session_id'); } catch (_) {}
                            this.stopCamera();
                            return;
                        }
                    }
                    
                    // Re-ask prompt without copying the previous question verbatim
                    const msg = "I didn’t quite catch that. Please answer in clear words. Try responding to the previous question in your own words.";
                    this.transcript.push({ role: 'ai', content: msg });
                    if (this.speaker) this.speak(msg);
                    
                    this.resetInactivityTimer();
                    this.submitting = false;
                    this.thinking = false;
                    return;
                }
                
                const fd = new FormData();
                fd.append('user_text', userAnswer);
                const response = await axios.post(window.icp.apiUrl(`/api/interview/${this.sessionId}/reply`), fd);
                
                const msg = response.data.message;
                const ended = !!response.data.ended;
                this.transcript.push({ role: 'ai', content: msg });
                if (window.InvalidGuard) window.InvalidGuard.reset(); else this.invalidLocalAttempts = 0;
                
                if (ended) {
                    if (this.interviewTimerId) clearInterval(this.interviewTimerId);
                    this.sessionId = null;
                    try { 
                        localStorage.removeItem('interview_session_id'); 
                        localStorage.removeItem('interview_remaining_time');
                    } catch (_) {}
                    // Extract score
                    const match = /Interview Readiness Score:\s*(\d+)\/100/i.exec(msg);
                    this.readinessScore = match ? parseInt(match[1]) : null;
                    this.feedbackExplanation = msg.replace(/Interview Readiness Score:\s*\d+\/100/i, '').trim();
                    if (this.speaker) this.speak(this.feedbackExplanation);
                    this.interviewAttempts = Math.max(0, this.interviewAttempts - 1);
                } else {
                    const asked = typeof response.data.asked_count !== 'undefined' ? parseInt(response.data.asked_count) : null;
                    if (!isNaN(asked) && asked > 0) {
                        this.currentQuestion = asked;
                    }
                    if (this.speaker) this.speak(msg);
                }
                
                this.resetInactivityTimer();
                
            } catch (e) {
                console.error('Failed to submit answer', e);
                Swal.fire('Error', 'Failed to submit answer.', 'error');
                // Restore answer in case of error
                this.answer = userAnswer; 
                this.transcript.pop(); // Remove user message from transcript
            } finally {
                this.submitting = false;
                this.thinking = false;
            }
        },
        
        isLikelyGibberish(text) {
            const s = (text || '').trim();
            if (!s) return true;
            if (s.length < 3) return true;
            // Stronger heuristics
            const alpha = (s.match(/[a-zA-Z]/g) || []).length;
            const digits = (s.match(/[0-9]/g) || []).length;
            const nonWord = (s.match(/[^a-zA-Z0-9\s]/g) || []).length;
            const vowels = (s.match(/[aeiouAEIOU]/g) || []).length;
            const alphaRatio = alpha / s.length;
            const nonWordRatio = nonWord / s.length;
            const repeatedChar = /(.)\1{3,}/.test(s);
            const hasWords = /\b[a-zA-Z]{2,}\b/.test(s);
            if (nonWordRatio > 0.25) return true;
            if (alphaRatio < 0.5 && digits > alpha) return true;
            if (s.length < 10 && nonWordRatio > 0) return true;
            if (vowels === 0 && hasWords) return true;
            if (repeatedChar) return true;
            if (!hasWords) return true;
            return false;
        },
        
        async finishInterview(results) {
            if (this.interviewTimerId) clearInterval(this.interviewTimerId);
            this.sessionId = null;
            this.readinessScore = results.score;
            this.feedbackExplanation = results.feedback;
            
            Swal.fire({
                title: 'Interview Completed!',
                text: `Your Readiness Score: ${results.score}/100`,
                icon: 'success'
            });
        },

        endInterview(reason = 'User terminated') {
            Swal.fire({
                title: 'End Interview?',
                text: "Are you sure you want to end the current session?",
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#d33',
                cancelButtonColor: '#3085d6',
                confirmButtonText: 'Yes, end it!'
            }).then((result) => {
                if (result.isConfirmed) {
                    const sid = this.sessionId;
                    if (this.interviewTimerId) clearInterval(this.interviewTimerId);
                    axios.post(window.icp.apiUrl(`/api/interview/${sid}/end`))
                        .then((response) => {
                            const msg = response.data && response.data.message ? response.data.message : 'Session ended.';
                            this.transcript.push({ role: 'ai', content: msg });
                            this.readinessScore = null;
                            this.feedbackExplanation = msg;
                            if (this.speaker) this.speak(msg);
                            this.interviewAttempts = Math.max(0, this.interviewAttempts - 1);
                        })
                        .catch(() => {
                            this.transcript.push({ role: 'ai', content: 'Session ended early. No score generated.' });
                            this.readinessScore = null;
                            this.feedbackExplanation = 'Session ended early. No score generated.';
                            this.interviewAttempts = Math.max(0, this.interviewAttempts - 1);
                        })
                        .finally(() => {
                            this.sessionId = null;
                            this.currentQuestion = 0;
                            try { 
                                localStorage.removeItem('interview_session_id'); 
                                localStorage.removeItem('interview_remaining_time');
                            } catch (_) {}
                            this.stopCamera();
                        });
                }
            });
        },
        
        pauseInterview(title, message) {
            this.isPaused = true;
            if (this.interviewTimerId) {
                clearInterval(this.interviewTimerId);
                this.interviewTimerId = null;
            }
            if (this.inactivityTimer) {
                clearTimeout(this.inactivityTimer);
                this.inactivityTimer = null;
            }
            this.stopCamera();
            Swal.fire({
                title: title,
                text: message,
                icon: 'info'
            });
        },
        
        async showInactivityConfirm() {
            const res = await Swal.fire({
                title: 'Are you still there?',
                text: 'No activity detected. Continue the interview?',
                icon: 'question',
                showCancelButton: true,
                confirmButtonText: 'Yes, continue',
                cancelButtonText: 'Pause',
                timer: 10000,
                timerProgressBar: true,
                allowOutsideClick: false,
                allowEscapeKey: false,
                footer: '<div class="text-secondary small">If paused, you can resume later from History → Resume Session.</div>'
            });
            if (res.isConfirmed) {
                this.isPaused = false;
                this.resetInactivityTimer();
            } else {
                this.pauseInterview('Paused Due to Inactivity', 'You have been inactive. The interview is paused. You can resume later from History → Resume Session.');
            }
        },
        
        async showPresenceConfirm(kind) {
            const isCamera = kind === 'camera';
            const res = await Swal.fire({
                title: isCamera ? 'We can’t detect you' : 'Are you still there?',
                text: isCamera ? 'Please look towards the camera. Continue the interview?' : 'No activity detected. Continue the interview?',
                icon: isCamera ? 'warning' : 'question',
                showCancelButton: true,
                confirmButtonText: 'Yes, continue',
                cancelButtonText: 'Pause',
                timer: 10000,
                timerProgressBar: true,
                allowOutsideClick: false,
                allowEscapeKey: false,
                footer: '<div class="text-secondary small">If paused, you can resume later from History → Resume Session.</div>'
            });
            if (res.isConfirmed) {
                this.isPaused = false;
                this.resetInactivityTimer();
            } else {
                this.pauseInterview(isCamera ? 'Paused: Face Not Detected' : 'Paused Due to Inactivity', 'The interview is paused. You can resume later from History → Resume Session.');
            }
        },

        // --- Camera & Face API ---
        async startCamera() {
            if (!this.useCamera) return;
            
            try {
                if (!this.modelsLoaded) {
                    const MODEL_URL = 'https://cdn.jsdelivr.net/gh/justadudewhohacks/face-api.js@master/weights';
                    await Promise.all([
                        faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL),
                    ]);
                    this.modelsLoaded = true;
                }

                // 1) Ensure permission prompt so device labels become available
                await this.ensureCameraPermissions();
                
                // 2) Enumerate devices and pick the best available camera (prefer external)
                const devices = await this.getVideoDevices();
                this.videoDevices = devices;
                if (!devices || devices.length === 0) {
                    throw new Error('No camera devices found');
                }
                
                const preferredId = this.selectedCameraId || localStorage.getItem('interview_camera_device_id') || null;
                let deviceToUse = devices.find(d => d.deviceId === preferredId) || this.chooseCameraDevice(devices);
                
                // 3) Try starting with preferred device; fall back through others if it fails
                let stream = await this.tryStartStreamWithDeviceId(deviceToUse.deviceId);
                if (!stream) {
                    for (const dev of devices) {
                        if (dev.deviceId === deviceToUse.deviceId) continue;
                        stream = await this.tryStartStreamWithDeviceId(dev.deviceId);
                        if (stream) {
                            deviceToUse = dev;
                            break;
                        }
                    }
                }
                
                if (!stream) {
                    throw new Error('Could not start any camera stream');
                }
                
                // Cache the selected device
                try { localStorage.setItem('interview_camera_device_id', deviceToUse.deviceId); } catch (_) {}
                
                this.cameraStream = stream;
                
                this.$nextTick(() => {
                    const video = document.getElementById('interviewVideo');
                    if (video) {
                        video.srcObject = stream;
                        this.startFaceDetection();
                    }
                });

                Swal.fire({
                    icon: 'info',
                    title: 'Camera Active',
                    text: 'Please ensure you have good lighting.',
                    showConfirmButton: true,
                    confirmButtonText: 'OK, got it'
                });

            } catch (err) {
                console.error("Camera error:", err);
                this.useCamera = false;
                Swal.fire('Camera Error', 'Could not access camera. Please check permissions.', 'error');
            }
        },
        
        async ensureCameraPermissions() {
            try {
                // Request generic video permission to allow device labels
                await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
            } catch (e) {
                // Permission could be already granted or denied; continue, startCamera will handle failures
            }
        },
        
        async getVideoDevices() {
            if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return [];
            const all = await navigator.mediaDevices.enumerateDevices();
            return all.filter(d => d.kind === 'videoinput');
        },
        
        chooseCameraDevice(devices) {
            // Prefer external-looking devices
            const prefer = devices.find(d => /logitech|usb|external|hd|webcam|facetime/i.test(d.label) && !/integrated|built[- ]?in/i.test(d.label));
            return prefer || devices[0];
        },
        
        async tryStartStreamWithDeviceId(deviceId) {
            try {
                const constraints = { video: { deviceId: { exact: deviceId }, width: 320, height: 240 } };
                const s = await navigator.mediaDevices.getUserMedia(constraints);
                return s;
            } catch (e) {
                return null;
            }
        },

        stopCamera() {
            if (this.cameraStream) {
                this.cameraStream.getTracks().forEach(track => track.stop());
                this.cameraStream = null;
            }
            if (this.faceDetectionTimer) clearInterval(this.faceDetectionTimer);
            if (this.faceAbsentTimer) clearTimeout(this.faceAbsentTimer);
        },

        startFaceDetection() {
            if (this.faceDetectionTimer) clearInterval(this.faceDetectionTimer);
            
            const video = document.getElementById('interviewVideo');
            if (!video) return;

            this.faceDetectionTimer = setInterval(async () => {
                if (!video.srcObject) return;
                
                const detections = await faceapi.detectAllFaces(video, new faceapi.TinyFaceDetectorOptions());
                
                if (detections.length > 0) {
                    this.isFaceDetected = true;
                    if (this.faceAbsentTimer) {
                        clearTimeout(this.faceAbsentTimer);
                        this.faceAbsentTimer = null;
                    }
                    if (this.faceConfirmTimer) {
                        clearTimeout(this.faceConfirmTimer);
                        this.faceConfirmTimer = null;
                    }
                    this.faceWarningShown = false;
                    // Update status badge if exists
                    const statusBadge = document.getElementById('faceStatus');
                    if (statusBadge) {
                        statusBadge.className = 'badge bg-success';
                        statusBadge.innerText = 'Face Detected';
                    }
                } else {
                    this.isFaceDetected = false;
                    const statusBadge = document.getElementById('faceStatus');
                    if (statusBadge) {
                        statusBadge.className = 'badge bg-warning text-dark';
                        statusBadge.innerText = 'No Face';
                    }
                    if (!this.faceAbsentTimer && this.sessionId) {
                        this.faceAbsentTimer = setTimeout(async () => {
                            if (this.sessionId && !this.isFaceDetected) {
                                await this.showPresenceConfirm('camera');
                                this.faceWarningShown = true;
                            }
                        }, 15000);
                    }
                }
            }, 1000);
        },

        // --- Audio & Speech ---
        toggleMic() {
            if (!this.recognition) {
                Swal.fire('Error', 'Speech recognition is not supported in this browser.', 'error');
                return;
            }
            
            if (this.recording) {
                this.recognition.stop();
                this.recording = false;
            } else {
                try {
                    this.recognition.start();
                    this.recording = true;
                    this.mic = true;
                } catch (e) {
                    console.error("Mic start error", e);
                }
            }
        },

        speak(text) {
            if (!this.speaker || !text) return;
            
            // Cancel any current speech
            window.speechSynthesis.cancel();
            
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.lang = 'en-US';
            
            // Use stable preselected voices
            const voices = window.speechSynthesis.getVoices() || [];
            const resolveById = (id) => voices.find(v => v.voiceURI === id || v.name === id);
            
            // Re-init voices if needed to ensure we have the latest selection
            if (!this.selectedFemaleVoiceId || !this.selectedMaleVoiceId) {
                this.initVoices();
            }

            const targetId = (this.voiceGender === 'male') ? this.selectedMaleVoiceId : this.selectedFemaleVoiceId;
            let v = targetId ? resolveById(targetId) : null;
            
            if (v) {
                utterance.voice = v;
            } else {
                // Last resort fallback based on gender if voice ID lookup fails
                const preferred = this.selectPreferredVoice(voices, this.voiceGender);
                if (preferred) utterance.voice = preferred;
                utterance.pitch = this.voiceGender === 'male' ? 0.8 : 1.2;
            }
            
            this.speaking = true;
            utterance.onend = () => {
                this.speaking = false;
            };
            
            window.speechSynthesis.speak(utterance);
        },
        
        async ensureVoicesReady() {
            const getVoices = () => window.speechSynthesis.getVoices();
            let voices = getVoices();
            if (voices && voices.length > 0) return;
            await new Promise(resolve => {
                const handler = () => {
                    voices = getVoices();
                    if (voices && voices.length > 0) {
                        window.speechSynthesis.removeEventListener('voiceschanged', handler);
                        resolve();
                    }
                };
                window.speechSynthesis.addEventListener('voiceschanged', handler);
                setTimeout(() => {
                    window.speechSynthesis.removeEventListener('voiceschanged', handler);
                    resolve();
                }, 1500);
            });
        },
        
        async initVoices() {
            const voices = window.speechSynthesis.getVoices() || [];
            const resolveById = (id) => voices.find(v => v.voiceURI === id || v.name === id);
            
            // Prefer previously stored choices
            const storedFem = localStorage.getItem('interview_voice_female_id') || '';
            const storedMale = localStorage.getItem('interview_voice_male_id') || '';
            let fem = storedFem && resolveById(storedFem) ? storedFem : null;
            let male = storedMale && resolveById(storedMale) ? storedMale : null;
            
            // If not present or unavailable, select fresh
            if (!fem) {
                const vf = this.selectPreferredVoice(voices, 'female');
                fem = vf ? (vf.voiceURI || vf.name) : null;
            }
            if (!male) {
                const vm = this.selectPreferredVoice(voices, 'male');
                male = vm ? (vm.voiceURI || vm.name) : null;
            }
            
            this.selectedFemaleVoiceId = fem;
            this.selectedMaleVoiceId = male;
            try {
                localStorage.setItem('interview_voice_female_id', fem || '');
                localStorage.setItem('interview_voice_male_id', male || '');
            } catch (_) {}
        },
        
        selectPreferredVoice(voices, gender) {
            if (!voices || voices.length === 0) return null;
            
            // Try to find a high-quality Google or Microsoft voice for the specific gender
            const patterns = gender === 'male' 
                ? [/male/i, /david/i, /mark/i, /guy/i, /andrew/i, /brian/i] 
                : [/female/i, /zira/i, /jessa/i, /samantha/i, /victoria/i, /hazel/i];
            
            // Priority 1: Google/Microsoft high quality matches
            for (const p of patterns) {
                const match = voices.find(v => (v.name.match(p) || v.voiceURI.match(p)) && (v.name.includes('Google') || v.name.includes('Microsoft')));
                if (match) return match;
            }
            
            // Priority 2: Any match
            for (const p of patterns) {
                const match = voices.find(v => v.name.match(p) || v.voiceURI.match(p));
                if (match) return match;
            }
            
            // Priority 3: English fallback
            return voices.find(v => v.lang.startsWith('en')) || voices[0];
        },
        
        async restoreSessionIfAny() {
            try {
                const sid = localStorage.getItem('interview_session_id');
                if (!sid || !this.logged) return;
                const r = await axios.get(window.icp.apiUrl(`/api/interview/${sid}`));
                const d = r.data || {};
                if (d.ended_at) {
                    try { localStorage.removeItem('interview_session_id'); } catch (_) {}
                    return;
                }
                this.sessionId = d.session_id || sid;
                this.questionLimit = parseInt(d.questions_limit) || this.questionLimit;
                const asked = parseInt(d.asked_count || 0);
                if (!isNaN(asked) && asked > 0) this.currentQuestion = asked;
                this.transcript = [];
                const tr = Array.isArray(d.transcript) ? d.transcript : [];
                tr.forEach(t => {
                    const role = t.role === 'assistant' ? 'ai' : 'user';
                    this.transcript.push({ role, content: t.text });
                });
                
                // Restore remaining time if available
                const storedTime = localStorage.getItem('interview_remaining_time');
                if (storedTime) {
                    this.interviewTime = parseInt(storedTime);
                }
                
                // Resume timers
                this.startInterviewTimer();
                this.resetInactivityTimer();
            } catch (e) {
                console.warn('Restore session failed', e);
            }
        },

        startInterviewTimer() {
            if (this.interviewTimerId) clearInterval(this.interviewTimerId);
            
            // If interviewTime wasn't set (e.g. on refresh), estimate based on questions
            if (this.interviewTime === 1200) { // default value
                 this.interviewTime = parseInt(this.questionLimit) * 120;
            }

            this.interviewTimerId = setInterval(() => {
                if (this.interviewTime > 0) {
                    this.interviewTime--;
                } else {
                    this.endInterview('Time Limit Reached');
                }
            }, 1000);
        },

        resetInactivityTimer() {
            this.lastInteractionTime = Date.now();
            if (this.inactivityTimer) clearTimeout(this.inactivityTimer);
            
            if (!this.sessionId) return;
            
            this.inactivityTimer = setTimeout(() => {
                if (this.sessionId) {
                    this.showInactivityConfirm();
                }
            }, 4 * 60 * 1000);
        }
    }
});

try {
    app.mount('#app');
} catch (e) {
    console.error("Vue Mount Error:", e);
    // Remove v-cloak if mount fails so user sees something
    const el = document.getElementById('app');
    if (el) el.removeAttribute('v-cloak');
    document.body.innerHTML += `<div style="color: red; padding: 20px; text-align: center;">
        <h3>Application Error</h3>
        <p>Failed to initialize the interview interface. Please refresh or contact support.</p>
        <pre>${e.message}</pre>
    </div>`;
}
