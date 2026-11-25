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

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then begin
    if not Exec(ExpandConstant('{app}\RemoteMouse.exe'), '--enable-uac', '',
                SW_HIDE, ewWaitUntilTerminated, ResultCode) then
      ResultCode := -1;
    if ResultCode <> 0 then begin
      Log('UAC mouse support was not enabled. It can be repaired from the tray.');
      if not WizardSilent then
        MsgBox('UAC mouse control was not enabled. Use Enable / Repair in the tray menu to finish setup.',
               mbInformation, MB_OK);
    end;
  end;
end;

function InitializeUninstall(): Boolean;
var
  ResultCode: Integer;
begin
  Result := Exec(ExpandConstant('{app}\RemoteMouse.exe'), '--disable-uac', '',
                 SW_HIDE, ewWaitUntilTerminated, ResultCode);
  if Result then Result := ResultCode = 0;
  if not Result then
    MsgBox('UAC mouse support could not be removed. Please retry and approve the administrator prompt.',
           mbError, MB_OK);
end;
