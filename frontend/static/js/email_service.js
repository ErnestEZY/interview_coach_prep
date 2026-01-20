// Global variable to store config
let emailjsConfig = null;

/**
 * Fetches EmailJS configuration from the backend
 */
async function fetchEmailJSConfig() {
    if (emailjsConfig) return emailjsConfig;
    try {
        const response = await fetch('/api/auth/config');
        if (!response.ok) throw new Error('Failed to fetch config');
        emailjsConfig = await response.json();
        
        // Initialize EmailJS with the public key from backend
        emailjs.init({
            publicKey: emailjsConfig.emailjs_public_key,
        });
        
        return emailjsConfig;
    } catch (error) {
        console.error("Error loading EmailJS config:", error);
        return null;
    }
}

/**
 * Sends a verification OTP email via EmailJS
 * @param {string} email - Recipient email address
 * @param {string} otp - The 6-digit passcode
 * @param {string} expiryTime - formatted time string (e.g. "14:30")
 * @returns {Promise<{success: boolean, error?: string}>}
 */
async function sendVerificationEmail(email, otp, expiryTime) {
    const config = await fetchEmailJSConfig();
    if (!config) {
        return { success: false, error: "Could not load EmailJS configuration from server." };
    }

    // Template parameters based on the template:
    // {{passcode}}, {{time}}, and {{email}} are used in the message/routing
    const templateParams = {
        email: email,
        to_email: email,
        passcode: otp,
        time: expiryTime
    };

    try {
        const response = await emailjs.send(
            config.emailjs_service_id,
            config.emailjs_template_id,
            templateParams,
            config.emailjs_public_key
        );
        console.log("EmailJS Success:", response.status, response.text);
        return { success: true };
    } catch (error) {
        console.error("EmailJS Error:", error);
        // Extract a meaningful error message if possible
        const errorMsg = error?.text || error?.message || JSON.stringify(error) || "Unknown EmailJS error";
        return { success: false, error: errorMsg };
    }
}

/**
 * Sends a resume status notification email via Admin EmailJS
 * @param {string} email - Recipient email address
 * @param {string} message - The notification message
 * @returns {Promise<{success: boolean, error?: string}>}
 */
async function sendAdminNotificationEmail(email, message) {
    const config = await fetchEmailJSConfig();
    if (!config || !config.admin_emailjs_public_key) {
        return { success: false, error: "Could not load Admin EmailJS configuration from server." };
    }

    const templateParams = {
        admin_email: email,
        to_email: email,
        message: message
    };

    try {
        const response = await emailjs.send(
            config.admin_emailjs_service_id,
            config.admin_emailjs_template_id,
            templateParams,
            config.admin_emailjs_public_key
        );
        console.log("Admin EmailJS Success:", response.status, response.text);
        return { success: true };
    } catch (error) {
        console.error("Admin EmailJS Error:", error);
        const errorMsg = error?.text || error?.message || JSON.stringify(error) || "Unknown EmailJS error";
        return { success: false, error: errorMsg };
    }
}

// Start fetching config immediately
fetchEmailJSConfig();
