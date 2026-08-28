[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $SourcePath,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F]{40}$')]
    [string] $CommitSha,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9]+-[0-9]+$')]
    [string] $RunId,

    [string] $RootPath = 'C:\GlassBox',
    [string] $ServiceName = 'GlassBoxOrchestrator',
    [string] $LegacyServiceName = 'GlassBoxWorker',
    [string] $PythonExecutable = 'python.exe',
    [string] $NssmExecutable = 'nssm.exe',
    [ValidateRange(10, 300)]
    [int] $HealthWaitSeconds = 30
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Command,
        [Parameter(Mandatory = $true)]
        [string[]] $Arguments
    )

    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE`: $Command $($Arguments -join ' ')"
    }
}

function Set-NssmValue {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name,
        [Parameter(Mandatory = $true)]
        [string[]] $Value
    )

    Invoke-Checked -Command $NssmExecutable -Arguments (@('set', $ServiceName, $Name) + $Value)
}

function Get-NssmValue {
    param([Parameter(Mandatory = $true)][string] $Name)

    $value = & $NssmExecutable get $ServiceName $Name
    if ($LASTEXITCODE -ne 0) {
        throw "Could not read NSSM setting '$Name' for service '$ServiceName'."
    }
    return (($value | Out-String).Trim())
}

$source = (Resolve-Path -LiteralPath $SourcePath).Path
$root = [System.IO.Path]::GetFullPath($RootPath)
$releasesRoot = [System.IO.Path]::GetFullPath((Join-Path $root 'releases'))
$releaseId = "$($CommitSha.Substring(0, 12))-$RunId"
$releasePath = [System.IO.Path]::GetFullPath((Join-Path $releasesRoot $releaseId))
$logsPath = [System.IO.Path]::GetFullPath((Join-Path $root 'logs'))

$legacyService = Get-Service -Name $LegacyServiceName -ErrorAction SilentlyContinue
if ($null -ne $legacyService -and $legacyService.Status -eq 'Running') {
    throw "Legacy service '$LegacyServiceName' is still running. Stop and disable it before deploying the orchestrator to prevent duplicate execution."
}

if (-not $releasePath.StartsWith($releasesRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Resolved release path escaped the releases directory: $releasePath"
}
if (Test-Path -LiteralPath $releasePath) {
    throw "Release path already exists; refusing to overwrite it: $releasePath"
}

New-Item -ItemType Directory -Path $releasePath -Force | Out-Null
New-Item -ItemType Directory -Path $logsPath -Force | Out-Null

Write-Host "Preparing Glass Box release $releaseId"
Copy-Item -LiteralPath (Join-Path $source 'backend') -Destination $releasePath -Recurse
Copy-Item -LiteralPath (Join-Path $source 'requirements.txt') -Destination $releasePath
if (Test-Path -LiteralPath (Join-Path $source '.python-version')) {
    Copy-Item -LiteralPath (Join-Path $source '.python-version') -Destination $releasePath
}

$venvPath = Join-Path $releasePath '.venv'
$releasePython = Join-Path $venvPath 'Scripts\python.exe'

Write-Host 'Creating isolated Python environment'
Invoke-Checked -Command $PythonExecutable -Arguments @('-m', 'venv', $venvPath)
Invoke-Checked -Command $releasePython -Arguments @('-m', 'pip', 'install', '--disable-pip-version-check', '--upgrade', 'pip')
Invoke-Checked -Command $releasePython -Arguments @('-m', 'pip', 'install', '--disable-pip-version-check', '-r', (Join-Path $releasePath 'requirements.txt'))

Write-Host 'Running release preflight checks'
Invoke-Checked -Command $releasePython -Arguments @('-m', 'compileall', '-q', (Join-Path $releasePath 'backend'))

$existingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
$previous = $null
$installedNewService = $false
if ($null -ne $existingService) {
    $previous = @{
        Application = Get-NssmValue -Name 'Application'
        AppDirectory = Get-NssmValue -Name 'AppDirectory'
        AppParameters = Get-NssmValue -Name 'AppParameters'
    }
    if ($existingService.Status -ne 'Stopped') {
        Stop-Service -Name $ServiceName -Force
        (Get-Service -Name $ServiceName).WaitForStatus('Stopped', [TimeSpan]::FromSeconds(30))
    }
} else {
    Write-Host "Installing NSSM service $ServiceName"
    Invoke-Checked -Command $NssmExecutable -Arguments @(
        'install', $ServiceName, $releasePython, '-m', 'backend.services.orchestrator'
    )
    $installedNewService = $true
}

try {
    Set-NssmValue -Name 'Application' -Value @($releasePython)
    Set-NssmValue -Name 'AppDirectory' -Value @($releasePath)
    Set-NssmValue -Name 'AppParameters' -Value @('-m backend.services.orchestrator')
    Set-NssmValue -Name 'AppEnvironmentExtra' -Value @("LOG_DIR=$logsPath")
    Set-NssmValue -Name 'AppStdout' -Value @((Join-Path $logsPath 'orchestrator-service-stdout.log'))
    Set-NssmValue -Name 'AppStderr' -Value @((Join-Path $logsPath 'orchestrator-service-stderr.log'))
    Set-NssmValue -Name 'AppRotateFiles' -Value @('1')
    Set-NssmValue -Name 'Start' -Value @('SERVICE_AUTO_START')

    Start-Service -Name $ServiceName
    (Get-Service -Name $ServiceName).WaitForStatus('Running', [TimeSpan]::FromSeconds(30))

    Write-Host "Observing service health for $HealthWaitSeconds seconds"
    Start-Sleep -Seconds $HealthWaitSeconds
    $service = Get-Service -Name $ServiceName
    if ($service.Status -ne 'Running') {
        $stderrPath = Join-Path $logsPath 'orchestrator-service-stderr.log'
        $detail = if (Test-Path -LiteralPath $stderrPath) {
            (Get-Content -LiteralPath $stderrPath -Tail 40) -join [Environment]::NewLine
        } else {
            'No service stderr log was produced.'
        }
        throw "Service did not remain running. Recent stderr:`n$detail"
    }

    $currentMarker = Join-Path $root 'current-release.txt'
    $previousMarker = Join-Path $root 'previous-release.txt'
    if (Test-Path -LiteralPath $currentMarker) {
        Copy-Item -LiteralPath $currentMarker -Destination $previousMarker -Force
    }
    Set-Content -LiteralPath $currentMarker -Value $releasePath -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $releasePath 'release.json') -Encoding UTF8 -Value (@{
        commit_sha = $CommitSha
        github_run = $RunId
        deployed_at_utc = [DateTime]::UtcNow.ToString('o')
        service = $ServiceName
    } | ConvertTo-Json)

    Write-Host "Deployment healthy: commit=$CommitSha release=$releasePath service=$ServiceName"
} catch {
    Write-Warning "Deployment failed: $($_.Exception.Message)"

    $failedService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($null -ne $failedService -and $failedService.Status -ne 'Stopped') {
        Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
    }

    if ($null -ne $previous) {
        Write-Warning "Rolling $ServiceName back to $($previous.AppDirectory)"
        Set-NssmValue -Name 'Application' -Value @($previous.Application)
        Set-NssmValue -Name 'AppDirectory' -Value @($previous.AppDirectory)
        Set-NssmValue -Name 'AppParameters' -Value @($previous.AppParameters)
        Start-Service -Name $ServiceName
        (Get-Service -Name $ServiceName).WaitForStatus('Running', [TimeSpan]::FromSeconds(30))
    } elseif ($installedNewService) {
        Write-Warning "Removing newly installed failed service $ServiceName so a retry starts cleanly."
        Invoke-Checked -Command $NssmExecutable -Arguments @('remove', $ServiceName, 'confirm')
    } else {
        Write-Warning 'No previous NSSM release was available; the newly installed service remains stopped.'
    }

    throw
}
