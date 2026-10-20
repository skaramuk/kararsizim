# Kararsızım

İnsanların kararsız kaldıkları konularda ("Bugün sinemaya mı gitsem, restorana mı?") topluluğa anket açıp danıştığı bir web uygulaması.

**Canlı demo:** https://kararsizim-omega.vercel.app

## Özellikler

- **Anket oluşturma:** Bir soru ve 2–5 seçenek. Anket açmak için üyelik gerekir.
- **Herkese açık anketler:** Tüm anketler tek bir akışta; en yeni ya da en çok oylanan sıralamasıyla. Kullanıcıların kendi sayfası var (`/kullanici/<ad>/`).
- **Üyesiz oy verme:** Üye olmayanlar da oy verebilir. Her kişi bir ankete tek oy verebilir.
- **Sonuçlar:** Oy verdikten sonra sayı ve yüzde olarak görünür. Oy vermeden sonuçlar gizli kalır, böylece oylar birbirini etkilemez.
- **Gizlilik:** Kullanıcılar sadece kullanıcı adıyla görünür; e-posta adresi hiçbir sayfada ya da yanıtta yer almaz. IP adresi saklanmaz, yalnızca geri döndürülemeyen bir özeti tutulur.
- **JavaScript olmadan da çalışır:** Oy verme ve anket formu normal form gönderimiyle çalışır; JavaScript yalnızca deneyimi iyileştirir (sayfa yenilenmeden sonuç, dinamik seçenek alanları, bağlantı kopyalama).
- **Erişilebilirlik:** Mobil öncelikli tasarım (360 piksel ve üstünde yatay kaydırma yok), klavye odak halkaları, WCAG AA renk kontrastı.

## Teknolojiler

| Katman | Seçim |
|---|---|
| Dil / çatı | Python 3.12, Django 5.2 |
| Veritabanı | PostgreSQL (Supabase); yerelde SQLite |
| Arayüz | Django şablonları, saf HTML / CSS / JavaScript (çatı yok) |
| Statik dosyalar | WhiteNoise |
| Yayın | Vercel |

## Yerelde çalıştırma

Windows (PowerShell) için. Python 3.11 veya üstü gerekir.

```powershell
git clone https://github.com/skaramuk/kararsizim.git
cd kararsizim
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Ardından http://127.0.0.1:8000/ adresini aç. `DATABASE_URL` boş bırakılırsa yerel `db.sqlite3` dosyası kullanılır.

### Testler

```powershell
python manage.py test
```

### Ortam değişkenleri

`.env.example` dosyasını `.env` olarak kopyala. Gizli bilgiler asla git'e eklenmez.

| Değişken | Açıklama |
|---|---|
| `DJANGO_SECRET_KEY` | Django gizli anahtarı. Canlıda uzun ve rastgele olmalı. |
| `DJANGO_DEBUG` | Geliştirmede `True`; canlıda `False` (varsayılan). |
| `DATABASE_URL` | PostgreSQL bağlantı adresi. Boşsa SQLite kullanılır. |
| `DJANGO_ALLOWED_HOSTS` | Virgülle ayrılmış ek alan adları (isteğe bağlı). |

## Proje yapısı

```
├── config/        Django projesi (ayarlar, URL'ler)
├── accounts/      Kullanıcı modeli, kayıt, giriş, çıkış
├── polls/         Anketler, seçenekler, oylar; servis katmanı (services.py)
├── templates/     Sayfa şablonları
├── static/        CSS, JavaScript, simge
├── docs/          Yayın rehberi (DEPLOY.md)
├── scripts/       Yayın yardımcı betikleri (PowerShell)
└── vercel.json    Vercel ayarı (fonksiyon bölgesi)
```

İş mantığı (anket oluşturma, oy verme, sonuç hesaplama) `polls/services.py` içinde toplanır; view'lar ince kalır.

## Yayın

Supabase ve Vercel üzerinde yayına alma adımları [docs/DEPLOY.md](docs/DEPLOY.md) dosyasında.

## Bilinen sınırlamalar

- Üyesiz oy verenler imzalı bir çerezle tanınır. Çerezi silen ya da başka tarayıcı kullanan biri aynı ankete tekrar oy verebilir.
- Anket düzenleme, oy değiştirme, parola sıfırlama e-postası ve e-posta doğrulama henüz yok.
