// Global variable to store config
let emailjsConfig = null;

/**
 * Fetches EmailJS configuration from the backend
 */
async function fetchEmailJSConfig() {
    if (emailjsConfig) return emailjsConfig;
    try {
        const response = await fetch(icp.apiUrl('/api/auth/config'));
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
        const errorMsg = (typeof error?.text === 'string' && error.text.trim())
            ? error.text
            : (typeof error?.message === 'string' && error.message.trim())
                ? error.message
                : "Email service error. Please try again later.";
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
        const errorMsg = (typeof error?.text === 'string' && error.text.trim())
            ? error.text
            : (typeof error?.message === 'string' && error.message.trim())
                ? error.message
                : "Email service error. Please try again later.";
        return { success: false, error: errorMsg };
    }
}

/**
 * Sends a security alert email via Admin Alert EmailJS
 * @param {string[]} adminEmails - Array of admin email addresses
 * @param {string} offenderEmail - The email of the account that triggered the alert
 * @param {string} ipAddress - The IP address of the attempt
 * @param {string} reason - The reason for the alert
 * @returns {Promise<{success: boolean, results: any[]}>}
 */
async function sendSecurityAlertEmail(adminEmails, offenderEmail, ipAddress, reason) {
    const config = await fetchEmailJSConfig();
    if (!config || !config.admin_alert_emailjs_public_key) {
        console.error("Could not load Admin Alert EmailJS configuration.");
        return { success: false, error: "Configuration missing" };
    }

    const results = [];
    const timestamp = new Date().toLocaleString('en-GB', { timeZone: 'Asia/Kuala_Lumpur' });
    
    for (const adminEmail of adminEmails) {
        const templateParams = {
            email_alert: adminEmail,
            to_email: adminEmail,
            offender_email: offenderEmail,
            admin_message: `Security Alert: Suspicious Admin Activity\n\nReason: ${reason}\nOffender: ${offenderEmail}\nIP Address: ${ipAddress}\nTimestamp: ${timestamp}`,
        };

        try {
            const response = await emailjs.send(
                config.admin_alert_emailjs_service_id,
                config.admin_alert_emailjs_template_id,
                templateParams,
                config.admin_alert_emailjs_public_key
            );
            results.push({ email: adminEmail, success: true, response });
        } catch (error) {
            console.error(`Failed to send security alert to ${adminEmail}:`, error);
            results.push({ email: adminEmail, success: false, error });
        }
    }

    return { success: results.some(r => r.success), results };
}

// Start fetching config immediately
fetchEmailJSConfig();
