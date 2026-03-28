mod shortcuts;
mod tray;

use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_global_shortcut::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            // Set up system tray
            if let Err(err) = tray::setup_tray(app) {
                eprintln!("Failed to setup system tray: {}", err);
            }

            // Register global shortcuts
            if let Err(err) = shortcuts::setup_shortcuts(app) {
                eprintln!("Failed to setup shortcuts: {}", err);
            }

            let _ = app.get_webview_window("main");
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
