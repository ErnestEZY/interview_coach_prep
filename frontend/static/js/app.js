/**
 * Global application utilities
 */

// Global Mobile Menu Toggle Handler (Vanilla JS Fallback for better reliability)
window.handleMobileMenu = function(forceState) {
  const sidebar = document.getElementById('mobileSidebar');
  const overlay = document.getElementById('sidebarOverlay');
  if (!sidebar || !overlay) return;
  
  const isActive = sidebar.classList.contains('active');
  const newState = (forceState !== undefined) ? forceState : !isActive;

  if (newState) {
    sidebar.classList.add('active');
    overlay.classList.add('active');
    document.body.style.overflow = "hidden";
  } else {
    sidebar.classList.remove('active');
    overlay.classList.remove('active');
    document.body.style.overflow = "";
  }
};

// Global listener for hamburger buttons
document.addEventListener('click', (e) => {
  const btn = e.target.closest('.hamburger-btn') || e.target.closest('.sidebar-header .btn-link') || e.target.closest('.sidebar-overlay');
  if (btn) {
    // If it's a Vue-managed page, it might already have its own toggleMobileMenu.
    // But we use this as a reliable fallback.
    window.handleMobileMenu();
  }
});

window.setupSessionTimer = function(vueInstance) {
  const checkTimer = () => {
    if (vueInstance._isUnmounted) {
      // The interval will be cleared in the component's beforeUnmount hook
      return;
    }
    const expiration = localStorage.getItem('token_expiration');
    if (expiration) {
      const now = Math.floor(Date.now() / 1000);
      const timeLeft = expiration - now;
      if (timeLeft <= 0) {
        // Clear resume builder session when token expires
        localStorage.removeItem('resume_builder_session');
        localStorage.removeItem('resume_builder_imported');
        if (window.icp && window.icp.logout) window.icp.logout();
        else window.location.href = '/';
        return;
      }
      vueInstance.sessionTime = timeLeft;
    }
  };
  const intervalId = setInterval(checkTimer, 1000);
  checkTimer();
  return intervalId;
};

const icpState = {
  token: localStorage.getItem("token") || "",
  
  // Detect if running in Tauri
  get isTauri() {
    return !!window.__TAURI_INTERNALS__ || 
           !!window.__TAURI__ || 
           window.location.protocol === 'tauri:' || 
           window.location.protocol === 'asset:';
  },
  
  // Base API URL for Tauri
  get apiBase() {
    // If we're not in Tauri, we use relative paths ('')
    if (!this.isTauri) return '';
    
    // Check for a manual override in localStorage (useful for debugging)
    const override = localStorage.getItem('ICP_API_URL');
    if (override) return override;

    // Check if user has explicitly enabled "Local Mode" via debug helper
    if (localStorage.getItem('ICP_LOCAL_MODE') === 'true') {
      return 'http://127.0.0.1:8000'; // Default FastAPI port
    }

    const prodUrl = 'https://interview-coach-prep.onrender.com';
    return prodUrl;
  },
  
  setToken(t) {
    if (!t || t === "undefined" || t === "null") return;
    this.token = t;
    localStorage.setItem("token", t);
    try { 
      localStorage.setItem('resume_autoload_disabled', 'true'); 
    } catch (_) {}
    // Clear stale session expiry data on new token
    localStorage.removeItem('session_expiry_user');
    localStorage.removeItem('session_expiry_admin');
    window.dispatchEvent(new CustomEvent("auth:changed"));
  },
  
  clearToken() {
    this.token = "";
    localStorage.removeItem("token");
    try {
      // Forcefully remove everything related to the user session
      localStorage.removeItem('target_job_title');
      localStorage.removeItem('target_location');
      localStorage.removeItem('resume_feedback');
      localStorage.removeItem('resume_filename');
      localStorage.removeItem('resume_score');
      localStorage.removeItem('session_expiry_user');
      localStorage.removeItem('session_expiry_admin');
      localStorage.removeItem('interview_voice_gender');
      localStorage.removeItem('interview_mic_enabled');
      localStorage.removeItem('interview_speaker_enabled');
      localStorage.removeItem('interview_camera_enabled');
      localStorage.removeItem('interview_session_id');
      localStorage.removeItem('resume_autoload_disabled');
      localStorage.removeItem('resume_builder_session');
      localStorage.removeItem('resume_builder_imported');
      localStorage.removeItem('resume_builder_hide_import_prompt');
      
      // Also clear everything else just to be safe, except startup_id
      const keys = Object.keys(localStorage);
      keys.forEach(key => {
        if (key !== 'startup_id') {
          localStorage.removeItem(key);
        }
      });
    } catch (e) {}
    window.dispatchEvent(new CustomEvent("auth:changed"));
  }
};

if (icpState.token === "undefined" || icpState.token === "null") {
  icpState.clearToken();
}

// Setup Axios Interceptors
if (window.axios) {
  // Request Interceptor
  axios.interceptors.request.use(function (config) {
    // Only add token if it exists and we're NOT hitting the login endpoint
    if (icpState.token && !config.url.includes('/api/auth/login')) {
      config.headers['Authorization'] = 'Bearer ' + icpState.token;
    }
    
    // Prepend API base URL if in Tauri and request is for /api
    if (icpState.isTauri && config.url.startsWith('/api')) {
      const originalPath = config.url;
      config.url = icpState.apiBase + originalPath;
      console.log(`[Tauri Axios] ${originalPath} -> ${config.url}`);
    }
    return config;
  }, function (error) {
    return Promise.reject(error);
  });

  // Response Interceptor
  axios.interceptors.response.use(function (response) {
    return response;
  }, function (error) {
    // Check for network errors (no response)
    if (!error.response) {
      console.warn("Network error or server unreachable:", error);
      if (!navigator.onLine) {
        showOfflineToast();
        showOfflineOverlay();
      }
    }
    
    if (error.response && error.response.status === 401) {
      icpState.clearToken();
      const currentPath = window.location.pathname;
      const isPublicPage = 
        currentPath === '/' || 
        currentPath.includes('login.html') || 
        currentPath.includes('register.html') || 
        currentPath.includes('cta.html') || 
        currentPath.includes('reset_password.html') || 
        currentPath.includes('forgot_password.html');

      if (!isPublicPage) {
        const is_admin_page = currentPath.includes('icp-admin-');
        // Encoded auth path to protect against browser console discovery
        const auth_path = atob('L3N0YXRpYy9wYWdlcy9pY3AtYWRtaW4tYXV0aC05ZjJkOGI0ZS5odG1s');
        window.location.href = is_admin_page ? auth_path : '/static/pages/login.html';
      } else {
        // If we are on a public page and auth fails, just clear token but don't redirect away
        // This prevents redirect loops if we are already on login.html
        icpState.clearToken();
      }
    }
    return Promise.reject(error);
  });
}

function logout() {
  const currentPath = window.location.pathname;
  const is_admin_page = currentPath.includes('icp-admin-');
  icpState.clearToken();
  if (is_admin_page) {
    // Encoded auth path: /static/pages/icp-admin-auth-9f2d8b4e.html
    window.location.href = atob('L3N0YXRpYy9wYWdlcy9pY3AtYWRtaW4tYXV0aC05ZjJkOGI0ZS5odG1s');
  } else {
    window.location.href = "/";
  }
}

function decodeToken(token) {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
      return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
    }).join(''));
    return JSON.parse(jsonPayload);
  } catch (e) {
    return null;
  }
}

/**
 * Helper to get absolute API URL
 */
function apiUrl(path) {
  if (path.startsWith('http')) return path;
  const p = path.startsWith('/') ? path : '/' + path;
  const fullUrl = icpState.apiBase + p;
  // Log API calls in Tauri for easier debugging
  if (icpState.isTauri) {
    console.log(`[Tauri API] ${path} -> ${fullUrl}`);
  }
  return fullUrl;
}

/**
 * Debug helpers for Tauri
 */
window.icp_debug = {
  useLocal: () => {
    localStorage.setItem('ICP_LOCAL_MODE', 'true');
    console.log("Local mode enabled. API: http://127.0.0.1:8000. Reloading...");
    location.reload();
  },
  useProd: () => {
    localStorage.removeItem('ICP_LOCAL_MODE');
    localStorage.removeItem('ICP_API_URL');
    console.log("Production mode enabled. Reloading...");
    location.reload();
  },
  setApi: (url) => {
    localStorage.setItem('ICP_API_URL', url);
    console.log(`API URL set to ${url}. Reloading...`);
    location.reload();
  },
  getStatus: () => {
    console.log("Tauri Detected:", icpState.isTauri);
    console.log("Current API Base:", icpState.apiBase);
    console.log("Protocol:", window.location.protocol);
    console.log("Hostname:", window.location.hostname);
  }
};

// Initialize icp object with all required properties
if (!window.icp) {
  window.icp = {};
}

/**
 * Handles the response from the forgot password request
 * @param {Event} event HTMX after-request event
 */
window.handleForgotPasswordResponse = function(event) {
  if (event.detail.successful) {
    localStorage.removeItem('forgot_email');
    let message = 'A password reset link has been sent to your email address.';
    let debugLink = null;
    
    try {
      const res = JSON.parse(event.detail.xhr.response);
      message = res.message || message;
      debugLink = res.debug_link;
    } catch (e) {}

    Swal.fire({
      icon: 'success',
      title: 'Email Sent!',
      text: message,
      footer: '<div class="text-center w-100"><p class="small mb-1" style="color: #475569; font-weight: 500;"><i class="bi bi-clock-history me-1"></i>Arrival time: 4-5 minutes (Gmail processing)</p><p class="small mb-0" style="color: #475569; font-weight: 500;"><i class="bi bi-info-circle me-1"></i>Check your <b>Spam/Junk</b> folder</p></div>',
      confirmButtonText: 'Back to Login',
      confirmButtonColor: '#8b5cf6',
      allowOutsideClick: false
    }).then(() => {
      window.location = '/static/pages/login.html';
    });

    if (debugLink) {
      console.log('Reset Link (Dev Only):', debugLink);
    }
  } else {
    let msg = 'We encountered an issue sending the reset link.';
    let title = 'Request Failed';
    
    try {
      const res = JSON.parse(event.detail.xhr.response);
      msg = res.detail || msg;
      if (event.detail.xhr.status === 404) {
        title = 'Account Not Found';
      }
    } catch (e) {}

    Swal.fire({
      icon: 'error',
      title: title,
      text: msg,
      confirmButtonColor: '#8b5cf6'
    });
  }
};
// Attach to window.icp for global access
Object.assign(window.icp, {
  state: icpState,
  decodeToken,
  apiUrl,
  logout,
  isGibberish: (text) => {
    if (!text) return false;
    const s = text.trim();
    const total = s.length;
    if (total < 3) return false;
    
    // Allow short common abbreviations
    const commonAbbrev = ["hr", "vp", "it", "ai", "ceo", "cto", "cfo", "coo", "qa", "ux", "ui", "pm"];
    if (commonAbbrev.includes(s.toLowerCase())) return false;

    const alphaCount = (s.match(/[a-zA-Z]/g) || []).length;
    const digitCount = (s.match(/[0-9]/g) || []).length;
    const spaceCount = (s.match(/\s/g) || []).length;
    const symCount = total - (alphaCount + digitCount + spaceCount);
    const tokens = s.split(/\s+/);
    const wordCount = tokens.length;

    // --- LIGHT VERSION FOR INTERVIEWS ---
    // If it's a reasonably long string with multiple words, we are very lenient.
    if (wordCount >= 2 && alphaCount > 8) {
      // Only flag extreme repetition or pure symbol mashing
      if (/(.)\1{8,}/.test(s)) return true; 
      if (symCount / total > 0.5) return true; 
      return false;
    }

    // Basic mashing detection for short inputs
    if (/(.)\1{4,}/.test(s)) return true;
    if (symCount / total > 0.4) return true;
    
    const vowels = "aeiouy";
    const hasVowel = [...s.toLowerCase()].some(c => vowels.includes(c));
    if (total > 6 && !hasVowel && alphaCount > 0) return true;

    // Common keyboard mashing patterns (reduced set for light version)
    const mashingPatterns = [/asdf/i, /qwerty/i, /zxcv/i, /12345/, /!@#\$/];
    if (mashingPatterns.some(p => p.test(s))) return true;

    return false;
  },
  showTerms: () => {
    Swal.fire({
      title: 'Terms & Conditions',
      html: `
        <div class="text-start small overflow-auto px-2" style="max-height: 400px; line-height: 1.6;">
          
          <h6 class="fw-bold">1. Acceptance of Terms</h6>
          <p>By accessing or using ICP (Interview Coach Prep), you agree to be bound by these Terms and Conditions. These terms apply to all visitors, users, and others who access the service.</p>
          
          <h6 class="fw-bold">2. Service Description</h6>
          <p>ICP provides an AI-powered platform for interview preparation, including mock interviews, resume analysis, and career guidance. The service is provided "as is" and "as available".</p>
          
          <h6 class="fw-bold">3. User Accounts</h6>
          <p>You must provide accurate and complete information when creating an account. You are solely responsible for the activity that occurs on your account and must keep your password secure.</p>
          
          <h6 class="fw-bold">4. User Conduct</h6>
          <p>You agree not to use the service for any unlawful purpose or to conduct any activity that would violate the rights of others. This includes not attempting to reverse engineer the AI models or bypass any security features.</p>
          
          <h6 class="fw-bold">5. Intellectual Property</h6>
          <p>The Service and its original content, features, and functionality are and will remain the exclusive property of ICP and its licensors. User-submitted content (like resumes) remains the property of the user, but you grant us a license to process it for the purpose of providing the service.</p>
          
          <h6 class="fw-bold">6. Limitation of Liability</h6>
          <p>In no event shall ICP be liable for any indirect, incidental, special, or consequential damages resulting from your use of the service. AI feedback is for educational purposes only and does not guarantee job offers.</p>
          
          <h6 class="fw-bold">7. Termination</h6>
          <p>We may terminate or suspend access to our Service immediately, without prior notice, for any reason whatsoever, including without limitation if you breach the Terms.</p>
          
          <h6 class="fw-bold">8. Changes</h6>
          <p>We reserve the right to modify or replace these Terms at any time. We will try to provide at least 30 days' notice before any new terms take effect.</p>
        </div>
      `,
      confirmButtonText: 'Close',
      confirmButtonColor: '#8b5cf6'
    });
  },
  showPrivacy: () => {
    Swal.fire({
      title: 'Privacy Policy',
      html: `
        <div class="text-start small overflow-auto px-2" style="max-height: 400px; line-height: 1.6;">

          <h6 class="fw-bold">1. Information We Collect</h6>
          <p><strong>Personal Data:</strong> We collect your name and email address for account management and security.</p>
          <p><strong>Professional Data:</strong> We collect resume files and interview responses that you voluntarily upload or provide to our AI engine.</p>
          
          <h6 class="fw-bold">2. How We Use Your Data</h6>
          <p>We use the collected data to provide AI-driven feedback, personalize your experience, maintain account security, and improve our services through anonymized analysis.</p>
          
          <h6 class="fw-bold">3. Data Sharing & Third Parties</h6>
          <p>We do not sell your personal data. We share necessary information with:</p>
          <ul>
            <li><strong>AI Services:</strong> To process your resumes and interview responses.</li>
            <li><strong>Email Services:</strong> To send verification and reset links.</li>
            <li><strong>Database Services:</strong> To securely store your profile and history.</li>
          </ul>
          
          <h6 class="fw-bold">4. Data Security</h6>
          <p>We implement technical and organizational security measures to protect your data, including encryption for passwords and secure API communication.</p>
          
          <h6 class="fw-bold">5. Your Rights</h6>
          <p>You have the right to access, correct, or delete your personal data. You can manage your profile settings or contact us to request account deletion.</p>
          
          <h6 class="fw-bold">6. Cookies</h6>
          <p>We use local storage and essential cookies to maintain your session and preferences. We do not use tracking cookies for third-party advertising.</p>
          
          <h6 class="fw-bold">7. Children's Privacy</h6>
          <p>Our Service does not address anyone under the age of 15. We do not knowingly collect personal information from children under 15.</p>
        </div>
      `,
      confirmButtonText: 'Close',
      confirmButtonColor: '#8b5cf6'
    });
  }
});

// Global Startup Check: Clear sessions if server has restarted
(function checkStartup() {
  fetch(apiUrl('/api/meta/startup_id'))
    .then(r => r.ok ? r.json() : null)
    .then(j => {
      if (j && j.startup_id) {
        const prev = localStorage.getItem('startup_id') || '';
        // Force logout if startup_id changed (or is missing) to ensure fresh session on server restart
        if (prev !== j.startup_id) {
          localStorage.clear(); 
          localStorage.setItem('startup_id', j.startup_id);
          window.dispatchEvent(new CustomEvent("auth:changed"));
          // Force redirect to home if they were on a protected page
          try {
            const currentPath = window.location.pathname || '';
            const safePaths = [
              'login.html', 
              'register.html', 
              'reset_password.html', 
              'forgot_password.html', 
              'resume_builder.html',
              'cta.html'
            ];
            
            const isSafe = currentPath === '/' || safePaths.some(p => currentPath.includes(p));
            
            if (!isSafe) {
               window.location.href = "/";
             }
           } catch (e) {
             // Silent fail for redirect logic
           }
        } else {
          localStorage.setItem('startup_id', j.startup_id);
        }
      }
    })
    .catch(() => {});
})();

// Global Loader Logic
const hideLoader = () => {
  const loader = document.getElementById("global-loader");
  if (loader) {
    loader.classList.add("fade-out");
    setTimeout(() => loader.remove(), 500);
  }
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", hideLoader);
} else {
  hideLoader();
}

// Offline/Online Detection
const showOfflineToast = () => {
  const toast = document.createElement('div');
  toast.id = 'offline-toast';
  toast.className = 'offline-toast';
  toast.innerText = 'No internet connection. Please check your network.';
  document.body.appendChild(toast);
  setTimeout(() => toast.classList.add('visible'), 10);
};

const hideOfflineToast = () => {
  const toast = document.getElementById('offline-toast');
  if (toast) {
    toast.classList.remove('visible');
    setTimeout(() => toast.remove(), 300);
  }
};

const showOfflineOverlay = () => {
  if (document.getElementById('offline-overlay')) return;
  const overlay = document.createElement('div');
  overlay.id = 'offline-overlay';
  overlay.className = 'offline-overlay';
  overlay.innerHTML = `
    <div class="offline-card">
      <div class="offline-icon">📶✖</div>
      <div class="offline-title">You are offline</div>
      <div class="offline-desc">Please check your internet connection and try again.</div>
      <button id="offline-retry-btn" class="btn btn-primary btn-sm mt-2">Retry</button>
    </div>
  `;
  document.body.appendChild(overlay);
  const retryBtn = document.getElementById('offline-retry-btn');
  if (retryBtn) {
    retryBtn.addEventListener('click', () => {
      // Show loading state on button
      retryBtn.disabled = true;
      retryBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Retrying...';
      
      // Attempt reload regardless of navigator.onLine (more reliable)
      window.location.reload();
    });
  }
};

const setupTauriNavigation = () => {
  if (!icpState.isTauri) return;
  if (document.getElementById('tauri-nav-bar')) return;
  
  const navBar = document.createElement('div');
  navBar.id = 'tauri-nav-bar';
  navBar.className = 'tauri-nav-bar';
  navBar.innerHTML = `
    <div class="tauri-nav-controls">
      <button id="tauri-back-btn" class="tauri-nav-btn" title="Back">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
          <path fill-rule="evenodd" d="M15 8a.5.5 0 0 0-.5-.5H2.707l3.147-3.146a.5.5 0 1 0-.708-.708l-4 4a.5.5 0 0 0 0 .708l4 4a.5.5 0 0 0 .708-.708L2.707 8.5H14.5A.5.5 0 0 0 15 8z"/>
        </svg>
      </button>
      <button id="tauri-forward-btn" class="tauri-nav-btn" title="Forward">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
          <path fill-rule="evenodd" d="M1 8a.5.5 0 0 1 .5-.5h11.793l-3.147-3.146a.5.5 0 0 1 .708-.708l4 4a.5.5 0 0 1 0 .708l-4 4a.5.5 0 0 1-.708-.708L13.293 8.5H1.5A.5.5 0 0 1 1 8z"/>
        </svg>
      </button>
      <button id="tauri-reload-btn" class="tauri-nav-btn" title="Reload">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
          <path fill-rule="evenodd" d="M8 3a5 5 0 1 0 4.546 2.914.5.5 0 0 1 .908-.417A6 6 0 1 1 8 2v1z"/>
          <path d="M8 4.466V.534a.25.25 0 0 1 .41-.192l2.36 1.966c.12.1.12.284 0 .384L8.41 4.658a.25.25 0 0 1-.41-.192z"/>
        </svg>
      </button>
    </div>
    <div class="tauri-nav-title">${document.title}</div>
  `;
  
  // Prepend to body so it stays at the top
  document.body.prepend(navBar);
  
  // Event listeners
  document.getElementById('tauri-back-btn').addEventListener('click', () => window.history.back());
  document.getElementById('tauri-forward-btn').addEventListener('click', () => window.history.forward());
  document.getElementById('tauri-reload-btn').addEventListener('click', () => window.location.reload());
  
  // Update title dynamically
  const observer = new MutationObserver(() => {
    const titleEl = document.querySelector('.tauri-nav-title');
    if (titleEl) titleEl.innerText = document.title;
  });
  observer.observe(document.querySelector('title'), { childList: true });
};

const hideOfflineOverlay = () => {
  const el = document.getElementById('offline-overlay');
  if (el) el.remove();
};

window.addEventListener('offline', () => {
  showOfflineToast();
  showOfflineOverlay();
});
window.addEventListener('online', () => {
  hideOfflineToast();
  hideOfflineOverlay();
  // Attempt to reload if they were on a blank page or just to refresh
  window.location.reload();
});

// Initial check
if (!navigator.onLine) {
  showOfflineToast();
  showOfflineOverlay();
}

// --- PWA & App Download Banner ---

/**
 * Injects the App Download Banner and handle visibility logic
 */
function handleAppPromotion() {
  const bannerKey = 'icp_app_banner_dismissed';
  const path = window.location.pathname;
  
  // Exclude admin/portal pages from promotion
  const isAdminPage = path.includes('admin') || path.includes('portal');
  if (isAdminPage) {
    console.log('[App Promotion] Admin/Portal page detected, skipping promotion.');
    return;
  }

  const dismissedTime = localStorage.getItem(bannerKey);
  const urlParams = new URLSearchParams(window.location.search);
  const forceShow = urlParams.has('show_banner');

  // 1. Footer Promotion Injection
  const injectFooterPromotion = () => {
    // Small delay to ensure DOM is fully ready and other scripts haven't cleared body
    setTimeout(() => {
      // Only allow on CTA page
      const path = window.location.pathname;
      const isCtaPage = path.toLowerCase().includes('cta');
      
      if (!isCtaPage) {
        console.log('[App Promotion] Not a CTA page, skipping footer injection. Path:', path);
        return;
      }

      console.log('[App Promotion] CTA page detected, injecting footer promotion.');

      // Check if already injected
      if (document.getElementById('footer-app-promotion')) return;

      const promotionDiv = document.createElement('div');
      promotionDiv.id = 'footer-app-promotion';
      promotionDiv.className = 'container mt-4 mb-5 animate-fade-in';
      promotionDiv.innerHTML = `
        <div class="card border-0 glass-card p-4 text-center overflow-hidden position-relative shadow-lg rounded-4">
          <div class="position-absolute top-0 start-0 w-100 h-100 bg-primary opacity-5" style="z-index: -1;"></div>
          <div class="row align-items-center g-3">
            <div class="col-lg-6 text-lg-start">
              <h5 class="fw-bold mb-1">Take ICP with you!</h5>
              <p class="text-secondary small mb-lg-0">Get the official apps for your devices. <span class="opacity-50">(iOS & MacOS in development)</span></p>
            </div>
            <div class="col-lg-6 text-lg-end">
              <div class="d-flex flex-wrap justify-content-center justify-content-lg-end gap-3">
                <a href="/downloads/apk/app-release.apk" class="btn btn-primary rounded-pill px-4 py-2 fw-bold shadow-sm d-flex align-items-center gap-2">
                  <i class="bi bi-android2 fs-5"></i> 
                  <div class="text-start" style="line-height: 1.1;">
                    <span class="smaller d-block opacity-75 fw-normal">Download</span>
                    <span>Android APK</span>
                  </div>
                </a>
                <a href="/downloads/msi/installer" class="btn btn-primary rounded-pill px-4 py-2 fw-bold shadow-sm d-flex align-items-center gap-2" style="background: linear-gradient(135deg, #0078d4, #005a9e); border: none;">
                  <i class="bi bi-windows fs-5"></i> 
                  <div class="text-start" style="line-height: 1.1;">
                    <span class="smaller d-block opacity-75 fw-normal">Download</span>
                    <span>Windows MSI</span>
                  </div>
                </a>
                <div class="w-100 d-lg-none"></div>
                <button onclick="showAppModal()" class="btn btn-link text-secondary text-decoration-none small px-0">Other OS?</button>
              </div>
            </div>
          </div>
        </div>
      `;

      // Prefer appending to body to avoid Vue overwriting the #app container
      // and ensuring it's at the very bottom of the page
      document.body.appendChild(promotionDiv);
    }, 100);
  };

  injectFooterPromotion();
  injectAppPopUpBanner();
}

/**
 * Inject a fixed bottom pop-up banner for the app (Specifically for CTA page)
 */
function injectAppPopUpBanner() {
  const path = window.location.pathname;
  const isCtaPage = path.toLowerCase().includes('cta');
  
  if (!isCtaPage) return;

  // Use a timeout to ensure it appears after a brief delay
  setTimeout(() => {
    if (document.getElementById('app-popup-banner')) return;

    const banner = document.createElement('div');
    banner.id = 'app-popup-banner';
    banner.className = 'app-banner'; // Use existing CSS class
    banner.style.display = 'block';
    banner.innerHTML = `
      <div class="container-fluid px-4 d-flex align-items-center justify-content-between">
        <div class="d-flex align-items-center gap-3">
          <div class="text-primary fs-4 banner-icon">
            <i class="bi bi-phone-vibrate"></i>
          </div>
          <div class="text-start">
            <div class="fw-bold text-white small">Experience ICP Everywhere</div>
            <div class="smaller text-secondary">Download our official apps for Windows and Android. <span class="opacity-50">iOS/Mac coming soon.</span></div>
          </div>
        </div>
        <div class="d-flex align-items-center gap-3">
          <button onclick="showAppModal()" class="btn btn-primary btn-sm rounded-pill px-3 fw-bold shadow-sm banner-get-btn">Get App</button>
          <button onclick="document.getElementById('app-popup-banner').remove()" class="btn-close btn-close-white small" aria-label="Close"></button>
        </div>
      </div>
    `;
    
    // Add specific styles for the content if needed (to match image)
    const style = document.createElement('style');
    style.innerHTML = `
      #app-popup-banner .container {
        max-width: 900px;
      }
      #app-popup-banner .smaller {
        font-size: 0.75rem;
      }
      @media (max-width: 768px) {
        #app-popup-banner .smaller {
          display: none;
        }
      }
    `;
    document.head.appendChild(style);
    document.body.appendChild(banner);
  }, 500);
}

/**
 * Show a universal modal for all app downloads
 */
function showAppModal() {
  const content = `
    <div class="text-start">
      <div class="mb-4">
        <h6 class="fw-bold text-primary mb-2">Available Now</h6>
        <div class="d-grid gap-2">
          <a href="/downloads/apk/app-release.apk" class="btn btn-outline-light d-flex align-items-center justify-content-between p-3 rounded-4">
            <div class="d-flex align-items-center gap-3">
              <i class="bi bi-android2 fs-4 text-success"></i>
              <div class="text-start">
                <div class="fw-bold">Android APK</div>
                <div class="smaller text-secondary">Optimized for mobile screens</div>
              </div>
            </div>
            <i class="bi bi-download"></i>
          </a>
          <a href="/downloads/msi/installer" class="btn btn-outline-light d-flex align-items-center justify-content-between p-3 rounded-4">
            <div class="d-flex align-items-center gap-3">
              <i class="bi bi-windows fs-4 text-info"></i>
              <div class="text-start">
                <div class="fw-bold">Windows Installer (MSI)</div>
                <div class="smaller text-secondary">Native desktop experience</div>
              </div>
            </div>
            <i class="bi bi-download"></i>
          </a>
        </div>
      </div>

      <div>
        <h6 class="fw-bold text-secondary mb-2 opacity-50">Coming Soon</h6>
        <div class="p-3 border border-secondary border-opacity-10 rounded-4 bg-light shadow-sm">
          <div class="d-flex align-items-center gap-3 mb-2">
            <i class="bi bi-apple fs-4 text-dark"></i>
            <div class="fw-bold text-dark">iOS & MacOS</div>
          </div>
          <p class="smaller text-dark mb-0 fw-medium">We are currently developing native apps for Apple devices. For now, please use the <strong>Web Version</strong> or <strong>Add to Home Screen</strong> on Safari.</p>
        </div>
      </div>
    </div>
  `;

  Swal.fire({
    title: 'Download ICP App',
    html: content,
    showConfirmButton: false,
    showCloseButton: true,
    background: '#0f172a',
    color: '#fff',
    width: '450px'
  });
}

// Expose IOS Hint helper
window.icp.showIOSHint = () => showAppModal('iOS');

/**
 * Inject promotion into mobile sidebar
 */
function injectSidebarPromotion() {
  const path = window.location.pathname;
  // Exclude admin pages
  if (path.includes('admin') || path.includes('portal')) {
    return;
  }
  
  const sidebarNav = document.querySelector('.sidebar-nav');
  if (!sidebarNav || document.getElementById('sidebar-app-promotion')) return;

  const promoDiv = document.createElement('div');
  promoDiv.id = 'sidebar-app-promotion';
  promoDiv.className = 'sidebar-promo-mini';
  promoDiv.innerHTML = `
    <div class="promo-title">Get the App</div>
    <p class="promo-text">Practice anywhere with our mobile app.</p>
    <button onclick="showAppModal()" class="btn btn-primary btn-sm w-100 rounded-pill mt-2 py-1 shadow-sm" style="font-size: 0.7rem;">
      <i class="bi bi-download me-1"></i>Download
    </button>
  `;
  sidebarNav.appendChild(promoDiv);
}

/**
 * Handle Offline Detection and UI
 */
function setupOfflineDetection() {
  const overlay = document.createElement('div');
  overlay.id = 'offline-overlay';
  overlay.className = 'offline-overlay';
  overlay.innerHTML = `
    <div class="offline-icon"><i class="bi bi-wifi-off"></i></div>
    <h2 class="offline-title">You're Offline</h2>
    <p class="offline-message">It looks like you've lost your internet connection. Some features of ICP may be limited until you're back online.</p>
    <button onclick="window.location.reload()" class="btn btn-primary offline-retry-btn">
      <i class="bi bi-arrow-clockwise me-2"></i> Try Reconnecting
    </button>
  `;
  document.body.appendChild(overlay);

  const toggleOfflineUI = () => {
    if (navigator.onLine) {
      overlay.classList.remove('active');
    } else {
      overlay.classList.add('active');
    }
  };

  window.addEventListener('online', toggleOfflineUI);
  window.addEventListener('offline', toggleOfflineUI);
  
  // Initial check
  toggleOfflineUI();
}

// Initialize everything on load
document.addEventListener('DOMContentLoaded', () => {
  // 0. Inject PWA Manifest
  if (!document.querySelector('link[rel="manifest"]')) {
    const link = document.createElement('link');
    link.rel = 'manifest';
    link.href = '/manifest.json';
    document.head.appendChild(link);
  }

  // 1. Register Service Worker for PWA (with versioning to force update)
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js?v=2').then(reg => {
      console.log('ICP Service Worker registered (v2)');
      
      // Check for updates
      reg.onupdatefound = () => {
        const installingWorker = reg.installing;
        installingWorker.onstatechange = () => {
          if (installingWorker.state === 'installed' && navigator.serviceWorker.controller) {
            console.log('New content available; please refresh.');
            // Optionally show a "Refresh to update" toast here
          }
        };
      };
    }).catch(err => {
      console.warn('SW registration failed:', err);
    });
  }

  setupOfflineDetection();
  handleAppPromotion();
  injectSidebarPromotion();
  
  // 3. Setup Tauri Navigation
  setupTauriNavigation();
});

