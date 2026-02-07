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

    const prodUrl = 'https://interview-coach-prep.onrender.com';
    
    // In Tauri dev mode (running on localhost), we might want local backend.
    // However, to ensure "it works like production", we'll default to production
    // unless the user has specifically enabled "Local Mode" or a local backend is detected
    // and they are in a dev environment.
    
    const isDev = window.location.protocol === 'http:' || window.location.protocol === 'https:';
    const isLocalHost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
    
    // If we're in dev mode AND the user has set a flag to use local, or we want to be helpful:
    if (isDev && isLocalHost && localStorage.getItem('ICP_LOCAL_MODE') === 'true') {
      return 'http://127.0.0.1:5000';
    }
    
    // Default to production so it "just works" with real data
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
    if (state.token) {
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
    if (error.response && error.response.status === 401) {
      state.clearToken();
      if (window.location.pathname !== '/' && !window.location.pathname.includes('login.html') && !window.location.pathname.includes('register.html') && !window.location.pathname.includes('cta.html')) {
        const is_admin_page = window.location.pathname.includes('admin');
        window.location.href = is_admin_page ? '/static/pages/admin.html' : '/static/pages/login.html';
      }
    }
    return Promise.reject(error);
  });
}

function logout() {
  state.clearToken();
  window.location.href = "/";
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
    console.log("Local mode enabled. Reloading...");
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
      footer: '<div class="text-center w-100"><p class="text-secondary small mb-1"><i class="bi bi-clock-history me-1"></i>Arrival time: 4-5 minutes (Gmail processing)</p><p class="text-secondary small mb-0"><i class="bi bi-info-circle me-1"></i>Check your <b>Spam/Junk</b> folder</p></div>',
      confirmButtonText: 'Back to Login',
      confirmButtonColor: '#fc0038',
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
      confirmButtonColor: '#fc0038'
    });
  }
};
// Attach to window.icp for global access
Object.assign(window.icp, {
  state,
  decodeToken,
  apiUrl,
  logout,
  showTerms: () => {
    Swal.fire({
      title: 'Terms & Conditions',
      html: `
        <div class="text-start small overflow-auto px-2" style="max-height: 400px; line-height: 1.6;">
          <h6 class="fw-bold">1. Acceptance of Terms</h6>
          <p>By using ICP (Interview Coach Prep), you agree to be bound by these terms and conditions. If you do not agree, please do not use the service.</p>
          <h6 class="fw-bold">2. Service Description</h6>
          <p>ICP provides AI-driven interview coaching, resume analysis, and job search tools to help users prepare for professional interviews.</p>
          <h6 class="fw-bold">3. User Responsibility</h6>
          <p>You are responsible for maintaining the confidentiality of your account and for all activities that occur under your account.</p>
          <h6 class="fw-bold">4. Content & Privacy</h6>
          <p>Resumes and interview responses provided are processed by AI to give feedback. Your data is handled as described in our Privacy Policy.</p>
          <h6 class="fw-bold">5. Limitations</h6>
          <p>The feedback provided by the AI is for preparation purposes only and does not guarantee job placement or success.</p>
        </div>
      `,
      confirmButtonText: 'Close',
      confirmButtonColor: '#fc0038'
    });
  },
  showPrivacy: () => {
    Swal.fire({
      title: 'Privacy Policy',
      html: `
        <div class="text-start small overflow-auto px-2" style="max-height: 400px; line-height: 1.6;">
          <h6 class="fw-bold">1. Information We Collect</h6>
          <p>We collect your name, email address, and any professional documents (resumes) or interview responses you provide.</p>
          <h6 class="fw-bold">2. How We Use Information</h6>
          <p>We use your data to generate personalized AI feedback, track your progress, and improve our coaching algorithms.</p>
          <h6 class="fw-bold">3. Data Security</h6>
          <p>We implement industry-standard security measures to protect your personal information from unauthorized access.</p>
          <h6 class="fw-bold">4. Third-Party Processing</h6>
          <p>We use Gemini AI for analysis and EmailJS for email notifications. Your data is only shared with these services for the purpose of providing ICP features.</p>
          <h6 class="fw-bold">5. Data Retention</h6>
          <p>We retain your data as long as your account is active. You may request account deletion at any time.</p>
        </div>
      `,
      confirmButtonText: 'Close',
      confirmButtonColor: '#fc0038'
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
          if (window.location.pathname !== '/' && !window.location.pathname.includes('login.html') && !window.location.pathname.includes('register.html')) {
            window.location.href = "/";
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
