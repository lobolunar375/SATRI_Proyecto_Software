; ============================================================
; SATRI v2 — Inno Setup Installer Script
; ============================================================
; Genera un instalador profesional para Windows.
; Descarga Inno Setup gratis de: https://jrsoftware.org/isinfo.php
; Compilar con: iscc satri_installer.iss
; ============================================================

[Setup]
AppName=SATRI Endpoint Protection
AppVersion=2.0.0
AppPublisher=SATRI Security
AppPublisherURL=https://github.com/satri-security
DefaultDirName={autopf}\SATRI
DefaultGroupName=SATRI Protection
OutputDir=..\dist\installer
OutputBaseFilename=SATRI_Setup_v2.0.0
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
; UninstallDisplayIcon={app}\SATRI_Protection.exe
LicenseFile=..\PRIVACY_MODEL.md
SetupIconFile=satri_icon.ico
UninstallDisplayName=SATRI Endpoint Protection

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "autostart"; Description: "Iniciar SATRI automáticamente con Windows"; GroupDescription: "Opciones adicionales:"

[Files]
Source: "..\dist\SATRI_Protection.exe"; DestDir: "{app}"; Flags: ignoreversion
; Extensión de navegador (para instalación manual)
Source: "..\browser_extension\*"; DestDir: "{app}\browser_extension"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{group}\SATRI Protection"; Filename: "{app}\SATRI_Protection.exe"
Name: "{group}\Desinstalar SATRI"; Filename: "{uninstallexe}"
Name: "{commonstartup}\SATRI Protection"; Filename: "{app}\SATRI_Protection.exe"; Tasks: autostart

[Run]
Filename: "{app}\SATRI_Protection.exe"; Description: "Iniciar SATRI Protection"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Detener procesos SATRI antes de desinstalar
Filename: "taskkill"; Parameters: "/F /IM SATRI_Protection.exe"; Flags: runhidden

[UninstallDelete]
; Limpiar datos locales de la app
Type: filesandordirs; Name: "{userappdata}\SATRI"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    { Limpiar reglas de firewall de SATRI }
    Exec('netsh', 'advfirewall firewall delete rule name=all dir=in remoteip=any', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    { Confirmar limpieza }
    MsgBox('SATRI ha sido desinstalado completamente.' + #13#10 +
           'Todos los datos locales y reglas de firewall han sido eliminados.' + #13#10 +
           'No quedan procesos ni datos residuales.',
           mbInformation, MB_OK);
  end;
end;
