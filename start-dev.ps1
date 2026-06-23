param(
    [switch]$SkipPortCheck
)

$ErrorActionPreference = "Stop"

$RootDir = $PSScriptRoot
$PythonDir = Join-Path $RootDir "python-api"
$BackendDir = Join-Path $RootDir "medical-system"
$FrontendDir = Join-Path $RootDir "medical-web"
$LogDir = Join-Path $env:TEMP "medical-system-dev-logs"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$Services = New-Object System.Collections.Generic.List[object]

function Resolve-CommandPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CommandName,

        [string]$FallbackPath
    )

    $command = Get-Command $CommandName -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    if ($FallbackPath -and (Test-Path -LiteralPath $FallbackPath)) {
        return $FallbackPath
    }

    throw "Command not found: $CommandName"
}

function Test-PortInUse {
    param([Parameter(Mandatory = $true)][int]$Port)

    $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return $null -ne $connection
}

function Assert-PortFree {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][int]$Port
    )

    if (-not $SkipPortCheck -and (Test-PortInUse -Port $Port)) {
        throw "$Name port $Port is already in use. Stop the old process or run with -SkipPortCheck."
    }
}

function Stop-ProcessTree {
    param([Parameter(Mandatory = $true)][int]$ProcessId)

    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $ProcessId" -ErrorAction SilentlyContinue
    foreach ($child in $children) {
        Stop-ProcessTree -ProcessId $child.ProcessId
    }

    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($process) {
        Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
    }
}

function Start-DevService {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory
    )

    $stdout = Join-Path $LogDir "$Name.out.log"
    $stderr = Join-Path $LogDir "$Name.err.log"

    Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue

    $process = Start-Process `
        -FilePath $FilePath `
        -ArgumentList $Arguments `
        -WorkingDirectory $WorkingDirectory `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr `
        -PassThru

    $service = [pscustomobject]@{
        Name = $Name
        Process = $process
        Stdout = $stdout
        Stderr = $stderr
    }

    $Services.Add($service) | Out-Null
    Write-Host ("[{0}] started, pid={1}" -f $Name, $process.Id)
    Write-Host ("    stdout: {0}" -f $stdout)
    Write-Host ("    stderr: {0}" -f $stderr)
}

function Show-RecentLog {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Path
    )

    if (Test-Path -LiteralPath $Path) {
        Write-Host ""
        Write-Host ("----- {0}: {1} -----" -f $Name, $Path)
        Get-Content -LiteralPath $Path -Tail 40 -ErrorAction SilentlyContinue
    }
}

$PythonExe = Join-Path $RootDir ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $PythonExe)) {
    $PythonExe = Resolve-CommandPath -CommandName "python.exe"
}

$MavenExe = Resolve-CommandPath `
    -CommandName "mvn.cmd" `
    -FallbackPath (Join-Path $BackendDir "mvnw.cmd")

$NpmExe = Resolve-CommandPath -CommandName "npm.cmd"

Assert-PortFree -Name "python-api" -Port 8000
Assert-PortFree -Name "medical-system" -Port 8080
Assert-PortFree -Name "medical-web" -Port 5173

try {
    Write-Host "Starting services without opening extra terminal windows..."
    Write-Host ("Log directory: {0}" -f $LogDir)
    Write-Host ""

    Start-DevService `
        -Name "python-api" `
        -FilePath $PythonExe `
        -Arguments @("-m", "uvicorn", "app:app", "--reload", "--port", "8000") `
        -WorkingDirectory $PythonDir

    Start-Sleep -Seconds 2

    Start-DevService `
        -Name "medical-system" `
        -FilePath $MavenExe `
        -Arguments @("spring-boot:run") `
        -WorkingDirectory $BackendDir

    Start-Sleep -Seconds 2

    Start-DevService `
        -Name "medical-web" `
        -FilePath $NpmExe `
        -Arguments @("run", "dev", "--", "--host", "127.0.0.1", "--port", "5173") `
        -WorkingDirectory $FrontendDir

    Write-Host ""
    Write-Host "All services are starting."
    Write-Host "Frontend:  http://localhost:5173"
    Write-Host "Backend:   http://localhost:8080/api/health"
    Write-Host "Python:    http://localhost:8000/health"
    Write-Host ""
    Write-Host "Keep this window open. Press Ctrl+C to stop all services."

    while ($true) {
        foreach ($service in $Services) {
            $service.Process.Refresh()
            if ($service.Process.HasExited) {
                Write-Host ""
                Write-Host ("[{0}] exited unexpectedly, exitCode={1}" -f $service.Name, $service.Process.ExitCode)
                Show-RecentLog -Name $service.Name -Path $service.Stdout
                Show-RecentLog -Name $service.Name -Path $service.Stderr
                throw "Service stopped: $($service.Name)"
            }
        }

        Start-Sleep -Seconds 2
    }
}
finally {
    Write-Host ""
    Write-Host "Stopping services..."

    for ($i = $Services.Count - 1; $i -ge 0; $i--) {
        $service = $Services[$i]
        $service.Process.Refresh()
        if (-not $service.Process.HasExited) {
            Write-Host ("Stopping {0}, pid={1}" -f $service.Name, $service.Process.Id)
            Stop-ProcessTree -ProcessId $service.Process.Id
        }
    }

    Write-Host "Done."
}
