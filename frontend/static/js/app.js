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
  
  setToken(t) {
    if (!t || t === "undefined" || t === "null") return;
    this.token = t;
    localStorage.setItem("token", t);
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
      localStorage.removeItem('session_expiry_user');
      localStorage.removeItem('session_expiry_admin');
      localStorage.removeItem('interview_voice_gender');
      
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

document.addEventListener("htmx:configRequest", function (evt) {
  if (state.token) evt.detail.headers["Authorization"] = "Bearer " + state.token;
});

document.addEventListener("htmx:responseError", function (evt) {
  if (evt.detail.xhr.status === 401) {
    state.clearToken();
    if (window.location.pathname !== '/' && !window.location.pathname.includes('login.html') && !window.location.pathname.includes('register.html') && !window.location.pathname.includes('cta.html')) {
        const is_admin_page = window.location.pathname.includes('admin');
        window.location.href = is_admin_page ? '/static/pages/admin.html' : '/static/pages/login.html';
    }
  }
});

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
window.icp.state = state;
window.icp.logout = logout;
window.icp.decodeToken = decodeToken;

// Global Startup Check: Clear sessions if server has restarted
(function checkStartup() {
  fetch('/api/meta/startup_id')
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
