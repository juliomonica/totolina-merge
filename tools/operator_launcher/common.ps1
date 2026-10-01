# Windows PowerShell 5.1; no modules, secrets, or background MCP launchers.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:LauncherDirectory = $PSScriptRoot

function Test-SamePath($Left, $Right) {
    if (-not $Left -or -not $Right) { return $false }
    return [string]::Equals([IO.Path]::GetFullPath($Left).TrimEnd('\', '/'),
        [IO.Path]::GetFullPath($Right).TrimEnd('\', '/'), [StringComparison]::OrdinalIgnoreCase)
}

function Test-AbsoluteLocalPath($Path) {
    # IsPathRooted also accepts D:relative and \current-drive paths on Windows.
    # Neither proves an absolute path without another process's working directory.
    return $Path -and $Path -match '^[A-Za-z]:[\\/]'
}

function Get-RepositoryRoot {
    $expected = [IO.Path]::GetFullPath((Join-Path $script:LauncherDirectory '../..'))
    $root = & git -C $expected rev-parse --show-toplevel
    if ($LASTEXITCODE -ne 0 -or -not (Test-SamePath $root $expected)) {
        throw 'Launcher must be inside the totolina-merge checkout.'
    }
    $project = Get-Content -LiteralPath (Join-Path $root 'project.godot') -Raw
    $manifest = Get-Content -LiteralPath (Join-Path $root 'tools/lunitora_mcp/bridges/photoshop_uxp/manifest.json') -Raw | ConvertFrom-Json
    if ($project -notmatch '(?m)^config/name="Totolina Merge"\r?$' -or
        $manifest.id -cne 'com.lunitora.photoshop.bridge') {
        throw 'This is not the expected Totolina Merge project and Lunitora bridge.'
    }
    return [IO.Path]::GetFullPath($root)
}

function Assert-Executable($Path, $Kind) {
    if (-not $Path) { throw "$Kind is not configured. Run tools/operator_launcher/setup.ps1 with an explicit override." }
    if (-not (Test-AbsoluteLocalPath $Path) -or
        -not (Test-Path -LiteralPath $Path -PathType Leaf) -or [IO.Path]::GetExtension($Path) -ine '.exe') {
        throw "$Kind must be an existing absolute local .exe path. Run setup again after application updates."
    }
    $item = Get-Item -LiteralPath $Path
    if ($Kind -eq 'godotExe') {
        if ($item.Name -notmatch '^Godot(?:_[A-Za-z0-9._-]+)?\.exe$' -or
            $item.VersionInfo.ProductName -cne 'Godot Engine' -or
            $item.VersionInfo.ProductVersion -cnotmatch '^4\.7\.2\.stable\.official(?:\.[A-Za-z0-9]+)?$') {
            throw 'godotExe must identify itself as the official Godot Engine 4.7.2 stable editor.'
        }
        return
    }
    $names = switch ($Kind) {
        'desktopExe' { @('ChatGPT.exe', 'Codex.exe') }
        'photoshopExe' { @('Photoshop.exe') }
        'udtExe' { @('Adobe UXP Developer Tools.exe', 'UXP Developer Tool.exe') }
    }
    if ($item.Name -notin $names) { throw "Unexpected executable filename for $Kind." }
    # In particular, never mistake the Codex CLI/app-server for the desktop UI.
    if ($Kind -eq 'desktopExe' -and $item.VersionInfo.ProductName -notmatch '^(Codex|ChatGPT)$') {
        throw 'Desktop executable must identify itself as the Codex or ChatGPT desktop product.'
    }
}

function Read-LauncherConfig($Root) {
    $path = Join-Path $script:LauncherDirectory 'config.local.json'
    if (-not (Test-Path -LiteralPath $path)) { throw 'First run setup.ps1 from Git Bash. See tools/LUNITORA_COMMANDS.md.' }
    $config = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
    $keys = @($config.PSObject.Properties.Name)
    $required = @('repositoryRoot', 'desktopExe', 'photoshopExe', 'udtExe')
    if (@($keys | Where-Object { $_ -notin ($required + 'godotExe') }).Count -or
        @($required | Where-Object { $_ -notin $keys }).Count) {
        throw 'Local configuration requires repositoryRoot, desktopExe, photoshopExe and udtExe; godotExe is optional.'
    }
    if (-not (Test-SamePath $Root $config.repositoryRoot)) { throw 'Local configuration belongs to a different checkout. Run setup here.' }
    if ('godotExe' -notin $keys) { $config | Add-Member NoteProperty godotExe $null }
    return $config
}

function Get-LauncherProcesses {
    # Failure to inspect is an error, never interpreted as an empty process list.
    return @(Get-CimInstance Win32_Process -ErrorAction Stop)
}

function Test-ProcessIdentity($Left, $Right) {
    return $null -ne $Left -and $null -ne $Right -and
        $Left.ProcessId -eq $Right.ProcessId -and $null -ne $Left.CreationDate -and
        $Left.CreationDate -eq $Right.CreationDate -and
        (Test-SamePath $Left.ExecutablePath $Right.ExecutablePath)
}

function Test-ProcessStartTime([datetime]$Actual, [datetime]$Recorded) {
    # CIM records microseconds; .NET retains the final 100-nanosecond digit.
    $ticks = $Actual.ToUniversalTime().Ticks
    return ($ticks - ($ticks % 10)) -eq $Recorded.ToUniversalTime().Ticks
}

function Get-DesktopProcesses($Processes, $Path) {
    return @($Processes | Where-Object { Test-SamePath $_.ExecutablePath $Path })
}

function Get-OwnedDescendants($Processes, $Parents) {
    $owned = @($Parents)
    do {
        $more = @($Processes | Where-Object {
            $candidate = $_
            $candidate.ProcessId -notin @($owned.ProcessId) -and @($owned | Where-Object {
                $_.ProcessId -eq $candidate.ParentProcessId -and $_.CreationDate -le $candidate.CreationDate
            }).Count -gt 0
        })
        $owned += $more
    } while ($more.Count)
    return @($owned | Where-Object { $_.ProcessId -notin @($Parents.ProcessId) })
}

function Stop-VerifiedProcess($Snapshot) {
    $fresh = @(Get-LauncherProcesses | Where-Object { $_.ProcessId -eq $Snapshot.ProcessId })
    if (-not $fresh.Count) { return }
    if (-not (Test-ProcessIdentity $Snapshot $fresh[0])) { throw 'Process identity changed; refusing termination.' }
    try { $live = [Diagnostics.Process]::GetProcessById([int]$Snapshot.ProcessId) }
    catch [ArgumentException] { return }
    try {
        # Hold the OS process handle and verify creation time/path to defeat PID reuse.
        $null = $live.Handle
        if (-not (Test-ProcessStartTime $live.StartTime $Snapshot.CreationDate) -or
            -not (Test-SamePath $live.MainModule.FileName $Snapshot.ExecutablePath)) {
            throw 'Process identity could not be proven; refusing termination.'
        }
        $live.Kill()
        if (-not $live.WaitForExit(5000)) { throw 'Verified process did not exit.' }
    } finally { $live.Dispose() }
}

function Request-DesktopClose($Snapshot) {
    $live = [Diagnostics.Process]::GetProcessById([int]$Snapshot.ProcessId)
    try {
        $null = $live.Handle
        if ((Test-ProcessStartTime $live.StartTime $Snapshot.CreationDate) -and
            (Test-SamePath $live.MainModule.FileName $Snapshot.ExecutablePath)) {
            $null = $live.CloseMainWindow()
        }
    } finally { $live.Dispose() }
}

function Wait-ForExit($Snapshots, [int]$Seconds) {
    if (-not @($Snapshots).Count) { return @() }
    $clock = [Diagnostics.Stopwatch]::StartNew()
    do {
        $current = @(Get-LauncherProcesses)
        $remaining = @($Snapshots | Where-Object {
            $snapshot = $_
            @($current | Where-Object { Test-ProcessIdentity $snapshot $_ }).Count -gt 0
        })
        if (-not $remaining.Count) { return @() }
        if ($clock.Elapsed.TotalSeconds -ge $Seconds) { return $remaining }
        Start-Sleep -Milliseconds 250
    } while ($true)
}

function Close-Desktop($Path, $KeepOpenPath = $null) {
    $all = @(Get-LauncherProcesses)
    $desktop = @(Get-DesktopProcesses $all $Path)
    if (-not $desktop.Count) { return @() }
    $owned = @(Get-OwnedDescendants $all $desktop)
    if ($owned.Count -and $PID -in @($owned.ProcessId)) {
        throw 'Run refresh from an external Git Bash window, after desktop work finishes. It cannot close its own parent session.'
    }
    # An editor started by Desktop can be a descendant. Preserve its entire tree,
    # regardless of project arguments: any open editor may have unsaved work.
    $protected = @(Get-DesktopProcesses $all $KeepOpenPath)
    if ($protected.Count) {
        $protected += @(Get-OwnedDescendants $all $protected)
        $owned = @($owned | Where-Object { $_.ProcessId -notin @($protected.ProcessId) })
    }
    Write-Host 'Closing ChatGPT/Codex Desktop (active desktop work will stop)...'
    foreach ($process in $desktop) {
        # Processes can exit between the snapshot and CloseMainWindow.
        try { Request-DesktopClose $process } catch [ArgumentException] { }
    }
    $remaining = @(Wait-ForExit $desktop 8)
    foreach ($process in $remaining) { Stop-VerifiedProcess $process }
    if (@(Get-DesktopProcesses @(Get-LauncherProcesses) $Path).Count) {
        throw 'Desktop is still running; close it completely and retry from external Git Bash.'
    }
    return @(Wait-ForExit $owned 10)
}

function Get-PortOwners([int]$Port = 43127) {
    # IPGlobalProperties is independent of localized netstat output. CIM supplies PIDs.
    $listeners = @([Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners() |
        Where-Object { $_.Port -eq $Port })
    if (-not $listeners.Count) { return @() }
    $rows = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop)
    if (-not $rows.Count) { throw 'Port is occupied but the listener identity is unavailable.' }
    return @($rows.OwningProcess | Sort-Object -Unique)
}

function Assert-PortFree([int]$Port = 43127) {
    if (@(Get-PortOwners $Port).Count) { throw "Port $Port is still occupied." }
    $probe = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $Port)
    $probe.Server.ExclusiveAddressUse = $true
    try { $probe.Start() } finally { $probe.Stop() }
}

function Test-ServerCommand($Process, $Executable, $Module = 'core.server') {
    if ($Module -cnotin @('core.server', 'core.godot_server')) { return $false }
    if (-not (Test-SamePath $Process.ExecutablePath $Executable)) { return $false }
    # Exact allowlist; no -c, shell wrapper, extra flags, lookalike modules or substring match.
    $escaped = [regex]::Escape($Executable)
    return $Process.CommandLine -cmatch ('^(?i:"' + $escaped + '"|' + $escaped + ')\s+-B\s+-m\s+' + [regex]::Escape($Module) + '\s*$')
}

function Get-ProvenBridgeProcesses($Owner, $Processes, $Root, $Module = 'core.server') {
    $venv = Join-Path $Root 'tools/lunitora_mcp/.venv/Scripts/python.exe'
    if (Test-ServerCommand $Owner $venv $Module) { return @($Owner) }
    # Windows venv python is a redirector. Require its live, exact repo parent,
    # the base executable recorded in pyvenv.cfg, exact argv and creation order.
    $parent = @($Processes | Where-Object { $_.ProcessId -eq $Owner.ParentProcessId })
    $cfg = Join-Path $Root 'tools/lunitora_mcp/.venv/pyvenv.cfg'
    if ($parent.Count -ne 1 -or -not (Test-ServerCommand $parent[0] $venv $Module) -or
        $parent[0].CreationDate -gt $Owner.CreationDate -or -not (Test-Path -LiteralPath $cfg)) { return @() }
    $base = @(Get-Content -LiteralPath $cfg | Where-Object { $_ -match '^executable = (.+)$' } |
        ForEach-Object { $_.Substring(13).Trim() })
    if ($base.Count -eq 1 -and (Test-ServerCommand $Owner $base[0] $Module)) { return @($Owner, $parent[0]) }
    return @()
}

function Clear-StaleBridgePort($Root, $DesktopOwned, [int]$Port = 43127, $Module = 'core.server') {
    if (-not (($Port -eq 43127 -and $Module -ceq 'core.server') -or
        ($Port -eq 43128 -and $Module -ceq 'core.godot_server'))) {
        throw 'Unsupported bridge port/module pair. Nothing terminated.'
    }
    $clock = [Diagnostics.Stopwatch]::StartNew()
    while (@(Get-PortOwners $Port).Count -and $clock.Elapsed.TotalSeconds -lt 10) { Start-Sleep -Milliseconds 250 }
    foreach ($ownerId in @(Get-PortOwners $Port)) {
        $all = @(Get-LauncherProcesses)
        $owners = @($all | Where-Object { $_.ProcessId -eq $ownerId })
        if ($owners.Count -ne 1) { throw "Port $Port owner PID $ownerId cannot be inspected. Nothing terminated." }
        $owner = $owners[0]
        # Never echo arbitrary command lines: other applications may put secrets there.
        Write-Host "Port $Port owner: PID $ownerId; $($owner.Name); $($owner.ExecutablePath)"
        $proof = @(Get-ProvenBridgeProcesses $owner $all $Root $Module)
        if (-not $proof.Count) { throw 'Unknown port owner. Nothing terminated. Close its owning application yourself.' }
        $anchor = $proof[-1]
        $wasOwned = @($DesktopOwned | Where-Object { Test-ProcessIdentity $_ $owner }).Count -gt 0
        $parentAlive = @($all | Where-Object { $_.ProcessId -eq $anchor.ParentProcessId }).Count -gt 0
        if (-not $wasOwned -and $parentAlive) { throw 'Exact bridge belongs to another live process; it is not proven stale. Nothing terminated.' }
        foreach ($process in $proof) { Stop-VerifiedProcess $process }
    }
    Assert-PortFree $Port
    Write-Host "Port $Port is free."
}

function Get-DesktopLaunchTarget($Path) {
    Assert-Executable $Path 'desktopExe'
    # A parent PowerShell 7 process can prepend its modules to PSModulePath.
    # Load this host's built-in security module, preserving publisher validation.
    Import-Module (Join-Path $PSHOME 'Modules/Microsoft.PowerShell.Security/Microsoft.PowerShell.Security.psd1') -ErrorAction Stop
    # File/product names alone are insufficient proof for an executable fallback.
    $signature = Get-AuthenticodeSignature -LiteralPath $Path -ErrorAction Stop
    if ($signature.Status -ne 'Valid' -or $null -eq $signature.SignerCertificate -or
        $signature.SignerCertificate.GetNameInfo([Security.Cryptography.X509Certificates.X509NameType]::SimpleName, $false) -notmatch
            '^OpenAI(?: OpCo)?(?:,? (?:LLC|Inc\.?))?$') {
        throw 'Desktop executable must have a valid OpenAI publisher signature.'
    }
    $fullPath = [IO.Path]::GetFullPath($Path)
    # Use current-user registration, not a guessed package name, version or AUMID.
    # Discovery failures must never turn a packaged app into an executable launch.
    $packages = @(Get-AppxPackage -ErrorAction Stop | Where-Object {
        $_.InstallLocation -and $fullPath.StartsWith(
            [IO.Path]::GetFullPath($_.InstallLocation).TrimEnd('\', '/') + '\',
            [StringComparison]::OrdinalIgnoreCase)
    })
    if ($packages.Count -gt 1) { throw 'Desktop package registration is ambiguous; refusing launch.' }
    if ($packages.Count -eq 1) {
        $package = $packages[0]
        $manifest = Get-AppxPackageManifest -Package $package -ErrorAction Stop
        $applications = @($manifest.Package.Applications.Application | Where-Object {
            $executable = $_.GetAttribute('Executable')
            $executable -and (Test-SamePath (Join-Path $package.InstallLocation $executable) $fullPath)
        })
        if ($applications.Count -ne 1) {
            throw 'Desktop package must register exactly one application for the verified ChatGPT/Codex executable.'
        }
        $aumid = $package.PackageFamilyName + '!' + $applications[0].GetAttribute('Id')
        if ($aumid -cnotmatch '^[A-Za-z0-9._-]+![A-Za-z0-9._-]+$') { throw 'Invalid Desktop application identity.' }
        return [pscustomobject]@{ Kind = 'Packaged'; Aumid = $aumid; Executable = $fullPath }
    }
    # An unregistered/staged package is not an unpackaged installation. Also
    # reject package manifests outside WindowsApps (for example a loose layout).
    if ($fullPath -match '(?i)[\\/]WindowsApps[\\/]') { throw 'Desktop package is not registered; refusing direct executable launch.' }
    $directory = [IO.Path]::GetDirectoryName($fullPath)
    while ($directory) {
        if (Test-Path -LiteralPath (Join-Path $directory 'AppxManifest.xml') -PathType Leaf) {
            throw 'Desktop has a package manifest but no matching registration; refusing direct executable launch.'
        }
        $directory = [IO.Path]::GetDirectoryName($directory)
    }
    return [pscustomobject]@{ Kind = 'Unpackaged'; Aumid = $null; Executable = $fullPath }
}

function Ensure-Application($Path, $Label, $Root, [switch]$Desktop) {
    if (@(Get-DesktopProcesses @(Get-LauncherProcesses) $Path).Count) {
        Write-Host "$Label is already running."
        return
    }
    # These are interactive applications the operator explicitly requested to see.
    if ($Desktop) {
        $target = Get-DesktopLaunchTarget $Path
        if ($target.Kind -eq 'Packaged') {
            # Windows activation supplies package identity; never execute the
            # WindowsApps binary directly, even if activation reports an error.
            $null = Start-Process -FilePath (Join-Path $env:WINDIR 'explorer.exe') -ArgumentList ('shell:AppsFolder\' + $target.Aumid) -PassThru
        } else {
            $null = Start-Process -FilePath $target.Executable -WorkingDirectory $Root -PassThru
        }
    } else {
        $null = Start-Process -FilePath $Path -WorkingDirectory $Root -PassThru
    }
    Write-Host "$Label launch requested."
}

function ConvertFrom-WindowsCommandLine($CommandLine) {
    # Accept the unambiguous subset used by this launcher/Godot's project manager:
    # whole quoted arguments or bare words. Fail closed on mixed/escaped quotes.
    # Do not execute or log the command line.
    if (-not $CommandLine -or $CommandLine -match '[\r\n]') { return @() }
    $tokens = [Collections.Generic.List[string]]::new()
    $remaining = $CommandLine.Trim()
    while ($remaining.Length) {
        $match = [regex]::Match($remaining, '^(?:"([^"\r\n]*)"|([^\s"]+))(?=\s|$)')
        if (-not $match.Success) { return @() }
        if ($match.Groups[1].Success) {
            $value = $match.Groups[1].Value
            if ($value.EndsWith('\')) { return @() }
        } else { $value = $match.Groups[2].Value }
        $tokens.Add($value)
        $remaining = $remaining.Substring($match.Length).TrimStart()
    }
    return $tokens.ToArray()
}

function Test-GodotEditorCommand($Process, $Executable, $Root) {
    if (-not (Test-SamePath $Process.ExecutablePath $Executable)) { return $false }
    $argv = @(ConvertFrom-WindowsCommandLine $Process.CommandLine)
    if ($argv.Count -lt 2 -or -not (Test-AbsoluteLocalPath $argv[0]) -or
        -not (Test-SamePath $argv[0] $Executable)) { return $false }
    $editorFlag = $false
    $projectFile = $false
    $project = $null
    for ($index = 1; $index -lt $argv.Count; $index++) {
        $argument = $argv[$index]
        switch -CaseSensitive ($argument) {
            { $_ -cin @('--editor', '-e') } {
                if ($editorFlag) { return $false }
                $editorFlag = $true
            }
            '--path' {
                if ($project -or $index + 1 -ge $argv.Count) { return $false }
                $index++
                # A relative path cannot be proven without the process cwd.
                if (-not (Test-AbsoluteLocalPath $argv[$index])) { return $false }
                $project = $argv[$index]
            }
            default {
                # Godot also supports an absolute project.godot positional arg.
                # Unknown switches, Project Manager and runtime args are not proof.
                if ($project -or -not (Test-AbsoluteLocalPath $argument) -or
                    [IO.Path]::GetFileName($argument) -cne 'project.godot') { return $false }
                $project = [IO.Path]::GetDirectoryName($argument)
                $projectFile = $true
            }
        }
    }
    return ($editorFlag -or $projectFile) -and (Test-SamePath $project $Root)
}

function Ensure-GodotEditor($Path, $Root) {
    $editors = @(Get-LauncherProcesses | Where-Object { Test-GodotEditorCommand $_ $Path $Root })
    if ($editors.Count) {
        Write-Host 'Godot editor is already running for this checkout.'
        return
    }
    # Use an explicit project path, never the Project Manager. Start-Process on
    # Windows PowerShell joins arguments; quote the path to preserve spaces.
    $projectPath = [IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
    $null = Start-Process -FilePath $Path -ArgumentList ('--editor --path "' + $projectPath + '"') -WorkingDirectory $Root -PassThru
    Write-Host 'Godot editor launch requested for this checkout.'
}

function Invoke-Workflow($Mode, $Config, $Root) {
    Assert-Executable $Config.desktopExe 'desktopExe'
    $art = $Mode -in @('art', 'art-refresh', 'art-dev')
    if ($art) { Assert-Executable $Config.photoshopExe 'photoshopExe' }
    if ($Mode -eq 'art-dev') { Assert-Executable $Config.udtExe 'udtExe' }
    $godot = $Mode -in @('godot', 'godot-refresh')
    if ($godot) {
        $godotPath = if ($Config.PSObject.Properties['godotExe']) { $Config.godotExe } else { $null }
        Assert-Executable $godotPath 'godotExe'
    }
    if ($Mode -in @('art-refresh', 'dev-refresh', 'godot-refresh')) {
        if ($Mode -eq 'godot-refresh') {
            Write-Host 'Keeping Godot open to protect unsaved editor work.'
            $leftovers = @(Close-Desktop $Config.desktopExe $godotPath)
            Clear-StaleBridgePort $Root $leftovers 43128 'core.godot_server'
        } else { $leftovers = @(Close-Desktop $Config.desktopExe) }
        if ($Mode -eq 'art-refresh') { Clear-StaleBridgePort $Root $leftovers }
        $leftovers = @(Wait-ForExit $leftovers 2)
        if ($leftovers.Count) {
            Write-Host ('Desktop-owned processes still exiting: ' + (($leftovers | ForEach-Object { "$($_.Name) (PID $($_.ProcessId))" }) -join ', '))
            throw 'Recovery stopped before reopening Desktop. No unrelated process was terminated. Retry after those processes exit.'
        }
    }
    if ($art) { Ensure-Application $Config.photoshopExe 'Photoshop' $Root }
    if ($Mode -eq 'art-dev') {
        Write-Host 'DEVELOPER ONLY: UXP Developer Tool is for loading, packaging and debugging.'
        Ensure-Application $Config.udtExe 'UXP Developer Tool' $Root
    }
    Ensure-Application $Config.desktopExe 'ChatGPT/Codex Desktop' $Root -Desktop
    if ($Mode -eq 'godot') { Ensure-GodotEditor $godotPath $Root }
    Write-Host "OK: $Mode startup complete for $Root. Configured stdio MCP servers remain Desktop-owned."
    if ($godot) { Write-Host 'lunitora_godot stays Codex-owned; the open Godot editor reconnects automatically.' }
    if ($art) {
        Write-Host 'After one-time plugin installation and pairing, try:'
        Write-Host '  Remove the background from <file>.png'
        Write-Host '  Resize <file>.png to 384x384'
        Write-Host '  Remove the background and resize <file>.png to 384x384'
    }
}
