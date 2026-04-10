// Strict invalid text guard module
// Exposes global InvalidGuard for interview.js to use
(function () {
  const state = {
    attempts: parseInt(localStorage.getItem('invalid_attempts') || '0'),
    threshold: 3
  };
  
  function isInvalid(text) {
    // Centralize gibberish detection to app.js logic if available
    if (window.icp && window.icp.isGibberish) {
      return window.icp.isGibberish(text);
    }

    const s = (text || '').trim().toLowerCase();
    if (!s || s.length < 3) return true;

    const alpha = (s.match(/[a-z]/g) || []).length;
    const digits = (s.match(/[0-9]/g) || []).length;
    const spaces = (s.match(/\s/g) || []).length;
    const nonWord = (s.match(/[^a-z0-9\s]/g) || []).length;
    const tokens = s.split(/\s+/);
    const wordCount = tokens.length;

    // Sentence exemption
    if (wordCount >= 3 && spaces >= 2 && alpha > 10) {
      if (/(.)\1{6,}/.test(s)) return true;
      if (nonWord / s.length > 0.45) return true;
      return false;
    }

    const alphaRatio = alpha / s.length;
    const nonWordRatio = nonWord / s.length;
    const repeatedChar = /(.)\1{3,}/.test(s);
    const hasWords = /\b[a-z]{2,}\b/.test(s);
    
    if (nonWordRatio > 0.35) return true;
    if (alphaRatio < 0.3 && digits > alpha) return true;
    if (repeatedChar) return true;
    if (!hasWords && alpha > 0 && s.length > 5) return true;
    
    return false;
  }
  
  function increment() {
    state.attempts += 1;
    try { localStorage.setItem('invalid_attempts', String(state.attempts)); } catch (_) {}
  }
  
  function reset() {
    state.attempts = 0;
    try { localStorage.removeItem('invalid_attempts'); } catch (_) {}
  }
  
  function getAttempts() {
    return state.attempts;
  }
  
  function setThreshold(n) {
    state.threshold = Math.max(1, parseInt(n || 3));
  }
  
  async function endSession(app) {
    try {
      const sid = app.sessionId;
      if (app.interviewTimerId) clearInterval(app.interviewTimerId);
      app.interviewTimerId = null;
      if (app.inactivityTimer) clearTimeout(app.inactivityTimer);
      app.inactivityTimer = null;
      app.stopCamera();
      const endMsg = "Session ended due to repeated invalid responses. Readiness Score: N/A.";
      app.transcript.push({ role: 'ai', content: endMsg });
      app.readinessScore = null;
      app.feedbackExplanation = "We received multiple responses that looked like random characters or non-words. The session is now closed. Readiness Score is N/A.";
      try { if (app.speaker) app.speak(app.feedbackExplanation); } catch (_) {}
      // Notify backend of end (no AI reply triggered)
      if (sid) {
        try { await axios.post(window.icp.apiUrl(`/api/interview/${sid}/end`)); } catch (_) {}
      }
      app.interviewAttempts = Math.max(0, app.interviewAttempts - 1);
      app.sessionId = null;
      app.currentQuestion = 0;
      try { localStorage.removeItem('interview_session_id'); } catch (_) {}
      reset();
    } catch (e) {
      console.error('InvalidGuard endSession error', e);
    }
  }
  
  window.InvalidGuard = {
    isInvalid,
    increment,
    reset,
    getAttempts,
    setThreshold,
    endSession
  };
})();
