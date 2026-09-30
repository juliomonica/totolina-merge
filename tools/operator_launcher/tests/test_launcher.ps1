# Dependency-free safety tests. All application/process mutations are mocked.
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
$config = [pscustomobject]@{ desktopExe = 'C:\Apps\ChatGPT.exe'; photoshopExe = 'C:\Apps\Photoshop.exe'; udtExe = 'C:\Apps\Adobe UXP Developer Tools.exe' }
$venv = Join-Path $root 'tools/lunitora_mcp/.venv/Scripts/python.exe'
$wrapper = Process 101 10 $venv ('"' + $venv + '" -B -m core.server')

Check 'repository identity' { Assert ($root -eq (Get-RepositoryRoot)) }
Check 'path identity is full and case insensitive' {
    Assert (Test-SamePath 'C:\Apps\ChatGPT.exe' 'c:/apps/ChatGPT.exe')
    Assert (-not (Test-SamePath $null $config.desktopExe))
}
Check 'missing and wrong executables rejected' {
    Throws { Assert-Executable 'C:\missing\Photoshop.exe' 'photoshopExe' } 'existing absolute'
    Throws { Assert-Executable 'Photoshop.exe' 'photoshopExe' } 'absolute'
    Throws { Assert-Executable $null 'udtExe' } 'not configured'
    Throws { Assert-Executable $PSHOME\powershell.exe 'desktopExe' } 'Unexpected executable'
}
Check 'exact repository Python command accepted' { Assert (Test-ServerCommand $wrapper $venv) }
Check 'lookalikes flags and arbitrary Python rejected' {
    foreach ($command in @(' -m core.server', ' -b -m core.server', ' -B -m core.server.extra', ' -B -m core.server --other', ' -c core.server', ' -B -m core.server & other')) {
        $bad = Process 101 10 $venv ('"' + $venv + '"' + $command)
        Assert (-not (Test-ServerCommand $bad $venv))
    }
    Assert (-not (Test-ServerCommand (Process 101 10 'C:\Other\python.exe' $wrapper.CommandLine) $venv))
}
Check 'PID reuse rejected by identity' {
    $reused = Process 101 10 $venv $wrapper.CommandLine ([datetime]'2026-01-02')
    Assert (-not (Test-ProcessIdentity $wrapper $reused))
}
Check 'CIM creation times use microseconds without accepting another microsecond' {
    $recorded = [datetime]::new(639263472946833590)
    Assert (Test-ProcessStartTime ([datetime]::new(639263472946833594)) $recorded)
    Assert (-not (Test-ProcessStartTime ([datetime]::new(639263472946833600)) $recorded))
}
Check 'unrelated same-name desktop excluded' {
    $all = @((Process 1 0 $config.desktopExe), (Process 2 0 'C:\Other\ChatGPT.exe'))
    Assert (@(Get-DesktopProcesses $all $config.desktopExe).Count -eq 1)
}
Check 'owned descendants exclude unrelated and reused-parent PIDs' {
    $desktop = Process 1 0 $config.desktopExe
    $all = @($desktop, (Process 2 1 'C:\Apps\codex.exe'), (Process 3 2 $venv),
        (Process 4 0 'C:\Other\python.exe'), (Process 5 1 'C:\Old.exe' '' ([datetime]'2025-01-01')))
    $ids = @(Get-OwnedDescendants $all @($desktop)).ProcessId
    Assert (($ids -join ',') -eq '2,3')
}
# Each activation scenario gets isolated Windows-registration and process mocks.
function Check-DesktopLaunch($Name, [scriptblock]$Scenario) {
    Check $Name {
        $certificate = [pscustomobject]@{ Publisher = 'OpenAI OpCo, LLC' }
        $certificate | Add-Member ScriptMethod GetNameInfo { param($Type, $Issuer) $this.Publisher }
        $fixture = [pscustomobject]@{
            Path = 'C:\Program Files\WindowsApps\Desktop_1.0\app\ChatGPT.exe'
            Packages = @([pscustomobject]@{ InstallLocation = 'C:\Program Files\WindowsApps\Desktop_1.0'; PackageFamilyName = 'Discovered.Desktop_publisher' })
            Manifest = [xml]'<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"><Applications><Application Id="DesktopUI" Executable="app/ChatGPT.exe"/><Application Id="CommandRunner" Executable="app/resources/codex-command-runner.exe"/></Applications></Package>'
            Signature = [pscustomobject]@{ Status = 'Valid'; SignerCertificate = $certificate }
            Product = 'Codex'
            ManifestOnDisk = $false
            RegistrationError = $false
            ManifestError = $false
            ActivationError = $false
            Processes = @()
            Starts = [Collections.Generic.List[object]]::new()
        }
        function Get-AppxPackage {
            param($ErrorAction)
            if ($fixture.RegistrationError) { throw 'Registration inspection failed' }
            $fixture.Packages
        }
        function Get-AppxPackageManifest {
            param($Package, $ErrorAction)
            Assert ($Package -eq $fixture.Packages[0])
            if ($fixture.ManifestError) { throw 'Manifest inspection failed' }
            $fixture.Manifest
        }
        function Get-AuthenticodeSignature { param($LiteralPath, $ErrorAction) $fixture.Signature }
        function Test-Path {
            param($LiteralPath, $PathType)
            if ([IO.Path]::GetFileName($LiteralPath) -eq 'AppxManifest.xml') { return $fixture.ManifestOnDisk }
            return (Test-SamePath $LiteralPath $fixture.Path)
        }
        function Get-Item {
            param($LiteralPath)
            [pscustomobject]@{ Name = [IO.Path]::GetFileName($LiteralPath); VersionInfo = [pscustomobject]@{ ProductName = $fixture.Product } }
        }
        function Get-LauncherProcesses { $fixture.Processes }
        function Start-Process {
            param($FilePath, $ArgumentList, $WorkingDirectory, [switch]$PassThru)
            $fixture.Starts.Add([pscustomobject]@{ FilePath = $FilePath; Arguments = $ArgumentList; WorkingDirectory = $WorkingDirectory })
            if ($fixture.ActivationError) { throw 'Activation failed' }
        }
        & $Scenario
    }
}
Check-DesktopLaunch 'package identity uses discovered family and exact Desktop application, not the command runner' {
    $target = Get-DesktopLaunchTarget $fixture.Path
    Assert ($target.Kind -eq 'Packaged')
    Assert ($target.Aumid -ceq 'Discovered.Desktop_publisher!DesktopUI')
}
Check-DesktopLaunch 'packaged Desktop activates through Explorer and never executes the WindowsApps binary' {
    Ensure-Application $fixture.Path 'Desktop' $root -Desktop
    Assert ($fixture.Starts.Count -eq 1)
    Assert (Test-SamePath $fixture.Starts[0].FilePath (Join-Path $env:WINDIR 'explorer.exe'))
    Assert ($fixture.Starts[0].Arguments -ceq 'shell:AppsFolder\Discovered.Desktop_publisher!DesktopUI')
    Assert (-not $fixture.Starts[0].WorkingDirectory)
}
Check-DesktopLaunch 'registered package outside WindowsApps also uses application activation' {
    $fixture.Packages[0].InstallLocation = 'C:\RegisteredDesktop'
    $fixture.Path = 'C:\RegisteredDesktop\app\ChatGPT.exe'
    Ensure-Application $fixture.Path 'Desktop' $root -Desktop
    Assert ($fixture.Starts.Count -eq 1)
    Assert ($fixture.Starts[0].Arguments -like 'shell:AppsFolder\*!DesktopUI')
}
Check-DesktopLaunch 'command-runner-only registration cannot masquerade as Desktop' {
    $fixture.Manifest.Package.Applications.Application[0].SetAttribute('Executable', 'app/resources/codex-command-runner.exe')
    Throws { Ensure-Application $fixture.Path 'Desktop' $root -Desktop } 'exactly one application'
    Assert ($fixture.Starts.Count -eq 0)
}
Check-DesktopLaunch 'ambiguous application entries are rejected' {
    $fixture.Manifest.Package.Applications.Application[1].SetAttribute('Executable', 'app/ChatGPT.exe')
    Throws { Get-DesktopLaunchTarget $fixture.Path } 'exactly one application'
}
Check-DesktopLaunch 'ambiguous package registration is rejected' {
    $fixture.Packages = @($fixture.Packages[0], $fixture.Packages[0])
    Throws { Get-DesktopLaunchTarget $fixture.Path } 'ambiguous'
}
Check-DesktopLaunch 'malformed AUMID cannot become Explorer arguments' {
    $fixture.Manifest.Package.Applications.Application[0].SetAttribute('Id', 'DesktopUI --other')
    Throws { Ensure-Application $fixture.Path 'Desktop' $root -Desktop } 'Invalid Desktop application identity'
    Assert ($fixture.Starts.Count -eq 0)
}
Check-DesktopLaunch 'registration inspection failure never falls back to direct execution' {
    $fixture.RegistrationError = $true
    Throws { Ensure-Application $fixture.Path 'Desktop' $root -Desktop } 'Registration inspection failed'
    Assert ($fixture.Starts.Count -eq 0)
}
Check-DesktopLaunch 'manifest inspection failure never falls back to direct execution' {
    $fixture.ManifestError = $true
    Throws { Ensure-Application $fixture.Path 'Desktop' $root -Desktop } 'Manifest inspection failed'
    Assert ($fixture.Starts.Count -eq 0)
}
Check-DesktopLaunch 'activation failure never retries the packaged binary' {
    $fixture.ActivationError = $true
    Throws { Ensure-Application $fixture.Path 'Desktop' $root -Desktop } 'Activation failed'
    Assert ($fixture.Starts.Count -eq 1)
    Assert (Test-SamePath $fixture.Starts[0].FilePath (Join-Path $env:WINDIR 'explorer.exe'))
}
Check-DesktopLaunch 'unregistered WindowsApps executable is not an unpackaged fallback' {
    $fixture.Packages = @()
    Throws { Ensure-Application $fixture.Path 'Desktop' $root -Desktop } 'not registered'
    Assert ($fixture.Starts.Count -eq 0)
}
Check-DesktopLaunch 'unregistered loose package is not an unpackaged fallback' {
    $fixture.Packages = @(); $fixture.Path = 'C:\LooseDesktop\app\ChatGPT.exe'; $fixture.ManifestOnDisk = $true
    Throws { Ensure-Application $fixture.Path 'Desktop' $root -Desktop } 'package manifest'
    Assert ($fixture.Starts.Count -eq 0)
}
Check-DesktopLaunch 'validated OpenAI unpackaged Desktop retains executable startup' {
    $fixture.Packages = @(); $fixture.Path = 'C:\Apps\ChatGPT.exe'
    Ensure-Application $fixture.Path 'Desktop' $root -Desktop
    Assert ($fixture.Starts.Count -eq 1)
    Assert (Test-SamePath $fixture.Starts[0].FilePath $fixture.Path)
    Assert (-not $fixture.Starts[0].Arguments)
    Assert ($fixture.Starts[0].WorkingDirectory -eq $root)
}
Check-DesktopLaunch 'package location matching respects directory boundaries' {
    $fixture.Packages[0].InstallLocation = 'C:\Apps'
    $fixture.Path = 'C:\AppsOther\ChatGPT.exe'
    Assert ((Get-DesktopLaunchTarget $fixture.Path).Kind -eq 'Unpackaged')
}
Check-DesktopLaunch 'unsigned unpackaged executable is rejected' {
    $fixture.Packages = @(); $fixture.Path = 'C:\Apps\ChatGPT.exe'; $fixture.Signature.Status = 'NotSigned'
    Throws { Ensure-Application $fixture.Path 'Desktop' $root -Desktop } 'valid OpenAI publisher signature'
    Assert ($fixture.Starts.Count -eq 0)
}
Check-DesktopLaunch 'another publisher cannot masquerade as ChatGPT' {
    $fixture.Signature.SignerCertificate.Publisher = 'Not OpenAI OpCo, LLC'
    Throws { Ensure-Application $fixture.Path 'Desktop' $root -Desktop } 'valid OpenAI publisher signature'
    Assert ($fixture.Starts.Count -eq 0)
}
Check-DesktopLaunch 'a missing signer certificate is rejected' {
    $fixture.Signature.SignerCertificate = $null
    Throws { Get-DesktopLaunchTarget $fixture.Path } 'valid OpenAI publisher signature'
}
Check-DesktopLaunch 'non-Desktop product cannot use package activation' {
    $fixture.Product = 'Codex CLI'
    Throws { Get-DesktopLaunchTarget $fixture.Path } 'desktop product'
}
Check-DesktopLaunch 'already running Desktop retains exact-path process detection without relaunch' {
    $fixture.Processes = @(Process 1 0 $fixture.Path)
    $fixture.RegistrationError = $true
    Ensure-Application $fixture.Path 'Desktop' $root -Desktop
    Assert ($fixture.Starts.Count -eq 0)
}
Check-DesktopLaunch 'non-Desktop applications retain their executable launch path' {
    $fixture.RegistrationError = $true
    Ensure-Application $config.photoshopExe 'Photoshop' $root
    Assert ($fixture.Starts.Count -eq 1)
    Assert (Test-SamePath $fixture.Starts[0].FilePath $config.photoshopExe)
    Assert ($fixture.Starts[0].WorkingDirectory -eq $root)
}
# Use mocked pyvenv.cfg contents for deterministic redirector identity tests.
function Get-Content { param($LiteralPath) 'executable = C:\Python\python.exe' }
function Test-Path { param($LiteralPath) $true }
$child = Process 102 101 'C:\Python\python.exe' '"C:\Python\python.exe" -B -m core.server' ([datetime]'2026-01-01T00:00:01')
Check 'Windows venv child requires exact parent and base executable' {
    Assert (@(Get-ProvenBridgeProcesses $child @($wrapper, $child) $root).Count -eq 2)
    Assert (@(Get-ProvenBridgeProcesses $child @($child) $root).Count -eq 0)
    $other = Process 102 101 'C:\Other\python.exe' '"C:\Other\python.exe" -B -m core.server'
    Assert (@(Get-ProvenBridgeProcesses $other @($wrapper, $other) $root).Count -eq 0)
}
Check 'direct repository Python is proven without matching by name' {
    Assert (@(Get-ProvenBridgeProcesses $wrapper @($wrapper) $root).Count -eq 1)
}
# Workflow mocks: accidental real starts/stops are impossible in this suite.
function Assert-Executable { param($Path, $Kind) $script:events.Add("validate:$Kind") }
function Ensure-Application {
    param($Path, $Label, $Root, [switch]$Desktop)
    Assert ($Desktop.IsPresent -eq ($Label -eq 'ChatGPT/Codex Desktop')) 'All five commands must select Desktop activation only for Desktop.'
    $script:events.Add("open:$Label")
}
function Close-Desktop { param($Path) $script:events.Add('close:desktop'); return @() }
function Clear-StaleBridgePort { param($Root, $DesktopOwned) $script:events.Add('clear:port') }
function Wait-ForExit { param($Snapshots, $Seconds) return @($Snapshots) }
foreach ($mode in @('art', 'art-refresh', 'art-dev', 'dev', 'dev-refresh')) {
    Check "$mode workflow touches only its specified applications" {
        $script:events = [Collections.Generic.List[string]]::new()
        Invoke-Workflow $mode $config $root
        $actual = @($script:events | Where-Object { $_ -notlike 'validate:*' }) -join ','
        $expected = switch ($mode) {
            'art' { 'open:Photoshop,open:ChatGPT/Codex Desktop' }
            'art-refresh' { 'close:desktop,clear:port,open:Photoshop,open:ChatGPT/Codex Desktop' }
            'art-dev' { 'open:Photoshop,open:UXP Developer Tool,open:ChatGPT/Codex Desktop' }
            'dev' { 'open:ChatGPT/Codex Desktop' }
            'dev-refresh' { 'close:desktop,open:ChatGPT/Codex Desktop' }
        }
        Assert ($actual -eq $expected) $actual
    }
}
Check 'lingering desktop children prevent reopen and are not terminated' {
    function Close-Desktop { @($wrapper) }
    $script:events.Clear()
    Throws { Invoke-Workflow 'dev-refresh' $config $root } 'Recovery stopped'
    Assert (@($script:events | Where-Object { $_ -like 'open:*' }).Count -eq 0)
}
# Restore real recovery orchestration; replace only operating system operations.
. (Join-Path $PSScriptRoot '../common.ps1')
Check 'termination rechecks identity before obtaining an OS handle' {
    function Get-LauncherProcesses { @(Process 101 10 $venv $wrapper.CommandLine ([datetime]'2026-01-02')) }
    Throws { Stop-VerifiedProcess $wrapper } 'identity changed'
}
Check 'desktop with no children closes cleanly' {
    $script:closeRequested = $false
    function Get-LauncherProcesses {
        if (-not $script:closeRequested) { @(Process 101 0 $config.desktopExe) } else { @() }
    }
    function Request-DesktopClose { param($Snapshot) $script:closeRequested = $true }
    Assert (@(Close-Desktop $config.desktopExe).Count -eq 0)
    Assert $script:closeRequested
}
function Start-Sleep { param($Milliseconds) }
function Stop-VerifiedProcess { param($Snapshot) $script:killed.Add($Snapshot.ProcessId) }
function Assert-PortFree { $script:freeChecked = $true }
function Get-LauncherProcesses { return $script:processes }
function Get-PortOwners { return $script:owners }
# Return free during the wait loop, then a listener on the final check (port race).
function Get-PortOwners {
    $script:portChecks++
    if ($script:portChecks -eq 1) { return @() }
    return $script:owners
}
Check 'unknown port owner is reported and never killed' {
    $script:killed = [Collections.Generic.List[int]]::new(); $script:portChecks = 0
    $script:owners = @(900); $script:processes = @((Process 900 10 'C:\Other\python.exe'))
    Throws { Clear-StaleBridgePort $root @() } 'Unknown port owner'
    Assert ($script:killed.Count -eq 0)
}
Check 'live external owner is not mistaken for a stale exact bridge' {
    $script:portChecks = 0; $script:owners = @(101)
    $script:processes = @($wrapper, (Process 10 0 'C:\Other\client.exe'))
    Throws { Clear-StaleBridgePort $root @() } 'not proven stale'
    Assert ($script:killed.Count -eq 0)
}
Check 'proven stale orphan is stopped and port is verified' {
    $script:portChecks = 0; $script:owners = @(101); $script:processes = @($wrapper); $script:freeChecked = $false
    Clear-StaleBridgePort $root @()
    Assert (($script:killed -join ',') -eq '101')
    Assert $script:freeChecked
}
Check 'desktop-owned bridge can be recovered even while parent is exiting' {
    $script:killed.Clear(); $script:portChecks = 0; $script:owners = @(101)
    $script:processes = @($wrapper, (Process 10 0 'C:\Apps\codex.exe'))
    Clear-StaleBridgePort $root @($wrapper)
    Assert (($script:killed -join ',') -eq '101')
}
Write-Host "LAUNCHER TESTS: $script:passed passed. No real processes started or stopped."
