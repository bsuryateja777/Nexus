import { PublicClientApplication } from "@azure/msal-browser"

/**
 * MSAL Configuration for Azure Entra ID OAuth2
 *
 * Environment variables required:
 * - VITE_ENTRA_CLIENT_ID: Application (client) ID from Entra ID app registration
 * - VITE_ENTRA_AUTHORITY: Azure Entra ID authority URL (e.g., https://login.microsoftonline.com/tenant-id)
 * - VITE_ENTRA_REDIRECT_URI: Redirect URI after login (e.g., http://localhost:5173/auth/callback)
 */

export const authConfig = {
  auth: {
    clientId: import.meta.env.VITE_ENTRA_CLIENT_ID || "",
    authority: import.meta.env.VITE_ENTRA_AUTHORITY || "",
    redirectUri: import.meta.env.VITE_ENTRA_REDIRECT_URI || "http://localhost:5173/auth/callback",
    postLogoutRedirectUri: import.meta.env.VITE_ENTRA_REDIRECT_URI || "http://localhost:5173",
    navigateToLoginRequestUrl: true,
  },
  cache: {
    cacheLocation: "localStorage" as const,
    storeAuthStateInCookie: false,
  },
  system: {
    allowNativeBroker: false,
    loggerOptions: {
      loggerCallback: (level: any, message: string, piiEnabled: boolean) => {
        if (piiEnabled) {
        }
      },
      piiLoggingEnabled: false,
      logLevel: "Warning" as any,
    },
  },
}

/**
 * For basic OIDC authentication, we only need openid scope
 * This tells Entra ID to return an ID token with user info
 */
export const loginRequest = {
  scopes: ["openid", "profile", "email"],
}

export const graphApiScopes = {
  scopes: ["https://graph.microsoft.com/.default"],
}

/**
 * Initialize MSAL Public Client Application
 * This handles all OAuth2/OIDC flows with Azure Entra ID
 */
export const msalInstance = new PublicClientApplication(authConfig)
