; =====================================================
; Inno Setup Script for UltimateMediaRenamer [v1.0.0]
; =====================================================

[Setup]
AppName=UltimateMediaRenamer
AppVersion=1.0.0
AppPublisher=Cameron Drake
AppPublisherURL=UltimateMediaRenamer@proton.me
DefaultDirName={userappdata}\UltimateMediaRenamer
DisableDirPage=yes
DisableProgramGroupPage=yes
OutputDir="C:\.temp\UltimateMediaRenamer\Installer"
OutputBaseFilename=UltimateMediaRenamer [v1.0.0] [x64]_Setup
Compression=lzma
SolidCompression=yes
LicenseFile="C:\.temp\UltimateMediaRenamer\LICENSE.txt"
PrivilegesRequired=admin
SetupIconFile="C:\.temp\UltimateMediaRenamer\Installer\UMR_ContextMenus_256.ico"

[Files]
; Batch scripts
Source: "C:\.temp\UltimateMediaRenamer\Batch\*";     DestDir: "{app}\Batch";       Flags: recursesubdirs createallsubdirs ignoreversion
; Python scripts & config
Source: "C:\.temp\UltimateMediaRenamer\Scripts\*";   DestDir: "{app}\Scripts";     Flags: recursesubdirs createallsubdirs ignoreversion
; Registry files
Source: "C:\.temp\UltimateMediaRenamer\Registry\*";  DestDir: "{app}\Registry";    Flags: recursesubdirs createallsubdirs ignoreversion

; *** Embed the Python runtime you checked into Tools\Python ***
Source: "C:\.temp\UltimateMediaRenamer\Tools\Python\*"; DestDir: "{app}\Tools\Python"; Flags: recursesubdirs createallsubdirs ignoreversion

; Ship the bootstrap script + CA bundle
Source: "C:\.temp\UltimateMediaRenamer\Setup\setup_installer.py"; DestDir: "{app}\Setup"; Flags: ignoreversion
Source: "C:\.temp\UltimateMediaRenamer\Setup\cacert.pem";        DestDir: "{app}\Setup"; Flags: ignoreversion

; requirements for pip
Source: "C:\.temp\UltimateMediaRenamer\Setup\requirements.txt";  DestDir: "{app}\Setup"; Flags: ignoreversion

; License and ReadMe
Source: "C:\.temp\UltimateMediaRenamer\LICENSE.txt";             DestDir: "{app}"; Flags: ignoreversion
Source: "C:\.temp\UltimateMediaRenamer\README.txt";              DestDir: "{app}"; Flags: ignoreversion

[Registry]
; Mark install for future upgrade checks
Root: HKCU; Subkey: "Software\UltimateMediaRenamer"; \
  ValueType: string; ValueName: "Installed"; ValueData: "1";

[Run]
; Force Explorer to reload user environment variables
Filename: "powershell.exe"; Parameters: "-NoProfile -EncodedCommand WwBFAG4AdgBpAHIAbwBuAG0AZQBuAHQAXQA6ADoAUwBlAHQARQBuAHYAaQByAG8AbgBtAGUAbgB0AFYAYQByAGkAYQBiAGwAZQAoACcARABVAE0ATQBZACcALAAnAHIAZQBmAHIAZQBzAGgAJwAsAFsARQBuAHYAaQByAG8AbgBtAGUAbgB0AFYAYQByAGkAYQBiAGwAZQBUAGEAcgBnAGUAdABdADoAOgBVAHMAZQByACkAOwAgACQAdwBzAGgAZQBsAGwAIAA9ACAATgBlAHcALQBPAGIAagBlAGMAdAAgAC0AQwBvAG0ATwBiAGoAZQBjAHQAIABXAFMAYwByAGkAcAB0AC4AUwBoAGUAbABsADsAIAAkAHcAcwBoAGUAbABsAC4AUwBlAG4AZABLAHkAcwAoACcAXigAewBFAFMAQwB9ACkAJwApADsAIABTAHQAYQByAHQALQBTAGwAZQBlAHAAIAAtAE0AaQBsAGwAaQBzAGUAYwBvAG4AZABzACAAMwAwADAAOwA="; Flags: runhidden

[Code]
var
  ResultCode: Integer;

// Checks if this is an upgrade
function PreviousInstallDetected(): Boolean;
begin
  Result := RegValueExists(HKEY_CURRENT_USER, 'Software\UltimateMediaRenamer', 'Installed');
end;

// Replaces placeholder in your context-menu .reg
procedure ModifyRegistryFile();
var
  AppDir, RegPath: string;
  ContentAnsi: AnsiString;
  Content: string;
begin
  AppDir := ExpandConstant('{app}');
  StringChange(AppDir, '\', '\\');
  RegPath := ExpandConstant('{app}\Registry\UMR_ContextMenus.reg');

  if LoadStringFromFile(RegPath, ContentAnsi) then
  begin
    Content := ContentAnsi;
    StringChangeEx(Content, '[INSTALL_DIR]', AppDir, True);
    SaveStringToFile(RegPath, Content, False);
  end
  else
    MsgBox('Failed to load UMR_ContextMenus.reg.', mbError, MB_OK);
end;

// Launches your Python-based installer
procedure RunPythonBootstrap();
var
  PyExe, Script, Params: string;
begin
  PyExe   := ExpandConstant('{app}\Tools\Python\python.exe');
  Script  := ExpandConstant('{app}\Setup\setup_installer.py');
  Params  := '--quiet --log';

  if FileExists(PyExe) and FileExists(Script) then
  begin
    if not Exec(PyExe, '"' + Script + '" ' + Params, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
      MsgBox('Error running embedded Python installer.', mbError, MB_OK);
  end
  else
    MsgBox('Embedded Python or bootstrap script missing.', mbError, MB_OK);
end;

// After files are copied, run our install logic
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    ModifyRegistryFile();
    // Apply context-menu entries
    Exec('regedit.exe',
         '/s "' + ExpandConstant('{app}\Registry\UMR_ContextMenus.reg') + '"',
         '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    // Run the Python bootstrap
    RunPythonBootstrap();
    // Final confirmation
    MsgBox('UltimateMediaRenamer has been successfully installed!', mbInformation, MB_OK);
  end;
end;

// Offer upgrade/repair if previously installed
procedure InitializeWizard();
begin
  if PreviousInstallDetected() then
    if MsgBox(
      'A previous installation was detected. Continue as upgrade/repair?',
      mbConfirmation, MB_YESNO) = IDNO
    then
      WizardForm.Close;
end;
