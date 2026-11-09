const { createApp } = Vue;

/**
 * Reads the token and its role synchronously. app.min.js is loaded before
 * this file, so window.icp and its decoder already exist.
 *
 * This has to happen before the first paint: an admin who lands on a public
 * page must never see the candidate controls, not even for a frame.
 */
function readSession() {
    const token = (window.icp && window.icp.state && window.icp.state.token)
        || localStorage.getItem('token');
    const payload = token && window.icp && window.icp.decodeToken
        ? window.icp.decodeToken(token)
        : null;
    return {
        logged: !!token,
        role: (payload && payload.role) || '',
        // The token's subject is the account id: the same value that scopes the
        // personal best below.
        account: (payload && payload.sub) || '',
    };
}

/**
 * Coffee-break reflex check — the home page's one playful control.
 *
 * A panel turns green after an unpredictable pause; the visitor clicks it and
 * gets a reaction time. It says nothing about the person's role, so an
 * administrator and a candidate get the same easter egg. The personal best
 * lives in localStorage: no request, no quota, no server state.
 */
const REFLEX_STORE = 'icp_reflex_best';

// One personal best per account. The key carries the account id from the
// token's subject, so signing in with another email hands out a fresh
// scoreboard instead of inheriting the previous person's.
function reflexKey(account) {
    return account ? `${REFLEX_STORE}:${account}` : REFLEX_STORE;
}

function readReflexBest(account) {
    try {
        const saved = parseInt(localStorage.getItem(reflexKey(account)), 10);
        return Number.isFinite(saved) && saved > 0 ? saved : 0;
    } catch (e) {
        return 0;
    }
}

// The panel starts neutral, turns success-green on "go", and settles on the
// theme's primary once the click is in. Colours come from the theme; the
// data-state attribute is what the tests and the click handler read.
function paintReflexTarget(target, state, label, klass) {
    target.dataset.state = state;
    target.textContent = label;
    target.className = `btn w-100 py-3 fw-semibold reflex-target ${klass}`;
}

const app = createApp({
    data() {
        const session = readSession();
        return {
            logged: session.logged,
            role: session.role,
            userName: '',
            userEmail: '',
            hasAnalyzed: false,
            reflexAccount: session.account,
            reflexBest: readReflexBest(session.account)
        };
    },
    computed: {
        dashboardUrl() {
            if (this.role === 'admin' || this.role === 'super_admin') {
                // Encoded portal path: /static/pages/icp-admin-portal-5e6a1c3d.html
                return atob('L3N0YXRpYy9wYWdlcy9pY3AtYWRtaW4tcG9ydGFsLTVlNmExYzNkLmh0bWw=');
            }
            return '/static/pages/dashboard.html';
        },
        dashboardText() {
            // An admin is never offered a way back into the candidate
            // dashboard: the bar on the home page is short, so the label just
            // names the portal it leads to.
            return this.isAdmin ? 'Back to Portal' : 'Go to Dashboard';
        },
        isAdmin() {
            return this.role === 'admin' || this.role === 'super_admin';
        }
    },
    mounted() {
        // Prevent back button to authenticated pages when logged out
        this._popstateHandler = () => {
            history.pushState(null, '', window.location.href);
        };
        window.addEventListener('popstate', this._popstateHandler);
        history.pushState(null, '', window.location.href);

        this.checkAuth();
        this._authListener = () => {
            this.checkAuth();
        };
        window.addEventListener('auth:changed', this._authListener);
    },
    beforeUnmount() {
        if (this._authListener) window.removeEventListener('auth:changed', this._authListener);
        if (this._popstateHandler) window.removeEventListener('popstate', this._popstateHandler);
    },
    methods: {
        async checkAuth() {
            this.logged = !!(window.icp && window.icp.state && window.icp.state.token);
            if (!this.logged) {
                this.role = '';
                this.userName = '';
                this.userEmail = '';
                this.hasAnalyzed = false;
                this.reflexAccount = '';
                this.reflexBest = 0;
                return;
            }
            // The role travels inside the JWT, so it is known before the
            // /api/auth/me round-trip. Reading it first means the call-to-action
            // never points at the candidate dashboard for an admin, not even
            // for the frames the request is in flight.
            this.roleFromToken();
            await this.checkRole();
        },
        roleFromToken() {
            const session = readSession();
            if (session.role) this.role = session.role;
            // The account id rides in the token as well, so a token that
            // arrives later (another tab signing in) picks up that account's
            // personal best rather than keeping the last one's.
            if (session.account !== this.reflexAccount) {
                this.reflexAccount = session.account;
                this.reflexBest = readReflexBest(session.account);
            }
        },
        async checkRole() {
            if (!this.logged) return;
            try {
                const response = await axios.get(window.icp.apiUrl('/api/auth/me'));
                const me = response.data;
                this.role = me.role || '';
                this.userName = me.name || 'Guest';
                this.userEmail = me.email || '';
                this.hasAnalyzed = me.has_analyzed || !!localStorage.getItem('resume_feedback');
            } catch (e) {
                console.error('Error fetching user info:', e);
                const payload = window.icp.decodeToken(window.icp.state.token);
                this.role = payload?.role || '';
            }
        },
        logout() {
            if (window.icp && window.icp.logout) {
                window.icp.logout();
            }
        },
        // The game is three states and one stopwatch: wait, go, clicked. The
        // timer is cleared on close so a closed dialog cannot fire into a
        // detached panel.
        openReflex() {
            if (!window.Swal) {
                window.alert('Click the panel as soon as it turns green.');
                return;
            }
            let armedAt = 0;
            let armTimer = null;
            window.Swal.fire({
                title: '⚡ Reflex check',
                html: '<p class="text-secondary small mb-2">Click the panel the moment it turns green.</p>'
                    + '<button type="button" class="btn w-100 py-3 fw-semibold reflex-target btn-outline-secondary"'
                    + ' id="reflex-target" data-state="waiting">Wait for it…</button>'
                    + '<p class="small mt-2 mb-0" id="reflex-result"></p>',
                confirmButtonText: 'Close',
                confirmButtonColor: '#8b5cf6',
                didOpen: () => {
                    const target = document.getElementById('reflex-target');
                    const result = document.getElementById('reflex-result');
                    if (!target || !result) return;

                    armTimer = setTimeout(() => {
                        paintReflexTarget(target, 'go', 'CLICK!', 'btn-success');
                        armedAt = performance.now();
                    }, 1400 + Math.random() * 1600);

                    target.addEventListener('click', () => {
                        if (target.dataset.state === 'waiting') {
                            clearTimeout(armTimer);
                            paintReflexTarget(target, 'early', 'Too early!', 'btn-outline-danger');
                            result.textContent = 'Anticipation is not a skill the interviewers test.';
                            return;
                        }
                        if (target.dataset.state !== 'go') return;

                        const ms = Math.round(performance.now() - armedAt);
                        const previous = this.reflexBest;
                        paintReflexTarget(target, 'done', `${ms} ms`, 'btn-primary');
                        this.recordReflex(ms);
                        result.textContent = !previous || ms < previous
                            ? 'New personal best! Your fingers are officially trained.'
                            : `Personal best stays at ${previous} ms. The stopwatch is undefeated.`;
                    });
                },
                willClose: () => {
                    if (armTimer) clearTimeout(armTimer);
                },
            });
        },
        recordReflex(ms) {
            if (this.reflexBest && ms >= this.reflexBest) return this.reflexBest;
            this.reflexBest = ms;
            try {
                localStorage.setItem(reflexKey(this.reflexAccount), String(ms));
            } catch (e) {
                // Private mode: the personal best is a nicety, not a requirement.
            }
            return this.reflexBest;
        }
    }
});

app.mount('#app');