[Setup]
AppId={{B84B76F8-A7F2-4F86-8B57-52AF2AF3ED62}
AppName=KeyboardGod
AppVersion=1.0.1
AppPublisher=KeyboardGod
DefaultDirName={autopf}\KeyboardGod
DefaultGroupName=KeyboardGod
DisableProgramGroupPage=yes
OutputDir=installer
OutputBaseFilename=KeyboardGod_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; GroupDescription: "Additional icons:"

[Files]
Source: "dist\KeyboardGod.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\KeyboardGod"; Filename: "{app}\KeyboardGod.exe"
Name: "{autodesktop}\KeyboardGod"; Filename: "{app}\KeyboardGod.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\KeyboardGod.exe"; Description: "Launch KeyboardGod"; Flags: nowait postinstall skipifsilent
