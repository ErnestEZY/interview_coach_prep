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
            isLoading: false,
            hasSearched: false,
            careerjetWidgetId: '',
            syncInterval: null,
            sessionTime: 0,
            timerId: null,
            _isUnmounted: false,
            _popstateHandler: null
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
        this._popstateHandler = () => {
            const currentPath = window.location.pathname;
            const isAllowed = this._allowedUserRoutes.some(route => currentPath.includes(route));
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
        };
        window.addEventListener('auth:changed', this._authListener);

        this.init();
    },
    beforeUnmount() {
        this._isUnmounted = true;
        if (this.syncInterval) {
            clearInterval(this.syncInterval);
            this.syncInterval = null;
        }
        if (this.timerId) {
            clearInterval(this.timerId);
            this.timerId = null;
        }
        if (this._authListener) window.removeEventListener('auth:changed', this._authListener);
        if (this._popstateHandler) window.removeEventListener('popstate', this._popstateHandler);
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
            const token = window.icp && window.icp.state ? window.icp.state.token : localStorage.getItem("token");
            if (!token) return;

            // First: check JWT expiry locally so we never make a doomed network call
            try {
                const base64Url = token.split('.')[1];
                const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
                const payload = JSON.parse(atob(base64));
                const nowSec = Math.floor(Date.now() / 1000);
                if (payload.exp && payload.exp < nowSec) {
                    // Token is genuinely expired — clean logout without triggering axios interceptor
                    if (window.icp && window.icp.logout) window.icp.logout();
                    return;
                }
                // Pre-fill from JWT while network call is in-flight
                this.userName = payload.name || payload.sub || 'Guest';
                this.userEmail = payload.email || '';
                this.hasAnalyzed = !!payload.has_analyzed;
            } catch (_) {}

            // Use plain fetch (not axios) so the 401 interceptor cannot fire and wipe localStorage
            try {
                const apiBase = (window.icp && window.icp.state && window.icp.state.apiBase) || '';
                const res = await fetch(apiBase + '/api/auth/me', {
                    headers: { 'Authorization': 'Bearer ' + token }
                });
                if (res.ok) {
                    const me = await res.json();
                    this.userName = me.name || 'Guest';
                    this.userEmail = me.email || '';
                    this.hasAnalyzed = !!me.has_analyzed;
                }
                // If 401 — token expired server-side. The local check above should have caught this,
                // but either way we do nothing here; let the session timer handle expiry gracefully.
            } catch (_) {
                // Network error — keep using JWT-decoded values from above
            }
        },
        async fetchConfigIfNeeded() {
            try {
                let wid = localStorage.getItem('careerjet_widget_id');
                if (!wid) {
                    const token = (window.icp && window.icp.state && window.icp.state.token) || localStorage.getItem('token') || '';
                    const apiBase = (window.icp && window.icp.state && window.icp.state.apiBase) || '';
                    const r = await fetch(apiBase + '/api/auth/config', {
                        headers: token ? { 'Authorization': 'Bearer ' + token } : {}
                    });
                    if (r.ok) {
                        const data = await r.json();
                        wid = (data && data.careerjet_widget_id) || '';
                        if (wid) localStorage.setItem('careerjet_widget_id', wid);
                    }
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
        // Expand common Malaysian location abbreviations before passing to
        // the widget so "KL" → "Kuala Lumpur" and results actually appear.
        normalizeLocation(raw) {
            const aliases = {
                'kl':           'Kuala Lumpur',
                'k.l':          'Kuala Lumpur',
                'k.l.':         'Kuala Lumpur',
                'kl city':      'Kuala Lumpur',
                'klang valley': 'Kuala Lumpur',
                'bangsar':      'Kuala Lumpur',
                'mont kiara':   'Kuala Lumpur',
                "mont'kiara":   'Kuala Lumpur',
                'pj':           'Petaling Jaya',
                'p.j':          'Petaling Jaya',
                'p.j.':         'Petaling Jaya',
                'jb':           'Johor Bahru',
                'j.b':          'Johor Bahru',
                'j.b.':         'Johor Bahru',
                'pg':           'Penang',
                'kk':           'Kota Kinabalu',
                'kb':           'Kota Bharu',
                'kch':          'Kuching',
                'sbh':          'Sabah',
                'swk':          'Sarawak',
                'ns':           'Negeri Sembilan',
                'subang':       'Subang Jaya',
                'cyberjaya':    'Cyberjaya',
                'putrajaya':    'Putrajaya',
            };
            if (!raw) return raw;
            const key = raw.trim().toLowerCase();
            return aliases[key] || raw;
        },

        updateSearchBox() {
            this.isLoading = true;
            this.hasSearched = true;
            
            // Use nextTick to ensure DOM is updated if needed, though here we manipulate DOM directly for the widget
            this.$nextTick(() => {
                const container = document.getElementById('search-box-container');
                const query = localStorage.getItem('target_job_title') || '';
                const rawLocation = localStorage.getItem('target_location') || '';
                const location = this.normalizeLocation(rawLocation);

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

                    if (this.careerjetWidgetId) {
                        widgetDiv.setAttribute('data-url', widgetUrl);
                        container.appendChild(widgetDiv);

                        const script = document.createElement('script');
                        script.id = 'cj-search-box-script';
                        script.async = true;
                        script.src = 'https://static.careerjet.org/js/all_widget_search_box_3rd_party.min.js';
                        script.onload = () => { 
                            this.isLoading = false;
                            this.watchForEmptyResults(container);
                        };
                        script.onerror = () => { this.isLoading = false; };
                        container.appendChild(script);
                    } else {
                        // Fallback: if widget id is not configured in deployment, show a simple
                        // external link to Careerjet search so users can still find jobs.
                        const fallback = document.createElement('div');
                        fallback.className = 'cj-search-fallback';
                        const q = encodeURIComponent(query || '');
                        const l = encodeURIComponent(location || '');
                        const url = `https://www.careerjet.net/search/jobs?s=${q}&l=${l}`;
                        fallback.innerHTML = `
                            <div style="display:flex;gap:12px;align-items:center;">
                                <div style="flex:1">Careerjet widget is unavailable on this deployment. You can open the full search in a new tab.</div>
                                <div><a class="btn btn-primary btn-sm" href="${url}" target="_blank" rel="noopener">Open Job Search</a></div>
                            </div>
                        `;
                        container.appendChild(fallback);
                        this.isLoading = false;
                    }
                }
                
                setTimeout(() => { this.isLoading = false; }, 3000);
                this.syncFields();
            });
        },
        syncFields() {
            const query = localStorage.getItem('target_job_title') || '';
            const rawLocation = localStorage.getItem('target_location') || '';
            const location = this.normalizeLocation(rawLocation);
            
            if (!query && !location) return;
            console.log('[JobSearch] Starting persistent sync...', { query, location });
            
            if (this.syncInterval) clearInterval(this.syncInterval);

            let attempts = 0;
            const maxAttempts = 60;
            
            this.syncInterval = setInterval(() => {
                if (this._isUnmounted) {
                    if (this.syncInterval) {
                        clearInterval(this.syncInterval);
                        this.syncInterval = null;
                    }
                    return;
                }
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
        watchForEmptyResults(container) {
            const removeBanner = () => {
                const el = document.getElementById('cj-no-results-msg');
                if (el) el.remove();
            };

            const showNoResultsBanner = () => {
                if (document.getElementById('cj-no-results-msg')) return;
                const banner = document.createElement('div');
                banner.id = 'cj-no-results-msg';
                banner.style.cssText = 'display:flex;align-items:flex-start;gap:12px;margin-top:12px;background:rgba(239,68,68,0.08);border-left:3px solid rgba(239,68,68,0.6);border-radius:8px;padding:12px 14px;';
                banner.innerHTML = `
                    <i class="bi bi-emoji-frown" style="color:#f87171;font-size:1.1rem;flex-shrink:0;margin-top:2px;"></i>
                    <div style="font-size:0.85rem;">
                        <div style="font-weight:600;margin-bottom:4px;color:#fff;">No jobs found for your search</div>
                        <div style="color:#94a3b8;">
                            Try a broader keyword, or spell out the full city name —
                            e.g. <em>Kuala Lumpur</em> instead of <em>KL</em>.
                        </div>
                    </div>
                    <button onclick="document.getElementById('cj-no-results-msg').remove()"
                        style="margin-left:auto;background:none;border:none;color:#94a3b8;cursor:pointer;font-size:1rem;flex-shrink:0;line-height:1;"
                        aria-label="Dismiss">&#x2715;</button>
                `;
                container.after(banner);
            };

            // The widget iframe resizes itself via postMessage / inline style.
            // A frame with job results is tall; a "no results" page is short.
            // We poll the iframe height every 500ms for up to 10s after each
            // load event, which is the only cross-origin signal we can read.
            let pollTimer = null;
            let userHasSearched = !!(
                localStorage.getItem('target_job_title') ||
                localStorage.getItem('target_location')
            );

            const getIframe = () => container.querySelector('iframe');

            const pollHeight = () => {
                clearInterval(pollTimer);
                let ticks = 0;
                pollTimer = setInterval(() => {
                    ticks++;
                    const iframe = getIframe();
                    if (!iframe) { if (ticks > 20) clearInterval(pollTimer); return; }

                    const h = iframe.offsetHeight || iframe.clientHeight ||
                              parseInt(iframe.style.height || '0');

                    // Once we see a definitive height, decide and stop polling
                    if (h > 50) {
                        clearInterval(pollTimer);
                        if (h < 300) {
                            // Short iframe = no results page
                            showNoResultsBanner();
                        } else {
                            // Tall iframe = results present
                            removeBanner();
                        }
                    }
                    if (ticks > 20) clearInterval(pollTimer); // 10s max
                }, 500);
            };

            // Watch for the iframe being injected by the widget script
            const observer = new MutationObserver(() => {
                const iframe = getIframe();
                if (!iframe || iframe._cjWatched) return;
                iframe._cjWatched = true;

                iframe.addEventListener('load', () => {
                    if (!userHasSearched) return;
                    removeBanner();
                    pollHeight();
                });

                // Widget may already be loaded by the time observer fires
                if (iframe.src && userHasSearched) pollHeight();
            });
            observer.observe(container, { childList: true, subtree: true });

            // Also catch an iframe that was already there before observer attached
            const existing = getIframe();
            if (existing && !existing._cjWatched) {
                existing._cjWatched = true;
                existing.addEventListener('load', () => {
                    if (!userHasSearched) return;
                    removeBanner();
                    pollHeight();
                });
            }

            // Since we can't click inside the cross-origin iframe,
            // we use a document-level click + keydown listener.
            // Any click/Enter anywhere on the page after the widget loaded
            // counts as "user has searched" — safe because the widget is the
            // only interactive element on the page.
            const onUserAction = () => { userHasSearched = true; };
            document.addEventListener('click', onUserAction, { once: true });
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') userHasSearched = true;
            }, { once: true });

            window.addEventListener('beforeunload', () => {
                observer.disconnect();
                clearInterval(pollTimer);
            }, { once: true });
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
        resetSearch() {
            localStorage.removeItem('target_job_title');
            localStorage.removeItem('target_location');
            localStorage.setItem('resume_autoload_disabled', 'true');
            if (this.syncInterval) clearInterval(this.syncInterval);
            
            const findInputs = (doc) => {
                let s = doc.getElementById('s');
                let l = doc.getElementById('l');
                if (!s || !l) {
                    const allInputs = Array.from(doc.querySelectorAll('input:not([type="hidden"])'));
                    if (!s) s = allInputs.find(i => i.name === 's' || i.name === 'q' || i.name === 'keywords' || i.id === 's');
                    if (!l) l = allInputs.find(i => i.name === 'l' || i.id === 'l');
                }
                return { s, l };
            };
            
            const { s, l } = findInputs(document);
            if (s) s.value = '';
            if (l) l.value = '';
            
            Swal.fire({
                toast: true,
                position: 'top-end',
                icon: 'success',
                title: 'Search reset. You can start fresh.',
                showConfirmButton: false,
                timer: 3000
            });
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
                if (this._isUnmounted) {
                    if (this.timerId) {
                        clearInterval(this.timerId);
                        this.timerId = null;
                    }
                    return;
                }
                const now = Math.floor(Date.now() / 1000);
                this.sessionTime = Math.max(0, exp - now);
                
                if (this.sessionTime <= 0) {
                    if (this.timerId) {
                        clearInterval(this.timerId);
                        this.timerId = null;
                    }
                    if (this.logged) {
                        Swal.fire({
                            icon: 'warning',
                            title: 'Session Expired',
                            text: 'Your session has expired. Please login again to continue.',
                            confirmButtonText: 'Login Again',
                            confirmButtonColor: '#8b5cf6',
                            allowOutsideClick: false
                        }).then(() => {
                            if (window.icp) window.icp.logout();
                            else { localStorage.clear(); window.location.href = "/static/pages/login.html"; }
                        });
                    }
                }
            };
            
            updateTimer(); 
            this.timerId = setInterval(updateTimer, 1000);
        }
    }
});

app.mount('#app');
