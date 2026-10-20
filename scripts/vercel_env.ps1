# Vercel "Environment Variables" ekranina yapistirilacak degerleri hazirlar ve PANOYA kopyalar.
# Degerler ekrana yazdirilmaz, dosyaya kaydedilmez.
# Kullanim (PowerShell):
#   powershell -ExecutionPolicy Bypass -File scripts\vercel_env.ps1 secret   -> DJANGO_SECRET_KEY degeri
#   powershell -ExecutionPolicy Bypass -File scripts\vercel_env.ps1 db       -> DATABASE_URL degeri

param([Parameter(Mandatory = $true, Position = 0)][ValidateSet("secret", "db")][string]$What)

$ErrorActionPreference = "Stop"

if ($What -eq "secret") {
    $bytes = New-Object byte[] 48
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes)
    $value = [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
    Set-Clipboard -Value $value
    Write-Host "Yeni DJANGO_SECRET_KEY panoya kopyalandi ($($value.Length) karakter)." -ForegroundColor Green
    Write-Host "Vercel'de DJANGO_SECRET_KEY kutusuna Ctrl+V ile yapistir. Baska bir sey kopyalamadan once yapistirmayi bitir."
    $value = $null
}
else {
    # Bunlar gizli degildir; Supabase "Connect" ekranindaki Transaction pooler adresinden gelir.
    $dbUser = "postgres.vbncqgrtnlzmdpyqjwuh"
    $dbHost = "aws-0-eu-west-1.pooler.supabase.com"

    $secure = Read-Host "Supabase veritabani parolasi (yazarken gorunmez)" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
    if ([string]::IsNullOrWhiteSpace($plain)) { throw "Parola bos olamaz." }
    if ($plain -like "*://*") { throw "Buraya adresi degil, sadece parolayi yazmalisin." }

    # Transaction pooler: Vercel icin port 6543. Ozel karakterler otomatik URL-kodlanir.
    $encoded = [uri]::EscapeDataString($plain)
    $value = "postgresql://${dbUser}:${encoded}@${dbHost}:6543/postgres"
    Set-Clipboard -Value $value
    Write-Host "DATABASE_URL (Transaction pooler, port 6543) panoya kopyalandi." -ForegroundColor Green
    Write-Host "Vercel'de DATABASE_URL kutusuna Ctrl+V ile yapistir."
    $plain = $null; $encoded = $null; $value = $null
}
