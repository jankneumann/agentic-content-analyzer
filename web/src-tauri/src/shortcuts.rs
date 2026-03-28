use tauri::Manager;
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut};

pub fn setup_shortcuts(app: &tauri::App) -> Result<(), Box<dyn std::error::Error>> {
    // Cmd+Shift+Space (macOS) / Ctrl+Shift+Space (Windows/Linux)
    let shortcut = Shortcut::new(
        Some(if cfg!(target_os = "macos") {
            Modifiers::SUPER | Modifiers::SHIFT
        } else {
            Modifiers::CONTROL | Modifiers::SHIFT
        }),
        Code::Space,
    );

    let app_handle = app.handle().clone();

    match app.global_shortcut().on_shortcut(shortcut, move |_app, _shortcut, event| {
        if event == tauri_plugin_global_shortcut::ShortcutState::Pressed {
            if let Some(window) = app_handle.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
                let _ = window.eval("window.__TAURI_VOICE_TOGGLE__ = Date.now()");
            }
        }
    }) {
        Ok(_) => {
            println!("Global shortcut registered successfully");
        }
        Err(err) => {
            eprintln!("Failed to register global shortcut: {}", err);
            // Graceful degradation — voice input still accessible via UI
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.eval(
                    "window.__TAURI_SHORTCUT_FAILED__ = true"
                );
            }
        }
    }

    Ok(())
}
