#ifndef AppVersion
  #error AppVersion is required
#endif

[Setup]
AppId={{F36A75CD-8810-4DB8-A8D2-57D5FAE8E87A}
AppName=Remote Mouse
AppVersion={#AppVersion}
VersionInfoVersion={#NumericVersion}
AppVerName=Remote Mouse {#AppVersion}
AppPublisher=Remote Mouse
DefaultDirName={localappdata}\Programs\RemoteMouse
DefaultGroupName=Remote Mouse
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#OutputDir}
OutputBaseFilename={#OutputName}
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\RemoteMouse.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Remote Mouse"; Filename: "{app}\RemoteMouse.exe"
Name: "{autodesktop}\Remote Mouse"; Filename: "{app}\RemoteMouse.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\RemoteMouse.exe"; Description: "Launch Remote Mouse"; Flags: nowait postinstall skipifsilent
