param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('art', 'art-refresh', 'art-dev', 'dev', 'dev-refresh')]
    [string]$Mode,
    [switch]$Check
)
. (Join-Path $PSScriptRoot 'common.ps1')
try {
    $root = Get-RepositoryRoot
    $config = Read-LauncherConfig $root
    if ($Check) {
        foreach ($key in @('desktopExe', 'photoshopExe', 'udtExe')) {
            if ($config.$key) { Assert-Executable $config.$key $key }
        }
        $target = Get-DesktopLaunchTarget $config.desktopExe
        if ($target.Kind -eq 'Packaged') { Write-Host "Desktop activation: shell:AppsFolder\$($target.Aumid)" }
        else { Write-Host 'Desktop activation: verified unpackaged OpenAI executable.' }
        Write-Host "OK: checkout and local executable paths validated. No applications launched or closed ($Mode)."
    } else { Invoke-Workflow $Mode $config $root }
} catch {
    Write-Error $_ -ErrorAction Continue
    exit 1
}
