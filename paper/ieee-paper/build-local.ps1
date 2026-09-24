param([string]$TemplateDirectory)
$ErrorActionPreference = 'Stop'
if (-not $TemplateDirectory) { throw 'Pass the directory containing the IEEE Access template and font assets.' }
$paperDirectory = $PSScriptRoot
$buildDirectory = Join-Path $paperDirectory 'output/pdf'
$figureBuild = Join-Path $paperDirectory 'output/figures'
New-Item -ItemType Directory -Force -Path $buildDirectory,$figureBuild | Out-Null
$env:TEXINPUTS = "$paperDirectory;$TemplateDirectory;"
$env:TEXFONTMAPS = "$TemplateDirectory;"
$env:TEXFONTS = "$TemplateDirectory;"
Push-Location (Join-Path $paperDirectory 'figures')
try {
    foreach ($stem in @('pipeline_overview','endpoint_graph','completion')) {
        & pdflatex -interaction=nonstopmode -halt-on-error "-output-directory=$figureBuild" "${stem}_standalone.tex" *> (Join-Path $figureBuild "$stem.console.log")
        if ($LASTEXITCODE) { throw "Figure build failed: $stem" }
        Copy-Item -LiteralPath (Join-Path $figureBuild "${stem}_standalone.pdf") -Destination "$stem.pdf"
    }
} finally { Pop-Location }
Push-Location $paperDirectory
try {
    foreach ($stem in @('paper-build','paper-access')) {
        for ($pass = 1; $pass -le 3; $pass++) {
            & pdflatex -interaction=nonstopmode -halt-on-error -file-line-error "-output-directory=$buildDirectory" "$stem.tex" *> (Join-Path $buildDirectory "$stem.console.log")
            if ($LASTEXITCODE) { throw "Manuscript build failed: $stem" }
        }
        Write-Output "Built $stem.pdf"
    }
} finally { Pop-Location }
