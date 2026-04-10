const { createApp } = Vue;

// Immediate Global Sidebar Logic (defined early to prevent race conditions)
window.handleMobileMenu = function() {
  const sidebar = document.getElementById("mobileSidebar");
  const overlay = document.getElementById("sidebarOverlay");
  
  if (sidebar && overlay) {
    const isActive = sidebar.classList.contains("active");
    if (isActive) {
      sidebar.classList.remove("active");
      overlay.classList.remove("active");
      document.body.style.overflow = ""; // Enable scroll
    } else {
      sidebar.classList.add("active");
      overlay.classList.add("active");
      document.body.style.overflow = "hidden"; // Disable scroll
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
            isLoading: false,
            hasSearched: false,
            careerjetWidgetId: '',
            syncInterval: null,
            sessionTime: 0,
            timerId: null
        };
    },
    computed: {
        showResumeReminder() {
            const hasLocal = !!(localStorage.getItem('resume_feedback') || localStorage.getItem('target_job_title'));
            const disabled = localStorage.getItem('resume_autoload_disabled') === 'true';
            return !this.isLoading && (disabled || !hasLocal);
        }
    },
    mounted() {
        this.logged = !!(window.icp && window.icp.state && window.icp.state.token);
        
        // Listen for auth changes
        window.addEventListener('auth:changed', () => {
            const wasLogged = this.logged;
            this.logged = !!(window.icp && window.icp.state && window.icp.state.token);
            
            if (this.logged && !wasLogged) {
                this.setUserFromToken();
                this.init();
            } else if (!this.logged) {
                this.hasAnalyzed = false;
                this.hasSearched = false;
                this.updateSearchBox();
            }
        });

        this.init();
    },
    beforeUnmount() {
        if (this.syncInterval) {
            clearInterval(this.syncInterval);
        }
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
                this.hasAnalyzed = !!me.has_analyzed;
            } catch (e) {
                try {
                    const base64Url = token.split('.')[1];
                    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
                    const payload = JSON.parse(atob(base64));
                    this.userName = payload.name || 'Guest';
                    this.userEmail = payload.email || '';
                    this.hasAnalyzed = !!payload.has_analyzed;
                } catch (_) {}
            }
        },
        async fetchConfigIfNeeded() {
            try {
                let wid = localStorage.getItem('careerjet_widget_id');
                if (!wid) {
                    const r = await axios.get(window.icp.apiUrl('/api/auth/config'));
                    wid = (r.data && r.data.careerjet_widget_id) || '';
                    if (wid) localStorage.setItem('careerjet_widget_id', wid);
                }
                this.careerjetWidgetId = wid || this.careerjetWidgetId || '';
            } catch (e) {
                console.warn('Careerjet widget id not available; widget will render with defaults.');
                this.careerjetWidgetId = this.careerjetWidgetId || '';
            }
        },
        async init() {
            this.isLoading = true;
            this.setUserFromToken();
            await this.fetchConfigIfNeeded();
            
            if (this.logged) {
                this.startTimer();
            }
            
            this.updateSearchBox();
            
            await new Promise(r => setTimeout(r, 900));
            this.isLoading = false;
        },
        updateSearchBox() {
            this.isLoading = true;
            this.hasSearched = true;
            
            // Use nextTick to ensure DOM is updated if needed, though here we manipulate DOM directly for the widget
            this.$nextTick(() => {
                const container = document.getElementById('search-box-container');
                const query = localStorage.getItem('target_job_title') || '';
                const location = localStorage.getItem('target_location') || '';

                if (container) {
                    container.innerHTML = '';
                    
                    const oldScript = document.getElementById('cj-search-box-script');
                    if (oldScript) oldScript.remove();

                    const widgetDiv = document.createElement('div');
                    widgetDiv.className = 'cj-search-box';
                    widgetDiv.setAttribute('data-locale', 'en_MY'); 
                    widgetDiv.setAttribute('data-keywords', query);
                    widgetDiv.setAttribute('data-q', query);
                    widgetDiv.setAttribute('data-s', query);
                    widgetDiv.setAttribute('data-location', location);

                    let widgetUrl = 'https://widget.careerjet.net/search-box/' + this.careerjetWidgetId;
                    let params = [];
                    params.push('q=' + encodeURIComponent(query));
                    params.push('keywords=' + encodeURIComponent(query));
                    params.push('s=' + encodeURIComponent(query));
                    params.push('l=' + encodeURIComponent(location));
                    if (params.length > 0) widgetUrl += '?' + params.join('&');

                    if (this.careerjetWidgetId) widgetDiv.setAttribute('data-url', widgetUrl);
                    container.appendChild(widgetDiv);

                    const script = document.createElement('script');
                    script.id = 'cj-search-box-script';
                    script.async = true;
                    script.src = 'https://static.careerjet.org/js/all_widget_search_box_3rd_party.min.js';
                    script.onload = () => { this.isLoading = false; };
                    script.onerror = () => { this.isLoading = false; };
                    container.appendChild(script);
                }
                
                setTimeout(() => { this.isLoading = false; }, 3000);
                this.syncFields();
            });
        },
        syncFields() {
            const query = localStorage.getItem('target_job_title') || '';
            const location = localStorage.getItem('target_location') || '';
            
            if (!query && !location) return;
            console.log('[JobSearch] Starting persistent sync...', { query, location });
            
            if (this.syncInterval) clearInterval(this.syncInterval);

            let attempts = 0;
            const maxAttempts = 60;
            
            this.syncInterval = setInterval(() => {
                const findInputs = (doc) => {
                    let s = doc.getElementById('s');
                    let l = doc.getElementById('l');

                    if (!s || !l) {
                        const allInputs = Array.from(doc.querySelectorAll('input:not([type="hidden"])'));
                        if (!s) s = allInputs.find(i => i.name === 's' || i.name === 'q' || i.name === 'keywords' || i.id === 's' || (i.placeholder && /job|title|keyword/i.test(i.placeholder)));
                        if (!l) l = allInputs.find(i => i.name === 'l' || i.id === 'l' || (i.placeholder && /location|city|postcode/i.test(i.placeholder)));
                        
                        if (!s || !l) {
                            const textInputs = allInputs.filter(i => i.type === 'text' || !i.type);
                            if (textInputs.length >= 1 && !s) s = textInputs[0];
                            if (textInputs.length >= 2 && !l) l = textInputs[1];
                        }
                    }
                    return { s, l };
                };

                const setVal = (el, val, name) => {
                    if (el && val && el.value !== val) {
                        // 1. Standard value setting
                        el.value = val;
                        
                        // 2. Event dispatching
                        ['input', 'change', 'blur', 'keyup', 'keydown'].forEach(type => {
                            el.dispatchEvent(new Event(type, { bubbles: true }));
                        });

                        // 3. React/Vue/Angular specific hack
                        try {
                            const nativeValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                            nativeValueSetter.call(el, val);
                            el.dispatchEvent(new Event('input', { bubbles: true }));
                        } catch (e) {}
                        
                        el.setAttribute('value', val);
                    }
                };

                const inputs = findInputs(document);
                if (!inputs.s || !inputs.l) {
                    document.querySelectorAll('iframe').forEach(iframe => {
                        try {
                            const doc = iframe.contentDocument || iframe.contentWindow.document;
                            const found = findInputs(doc);
                            if (!inputs.s) inputs.s = found.s;
                            if (!inputs.l) inputs.l = found.l;
                        } catch (e) {}
                    });
                }

                if (inputs.s || inputs.l) {
                    if (inputs.s) setVal(inputs.s, query, 'Job Title');
                    if (inputs.l) setVal(inputs.l, location, 'Location');
                    
                    const sOk = !query || (inputs.s && inputs.s.value === query);
                    const lOk = !location || (inputs.l && inputs.l.value === location);
                    
                    if (sOk && lOk && attempts > 10) { 
                        clearInterval(this.syncInterval);
                        this.syncInterval = null;
                    }
                }
                
                attempts++;
                if (attempts >= maxAttempts) {
                    clearInterval(this.syncInterval);
                    this.syncInterval = null;
                }
            }, 500); 
        },
        logout() {
            window.icp.logout();
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
            
            const updateTimer = () => {
                const now = Math.floor(Date.now() / 1000);
                this.sessionTime = Math.max(0, exp - now);
                
                if (this.sessionTime <= 0) {
                    clearInterval(this.timerId);
                    this.timerId = null;
                    if (this.logged) {
                        alert('Your session has expired. Please login again.');
                        window.icp.logout();
                    }
                }
            };
            
            updateTimer(); 
            this.timerId = setInterval(updateTimer, 1000);
        }
    }
});

app.mount('#app');
