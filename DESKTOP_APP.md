# Desktop App Setup (Tauri)

This project now includes a desktop application wrapper using **Tauri**. It uses your existing `frontend/` static files to provide a lightweight, high-performance desktop experience.

## Prerequisites

1. **Rust**: You must have Rust installed to compile the desktop app.
   - Install from [rustup.rs](https://rustup.rs/).
2. **WebView2**: Most Windows machines have this by default. If not, it will be installed automatically during the first run.
3. **Node.js & npm** (Optional but recommended): For running the Tauri CLI.

## How to Run (Development)

I have added a `package.json` to your root folder so you can use these commands:

1. Open your terminal in the project root.
2. Run the application in development mode:
   ```bash
   npm run tauri dev
   ```
   *Note: If it's your first time, it will take a few minutes to download and compile the Rust dependencies.*

   *Alternatively, you can use the global CLI directly:*
   ```bash
   tauri dev
   ```

## How to Build (Production)

To create a standalone `.exe` installer:
```bash
npm run tauri build
```
The installer will be located in `src-tauri/target/release/bundle/msi/`.

## Project Structure
- `src-tauri/`: Contains the Rust code and configuration for the desktop app.
- `src-tauri/tauri.conf.json`: Main configuration file where the window size, title, and icons are defined.
- `src-tauri/src/main.rs`: The entry point for the desktop application.
- `frontend/`: The desktop app points directly to this folder for its UI.
