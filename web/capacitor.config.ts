import type { CapacitorConfig } from "@capacitor/cli"

const config: CapacitorConfig = {
  appId: "com.aca.newsletter",
  appName: "ACA Newsletter",
  webDir: "dist",
  server: {
    // In dev mode, set this to the Vite dev server URL for live reload
    // url: "http://localhost:5173",
    // cleartext: true,
    androidScheme: "https",
  },
  plugins: {
    SplashScreen: {
      launchShowDuration: 2000,
      launchAutoHide: true,
      backgroundColor: "#0f172a",
      showSpinner: false,
    },
    PushNotifications: {
      presentationOptions: ["badge", "sound", "alert"],
    },
  },
  ios: {
    // App Group for Share Extension IPC
    // Configure in Xcode: main app + ShareExtension targets
    // Group ID: group.com.aca.newsletter
  },
}

export default config
