const { createApp } = Vue;

const app = createApp({
    data() {
        return {
            logged: false,
            id: null,
            detail: null,
            fileUrl: '',
            // The extracted text is a disclosure, so its state belongs to the
            // admin once they have touched it: a late render must not snap it
            // shut under their cursor.
            extractedOpen: false,
            _extractedTouched: false,
            errorMsg: '',
            sessionTime: 0,
            timerId: null,
            fullscreen: false,
            userName: 'Admin',
            userEmail: '',
            _popstateHandler: null,
            _isUnmounted: false
        };
    },
    computed: {
        // Drives both the iframe and the full screen control. The extension is
        // checked as well because older records were stored without a
        // mime_type, and a PDF shown as text is the one failure that matters.
        isPdf() {
            if (!this.detail) return false;
            return this.detail.mime_type === 'application/pdf'
                || /\.pdf$/i.test(this.detail.filename || '');
        },
        isImage() {
            return !!(this.detail && /^image\//.test(this.detail.mime_type || ''));
        },
        // True when the document itself is on screen, which is what makes the
        // extracted text optional rather than the only thing to read.
        renderable() {
            return !!this.fileUrl && (this.isPdf || this.isImage);
        },
        extractedBlocks() {
            return window.icpResumeText
                ? window.icpResumeText.blocks(this.detail && this.detail.text)
                : [];
        }
    },
    mounted() {
        this.init();
        
        // Prevent back button to unauthenticated pages
        this._allowedAdminRoutes = [
            '/static/pages/icp-admin-view-2b8f4a10.html',
            '/static/pages/icp-admin-portal-5e6a1c3d.html'
        ];
        // Check current URL on load
        const checkCurrentUrl = () => {
            const currentPath = window.location.pathname;
            const isAllowed = this._allowedAdminRoutes.some(route => currentPath.includes(route));
            if (!isAllowed && this.logged) {
                window.location.replace('/static/pages/icp-admin-portal-5e6a1c3d.html');
            }
        };
        checkCurrentUrl();
        // Popstate handler
        this._popstateHandler = () => {
            const currentPath = window.location.pathname;
            const isAllowed = this._allowedAdminRoutes.some(route => currentPath.includes(route));
            if (!isAllowed) {
                // Push multiple entries to prevent back button
                history.replaceState(null, '', location.href);
                for (let i = 0; i < 5; i++) {
                    history.pushState(null, '', location.href);
                }
            } else {
                history.pushState(null, '', location.href);
            }
        };
        // Initialize history
        history.replaceState(null, '', location.href);
        for (let i = 0; i < 5; i++) {
            history.pushState(null, '', location.href);
        }
        window.addEventListener('popstate', this._popstateHandler);
        
        // Named listener for auth changes
        this._authListener = () => {
            this.logged = !!(window.icp && window.icp.state && window.icp.state.token);
            if (this.logged) this.startTimer();
        };
        window.addEventListener('auth:changed', this._authListener);
        
        // Named listener for beforeunload
        this._unloadListener = () => {
            if (this.fileUrl) URL.revokeObjectURL(this.fileUrl);
        };
        window.addEventListener('beforeunload', this._unloadListener);

        // Full screen preview: Escape closes it, and any viewport change
        // re-measures the frame so a rotation never leaves a stale height.
        this._keydownHandler = (event) => {
            if (event.key === 'Escape' && this.fullscreen) {
                event.preventDefault();
                this.exitFullscreen();
            }
        };
        window.addEventListener('keydown', this._keydownHandler);

        this._resizeHandler = () => {
            if (!this.fullscreen) this.fitViewer();
        };
        window.addEventListener('resize', this._resizeHandler);
        window.addEventListener('orientationchange', this._resizeHandler);
    },
    beforeUnmount() {
        this._isUnmounted = true;
        if (this.timerId) clearInterval(this.timerId);
        if (this._authListener) window.removeEventListener('auth:changed', this._authListener);
        if (this._unloadListener) window.removeEventListener('beforeunload', this._unloadListener);
        if (this._popstateHandler) window.removeEventListener('popstate', this._popstateHandler);
        if (this._keydownHandler) window.removeEventListener('keydown', this._keydownHandler);
        if (this._resizeHandler) {
            window.removeEventListener('resize', this._resizeHandler);
            window.removeEventListener('orientationchange', this._resizeHandler);
        }
        document.documentElement.classList.remove('admin-viewer-fullscreen-open');
        document.body.classList.remove('admin-viewer-fullscreen-open');
    },
    methods: {
        onExtractedToggle(event) {
            this._extractedTouched = true;
            this.extractedOpen = event.target.open;
        },
        // Opens the text by itself only when there is no document to look at,
        // and only while the admin has expressed no preference.
        syncExtractedOpen() {
            if (!this._extractedTouched) this.extractedOpen = !this.renderable;
        },
        // Sizes the PDF frame from the space that is actually left below the
        // toolbar. A fixed 80vh overflows as soon as the navbar wraps on a
        // phone, and wastes a third of a wide monitor.
        fitViewer() {
            const frame = document.getElementById('resume-pdf-frame');
            const stage = document.getElementById('admin-viewer-stage');
            if (!frame || !stage || this.fullscreen) return;
            const available = window.innerHeight - stage.getBoundingClientRect().top - 16;
            frame.style.height = Math.max(240, Math.round(available)) + 'px';
        },
        toggleFullscreen() {
            if (this.fullscreen) {
                this.exitFullscreen();
            } else {
                this.fullscreen = true;
                // Set on <html>: styles.css pins a scrollbar there, and body
                // overflow alone cannot release it.
                document.documentElement.classList.add('admin-viewer-fullscreen-open');
                document.body.classList.add('admin-viewer-fullscreen-open');
                // fitViewer() leaves an inline height on the frame, which beats
                // the full screen rule's 100dvh. Clearing it lets the sheet
                // claim the whole screen; exiting re-measures it.
                const frame = document.getElementById('resume-pdf-frame');
                if (frame) frame.style.height = '';
                this.$nextTick(() => {
                    const exit = document.querySelector('.admin-viewer-exit');
                    if (exit) exit.focus({ preventScroll: true });
                });
            }
        },
        exitFullscreen() {
            this.fullscreen = false;
            document.documentElement.classList.remove('admin-viewer-fullscreen-open');
            document.body.classList.remove('admin-viewer-fullscreen-open');
            this.$nextTick(() => {
                const btn = document.getElementById('toggle-viewer-fullscreen');
                if (btn) btn.focus({ preventScroll: true });
                this.fitViewer();
            });
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
            const token = window.icp.state.token;
            if (!token) return;
            
            const payload = window.icp.decodeToken(token);
            if (!payload || !payload.exp) return;
            
            const exp = payload.exp;
            localStorage.setItem('session_expiry_admin', exp);
            
            const updateTimer = () => {
                const now = Math.floor(Date.now() / 1000);
                this.sessionTime = Math.max(0, exp - now);
                if (this.sessionTime <= 0) {
                    clearInterval(this.timerId);
                    this.timerId = null;
                    localStorage.removeItem('session_expiry_admin');
                    Swal.fire({
                        icon: 'warning',
                        title: 'Session Expired',
                        text: 'Admin session has expired. Please login again to continue.',
                        confirmButtonText: 'Login Again',
                        confirmButtonColor: '#8b5cf6',
                        allowOutsideClick: false
                    }).then(() => {
                        window.icp.logout();
                    });
                }
            };
            
            updateTimer();
            this.timerId = setInterval(updateTimer, 1000);
        },
        async init() {
        const urlParams = new URLSearchParams(window.location.search);
        this.id = urlParams.get('id');
        
        this.logged = !!(window.icp && window.icp.state && window.icp.state.token);
        
        if (!this.logged) {
            // Encoded login path: /static/pages/icp-admin-auth-9f2d8b4e.html
            window.location.href = atob('L3N0YXRpYy9wYWdlcy9pY3AtYWRtaW4tYXV0aC05ZjJkOGI0ZS5odG1s');
            return;
        }
        
        this.startTimer();
        
        try {
            const me = await axios.get(window.icp.apiUrl('/api/auth/me')).then(r => r.data);
            this.userName = me.name || 'Admin';
            this.userEmail = me.email || '';
            if (!(me.role === 'admin' || me.role === 'super_admin')) {
                // Encoded login path: /static/pages/icp-admin-auth-9f2d8b4e.html
                window.location.href = atob('L3N0YXRpYy9wYWdlcy9pY3AtYWRtaW4tYXV0aC05ZjJkOGI0ZS5odG1s');
                return;
            }
        } catch (e) {
            // Encoded login path: /static/pages/icp-admin-auth-9f2d8b4e.html
            window.location.href = atob('L3N0YXRpYy9wYWdlcy9pY3AtYWRtaW4tYXV0aC05ZjJkOGI0ZS5odG1s');
            return;
        }
            
            if (!this.id) {
                Swal.fire({ 
                    icon: 'error', 
                    title: 'Missing resume id',
                    confirmButtonColor: '#8b5cf6'
                });
                return;
            }
            
            try {
                const response = await axios.get(window.icp.apiUrl(`/api/admin/resumes/${this.id}`));
                this.detail = response.data;
                
                // Fetch file
                try {
                    const fileResponse = await axios.get(window.icp.apiUrl(`/api/admin/resumes/${this.id}/file`), {
                        responseType: 'blob'
                    });
                    this.fileUrl = URL.createObjectURL(fileResponse.data);
                } catch (err) {
                    console.error('File fetch error:', err);
                    if (err.response && err.response.status === 404) {
                        this.errorMsg = 'No file available for this resume.';
                    } else {
                        // Fallback
                        this.fileUrl = window.icp.apiUrl(`/api/admin/resumes/${this.id}/file_open?token=${encodeURIComponent(window.icp.state.token)}`);
                    }
                }

                // The iframe is rendered by Vue, so measure on the next tick.
                this.$nextTick(() => this.fitViewer());
                this.syncExtractedOpen();
            } catch (err) {
                console.error(err);
                if (err.response && err.response.status === 401) {
                    window.location.href = '/static/pages/admin.html';
                }
            }
        },
        logout() {
            window.icp.logout();
        }
    }
});

app.mount('#app');
