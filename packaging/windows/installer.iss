; ====================================================================
; text2sql-agent Windows 安装包脚本（Inno Setup 6.x，打包 spec §5.5）
; ====================================================================
; 输入：dist\text2sql-agent\（PyInstaller onedir 产物：text2sql-agent.exe
;       + _internal\；先在本机/CI 运行 pyinstaller text2sql.spec）。
; 输出：dist\text2sql-agent-<版本>-windows-x64-setup.exe
;
; 构建（仅 Windows，CI Task 6 windows-latest）：
;   choco install innosetup
;   ISCC.exe packaging\windows\installer.iss
;   ISCC.exe /DVERSION=1.2.3 packaging\windows\installer.iss   ; 指定版本
; 版本优先级：ISCC /DVERSION > 环境变量 VERSION > 默认 1.0.0。
;
; 说明：
; - exe 为 windowed 子系统（text2sql.spec console=False）：无控制台窗口，
;   启动后自动开浏览器（127.0.0.1:8501 起，占用递增）；日志在用户数据目录
;   %LOCALAPPDATA%\text2sql-agent\logs\app.log。
; - v1 未签名：SmartScreen「更多信息 → 仍要运行」绕过（见 README_FIRST_RUN.txt）。
; - 本文件为 UTF-8 with BOM 编码（Inno Setup 6 中文脚本要求）。
; ====================================================================

; --- 版本解析：/DVERSION > 环境变量 VERSION > 默认 1.0.0 ---
#ifndef VERSION
  #define VERSION GetEnv("VERSION")
#endif
#if VERSION == ""
  #define VERSION "1.0.0"
#endif

#define MyAppName "溯算编程 Text2SQL 智能体"
#define MyAppExeName "text2sql-agent.exe"
#define MyAppPublisher "溯算编程"

[Setup]
AppName={#MyAppName}
AppVersion={#VERSION}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\text2sql-agent
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; 产物统一落 dist\（与 dmg/AppImage 一致；dist\ 已 gitignore）
OutputDir=..\..\dist
OutputBaseFilename=text2sql-agent-{#VERSION}-windows-x64-setup
Compression=lzma2
SolidCompression=yes
; v1 仅支持 x64（CI windows-latest；Win arm64 留后续）。
; Inno Setup 6.3+ 弃用裸 x64（告警），改用 x64compatible（含 x64 与兼容 ARM64 模拟）。
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
; 升级安装时若应用正在运行，提示关闭（Restart Manager）
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式(&D)"; GroupDescription: "附加图标:"

[Files]
; PyInstaller onedir 全量（exe + _internal\ 依赖树）
Source: "..\..\dist\text2sql-agent\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; 首跑说明（前提/签名绕过/数据目录），随包分发
Source: "..\README_FIRST_RUN.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; 桌面快捷方式（可选任务）
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
; 开始菜单
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\首次运行说明"; Filename: "{app}\README_FIRST_RUN.txt"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"

[Run]
; 安装完成后可选立即启动（静默安装跳过）
Filename: "{app}\{#MyAppExeName}"; Description: "立即启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent

; 卸载说明：应用只写用户数据目录 %LOCALAPPDATA%\text2sql-agent，
; 安装目录 {app} 内无运行时生成文件，标准卸载即可；数据目录保留由用户自行删除。
