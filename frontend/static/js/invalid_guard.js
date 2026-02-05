// Strict invalid text guard module
// Exposes global InvalidGuard for interview.js to use
(function () {
  const state = {
    attempts: parseInt(localStorage.getItem('invalid_attempts') || '0'),
    threshold: 3
  };
  
  function isInvalid(text) {
    const s = (text || '').trim().toLowerCase();
    if (!s) return true;
    if (s.length < 3) return true;
    
    const alpha = (s.match(/[a-z]/g) || []).length;
    const digits = (s.match(/[0-9]/g) || []).length;
    const nonWord = (s.match(/[^a-z0-9\s]/g) || []).length;
    const vowels = (s.match(/[aeiou]/g) || []).length;
    
    const alphaRatio = alpha / s.length;
    const nonWordRatio = nonWord / s.length;
    const vowelRatio = alpha > 0 ? vowels / alpha : 0;
    
    // Check for repeated characters (e.g., "aaaaa")
    const repeatedChar = /(.)\1{3,}/.test(s);
    
    // Check for excessive symbols (e.g., "!!!!!!!!!!")
    const excessiveSymbols = /[^a-z0-9\s]{3,}/.test(s);
    
    // Check for consonant clusters (e.g., "bcdfghj")
    // 6 or more consonants in a row is almost certainly gibberish in English
    const consonantCluster = /[^aeiou\s0-9]{6,}/.test(s);
    
    // Check for basic word structure
    // A "word" here is 2+ letters with at least one vowel if it's longer than 3 chars
    const hasWords = /\b[a-z]{2,}\b/.test(s);
    
    // Heuristics
    if (nonWordRatio > 0.20) return true; // More than 20% symbols
    if (alphaRatio < 0.4 && digits > alpha) return true; // Mostly numbers
    if (s.length < 10 && nonWordRatio > 0) return true; // Short string with symbols
    
    // Gibberish detection for long strings (like the user provided)
    if (alpha > 10) {
      if (vowelRatio < 0.20) return true; // Very few vowels (English is usually >30%)
      if (consonantCluster) return true;   // Long strings of consonants
    }
    
    if (repeatedChar) return true; // "aaaaa"
    if (excessiveSymbols) return true; // "!!!!!"
    if (!hasWords && s.length > 3) return true; // No actual words
    
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
