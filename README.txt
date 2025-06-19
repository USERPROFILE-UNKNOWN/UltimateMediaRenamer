╔════════════════════════════════════════════════════════════╗
║                  UltimateMediaRenamer                      ║
║                Advanced Media Organization Suite           ║
╚════════════════════════════════════════════════════════════╝

=== PROJECT OVERVIEW ===
A comprehensive tool for renaming, organizing, and deduplicating media files 
using metadata analysis. Features context menu integration, multi-platform 
pattern recognition, and full transaction logging for undo/restore operations.

■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
✔ KEY FEATURES:
- Smart metadata-based renaming (EXIF/XMP/FFprobe/MediaInfo)
- Platform-specific organization (Instagram, Facebook, Android, etc.)
- Duplicate file detection and management
- Full undo/restore capabilities via SQLite logging
- Windows context menu integration (file/folder/background actions)
- Multi-pass file categorization with conflict resolution
- SHA-256/SHA-1 hash verification system
- Automatic dependency installer (Python, ExifTool, FFmpeg, MediaInfo, SQLite)
- Silent installer support and clean uninstall behavior
- Inno Setup integration with custom .reg patching

=== INSTALLATION ===

1. SYSTEM REQUIREMENTS:
   - Windows 10/11 (64-bit)
   - Admin privileges for initial setup

2. INSTALLATION METHODS:
   a) Installer (recommended)
      - Use the provided `UltimateMediaRenamer [v1.0.0] [x64]_Setup.exe`
      - Installs to: `%APPDATA%\UltimateMediaRenamer`
      - Automatically installs:
        • Python (embedded)
        • ExifTool
        • FFmpeg (ffmpeg.exe, ffprobe.exe)
        • MediaInfo CLI (MediaInfo.exe)
        • SQLite CLI (sqlite3.exe)
      - Adds system context menus (via .reg patch)
      - Supports silent mode:
        ```
        setup.bat --quiet --log
        ```

   b) Manual Setup:
      - Extract contents to `%APPDATA%\UltimateMediaRenamer`
      - Run `setup.bat` manually as Administrator
      - Apply `UMR_ContextMenus.reg`

3. DIRECTORY STRUCTURE:
   ├── Batch\          - Context menu batch scripts
   ├── Database\       - SQLite operation logs
   ├── Registry\       - Context menu registry entries/icons
   ├── Scripts\        - Core Python modules + platforms.json
   ├── Tools\          - Python, ffmpeg, MediaInfo, exiftool, sqlite3
   └── Setup\          - cacert.pem, requirements.txt, setup_installer.py

4. CONTEXT MENU SETUP:
   - Auto-imported during install via `UMR_ContextMenus.reg`
   - If needed: apply manually by running as Admin
   - Uninstall automatically removes registry keys via `UMR_ContextMenus_Uninstall.reg`

=== USAGE GUIDE ===

■■■ COMMAND-LINE INTERFACE ■■■
Syntax: UltimateMediaRenamer.py <mode> [options]

MODES:
1. rename - File renaming operations
   Actions:
   - single: Rename individual file
   - batch: Rename all files in directory
   - undo: Undo last rename on file
   - restore-original: Full history revert

   Example:
   python UltimateMediaRenamer.py rename single "C:\MyPhoto.jpg" --recursive

2. organize - File categorization
   Actions:
   - run: Organize files using platforms.json rules
   - restore-dir: Revert to original locations

3. clean-duplicates - Duplicate management
   Example:
   python UltimateMediaRenamer.py clean-duplicates "C:\Photos" 

=== CONFIGURATION ===
Edit \Scripts\platforms.json to modify:
- Platform recognition patterns
- Folder destinations
- Processing priority (pass_num)

Sample Android pattern:
{
  "name": "Android_Videos",
  "folder": "Android/Videos",
  "filename_patterns": [
    "(?i)^VID_\\d{8}_\\d{6}_\\d{3}.*\\.(?:mp4|mkv|mov)$"
  ],
  "pass": 1
}

=== DATABASE SCHEMA ===
Tracked in UltimateMediaRenamer.db:
- Original/new paths
- File hashes
- Metadata dates (EXIF/XMP/FFprobe)
- Operation timestamps
- Platform detection results

=== NOTES/WARNINGS ===
‼ CRITICAL:
- Always backup files before batch operations
- Maintain directory structure integrity
- Update platforms.json cautiously
- Uses UTC timestamps for consistency

⚙ OPTIMIZATION TIPS:
- Run duplicate cleaner before organization
- Use 2-pass processing for complex categorizations
- Combine with cloud storage clients for automated workflows

📧 Support/Error Reporting: UltimateMediaRenamer@proton.me
