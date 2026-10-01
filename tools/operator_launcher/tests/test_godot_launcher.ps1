# Dependency-free Godot launcher safety tests. Application starts and process stops are mocked.
. (Join-Path $PSScriptRoot '../common.ps1')
$script:passed = 0
function Check($Name, [scriptblock]$Test) {
    & $Test
    $script:passed++
    Write-Host "PASS $Name"
}
function Assert($Condition, $Message = 'Assertion failed') { if (-not $Condition) { throw $Message } }
function Throws([scriptblock]$Action, $Pattern) {
    $caught = $false
    try { & $Action } catch { $caught = $true; Assert ($_.Exception.Message -match $Pattern) $_.Exception.Message }
    Assert $caught 'Expected a failure'
}
function Process($Id, $Parent, $Path, $Command = '', $Created = [datetime]'2026-01-01') {
    [pscustomobject]@{ ProcessId = $Id; ParentProcessId = $Parent; ExecutablePath = $Path;
        Name = [IO.Path]::GetFileName($Path); CommandLine = $Command; CreationDate = $Created }
}
$root = Get-RepositoryRoot
$godot = 'C:\Tools\Godot\Godot_v4.7.2-stable_win64.exe'
$config = [pscustomobject]@{ desktopExe = 'C:\Apps\ChatGPT.exe'; photoshopExe = 'C:\Apps\Photoshop.exe';
    udtExe = 'C:\Apps\Adobe UXP Developer Tools.exe'; godotExe = $godot }
$venv = Join-Path $root 'tools/lunitora_mcp/.venv/Scripts/python.exe'
$godotBridge = Process 101 10 $venv ('"' + $venv + '" -B -m core.godot_server')
$godotCommand = '"' + $godot + '" --editor --path "' + $root + '"'

function Check-GodotExecutable($Name, [scriptblock]$Scenario) {
    Check $Name {
        $fixture = [pscustomobject]@{ Exists = $true; Version = '4.7.2.stable.official.abc123456'; Product = 'Godot Engine' }
        function Test-Path { param($LiteralPath, $PathType) $fixture.Exists }
        function Get-Item {
            param($LiteralPath)
            [pscustomobject]@{ Name = [IO.Path]::GetFileName($LiteralPath);
                VersionInfo = [pscustomobject]@{ ProductName = $fixture.Product; ProductVersion = $fixture.Version } }
        }
        function Start-Process { throw 'Executable validation must not launch Godot.' }
        & $Scenario
    }
}
Check-GodotExecutable 'Godot 4.7.2 stable official executable is accepted' {
    Assert-Executable $godot 'godotExe'
}
Check-GodotExecutable 'missing, relative and network Godot executables are rejected' {
    $fixture.Exists = $false
    Throws { Assert-Executable $godot 'godotExe' } 'existing absolute|absolute local'
    $fixture.Exists = $true
    Throws { Assert-Executable 'Godot_v4.7.2-stable_win64.exe' 'godotExe' } 'absolute'
    Throws { Assert-Executable '\\remote\Tools\Godot_v4.7.2-stable_win64.exe' 'godotExe' } 'local'
    Throws { Assert-Executable $null 'godotExe' } 'not configured'
}
Check-GodotExecutable 'drive-relative and volume-relative executable paths are rejected' {
    foreach ($path in @('D:Godot_v4.7.2-stable_win64.exe', '\Tools\Godot_v4.7.2-stable_win64.exe',
            '.\Godot_v4.7.2-stable_win64.exe')) {
        Throws { Assert-Executable $path 'godotExe' } 'absolute local'
    }
}
Check-GodotExecutable 'other executable filenames cannot masquerade as Godot' {
    Throws { Assert-Executable 'C:\Tools\python.exe' 'godotExe' } 'Unexpected executable|Godot'
    $fixture.Product = 'Other Engine'
    Throws { Assert-Executable $godot 'godotExe' } 'Godot|4\.7\.2|product'
}
Check-GodotExecutable 'wrong Godot version, development build and ambiguous output are rejected' {
    foreach ($version in @('4.7.1.stable.official.abc123456', '4.7.2.dev.official.abc123456',
            '4.7.2.stable.custom.abc123456', '4.7.2.stable.official.abc123456 extra', '')) {
        $fixture.Version = $version
        Throws { Assert-Executable $godot 'godotExe' } '4\.7\.2|version'
    }
}
Check 'Desktop signature validation explicitly imports this PowerShell host security module' {
    $fixture = [pscustomobject]@{ Imported = $null; ErrorAction = $null }
    function Assert-Executable { param($Path, $Kind) Assert ($Kind -eq 'desktopExe') }
    function Import-Module { param($Name, $ErrorAction) $fixture.Imported = $Name; $fixture.ErrorAction = $ErrorAction }
    function Get-AuthenticodeSignature {
        param($LiteralPath, $ErrorAction)
        Assert ($null -ne $fixture.Imported) 'Signature lookup ran before selecting the native security module.'
        Assert ($ErrorAction -eq 'Stop')
        throw 'Signature inspection sentinel'
    }
    Throws { Get-DesktopLaunchTarget $config.desktopExe } 'Signature inspection sentinel'
    Assert (Test-SamePath $fixture.Imported (Join-Path $PSHOME 'Modules/Microsoft.PowerShell.Security/Microsoft.PowerShell.Security.psd1'))
    Assert ($fixture.ErrorAction -eq 'Stop') 'Native security module import must fail closed.'
}

Check 'Godot editor identity requires exact executable and exact repository path' {
    Assert (Test-GodotEditorCommand (Process 201 0 $godot $godotCommand) $godot $root)
    Assert (-not (Test-GodotEditorCommand (Process 202 0 'C:\Other\Godot_v4.7.2-stable_win64.exe' $godotCommand) $godot $root))
    Assert (-not (Test-GodotEditorCommand (Process 203 0 $godot ('"' + $godot + '" --editor --path "C:\OtherProject"')) $godot $root))
}
Check 'Godot Project Manager, title matches and missing command lines are insufficient proof' {
    foreach ($command in @(('"' + $godot + '"'), ('"' + $godot + '" --project-manager'), '',
            ('"' + $godot + '" --path "' + $root + '"'))) {
        $candidate = Process 204 0 $godot $command
        $candidate | Add-Member NoteProperty MainWindowTitle 'Totolina Merge - Godot Engine'
        Assert (-not (Test-GodotEditorCommand $candidate $godot $root))
    }
}
Check 'Godot command parsing retains quoted project paths containing spaces' {
    $project = 'C:\Game Projects\Totolina Merge'
    Assert (Test-GodotEditorCommand (Process 205 0 $godot ('"' + $godot + '" --editor --path "' + $project + '"')) $godot $project)
    Assert (-not (Test-GodotEditorCommand (Process 205 0 $godot ('"' + $godot + '" --editor --path "' + $project + 'Other"')) $godot $project))
}
Check 'duplicate Godot project path flags cannot prove a single project' {
    $command = $godotCommand + ' --path "C:\OtherProject"'
    Assert (-not (Test-GodotEditorCommand (Process 206 0 $godot $command) $godot $root))
}
Check 'relative, drive-relative and volume-relative Godot argv0 cannot prove executable identity' {
    foreach ($executableArgument in @([IO.Path]::GetFileName($godot), 'C:Tools\Godot\Godot_v4.7.2-stable_win64.exe',
            '\Tools\Godot\Godot_v4.7.2-stable_win64.exe')) {
        $command = '"' + $executableArgument + '" --editor --path "' + $root + '"'
        Assert (-not (Test-GodotEditorCommand (Process 207 0 $godot $command) $godot $root))
    }
}
Check 'relative, drive-relative, volume-relative and network Godot project paths cannot prove the checkout' {
    foreach ($project in @('.', 'D:totolina-merge', $root.Substring(2), '\\host\share\totolina-merge')) {
        $command = '"' + $godot + '" --editor --path "' + $project + '"'
        Assert (-not (Test-GodotEditorCommand (Process 208 0 $godot $command) $godot $root))
        $projectFile = $project.TrimEnd('\') + '\project.godot'
        $command = '"' + $godot + '" --editor "' + $projectFile + '"'
        Assert (-not (Test-GodotEditorCommand (Process 208 0 $godot $command) $godot $root))
    }
}
Check 'absolute project.godot and short editor flags prove the checkout in either argument order' {
    $projectFile = Join-Path $root 'project.godot'
    foreach ($arguments in @(('--editor "' + $projectFile + '"'), ('"' + $projectFile + '" --editor'),
            ('-e "' + $projectFile + '"'), ('"' + $projectFile + '" -e'), ('"' + $projectFile + '"'),
            ('-e --path "' + $root + '"'), ('--path "' + $root + '" -e'))) {
        $command = '"' + $godot + '" ' + $arguments
        Assert (Test-GodotEditorCommand (Process 209 0 $godot $command) $godot $root) $arguments
    }
}
Check 'Project Manager flag alongside valid editor and project arguments is rejected' {
    foreach ($arguments in @(('--editor --path "' + $root + '" --project-manager'),
            ('--project-manager --editor --path "' + $root + '"'))) {
        $command = '"' + $godot + '" ' + $arguments
        Assert (-not (Test-GodotEditorCommand (Process 210 0 $godot $command) $godot $root))
    }
}

function Check-GodotLaunch($Name, [scriptblock]$Scenario) {
    Check $Name {
        $fixture = [pscustomobject]@{ Processes = @(); Starts = [Collections.Generic.List[object]]::new() }
        function Get-LauncherProcesses { $fixture.Processes }
        function Start-Process {
            param($FilePath, $ArgumentList, $WorkingDirectory, [switch]$PassThru, $WindowStyle)
            $fixture.Starts.Add([pscustomobject]@{ FilePath = $FilePath; Arguments = $ArgumentList; WorkingDirectory = $WorkingDirectory })
        }
        function Stop-VerifiedProcess { throw 'Godot editors must never be closed by the launcher.' }
        & $Scenario
    }
}
Check-GodotLaunch 'Godot launch uses configured executable and --editor --path for this checkout' {
    Ensure-GodotEditor $godot $root
    Assert ($fixture.Starts.Count -eq 1)
    Assert (Test-SamePath $fixture.Starts[0].FilePath $godot)
    Assert ($fixture.Starts[0].Arguments -ceq ('--editor --path "' + $root + '"')) $fixture.Starts[0].Arguments
    Assert (Test-SamePath $fixture.Starts[0].WorkingDirectory $root)
}
Check-GodotLaunch 'already running Godot editor for this checkout is reused' {
    $fixture.Processes = @(Process 201 0 $godot $godotCommand)
    Ensure-GodotEditor $godot $root
    Assert ($fixture.Starts.Count -eq 0)
}
Check-GodotLaunch 'Godot opened on another project stays open while this checkout is launched' {
    $fixture.Processes = @(Process 201 0 $godot ('"' + $godot + '" --editor --path "C:\OtherProject"'))
    Ensure-GodotEditor $godot $root
    Assert ($fixture.Starts.Count -eq 1)
}
Check-GodotLaunch 'same-name Godot from another executable cannot prevent the configured launch' {
    $fixture.Processes = @(Process 201 0 'C:\Other\Godot_v4.7.2-stable_win64.exe' $godotCommand)
    Ensure-GodotEditor $godot $root
    Assert ($fixture.Starts.Count -eq 1)
}
Check-GodotLaunch 'uninspectable Godot command line does not imply the correct project' {
    $fixture.Processes = @(Process 201 0 $godot '')
    Ensure-GodotEditor $godot $root
    Assert ($fixture.Starts.Count -eq 1)
}

function Check-GodotWorkflow($Name, [scriptblock]$Scenario) {
    Check $Name {
        $fixture = [pscustomobject]@{ Events = [Collections.Generic.List[string]]::new(); Leftovers = @(); KeepOpen = $null }
        function Assert-Executable { param($Path, $Kind) $fixture.Events.Add("validate:$Kind") }
        function Ensure-Application {
            param($Path, $Label, $Root, [switch]$Desktop)
            Assert ($Desktop.IsPresent -and $Label -eq 'ChatGPT/Codex Desktop') 'Godot workflows may only open Desktop through Ensure-Application.'
            $fixture.Events.Add('open:desktop')
        }
        function Ensure-GodotEditor { param($Path, $Root) $fixture.Events.Add('open:godot') }
        function Close-Desktop { param($Path, $KeepOpenPath = $null) $fixture.KeepOpen = $KeepOpenPath; $fixture.Events.Add('close:desktop'); @($fixture.Leftovers) }
        function Clear-StaleBridgePort {
            param($Root, $DesktopOwned, [int]$Port = 43127, $Module = 'core.server')
            $fixture.Events.Add("clear:${Port}:$Module")
        }
        function Wait-ForExit { param($Snapshots, $Seconds) @($Snapshots) }
        function Stop-VerifiedProcess { throw 'Workflow must not directly terminate Godot or any other application.' }
        function Start-Process { throw 'Unmocked application launch or manually launched MCP server.' }
        & $Scenario
    }
}
Check-GodotWorkflow 'git godot opens Desktop and Godot without Photoshop, UDT or bridge cleanup' {
    Invoke-Workflow 'godot' $config $root
    Assert (($fixture.Events | Where-Object { $_ -notlike 'validate:*' }) -join ',' -eq 'open:desktop,open:godot')
    Assert (($fixture.Events | Where-Object { $_ -like 'validate:*' }) -join ',' -eq 'validate:desktopExe,validate:godotExe')
}
Check-GodotWorkflow 'git godot-refresh restarts Desktop and cleans only Godot MCP port 43128' {
    Invoke-Workflow 'godot-refresh' $config $root
    Assert (($fixture.Events | Where-Object { $_ -notlike 'validate:*' }) -join ',' -eq 'close:desktop,clear:43128:core.godot_server,open:desktop')
}
Check-GodotWorkflow 'refresh asks Desktop recovery to preserve configured Godot and never launches or closes it' {
    Invoke-Workflow 'godot-refresh' $config $root
    Assert (Test-SamePath $fixture.KeepOpen $godot)
    Assert ($fixture.Events.Contains('open:desktop'))
    Assert (-not $fixture.Events.Contains('open:godot'))
}
Check-GodotWorkflow 'lingering non-Godot Desktop children stop refresh before reopening Desktop' {
    $fixture.Leftovers = @(Process 301 10 'C:\Other\worker.exe')
    Throws { Invoke-Workflow 'godot-refresh' $config $root } 'Recovery stopped'
    Assert (-not $fixture.Events.Contains('open:desktop'))
}

Check 'Desktop recovery excludes existing Godot and its descendants from waits and termination' {
    $desktop = Process 10 0 $config.desktopExe
    $editor = Process 201 10 $godot $godotCommand
    $editorChild = Process 202 201 'C:\Tools\Godot\renderer.exe'
    $fixture = [pscustomobject]@{ Closed = $false; Waited = [Collections.Generic.List[int]]::new() }
    function Get-LauncherProcesses {
        if ($fixture.Closed) { @($editor, $editorChild) } else { @($desktop, $editor, $editorChild) }
    }
    function Request-DesktopClose { param($Snapshot) Assert ($Snapshot.ProcessId -eq 10); $fixture.Closed = $true }
    function Wait-ForExit {
        param($Snapshots, $Seconds)
        foreach ($snapshot in @($Snapshots)) { $fixture.Waited.Add($snapshot.ProcessId) }
        @()
    }
    function Stop-VerifiedProcess { throw 'Preserved Godot process must never be terminated.' }
    Assert (@(Close-Desktop $config.desktopExe $godot).Count -eq 0)
    Assert $fixture.Closed
    Assert (-not $fixture.Waited.Contains(201))
    Assert (-not $fixture.Waited.Contains(202))
}
Check 'preserving Godot does not bypass the refresh self-parent safety guard' {
    $desktop = Process 10 0 $config.desktopExe
    $editor = Process 201 10 $godot $godotCommand
    $self = Process $PID 201 (Join-Path $PSHOME 'powershell.exe')
    function Get-LauncherProcesses { @($desktop, $editor, $self) }
    function Request-DesktopClose { throw 'Self-parent guard must run before requesting Desktop close.' }
    function Stop-VerifiedProcess { throw 'Self-parent guard must run before terminating any process.' }
    Throws { Close-Desktop $config.desktopExe $godot } 'own parent session|external Git Bash'
}

Check 'Godot bridge command proof excludes Photoshop, lookalikes and another checkout' {
    Assert (Test-ServerCommand $godotBridge $venv 'core.godot_server')
    foreach ($command in @(' -B -m core.server', ' -B -m core.godot_server.extra',
            ' -B -m core.godot_server --other', ' -m core.godot_server', ' -c core.godot_server')) {
        Assert (-not (Test-ServerCommand (Process 101 10 $venv ('"' + $venv + '"' + $command)) $venv 'core.godot_server'))
    }
    Assert (-not (Test-ServerCommand (Process 101 10 'C:\OtherRepo\.venv\Scripts\python.exe' $godotBridge.CommandLine) $venv 'core.godot_server'))
}
Check 'Godot Windows venv child requires exact redirector parent and recorded base executable' {
    function Get-Content { param($LiteralPath) 'executable = C:\Python\python.exe' }
    function Test-Path { param($LiteralPath) $true }
    $child = Process 102 101 'C:\Python\python.exe' '"C:\Python\python.exe" -B -m core.godot_server' ([datetime]'2026-01-01T00:00:01')
    Assert (@(Get-ProvenBridgeProcesses $child @($godotBridge, $child) $root 'core.godot_server').Count -eq 2)
    Assert (@(Get-ProvenBridgeProcesses $child @($child) $root 'core.godot_server').Count -eq 0)
    Assert (@(Get-ProvenBridgeProcesses $child @($godotBridge, $child) $root 'core.server').Count -eq 0)
}
Check 'unsupported bridge port and module pairs cannot inspect or terminate processes' {
    function Get-PortOwners { throw 'Unsupported recovery must not inspect port owners.' }
    function Get-LauncherProcesses { throw 'Unsupported recovery must not inspect processes.' }
    function Stop-VerifiedProcess { throw 'Unsupported recovery must not terminate processes.' }
    function Assert-PortFree { throw 'Unsupported recovery must not probe ports.' }
    foreach ($pair in @(@(43128, 'core.server'), @(43127, 'core.godot_server'),
            @(80, 'core.godot_server'), @(43128, 'core.unknown'))) {
        Throws { Clear-StaleBridgePort $root @() $pair[0] $pair[1] } 'Unsupported bridge port/module pair'
    }
}

function Check-GodotPortRecovery($Name, [scriptblock]$Scenario) {
    Check $Name {
        $fixture = [pscustomobject]@{ Processes = @(); Owners = @(); Checks = 0;
            Killed = [Collections.Generic.List[int]]::new(); Ports = [Collections.Generic.List[int]]::new(); Verified = $false }
        function Start-Sleep { param($Milliseconds) }
        function Get-LauncherProcesses { $fixture.Processes }
        function Get-PortOwners {
            param([int]$Port = 43127)
            $fixture.Ports.Add($Port); $fixture.Checks++
            # Avoid real waiting; introduce the listener on the final snapshot as in a port race.
            if ($fixture.Checks -eq 1) { return @() }
            $fixture.Owners
        }
        function Stop-VerifiedProcess { param($Snapshot) $fixture.Killed.Add($Snapshot.ProcessId) }
        function Assert-PortFree {
            param([int]$Port = 43127)
            Assert ($Port -eq 43128); $fixture.Verified = $true
        }
        & $Scenario
        Assert (@($fixture.Ports | Where-Object { $_ -ne 43128 }).Count -eq 0) 'Godot recovery touched Photoshop port 43127.'
    }
}
Check-GodotPortRecovery 'stale exact repository Godot bridge is stopped and port 43128 is verified free' {
    $fixture.Owners = @(101); $fixture.Processes = @($godotBridge)
    Clear-StaleBridgePort $root @() 43128 'core.godot_server'
    Assert (($fixture.Killed -join ',') -eq '101')
    Assert $fixture.Verified
}
Check-GodotPortRecovery 'unknown PID on Godot port 43128 is never killed' {
    $fixture.Owners = @(900); $fixture.Processes = @(Process 900 0 'C:\Other\python.exe')
    Throws { Clear-StaleBridgePort $root @() 43128 'core.godot_server' } 'Unknown port owner'
    Assert ($fixture.Killed.Count -eq 0)
}
Check-GodotPortRecovery 'uninspectable Godot port PID is never killed' {
    $fixture.Owners = @(900); $fixture.Processes = @()
    Throws { Clear-StaleBridgePort $root @() 43128 'core.godot_server' } 'cannot be inspected'
    Assert ($fixture.Killed.Count -eq 0)
}
Check-GodotPortRecovery 'exact Photoshop bridge on Godot port is unknown and never killed' {
    $fixture.Owners = @(101); $fixture.Processes = @(Process 101 10 $venv ('"' + $venv + '" -B -m core.server'))
    Throws { Clear-StaleBridgePort $root @() 43128 'core.godot_server' } 'Unknown port owner'
    Assert ($fixture.Killed.Count -eq 0)
}
Check-GodotPortRecovery 'exact Godot bridge owned by another live client is not proven stale' {
    $fixture.Owners = @(101); $fixture.Processes = @($godotBridge, (Process 10 0 'C:\Other\client.exe'))
    Throws { Clear-StaleBridgePort $root @() 43128 'core.godot_server' } 'not proven stale'
    Assert ($fixture.Killed.Count -eq 0)
}
Check-GodotPortRecovery 'exact Desktop-owned Godot bridge is recoverable while its parent exits' {
    $fixture.Owners = @(101); $fixture.Processes = @($godotBridge, (Process 10 0 'C:\Apps\codex.exe'))
    Clear-StaleBridgePort $root @($godotBridge) 43128 'core.godot_server'
    Assert (($fixture.Killed -join ',') -eq '101')
}

Check 'legacy local launcher config remains readable with optional Godot configuration' {
    $json = [pscustomobject]@{ repositoryRoot = $root; desktopExe = $config.desktopExe;
        photoshopExe = $config.photoshopExe; udtExe = $config.udtExe } | ConvertTo-Json
    function Test-Path { param($LiteralPath) $true }
    function Get-Content { param($LiteralPath, [switch]$Raw) $json }
    $legacy = Read-LauncherConfig $root
    Assert ($legacy.desktopExe -eq $config.desktopExe)
    Assert ($legacy.photoshopExe -eq $config.photoshopExe)
    Assert ($legacy.udtExe -eq $config.udtExe)
}
Check 'Godot local launcher config accepts the optional path and rejects unknown fields' {
    $values = [ordered]@{ repositoryRoot = $root; desktopExe = $config.desktopExe;
        photoshopExe = $config.photoshopExe; udtExe = $config.udtExe; godotExe = $godot }
    $json = $values | ConvertTo-Json
    function Test-Path { param($LiteralPath) $true }
    function Get-Content { param($LiteralPath, [switch]$Raw) $json }
    Assert ((Read-LauncherConfig $root).godotExe -eq $godot)
    $values['unexpected'] = 'C:\Other.exe'; $json = $values | ConvertTo-Json
    Throws { Read-LauncherConfig $root } 'configuration|contain'
}

Check 'setup saves Godot path, preserves legacy art paths and installs seven local aliases' {
    $fixtureRoot = Join-Path ([IO.Path]::GetTempPath()) ('lunitora-godot-launcher-tests-' + [guid]::NewGuid().ToString('N'))
    $null = New-Item -ItemType Directory -Path $fixtureRoot
    try {
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot '../setup.ps1') -Destination (Join-Path $fixtureRoot 'setup.ps1')
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot '../common.ps1') -Destination (Join-Path $fixtureRoot 'common.ps1')
        $fixtureConfig = [ordered]@{ repositoryRoot = $fixtureRoot;
            desktopExe = (Join-Path $fixtureRoot 'ChatGPT.exe'); photoshopExe = (Join-Path $fixtureRoot 'Photoshop.exe');
            udtExe = (Join-Path $fixtureRoot 'Adobe UXP Developer Tools.exe') }
        $fixtureGodot = Join-Path $fixtureRoot 'Godot_v4.7.2-stable_win64.exe'
        foreach ($path in @($fixtureConfig.desktopExe, $fixtureConfig.photoshopExe, $fixtureConfig.udtExe, $fixtureGodot)) {
            $null = New-Item -ItemType File -Path $path
        }
        $fixtureConfig | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $fixtureRoot 'config.local.json') -Encoding UTF8
        # Copy the real scripts, replacing only OS discovery/validation and Git writes.
        # The fixture never launches applications or modifies this checkout's Git config.
        @'
function Get-RepositoryRoot { $script:LauncherDirectory }
function Get-AppxPackage { param($Name, $ErrorAction) @() }
function Assert-Executable {
    param($Path, $Kind)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw 'Fixture executable missing.' }
    Add-Content -LiteralPath (Join-Path $script:LauncherDirectory 'validated.txt') -Value $Kind
}
function git {
    $args | ConvertTo-Json -Compress | Add-Content -LiteralPath (Join-Path $script:LauncherDirectory 'aliases.jsonl')
    $global:LASTEXITCODE = 0
}
function Start-Process { throw 'Setup must not launch applications.' }
function Stop-Process { throw 'Setup must not stop applications.' }
'@ | Add-Content -LiteralPath (Join-Path $fixtureRoot 'common.ps1') -Encoding UTF8
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $fixtureRoot 'setup.ps1') -GodotExe $fixtureGodot
        Assert ($LASTEXITCODE -eq 0) 'Fixture setup failed.'
        $saved = Get-Content -LiteralPath (Join-Path $fixtureRoot 'config.local.json') -Raw | ConvertFrom-Json
        foreach ($key in @('repositoryRoot', 'desktopExe', 'photoshopExe', 'udtExe')) {
            Assert ($saved.$key -eq $fixtureConfig[$key]) "Setup changed existing $key."
        }
        Assert ($saved.godotExe -eq $fixtureGodot)
        $validated = @(Get-Content -LiteralPath (Join-Path $fixtureRoot 'validated.txt'))
        Assert ($validated -contains 'godotExe') 'Setup did not validate the Godot executable.'
        $writes = @(Get-Content -LiteralPath (Join-Path $fixtureRoot 'aliases.jsonl') | ForEach-Object { ,(ConvertFrom-Json $_) })
        Assert ($writes.Count -eq 7) 'Expected seven local aliases.'
        foreach ($mode in @('art', 'art-refresh', 'art-dev', 'dev', 'dev-refresh', 'godot', 'godot-refresh')) {
            $matching = @($writes | Where-Object { $_ -contains "alias.$mode" })
            Assert ($matching.Count -eq 1) "Missing/duplicate alias $mode."
            $entry = $matching[0]
            Assert ($entry.Count -eq 7 -and $entry[0] -eq '-C' -and $entry[1] -eq $fixtureRoot -and
                $entry[2] -eq 'config' -and $entry[3] -eq '--local' -and $entry[4] -eq '--replace-all') 'Alias write was not repository-local.'
            Assert ($entry[6] -ceq ('!powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./tools/operator_launcher/launch.ps1 ' + $mode)) 'Unexpected alias command.'
        }
        Check 'setup rerun without Godot override preserves the saved Godot and art paths' {
            & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $fixtureRoot 'setup.ps1')
            Assert ($LASTEXITCODE -eq 0) 'Fixture setup rerun failed.'
            $rerun = Get-Content -LiteralPath (Join-Path $fixtureRoot 'config.local.json') -Raw | ConvertFrom-Json
            Assert ($rerun.godotExe -eq $fixtureGodot)
            foreach ($key in @('repositoryRoot', 'desktopExe', 'photoshopExe', 'udtExe')) {
                Assert ($rerun.$key -eq $fixtureConfig[$key]) "Setup rerun changed existing $key."
            }
        }
        Check 'legacy setup without Godot still saves art configuration and installs aliases' {
            $fixtureConfig | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $fixtureRoot 'config.local.json') -Encoding UTF8
            Remove-Item -LiteralPath (Join-Path $fixtureRoot 'validated.txt')
            & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $fixtureRoot 'setup.ps1')
            Assert ($LASTEXITCODE -eq 0) 'Legacy fixture setup failed without Godot.'
            $legacySaved = Get-Content -LiteralPath (Join-Path $fixtureRoot 'config.local.json') -Raw | ConvertFrom-Json
            Assert (-not $legacySaved.godotExe)
            foreach ($key in @('repositoryRoot', 'desktopExe', 'photoshopExe', 'udtExe')) {
                Assert ($legacySaved.$key -eq $fixtureConfig[$key]) "Legacy setup changed existing $key."
            }
            $legacyValidated = @(Get-Content -LiteralPath (Join-Path $fixtureRoot 'validated.txt'))
            Assert ($legacyValidated -notcontains 'godotExe') 'Optional missing Godot path must not fail validation.'
            foreach ($key in @('desktopExe', 'photoshopExe', 'udtExe')) {
                Assert ($legacyValidated -contains $key) "Legacy setup skipped $key validation."
            }
        }
    } finally {
        $resolvedFixture = [IO.Path]::GetFullPath($fixtureRoot)
        $tempPrefix = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
        Assert ($resolvedFixture.StartsWith($tempPrefix, [StringComparison]::OrdinalIgnoreCase) -and
            [IO.Path]::GetFileName($resolvedFixture) -like 'lunitora-godot-launcher-tests-*') 'Unsafe fixture cleanup path.'
        Remove-Item -LiteralPath $resolvedFixture -Recurse -Force
    }
}
Write-Host "GODOT LAUNCHER TESTS: $script:passed passed. No real applications started or processes stopped."
