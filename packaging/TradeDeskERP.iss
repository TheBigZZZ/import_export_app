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
#if FileExists("..\.env.production.example")
Source: "..\.env.production.example"; DestDir: "{app}"; Flags: ignoreversion
#endif

[Icons]
Name: "{group}\TradeDesk ERP"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\TradeDesk ERP"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch TradeDesk ERP"; Flags: nowait postinstall skipifsilent

[Code]
var
	DeleteUserDataPage: TWizardPage;
	DeleteUserDataCheckbox: TNewCheckBox;

function UserDataRoot: string;
begin
	Result := ExpandConstant('{userprofile}\TradeDesk');
end;

procedure CreateUninstallOptionsPage;
begin
	DeleteUserDataPage := CreateCustomPage(
		wpWelcome,
		'Remove User Data',
		'Choose whether uninstall should also delete all TradeDesk user data and local folders.'
	);

	DeleteUserDataCheckbox := TNewCheckBox.Create(DeleteUserDataPage.Surface);
	with DeleteUserDataCheckbox do
	begin
		Parent := DeleteUserDataPage.Surface;
		Left := ScaleX(0);
		Top := ScaleY(8);
		Width := DeleteUserDataPage.Surface.ClientWidth;
		Height := ScaleY(40);
		Caption := 'Delete all TradeDesk user data, backups, logs, diagnostics, and local settings from this PC';
		Checked := False;
		WordWrap := True;
	end;
end;

function InitializeUninstall(): Boolean;
begin
	CreateUninstallOptionsPage;
	Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
	DeleteUserData: Boolean;
	UserDataPath: string;
begin
	if CurUninstallStep <> usPostUninstall then
		Exit;

	DeleteUserData := Assigned(DeleteUserDataCheckbox) and DeleteUserDataCheckbox.Checked;

	if not DeleteUserData then
		Exit;

	UserDataPath := UserDataRoot;
	if DirExists(UserDataPath) then
		DelTree(UserDataPath, True, True, True);
end;