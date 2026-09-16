$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    $pythonCommand = Get-Command python,py -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($pythonCommand) {
        $basePython = $pythonCommand.Source
    } else {
        $basePython = Get-ChildItem -Path "$env:LOCALAPPDATA\Programs\Python\Python*\python.exe" -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
    }
    if (-not $basePython) { throw 'Python 3.11+ is required. Install Python, then run setup.cmd again.' }
    & $basePython -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the virtual environment.' }
}
& $venvPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Pyxel installation failed.' }
foreach ($rpgAreaResource in @('game.pyxres', 'area2.pyxres', 'area3.pyxres')) {
    if (-not (Test-Path -LiteralPath $rpgAreaResource)) { throw "Missing $rpgAreaResource. Restore the bundled resource file." }
}
Write-Host 'Ready. Double-click run.cmd to play, or edit.cmd to edit sprites and maps.'
