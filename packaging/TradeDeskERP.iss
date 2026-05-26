#define MyAppName "TradeDesk ERP"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "TradeDesk"
#define MyAppExeName "TradeDeskERP.exe"

[Setup]
AppId={{0A4B911F-2A5D-4F17-9A6F-9231C83433D5}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\TradeDeskERP
DefaultGroupName=TradeDesk ERP
OutputDir=..\dist
OutputBaseFilename=TradeDeskERP-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; GroupDescription: "Additional icons:";

[Files]
Source: "..\dist\TradeDeskERP\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Include production .env template for operator configuration
Source: "..\.env.production.example"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\TradeDesk ERP"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\TradeDesk ERP"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch TradeDesk ERP"; Flags: nowait postinstall skipifsilent