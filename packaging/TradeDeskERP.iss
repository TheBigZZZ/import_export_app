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
	DeploymentPage: TWizardPage;
	LocalBackendRadio: TNewRadioButton;
	SharedBackendRadio: TNewRadioButton;
	BackendUrlEdit: TNewEdit;
	RememberConnectionCheckbox: TNewCheckBox;
	DeploymentSummaryLabel: TNewStaticText;
	DeleteUserDataPage: TWizardPage;
	DeleteUserDataCheckbox: TNewCheckBox;
	DeleteUserDataChoice: Boolean;

function UserDataRoot: string;
begin
	var up: string;
	up := GetEnv('USERPROFILE');
	if up = '' then
		Result := ExpandConstant('{userappdata}\TradeDesk')
	else
		Result := up + '\\TradeDesk';
end;

function ConnectionSettingsPath: string;
begin
	var up: string;
	up := GetEnv('USERPROFILE');
	if up = '' then
		Result := ExpandConstant('{userappdata}\TradeDesk\\client-settings.json')
	else
		Result := up + '\\TradeDesk\\client-settings.json';
end;

function CurrentBackendUrl: string;
begin
	if LocalBackendRadio.Checked then
		Result := 'http://127.0.0.1:8742'
	else
		Result := Trim(BackendUrlEdit.Text);
end;

procedure UpdateDeploymentSummary;
begin
	if LocalBackendRadio.Checked then
		DeploymentSummaryLabel.Caption := 'This install will use the local backend on this PC.'
	else
		DeploymentSummaryLabel.Caption := 'This install will connect to a shared backend at ' + Trim(BackendUrlEdit.Text) + '.';
end;

procedure UpdateDeploymentControls(Sender: TObject);
begin
	// No-op: installer should not configure runtime backend during install.
end;

procedure CreateInstallerWorkflowPage;
begin
	// Deployment UI removed: runtime backend selection is handled when the app first runs.
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
		Height := ScaleY(20);
		Caption := 'Delete all TradeDesk user data from this PC';
		Checked := False;
	end;
end;

function ValidateDeploymentPage(): Boolean;
begin
	// No validation needed; deployment page is not presented during install.
	Result := True;
end;

procedure PersistConnectionSettings;
var
	Lines: TArrayOfString;
	SettingsPath: string;
	BackendUrl: string;
begin
	// Disabled: do not persist backend connection settings at install time.
end;

procedure InitializeWizard;
begin
	// Default installer wizard only; no deployment UI.
end;

function InitializeUninstall(): Boolean;
begin
	// Do not create custom pages during uninstall (unsupported); use a confirmation prompt instead.
	DeleteUserDataChoice := False;
	Result := True;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
	// No custom page validation required.
	Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
	// Do not persist configuration during installation.
end;

function UpdateReadyMemo(Space, NewLine, MemoUserInfoInfo, MemoDirInfo, MemoTypeInfo,
	MemoComponentsInfo, MemoGroupInfo, MemoTasksInfo: String): String;
begin
	// Keep ready memo minimal and focused on install directories/tasks.
	Result := MemoDirInfo + NewLine + MemoGroupInfo + MemoTasksInfo;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
	DeleteUserData: Boolean;
	UserDataPath: string;
begin
	if CurUninstallStep = usUninstall then
	begin
		// Ask user whether to delete all TradeDesk user data now that uninstall is running
		if MsgBox('Delete all TradeDesk user data (logs, backups, settings) from this PC?', mbConfirmation, MB_YESNO) = IDYES then
			DeleteUserDataChoice := True
		else
			DeleteUserDataChoice := False;
		Exit;
	end;

	if CurUninstallStep <> usPostUninstall then
		Exit;

	if not DeleteUserDataChoice then
		Exit;

	UserDataPath := UserDataRoot;
	if DirExists(UserDataPath) then
		DelTree(UserDataPath, True, True, True);
end;