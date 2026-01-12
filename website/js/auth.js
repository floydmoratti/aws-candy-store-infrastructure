/**
 * auth.js
 * Centralized client-side authentication logic for Cognito Hosted UI
 * - Builds Sign In / Sign Up URLs
 * - Handles Sign Out
 * - Tracks authentication state
 * - Dynamically updates navbar UI
 */

const DEV_MOCK_AUTH = false; // <-- set to true for local testing only


(function () {
  "use strict";

  // ---------------------------------------------------------------------------
  // Guards
  // ---------------------------------------------------------------------------
  if (!window.APP_CONFIG) {
    console.error("APP_CONFIG not loaded. Make sure config.js is included first.");
    return;
  }

  const {
    COGNITO_DOMAIN,
    CLIENT_ID,
    REDIRECT_URI
  } = window.APP_CONFIG;

  if (!COGNITO_DOMAIN || !CLIENT_ID || !REDIRECT_URI) {
    console.error("Missing required Cognito configuration values.");
    return;
  }

  // ---------------------------------------------------------------------------
  // Auth State
  // ---------------------------------------------------------------------------
  function isAuthenticated() {
    if (DEV_MOCK_AUTH) return true;
    return !!sessionStorage.getItem("id_token");
  }

  // ---------------------------------------------------------------------------
  // OAuth URL Builder
  // ---------------------------------------------------------------------------
  function buildOAuthUrl(path) {
    const params = new URLSearchParams({
      client_id: CLIENT_ID,
      response_type: "code",
      scope: "email openid profile",
      redirect_uri: REDIRECT_URI
    });

    return `${COGNITO_DOMAIN}/${path}?${params.toString()}`;
  }

  // ---------------------------------------------------------------------------
  // UI Setup
  // ---------------------------------------------------------------------------
  function setupAuthLinks() {
    const signInBtn = document.getElementById("signin-btn");
    if (signInBtn) {
      signInBtn.setAttribute("href", buildOAuthUrl("login"));
    }

    const signUpBtn = document.getElementById("signup-btn");
    if (signUpBtn) {
      signUpBtn.setAttribute("href", buildOAuthUrl("signup"));
    }
  }

  function updateAuthUI() {
    const anonSection = document.getElementById("auth-anon");
    const userSection = document.getElementById("auth-user");

    if (!anonSection || !userSection) return;

    if (isAuthenticated()) {
      anonSection.classList.add("d-none");
      userSection.classList.remove("d-none");
    } else {
      userSection.classList.add("d-none");
      anonSection.classList.remove("d-none");
    }
  }

  // ---------------------------------------------------------------------------
  // Sign Out
  // ---------------------------------------------------------------------------
  function setupSignOut() {
    const signOutBtn = document.getElementById("signout-btn");
    if (!signOutBtn) return;

    signOutBtn.addEventListener("click", (e) => {
      e.preventDefault();

      // Clear local session
      sessionStorage.clear();

      // Redirect through Cognito logout
      const params = new URLSearchParams({
        client_id: CLIENT_ID,
        logout_uri: window.location.origin
      });

      window.location.href = `${COGNITO_DOMAIN}/logout?${params.toString()}`;
    });
  }

  // ---------------------------------------------------------------------------
  // Init
  // ---------------------------------------------------------------------------
  document.addEventListener("DOMContentLoaded", () => {
    setupAuthLinks();
    setupSignOut();
    updateAuthUI();
  });

})();
