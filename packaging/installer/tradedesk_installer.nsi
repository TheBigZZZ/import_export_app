; NSIS installer script for TradeDesk
; Produces dist\TradeDesk-Setup.exe

Name "TradeDeskERP"
OutFile "dist\\TradeDeskERP-Setup.exe"
InstallDir "$PROGRAMFILES\\TradeDeskERP"
SetCompress auto
SetCompressor lzma

Page directory
Page instfiles

Section "Install"
  SetOutPath "$INSTDIR"
  File "dist\\TradeDeskERP\\TradeDeskERP.exe"
  CreateDirectory "$SMPROGRAMS\\TradeDeskERP"
  CreateShortCut "$SMPROGRAMS\\TradeDeskERP\\TradeDeskERP.lnk" "$INSTDIR\\TradeDeskERP.exe"
  WriteUninstaller "$INSTDIR\\uninstall.exe"
SectionEnd

Section "Uninstall"
  Delete "$INSTDIR\\TradeDeskERP.exe"
  Delete "$SMPROGRAMS\\TradeDeskERP\\TradeDeskERP.lnk"
  RMDir "$SMPROGRAMS\\TradeDeskERP"
  Delete "$INSTDIR\\uninstall.exe"
  RMDir "$INSTDIR"
SectionEnd
