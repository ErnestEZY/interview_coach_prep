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
      const currentPath = window.location.pathname;
      const isPublicPage = 
        currentPath === '/' || 
        currentPath.includes('login.html') || 
        currentPath.includes('register.html') || 
        currentPath.includes('cta.html') || 
        currentPath.includes('reset_password.html') || 
        currentPath.includes('forgot_password.html');

      if (!isPublicPage) {
        const is_admin_page = currentPath.includes('admin');
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
      confirmButtonColor: '#fc0038'
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
