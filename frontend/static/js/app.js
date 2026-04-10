// Immediate Global Sidebar Logic (defined early to prevent race conditions)
window.handleMobileMenu = function() {
  console.log("handleMobileMenu called");
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
    console.log("Sidebar active state:", !isActive);
  } else {
    console.error("Mobile sidebar elements not found:", { sidebar: !!sidebar, overlay: !!overlay });
  }
};

window.setupSessionTimer = function(vueInstance) {
  const checkTimer = () => {
    const expiration = localStorage.getItem('token_expiration');
    if (expiration) {
      const now = Math.floor(Date.now() / 1000);
      const timeLeft = expiration - now;
      if (timeLeft <= 0) {
        // Clear resume builder session when token expires
        localStorage.removeItem('resume_builder_session');
        localStorage.removeItem('resume_builder_imported');
        window.logout();
        return;
      }
      vueInstance.sessionTime = timeLeft;
    }
  };
  setInterval(checkTimer, 1000);
  checkTimer();
};

const state = {
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

if (state.token === "undefined" || state.token === "null") {
  state.clearToken();
}

// Setup Axios Interceptors
if (window.axios) {
  // Request Interceptor
  axios.interceptors.request.use(function (config) {
    // Only add token if it exists and we're NOT hitting the login endpoint
    if (state.token && !config.url.includes('/api/auth/login')) {
      config.headers['Authorization'] = 'Bearer ' + state.token;
    }
    
    // Prepend API base URL if in Tauri and request is for /api
    if (state.isTauri && config.url.startsWith('/api')) {
      const originalPath = config.url;
      config.url = state.apiBase + originalPath;
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
      state.clearToken();
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
      }
    }
    return Promise.reject(error);
  });
}

function logout() {
  const currentPath = window.location.pathname;
  const is_admin_page = currentPath.includes('icp-admin-');
  state.clearToken();
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
  const fullUrl = state.apiBase + p;
  // Log API calls in Tauri for easier debugging
  if (state.isTauri) {
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
    console.log("Tauri Detected:", state.isTauri);
    console.log("Current API Base:", state.apiBase);
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
  state,
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
  if (!state.isTauri) return;
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

// Ensure Tauri navigation is setup after DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', setupTauriNavigation);
} else {
  setupTauriNavigation();
}
