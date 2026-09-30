param([string]$DesktopExe, [string]$PhotoshopExe, [string]$UdtExe)
. (Join-Path $PSScriptRoot 'common.ps1')

function Find-OneExecutable($Candidates, $Kind) {
    $valid = @($Candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Sort-Object -Unique)
    if ($valid.Count -gt 1) { throw "Multiple $Kind installations found. Supply an explicit local override." }
    if ($valid.Count -eq 1) { return $valid[0] }
    return $null
}

try {
    $root = Get-RepositoryRoot
    $local = Join-Path $PSScriptRoot 'config.local.json'
    $old = if (Test-Path -LiteralPath $local) { Read-LauncherConfig $root } else { $null }
    if (-not $DesktopExe) {
        # Discover the desktop package, never the codex CLI on PATH.
        $packages = @(Get-AppxPackage -Name 'OpenAI.Codex' -ErrorAction Stop)
        $candidates = @($packages | ForEach-Object {
            $package = $_
            $applications = ($package | Get-AppxPackageManifest -ErrorAction Stop).Package.Applications.Application
            foreach ($application in $applications) {
                if ([IO.Path]::GetFileName($application.Executable) -in @('ChatGPT.exe', 'Codex.exe')) {
                    Join-Path $package.InstallLocation $application.Executable
                }
            }
        })
        if ($old -and $old.desktopExe -and (Test-Path -LiteralPath $old.desktopExe)) { $DesktopExe = $old.desktopExe }
        else { $DesktopExe = Find-OneExecutable $candidates 'desktop' }
    }
    if (-not $PhotoshopExe) {
        if ($old -and $old.photoshopExe -and (Test-Path -LiteralPath $old.photoshopExe)) { $PhotoshopExe = $old.photoshopExe }
        else {
            $adobe = Join-Path $env:ProgramFiles 'Adobe'
            $candidates = @(Get-ChildItem -LiteralPath $adobe -Directory -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -like 'Adobe Photoshop *' } | ForEach-Object { Join-Path $_.FullName 'Photoshop.exe' })
            $PhotoshopExe = Find-OneExecutable $candidates 'Photoshop'
        }
    }
    if (-not $UdtExe) {
        if ($old -and $old.udtExe -and (Test-Path -LiteralPath $old.udtExe)) { $UdtExe = $old.udtExe }
        else { $UdtExe = Find-OneExecutable @((Join-Path $env:ProgramFiles 'Adobe/Adobe UXP Developer Tools/Adobe UXP Developer Tools.exe')) 'UDT' }
    }
    $config = [ordered]@{ repositoryRoot = $root; desktopExe = $DesktopExe; photoshopExe = $PhotoshopExe; udtExe = $UdtExe }
    Assert-Executable $DesktopExe 'desktopExe'
    foreach ($key in @('photoshopExe', 'udtExe')) {
        if ($config[$key]) { Assert-Executable $config[$key] $key }
        else { Write-Host "$key not installed; workflows requiring it will explain how to configure it." }
    }
    $config | ConvertTo-Json | Set-Content -LiteralPath $local -Encoding UTF8
    foreach ($mode in @('art', 'art-refresh', 'art-dev', 'dev', 'dev-refresh')) {
        $alias = '!powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./tools/operator_launcher/launch.ps1 ' + $mode
        & git -C $root config --local --replace-all "alias.$mode" $alias
        if ($LASTEXITCODE -ne 0) { throw "Could not install local alias $mode." }
    }
    Write-Host 'Installed five repository-local aliases. Local paths saved; no global Git settings or MCP settings changed.'
    Write-Host 'Use Git Bash in this checkout. See tools/LUNITORA_COMMANDS.md for one-time plugin setup.'
} catch {
    Write-Error $_ -ErrorAction Continue
    exit 1
}
