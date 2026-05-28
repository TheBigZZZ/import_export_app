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

function UserDataRoot: string;
begin
	Result := ExpandConstant('{userprofile}\TradeDesk');
end;

function ConnectionSettingsPath: string;
begin
	Result := ExpandConstant('{userprofile}\TradeDesk\client-settings.json');
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
	BackendUrlEdit.Enabled := SharedBackendRadio.Checked;
	RememberConnectionCheckbox.Enabled := True;
	UpdateDeploymentSummary;
end;

procedure CreateInstallerWorkflowPage;
begin
	DeploymentPage := CreateCustomPage(
		wpWelcome,
		'Choose Your Deployment',
		'Tell TradeDesk how this PC should connect so the app starts in the right mode.'
	);

	LocalBackendRadio := TNewRadioButton.Create(DeploymentPage.Surface);
	with LocalBackendRadio do
	begin
		Parent := DeploymentPage.Surface;
		Left := ScaleX(0);
		Top := ScaleY(8);
		Width := DeploymentPage.Surface.ClientWidth;
		Caption := 'This is the main PC and should run the local backend';
		Checked := True;
		OnClick := @UpdateDeploymentControls;
	end;

	SharedBackendRadio := TNewRadioButton.Create(DeploymentPage.Surface);
	with SharedBackendRadio do
	begin
		Parent := DeploymentPage.Surface;
		Left := ScaleX(0);
		Top := ScaleY(32);
		Width := DeploymentPage.Surface.ClientWidth;
		Caption := 'This PC should connect to a shared backend on another machine';
		OnClick := @UpdateDeploymentControls;
	end;

	BackendUrlEdit := TNewEdit.Create(DeploymentPage.Surface);
	with BackendUrlEdit do
	begin
		Parent := DeploymentPage.Surface;
		Left := ScaleX(24);
		Top := ScaleY(60);
		Width := ScaleX(360);
		Text := 'http://127.0.0.1:8742';
		Enabled := False;
	end;

	RememberConnectionCheckbox := TNewCheckBox.Create(DeploymentPage.Surface);
	with RememberConnectionCheckbox do
	begin
		Parent := DeploymentPage.Surface;
		Left := ScaleX(24);
		Top := ScaleY(92);
		Width := DeploymentPage.Surface.ClientWidth;
		Caption := 'Remember this connection on this PC';
		Checked := True;
	end;

	DeploymentSummaryLabel := TNewStaticText.Create(DeploymentPage.Surface);
	with DeploymentSummaryLabel do
	begin
		Parent := DeploymentPage.Surface;
		Left := ScaleX(0);
		Top := ScaleY(124);
		Width := DeploymentPage.Surface.ClientWidth;
		AutoSize := False;
		Caption := 'Choose local backend if this PC will host TradeDesk.'#13#10'Choose shared backend if another machine already runs the backend service.';
	end;

	UpdateDeploymentControls(nil);
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
	Result := True;
	if DeploymentPage = nil then
		Exit;

	if not SharedBackendRadio.Checked then
		Exit;

	if Trim(BackendUrlEdit.Text) = '' then
	begin
		MsgBox('Enter the shared backend URL before continuing.', mbError, MB_OK);
		Result := False;
	end;
end;

procedure PersistConnectionSettings;
var
	Lines: TArrayOfString;
	SettingsPath: string;
	BackendUrl: string;
begin
	if not RememberConnectionCheckbox.Checked then
	begin
		SettingsPath := ConnectionSettingsPath;
		if FileExists(SettingsPath) then
			DeleteFile(SettingsPath);
		Exit;
	end;

	BackendUrl := CurrentBackendUrl;
	if BackendUrl = '' then
		Exit;

	SettingsPath := ConnectionSettingsPath;
	ForceDirectories(ExtractFileDir(SettingsPath));
	SetArrayLength(Lines, 4);
	Lines[0] := '{';
	Lines[1] := '  "backend_url": "' + BackendUrl + '",';
	Lines[2] := '  "remember": true';
	Lines[3] := '}';
	SaveStringsToUTF8FileWithoutBOM(SettingsPath, Lines, False);
end;

procedure InitializeWizard;
begin
	CreateInstallerWorkflowPage;
end;

function InitializeUninstall(): Boolean;
begin
	CreateUninstallOptionsPage;
	Result := True;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
	Result := True;
	if Assigned(DeploymentPage) and (CurPageID = DeploymentPage.ID) then
		Result := ValidateDeploymentPage();
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
	if CurStep = ssPostInstall then
		PersistConnectionSettings;
end;

function UpdateReadyMemo(Space, NewLine, MemoUserInfoInfo, MemoDirInfo, MemoTypeInfo,
	MemoComponentsInfo, MemoGroupInfo, MemoTasksInfo: String): String;
begin
	Result := MemoDirInfo + NewLine;
	Result := Result + Space + 'TradeDesk deployment' + NewLine;
	if LocalBackendRadio.Checked then
		Result := Result + Space + '  - Local backend on this PC' + NewLine
	else
		Result := Result + Space + '  - Shared backend: ' + Trim(BackendUrlEdit.Text) + NewLine;
	if RememberConnectionCheckbox.Checked then
		Result := Result + Space + '  - Connection will be remembered for this Windows profile' + NewLine;
	Result := Result + MemoGroupInfo + MemoTasksInfo;
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