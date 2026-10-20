# Yayın rehberi — Supabase + Vercel

Bu rehber **Faz 4** içindir. Sırayla ilerle; her adımın sonunda **✅ Kontrol** satırı var, geçmeden sonrakine geçme.
Komutlar PowerShell içindir ve proje klasöründe çalıştırılır:

```powershell
cd C:\Users\semih\PythonProjects\kararsizim_projesi
```

> Menü adları zaman zaman değişebilir. Bir menüyü bulamazsan ekran görüntüsünü at, birlikte bakarız.

## Özet

| Ne | Nerede | Not |
|---|---|---|
| Veritabanı | Supabase (PostgreSQL) | Sadece veritabanı; Supabase Auth / JS istemcisi kullanılmıyor |
| Uygulama | Vercel | Django'yu `manage.py`'den otomatik tanır, `vercel.json` gerekmez |
| Tablolar | Yerelden `migrate` | Vercel build'inde migration çalışmaz |

Bağlantı adresleri:

| Kullanım | Supabase'te seçilecek yöntem | Port |
|---|---|---|
| Yerelden `migrate` / `createsuperuser` | **Session pooler** | 5432 |
| Vercel (canlı site) | **Transaction pooler** | 6543 |

"Direct connection" varsayılan olarak yalnızca IPv6'dır; Vercel IPv4 olduğu için **onu kullanma**.

---

## 1. Supabase projesi oluştur

1. https://supabase.com adresinde giriş yap → **New project**.
2. **Project name:** `kararsizim` (istediğin ad olur).
3. **Database password:** güçlü bir parola oluştur (**Generate a password** işe yarar) ve bir parola yöneticisine kaydet. Sonradan gerekecek.
4. **Region:** `Central EU (Frankfurt)` öner. Vercel fonksiyonlarını da aynı bölgeye alacağız (Adım 6).
5. Ekranda **Data API** ile ilgili bir seçenek varsa **kapalı** bırak. Yoksa Adım 3'te kapatacağız.
6. **Create new project**'e bas ve kurulum bitene kadar bekle (1–2 dakika).

✅ **Kontrol:** Proje paneli açılıyor, durum "Healthy" / aktif görünüyor.

> Ücretsiz projeler bir süre hareketsiz kalırsa duraklatılır. Panelden **Restore / Resume** diyerek tekrar başlatabilirsin.

## 2. Bağlantı adreslerini al

1. Proje panelinde üstteki **Connect** butonuna bas.
2. **Connection String** (Connection method) sekmesinde sırayla iki adres kopyala:
   - **Session pooler** (port **5432**) → yerelden migrate için.
   - **Transaction pooler** (port **6543**) → Vercel için.
3. Adres şuna benzer olur (kullanıcı adı `postgres.<proje-kodu>` biçimindedir, sadece `postgres` değil):
   ```
   postgresql://postgres.<proje-kodu>:[YOUR-PASSWORD]@aws-0-<bölge>.pooler.supabase.com:5432/postgres
   ```
4. `[YOUR-PASSWORD]` yerine Adım 1'deki parolayı yaz. **Parolada `@ # / : ? & %` gibi özel karakterler varsa URL-encode etmelisin.** Bunun için (parolayı yazarken ekranda görünmez):
   ```powershell
   .venv\Scripts\python.exe -c "import urllib.parse, getpass; print(urllib.parse.quote(getpass.getpass('Parola: '), safe=''))"
   ```
   Çıkan değeri adresteki parola yerine koy.

✅ **Kontrol:** İki adresin de parolası dolu ve `[YOUR-PASSWORD]` ifadesi kalmadı. Adresleri kimseyle paylaşma, sohbete yapıştırma, git'e koyma.

## 3. Supabase'in otomatik API'sini kapat

Django tabloları `public` şemasında oluşturur. Supabase bu şemayı varsayılan olarak otomatik REST API (Data API) ile internete açar ve yeni tablolara `anon` rolüne erişim verir. Biz bu API'yi hiç kullanmıyoruz, o yüzden iki katmanlı önlem alıyoruz:

1. **Data API'yi kapat:** Sol menüde **Integrations** → **Data API** → **Enable Data API** anahtarını **kapat**.
2. **RLS (satır güvenliği)** zaten kodda hazır: `polls/migrations/0002_enable_rls.py` tüm tablolarda RLS'yi açar. Adım 4'teki `migrate` bunu uygular. Policy tanımlamadığımız için `anon` / `authenticated` rolleri hiçbir satırı göremez; Django ise tabloların sahibi rolle bağlandığı için etkilenmez.

✅ **Kontrol (Adım 4'ten sonra):** **Advisors** bölümünde (Security) "RLS Disabled in Public" türünde hata kalmadı.

## 4. Tabloları Supabase'e kur (yerelden)

**Kolay yol:** `scripts\supabase_migrate.ps1` bu adımın tamamını yapar. Sadece veritabanı parolasını sorar (yazarken görünmez, özel karakterleri kendisi kodlar), `migrate` ve `createsuperuser`'ı çalıştırır, sonunda adresi bellekten siler:

```powershell
cd C:\Users\semih\PythonProjects\kararsizim_projesi
powershell -ExecutionPolicy Bypass -File scripts\supabase_migrate.ps1
```

(Betikteki sunucu adresi ve proje kodu bu projeye özeldir; başka bir Supabase projesine geçersen betiğin başındaki `$dbUser` ve `$dbHost` satırlarını güncelle.)

**Elle yol** (betiği kullanmak istemezsen):

Parolayı dosyaya yazmamak için adresi **sadece bu PowerShell penceresinde** tanımla. Aşağıdaki üç satırı **aynı pencerede** çalıştır; adres olarak **Session pooler (5432)** kullan:

```powershell
$env:DATABASE_URL = "postgresql://postgres.<proje-kodu>:<kodlanmış-parola>@aws-0-<bölge>.pooler.supabase.com:5432/postgres"
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py createsuperuser
```

`createsuperuser` e-posta, kullanıcı adı ve parola sorar. Bu, canlı sitedeki admin hesabın olur (yerel hesabından ayrıdır).

İş bitince adresi bu oturumdan sil, böylece yanlışlıkla yerel testlerde canlı veritabanına yazmazsın:

```powershell
Remove-Item Env:DATABASE_URL
```

> `.env` içindeki `DATABASE_URL` **boş kalmalı**. Yerel geliştirme SQLite ile devam eder.

✅ **Kontrol:**
- `migrate` hatasız bitti ve son satırlarda `polls.0002_enable_rls... OK` var.
- Supabase panelinde **Table Editor** → `accounts_user`, `polls_poll`, `polls_choice`, `polls_vote`, `django_session` tabloları listeleniyor.
- Table Editor'de tablolarda "RLS enabled" etiketi görünüyor.
- **Advisors** → Security'de kritik uyarı yok (Adım 3'ün kontrolü).

## 5. Kodu GitHub'a gönder

1. https://github.com → **New repository** → ad: `kararsizim` → **Private** (istersen Public) → README/.gitignore/lisans **ekleme** (repo boş olmalı) → **Create repository**.
2. Önce gizli dosyaların git'te olmadığından emin ol. Bu iki komutun çıktısı **boş** olmalı:
   ```powershell
   git ls-files .env db.sqlite3 .venv
   git status --short
   ```
3. Repoyu bağla ve gönder (`<kullanıcı-adın>` yerine GitHub kullanıcı adını yaz):
   ```powershell
   git branch -M main
   git remote add origin https://github.com/<kullanıcı-adın>/kararsizim.git
   git push -u origin main
   ```
   Giriş isterse tarayıcıda GitHub ile onaylarsın.

✅ **Kontrol:** GitHub'da repo dosyaları görünüyor; `.env`, `db.sqlite3` ve `.venv` **yok**; `.env.example` var.

## 6. Vercel'e yayınla

1. https://vercel.com → GitHub hesabınla giriş yap → **Add New…** → **Project**.
2. `kararsizim` reposunun yanında **Import**'a bas (GitHub erişimi isterse reposu seçerek izin ver).
3. **Framework Preset** otomatik **Django** çıkmalı. Değilse bana haber ver.
4. **Environment Variables** bölümünü aç ve **Deploy'dan önce** şu üçünü ekle (üçü de Production + Preview için):

   | Name | Value |
   |---|---|
   | `DJANGO_SECRET_KEY` | Aşağıdaki komutun çıktısı (yeni, uzun, rastgele) |
   | `DJANGO_DEBUG` | `False` |
   | `DATABASE_URL` | **Transaction pooler (6543)** adresi, parola kodlanmış |

   Gizli anahtar üretmek için:
   ```powershell
   .venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(64))"
   ```
   > Bu değişkenler **ilk build'den önce** tanımlı olmalı. Vercel build sırasında `manage.py`'yi çalıştırıp ayarları okur; `DJANGO_SECRET_KEY` yoksa uygulama bilerek açılmaz ve build `DJANGO_SECRET_KEY ortam değişkeni tanımlı olmalı` hatasıyla düşer. Böyle olursa değişkeni ekleyip **Redeploy** yeterli.

   Vercel'in "Storage / Integrations" bölümünden Supabase ya da başka bir veritabanı **ekleme**: kendi `DATABASE_URL`'ini yazıp bizimkini ezebilir.
5. **Deploy**'a bas. Build'i **Build Logs**'tan izle; `collectstatic` satırı görünmelidir (`STATIC_ROOT` tanımlı olduğu için Vercel bunu kendisi çalıştırır).
6. Site açılınca **Settings → Functions → Function Regions** bölümünden bölgeyi **Supabase projenle aynı bölgeye** çek (Hobby planda tek bölge seçilir): Supabase **Frankfurt** (`eu-central-1`) ise Vercel'de **`fra1`**, Supabase **İrlanda** (`eu-west-1`) ise Vercel'de **`dub1`** (Dublin). Varsayılan Washington D.C.'dir (`iad1`) ve her sorgu okyanus aşırı gider. Ayardan sonra son deploy'u **Redeploy** et.

✅ **Kontrol:** Deployment "Ready"; `https://<proje-adı>.vercel.app` ana sayfası Türkçe açılıyor.

## 7. Canlı ortam kontrol listesi

Canlı adreste sırayla dene (✔ işaretle):

- [ ] Ana sayfa açılıyor, "Henüz anket yok" mesajı görünüyor, **CSS yüklü** (sayfa düzgün biçimli).
- [ ] **Kayıt ol** → kayıt başarılı, otomatik giriş yapıldı, üstte `@kullanıcı_adın` görünüyor.
- [ ] **Çıkış** → çıkış yapıldı. **Giriş yap** → e-posta + parola ile girildi.
- [ ] **Anket oluştur** → 2–5 seçenekli anket yayınlandı; seçenek ekle/çıkar düğmeleri çalışıyor (JS yüklü).
- [ ] Başka bir tarayıcıda / gizli pencerede anket **görünüyor** ve **oy verilebiliyor**; sayfa yenilenmeden sonuçlar çıkıyor.
- [ ] Aynı tarayıcıda ikinci oy **reddediliyor**.
- [ ] Anketi sil → silindi, listeden kalktı.
- [ ] `/kullanici/<kullanıcı_adın>/` açılıyor; sayfada **e-postan görünmüyor**.
- [ ] `/admin/` açılıyor ve Adım 4'teki süper kullanıcıyla giriş yapılıyor (admin CSS'i de yüklü).
- [ ] Tarayıcıda adres çubuğunda 🔒 var; sayfa kaynağında `voter_id` çerezi (DevTools → Application → Cookies) `HttpOnly` + `Secure` işaretli.
- [ ] Supabase → **Advisors** → Security: kritik uyarı yok.
- [ ] Vercel → proje → **Logs**: 500 hatası yok. (Hatalar artık konsola yazılıyor, burada görünür.)

## Sonraki yayınlar

`git push` yeterli: `main` dalı Production'a, diğer dallar önizleme adresine yayınlanır.

**Şema değiştiren (migration içeren) her güncellemede**, push'tan **önce** migration'ı Supabase'e uygula (Adım 4'ün aynısı, Session pooler ile). Vercel migration çalıştırmaz.

## Yeni tablo eklenince (RLS)

`0002_enable_rls` migration'ı yalnızca çalıştığı andaki tabloları kapsar. İleride yeni bir model/tablo eklersen (Faz 6+), migration'dan sonra o tabloda da RLS'yi aç; Data API kapalı olduğu sürece risk düşüktür ama ikinci katman olarak şunu kullan:

```sql
alter table public.<yeni_tablo> enable row level security;
```

(Supabase **SQL Editor**'de çalıştırılır.) Ya da yeni bir `RunPython` migration'ında `0002_enable_rls.enable_rls` mantığını tekrar çalıştır.

## Sorun giderme

| Belirti | Olası neden | Çözüm |
|---|---|---|
| Build: `DJANGO_SECRET_KEY ortam değişkeni tanımlı olmalı` | Vercel'de değişken yok | Adım 6.4'teki üç değişkeni ekle → Redeploy |
| Sayfa 400 `Bad Request (400)` | Alan adı `ALLOWED_HOSTS`'ta yok | Özel alan adı kullanıyorsan `DJANGO_ALLOWED_HOSTS=alanadi.com` ekle (virgülle birden fazla) |
| Form gönderince `403 CSRF` | Özel alan adı `CSRF_TRUSTED_ORIGINS`'te yok | Aynı `DJANGO_ALLOWED_HOSTS` değişkeni bunu da kapsar → Redeploy |
| `500` ve Logs'ta `OperationalError: connection ... failed` | Yanlış adres / parola / duraklatılmış proje | Supabase'de projenin aktif olduğunu, adresteki parolanın **URL-encode** edildiğini ve Vercel'deki adresin **6543 (Transaction pooler)** olduğunu kontrol et |
| `500` ve Logs'ta `prepared statement ... does not exist` | Transaction pooler + hazır ifade | Ayar kodda kapalı (`prepare_threshold=None`); `DATABASE_URL`'in **6543** portunda olduğundan ve kodun güncel olduğundan emin ol |
| `migrate` yerelden bağlanamıyor | "Direct connection" (IPv6) kullanılmış | **Session pooler (5432)** adresini kullan |
| Sayfa açılıyor ama CSS yok | Build'de `collectstatic` çalışmamış | Build Logs'ta `collectstatic` ara; `STATIC_ROOT` ayarı kodda tanımlı |
| Giriş sonrası hemen çıkış yapılmış gibi | Çerezler `Secure` ama site HTTP'den açılmış | Siteyi `https://` ile aç |
