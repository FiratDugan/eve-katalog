# EVE Tekstil Katalog

## Klasörler
- `kaynak/katalog.json`: tüm metinler, ürünler, kodlar (TR + EN)
- `gorseller/`: ürün görselleri, ürün koduyla adlandırılır
  - `EVE-501_1.jpg` ana görsel, `EVE-501_2.jpg` ve `EVE-501_3.jpg` yan görseller
  - `kapak.jpg` kapak görseli, `bolum-cocuk.jpg` bölüm açılış görseli
- `cikti/`: üretilen dosyalar (her derlemede silinip yeniden oluşturulur)
  - `Eve-Tekstil-Katalog-TR.pdf` / `-EN.pdf`: e-posta ve WhatsApp için
  - `web/`: siteye yüklenecek klasörün tamamı

## Kataloğu yeniden üretmek
```
cd "katalog"
python3 kaynak/build.py
```
Mac'te Google Chrome kurulu olmalı. Derleme yaklaşık 15 saniye sürer.

## Görsel değiştirmek
Gerçek fotoğrafı aynı adla `gorseller/` klasörüne koy (örn. `EVE-501_1.jpg`) ve derlemeyi tekrar çalıştır.

## Yeni ürün eklemek
1. `katalog.json` içinde `urunler` listesine yeni bir blok ekle (mevcut bir ürünü kopyala).
2. Kod benzersiz olmalı. Aynı kod iki kez kullanılırsa derleme hata verir.
3. Görselleri `KOD_1.jpg`, `KOD_2.jpg` adıyla `gorseller/` klasörüne koy.

## Fiyatlar
Her kategorinin son ürününden sonra o kategorinin fiyat listesi sayfası otomatik eklenir. Liste bir sayfaya sığmazsa "devamı" sayfası açılır.
- Fiyatlar `kaynak/fiyatlar.json` içinde durur. Her satır bir ürünün bir adet kademesidir:
  `{"kod": "EVE-501", "adet": "10+", "tl": 1449, "usd": 34.67, "eur": 29.75}`
- TL, USD ve EUR elle girilir; kur hesabı yapılmaz. TL zorunludur; USD/EUR ve adet boş bırakılabilir (listede "—" görünür).
- Geçerlilik tarihi de `fiyatlar.json` içindedir (`gecerlilik`). Fiyat notları (KDV vb.) `metin.tr.fiyat_notlar` ve `metin.en.fiyat_notlar` altındadır.
- Yayındaki katalogda bu dosyayı firmanın Google E-Tablosu doldurur. Kurulum ve kullanım: `otomasyon/KURULUM.md`.
- Fiyatı olmayan ürün, fiyat listesinde görünmez.
- Fiyat listesinin arkasından, listedeki ürünlerin görsellerini kod ve adlarıyla gösteren bir sayfa gelir. Izgara ürün sayısına göre kendini ayarlar; her kutuya ürünün o kutuya en uygun oranlı fotoğrafı seçilir.

## Siteye yüklemek
`cikti/web/` klasörünü olduğu gibi sitede örneğin `/katalog/` adresine yükle.
- `siteadi.com/katalog/`: dil, tarayıcı diline göre seçilir
- `siteadi.com/katalog/?dil=en`: İngilizce açılır
- `siteadi.com/katalog/#EVE-502`: doğrudan o ürünün sayfası açılır
