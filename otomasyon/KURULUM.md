# Fiyat güncelleme otomasyonu: kurulum

Firma fiyatları bir Google E-Tablosunda değiştirir, **Katalog > Kataloğu güncelle** menüsüne basar.
GitHub kataloğu yeni fiyatlarla yeniden oluşturur (PDF'ler + sayfa çevirmeli web sürümü) ve aynı linkte yayınlar. Süre: 3–5 dakika.

```
Google E-Tablo ──(menü düğmesi)──► GitHub Actions ──(build.py, macOS)──► GitHub Pages
  Fiyatlar / Ayarlar                 fiyatlar.json'u depoya kaydeder          sabit link
```

- Tablo verisi gönderilmeden önce denetlenir (boş hücre, sayı olmayan fiyat, katalogda olmayan kod).
  Sorun varsa firma hangi satırda olduğunu hemen görür.
- Oluşturma yine de hata verirse **yayındaki katalog değişmez**, eski fiyatlarla kalır.
  Hata e-postası depo sahibine gelir.
- Her fiyat değişikliği depoda bir kayıt olarak kalır (kim, ne zaman, ne değişti).
- Zamanlanmış çalışma yok. GitHub'ın "60 gün hareketsizlikte zamanlanmış akışları kapatma" kuralı bu düzeni etkilemez.

## 1. GitHub deposu

1. github.com'da **herkese açık (Public)** yeni bir depo aç: `eve-katalog`. README ekleme, boş kalsın.
   (Ücretsiz hesapta GitHub Pages yalnızca açık depolarda çalışıyor. `PROJE-NOTLARI.md` depoya girmiyor.)
2. Bu klasörü (`katalog/`) depoya gönder:
   ```
   cd ".../Ayhan Duran Katalog/katalog"
   git remote add origin https://github.com/KULLANICI_ADI/eve-katalog.git
   git push -u origin main
   ```
3. Depoda **Settings > Pages > Build and deployment > Source: GitHub Actions** seç.
4. **Actions** sekmesi > **Katalog** > **Run workflow**. İlk yayın birkaç dakika sürer.
   Bitince katalog `https://KULLANICI_ADI.github.io/eve-katalog/` adresinde yayında olur.

## 2. GitHub anahtarı (tablonun GitHub'ı tetikleyebilmesi için)

github.com > sağ üstte profil > **Settings > Developer settings > Personal access tokens > Fine-grained tokens > Generate new token**

- Token name: `eve-katalog-tablo`
- Expiration: sunulan en uzun süre. **Bitiş tarihini takvime yaz**: süre dolunca düğme "401" hatası verir, yeni anahtar üretip 3.5. adımı tekrarlamak yeterli.
- Repository access: **Only select repositories** > `eve-katalog`
- Permissions > Repository permissions:
  - **Contents: Read and write** (güncellemeyi başlatmak için)
  - **Actions: Read-only** ("Son güncellemenin durumu" menüsü için)

Anahtar yalnızca bu depoya ve yalnızca bu iki yetkiyle erişir.

## 3. Google E-Tablo

1. Firmanın (demo için kendi) Google hesabında yeni bir tablo aç: **EVE Katalog Fiyatları**.
2. **Uzantılar > Apps Script**. Açılan düzenleyicide `Kod.gs` içeriğini sil, bu klasördeki `Kod.gs`'nin tamamını yapıştır.
3. Dosyanın başındaki iki satırı doldur:
   ```
   const DEPO = 'KULLANICI_ADI/eve-katalog';
   const SITE = 'https://KULLANICI_ADI.github.io/eve-katalog/';
   ```
   Kaydet (⌘S).
4. Tablo sekmesine dön, sayfayı yenile. Üst menüde **Katalog** belirir.
5. **Katalog > Kurulum > GitHub anahtarını kaydet**, 2. adımdaki anahtarı yapıştır.
   İlk seferde Google izin ister: *Advanced (Gelişmiş) > Go to … (unsafe)* > *Allow*.
   Bu uyarı, betiği Google'a doğrulatmadığımız için çıkıyor; betik yalnızca bu tabloyu ve GitHub'ı kullanır.
6. **Katalog > Kurulum > Tabloyu yayındaki fiyatlarla hazırla**. `Fiyatlar` ve `Ayarlar` sayfaları oluşur.
7. Tabloyu firmayla **Düzenleyici** olarak paylaş.
   Apps Script betiği ve anahtar, tabloya bağlı olduğu için tabloyla birlikte gider.
   Düzenleyiciler betiği görebilir. Anahtar betiğin içinde değil, betik ayarlarında durur.

## 4. Demo / test

1. `Fiyatlar` sayfasında bir fiyatı değiştir (ör. EVE-501, 1+, TL: 1.699).
2. `Ayarlar` > B1'deki geçerlilik tarihini güncelle.
3. **Katalog > Kataloğu güncelle** > Evet.
4. 3–5 dakika sonra **Katalog > Son güncellemenin durumu** > "Tamamlandı".
5. Katalog linkini yenile: fiyat listesi sayfası ve PDF yeni fiyatı gösterir.

Hata denemesi: bir USD hücresini boşalt ya da `EVE-999` gibi olmayan bir kod yaz, güncellemeye bas. Tablo hangi satırda sorun olduğunu söyler, hiçbir şey gönderilmez.

## Firmaya anlatılacak kısa kullanım

> Fiyat değiştiğinde:
> 1. **Fiyatlar** sayfasında TL, USD ve EUR fiyatlarını yazın. Üçü de dolu olmalı.
> 2. **Ayarlar** sayfasında geçerlilik tarihini güncelleyin.
> 3. **Katalog > Kataloğu güncelle**'ye basın.
>
> Birkaç dakika içinde katalog linki ve PDF yeni fiyatlarla yenilenir.
> "Ürün" sütunu yalnızca bilgi içindir; ürün adı, yeni ürün, görsel gibi değişiklikler için bize yazın.

## Sonra: kendi alan adı

Link firmanın alan adında olsun istenirse (ör. `katalog.evetekstil.com`):
1. Depoda **Settings > Pages > Custom domain**: `katalog.evetekstil.com`.
2. Alan adının DNS'ine bir CNAME kaydı ekle: `katalog` → `KULLANICI_ADI.github.io`.
3. `Kod.gs`'deki `SITE` satırını yeni adresle güncelle.
