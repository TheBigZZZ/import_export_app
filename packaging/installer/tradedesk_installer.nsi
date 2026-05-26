; NSIS installer script for TradeDesk
; Produces dist\TradeDesk-Setup.exe

Name "TradeDesk"
OutFile "dist\\TradeDesk-Setup.exe"
InstallDir "$PROGRAMFILES\\TradeDesk"
SetCompress auto
SetCompressor lzma

Page directory
Page instfiles

Section "Install"
  SetOutPath "$INSTDIR"
  File "dist\\launcher.exe"
  CreateDirectory "$SMPROGRAMS\\TradeDesk"
  CreateShortCut "$SMPROGRAMS\\TradeDesk\\TradeDesk.lnk" "$INSTDIR\\launcher.exe"
  WriteUninstaller "$INSTDIR\\uninstall.exe"
SectionEnd

Section "Uninstall"
  Delete "$INSTDIR\\launcher.exe"
  Delete "$SMPROGRAMS\\TradeDesk\\TradeDesk.lnk"
  RMDir "$SMPROGRAMS\\TradeDesk"
  Delete "$INSTDIR\\uninstall.exe"
  RMDir "$INSTDIR"
SectionEnd
