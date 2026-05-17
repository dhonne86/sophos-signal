param(
    [string]$Url = "http://192.168.1.170:8501"
)

$AdbPath = Join-Path $PSScriptRoot "platform-tools\adb.exe"

if (-not (Test-Path $AdbPath)) {
    Write-Error "ADB nao encontrado em $AdbPath. Baixe o Android SDK Platform Tools antes de executar."
    exit 1
}

$devicesOutput = & $AdbPath devices
$authorizedDevices = $devicesOutput | Select-String -Pattern "device$"

if (-not $authorizedDevices) {
    Write-Host "Nenhum Android autorizado encontrado."
    Write-Host "Ative Depuracao USB, conecte o cabo e aceite a autorizacao no celular."
    & $AdbPath devices -l
    exit 1
}

& $AdbPath shell am start -a android.intent.action.VIEW -d $Url
