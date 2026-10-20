# Supabase'e tablolari kurar (migrate) ve yonetici hesabi olusturur (createsuperuser).
# Parola dosyaya yazilmaz; calisirken sorulur ve is bitince bellekten silinir.
# Kullanim (PowerShell):
#   powershell -ExecutionPolicy Bypass -File scripts\supabase_migrate.ps1

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

# Bunlar gizli degildir; Supabase "Connect" ekranindaki Session pooler adresinden gelir.
$dbUser = "postgres.vbncqgrtnlzmdpyqjwuh"
$dbHost = "aws-0-eu-west-1.pooler.supabase.com"

$secure = Read-Host "Supabase veritabani parolasi (yazarken gorunmez)" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}
if ([string]::IsNullOrWhiteSpace($plain)) { throw "Parola bos olamaz." }

# Ozel karakterler (@ # / ? gibi) otomatik URL-kodlanir.
$encoded = [uri]::EscapeDataString($plain)
$env:DATABASE_URL = "postgresql://${dbUser}:${encoded}@${dbHost}:5432/postgres"
$plain = $null; $encoded = $null

try {
    Write-Host "`n--- 1/2: Tablolar kuruluyor (migrate) ---" -ForegroundColor Cyan
    & .venv\Scripts\python.exe manage.py migrate
    if ($LASTEXITCODE -ne 0) { throw "migrate basarisiz oldu. Yukaridaki hata yazisini kontrol et." }

    Write-Host "`n--- 2/2: Yonetici hesabi (createsuperuser) ---" -ForegroundColor Cyan
    & .venv\Scripts\python.exe manage.py createsuperuser
} finally {
    Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
    Write-Host "`nBitti. Parola ve adres bu oturumdan silindi." -ForegroundColor Green
}
