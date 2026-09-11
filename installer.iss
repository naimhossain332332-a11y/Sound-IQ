[Setup]
AppName=Sound IQ
AppVersion=2.0.0
AppPublisher=naimhossain332332-a11y
AppPublisherURL=https://github.com/naimhossain332332-a11y/Sound-IQ
AppSupportURL=https://github.com/naimhossain332332-a11y/Sound-IQ/issues
AppUpdatesURL=https://github.com/naimhossain332332-a11y/Sound-IQ/releases
DefaultDirName={autopf}\Sound IQ
DefaultGroupName=Sound IQ
OutputDir=installer_output
OutputBaseFilename=SoundIQ-Setup-2.0.0
SetupIconFile=soundiq_logo.ico
UninstallDisplayIcon={app}\soundiq_logo.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
RestartApplications=no
CloseApplications=yes
CloseApplicationsFilter=*.exe
UsePreviousAppDir=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"; Flags: checkedonce
Name: "associatefiles"; Description: "Associate audio files with Sound IQ"; GroupDescription: "File associations:"; Flags: unchecked

[Files]
Source: "dist\SoundIQ.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "soundiq_logo.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "soundiq_logo.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme

[Icons]
Name: "{group}\Sound IQ"; Filename: "{app}\SoundIQ.exe"; WorkingDir: "{app}"; IconFilename: "{app}\soundiq_logo.ico"
Name: "{group}\Uninstall Sound IQ"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Sound IQ"; Filename: "{app}\SoundIQ.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\SoundIQ.exe"; Description: "Launch Sound IQ now"; Flags: nowait postinstall skipifsilent

[Registry]
; File associations - WAV
Root: HKA; Subkey: "Software\Classes\.wav\OpenWithProgids"; ValueType: string; ValueName: "SoundIQ.AudioFile"; ValueData: ""; Flags: uninsdeletevalue; Tasks: associatefiles
Root: HKA; Subkey: "Software\Classes\.mp3\OpenWithProgids"; ValueType: string; ValueName: "SoundIQ.AudioFile"; ValueData: ""; Flags: uninsdeletevalue; Tasks: associatefiles
Root: HKA; Subkey: "Software\Classes\.flac\OpenWithProgids"; ValueType: string; ValueName: "SoundIQ.AudioFile"; ValueData: ""; Flags: uninsdeletevalue; Tasks: associatefiles
Root: HKA; Subkey: "Software\Classes\.ogg\OpenWithProgids"; ValueType: string; ValueName: "SoundIQ.AudioFile"; ValueData: ""; Flags: uninsdeletevalue; Tasks: associatefiles
Root: HKA; Subkey: "Software\Classes\.m4a\OpenWithProgids"; ValueType: string; ValueName: "SoundIQ.AudioFile"; ValueData: ""; Flags: uninsdeletevalue; Tasks: associatefiles
Root: HKA; Subkey: "Software\Classes\.aif\OpenWithProgids"; ValueType: string; ValueName: "SoundIQ.AudioFile"; ValueData: ""; Flags: uninsdeletevalue; Tasks: associatefiles
Root: HKA; Subkey: "Software\Classes\.aiff\OpenWithProgids"; ValueType: string; ValueName: "SoundIQ.AudioFile"; ValueData: ""; Flags: uninsdeletevalue; Tasks: associatefiles
Root: HKA; Subkey: "Software\Classes\.wma\OpenWithProgids"; ValueType: string; ValueName: "SoundIQ.AudioFile"; ValueData: ""; Flags: uninsdeletevalue; Tasks: associatefiles

; SoundIQ.AudioFile ProgID
Root: HKA; Subkey: "Software\Classes\SoundIQ.AudioFile"; ValueType: string; ValueName: ""; ValueData: "Audio File"; Flags: uninsdeletekey; Tasks: associatefiles
Root: HKA; Subkey: "Software\Classes\SoundIQ.AudioFile\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\soundiq_logo.ico"; Tasks: associatefiles
Root: HKA; Subkey: "Software\Classes\SoundIQ.AudioFile\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\SoundIQ.exe"" ""%1"""; Tasks: associatefiles

; App user model ID (taskbar grouping)
Root: HKA; Subkey: "Software\Classes\Applications\SoundIQ.exe\AppUserModelId"; ValueType: string; ValueName: ""; ValueData: "SoundIQ.2"; Flags: uninsdeletekey

; Start menu
Root: HKA; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\SoundIQ"; ValueType: string; ValueName: "DisplayName"; ValueData: "Sound IQ"
Root: HKA; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\SoundIQ"; ValueType: string; ValueName: "UninstallString"; ValueData: """{uninstallexe}"""
Root: HKA; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\SoundIQ"; ValueType: string; ValueName: "InstallLocation"; ValueData: "{app}"
Root: HKA; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\SoundIQ"; ValueType: dword; ValueName: "NoModify"; ValueData: 1
Root: HKA; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\SoundIQ"; ValueType: dword; ValueName: "NoRepair"; ValueData: 1

[Code]
function InitializeSetup: Boolean;
begin
  Result := True;
end;
