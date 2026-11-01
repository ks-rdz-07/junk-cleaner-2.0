# Builds out\JunkCleaner-<version>-x64.msi
# Needs: Python 3.10+ with PyInstaller (pip install pyinstaller), WiX v5 (dotnet tool install -g wix --version 5.0.1)
# and its extensions: wix extension add -g WixToolset.UI.wixext/5.0.1 WixToolset.Util.wixext/5.0.1
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true  # stop if any exe returns non-zero
Set-Location $PSScriptRoot

$version = python -c "import junkcleaner; print(junkcleaner.__version__)"
Write-Host "== Junk Cleaner $version ==" -ForegroundColor Cyan

Write-Host "-- unit tests"
python -m unittest tests.test_core

Write-Host "-- freezing with PyInstaller"
$assets = Join-Path $PSScriptRoot "assets"  # absolute: --specpath makes relative paths resolve from out\
python -m PyInstaller --noconfirm --clean --windowed --uac-admin --name JunkCleaner `
    --icon "$assets\app.ico" --add-data "$assets\app.png;assets" --add-data "$assets\check.svg;assets" `
    --distpath out\dist --workpath out\build --specpath out junkclean.py

Write-Host "-- building MSI with WiX"
$msi = "out\JunkCleaner-$version-x64.msi"
wix build installer\Package.wxs -arch x64 `
    -ext WixToolset.UI.wixext -ext WixToolset.Util.wixext `
    -d Version=$version -d "DistDir=$PSScriptRoot\out\dist\JunkCleaner" -o $msi

Write-Host "Done: $(Resolve-Path $msi)" -ForegroundColor Green
