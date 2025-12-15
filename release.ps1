param(
    [string]$Version = "2.0.1",
    [string]$Message = "Release v2.0.1"
)

# Atualizar version.py
Write-Host "Atualizando version.py para $Version..." -ForegroundColor Yellow
$versionContent = "__version__ = `"$Version`""
[System.IO.File]::WriteAllText("version.py", $versionContent, [System.Text.Encoding]::UTF8)

# Git commands
Write-Host "Enviando para GitHub..." -ForegroundColor Yellow
git add .
git commit -m "$Message"
git push origin develop

# Tag
Write-Host "Criando tag v$Version..." -ForegroundColor Yellow
git tag -a "v$Version" -m "$Message"
git push origin "v$Version"

Write-Host "Release enviado! O GitHub Actions fará o build e depois limpará os arquivos." -ForegroundColor Green