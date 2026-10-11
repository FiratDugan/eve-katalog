/**
 * EVE Tekstil katalog fiyat tablosu.
 *
 * Tabloya "Katalog" menüsü ekler:
 *   - Kataloğu güncelle: tablodaki fiyatları denetler, GitHub'a gönderir; katalog
 *     birkaç dakika içinde yeni fiyatlarla yeniden oluşturulup yayınlanır.
 *   - Son güncellemenin durumu: son oluşturmanın sürdüğünü, yayına alındığını ya da hata verdiğini gösterir.
 *
 * Kurulum için bkz. KURULUM.md. GitHub anahtarı betik ayarlarına kaydedilir. Anahtar yalnızca
 * katalog oluşturma akışını başlatabilir ve depoyu okuyabilir; depoya yazamaz.
 */

// ---- Ayarlar (kurulumda doldurulur) ----
const DEPO = 'KULLANICI_ADI/eve-katalog';        // GitHub'daki depo: sahip/ad
const SITE = 'https://KULLANICI_ADI.github.io/eve-katalog/';  // Kataloğun yayın adresi
// ---------------------------------------

const SAYFA_FIYAT = 'Fiyatlar';
const SAYFA_AYAR = 'Ayarlar';
const BASLIKLAR = ['Kod', 'Ürün (yalnızca bilgi)', 'Adet', 'TL', 'USD', 'EUR'];
const AKIS = 'katalog.yml';
const ANAHTAR_UYARI_GUN = 30;  // anahtarın bitmesine bu kadar gün kala uyarılır

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Katalog')
    .addItem('Kataloğu güncelle', 'kataloguGuncelle')
    .addItem('Son güncellemenin durumu', 'durumuGoster')
    .addSeparator()
    .addSubMenu(SpreadsheetApp.getUi().createMenu('Kurulum (yalnızca ilk kez)')
      .addItem('GitHub anahtarını kaydet', 'anahtariKaydet')
      .addItem('Tabloyu yayındaki fiyatlarla hazırla', 'tabloyuHazirla'))
    .addToUi();
}

function kataloguGuncelle() {
  const ui = SpreadsheetApp.getUi();
  let veri;
  try {
    veri = tabloyuOku();
  } catch (hata) {
    ui.alert('Tabloda düzeltilmesi gereken bir şey var', hata.message, ui.ButtonSet.OK);
    return;
  }

  const urunSayisi = new Set(veri.satirlar.map((s) => s.kod)).size;
  const onay = ui.alert(
    'Katalog güncellensin mi?',
    `${urunSayisi} ürün, ${veri.satirlar.length} fiyat satırı\n` +
    `Geçerlilik tarihi: ${veri.gecerlilik}\n\n` +
    'Tarih doğru değilse önce "Ayarlar" sayfasından düzeltin.',
    ui.ButtonSet.YES_NO);
  if (onay !== ui.Button.YES) return;

  const yanit = github('post', `/repos/${DEPO}/actions/workflows/${AKIS}/dispatches`, {
    ref: 'main',
    inputs: { fiyatlar: JSON.stringify(veri) },
  });
  if (yanit.getResponseCode() !== 204) {
    ui.alert('Gönderilemedi', `GitHub yanıtı: ${yanit.getResponseCode()}\n${yanit.getContentText()}`, ui.ButtonSet.OK);
    return;
  }
  ui.alert('Güncelleme başladı',
    'Katalog yaklaşık 3–5 dakika içinde yeni fiyatlarla yayında olur.\n\n' +
    'Sonucu "Katalog > Son güncellemenin durumu" menüsünden görebilirsiniz.' + anahtarUyarisi(yanit),
    ui.ButtonSet.OK);
}

/** Tabloyu okur ve denetler. Sorun varsa hangi satırda olduğunu söyleyen bir hata fırlatır. */
function tabloyuOku() {
  const ss = SpreadsheetApp.getActive();
  const fiyat = ss.getSheetByName(SAYFA_FIYAT);
  const ayar = ss.getSheetByName(SAYFA_AYAR);
  if (!fiyat || !ayar) throw new Error(`"${SAYFA_FIYAT}" ve "${SAYFA_AYAR}" sayfaları bulunamadı.`);

  const tarih = ayar.getRange('B1').getValue();
  const gecerlilik = Object.prototype.toString.call(tarih) === '[object Date]'
    ? Utilities.formatDate(tarih, ss.getSpreadsheetTimeZone(), 'dd.MM.yyyy')
    : String(tarih).trim();
  if (!gecerlilik) throw new Error(`"${SAYFA_AYAR}" sayfasında geçerlilik tarihi (B1) boş.`);

  const gecerliKodlar = katalogKodlari();
  const satirlar = [];
  const degerler = fiyat.getDataRange().getValues().slice(1);
  degerler.forEach((r, i) => {
    const satirNo = i + 2;
    if (r.slice(0, 6).every((h) => String(h).trim() === '')) return;  // boş satır
    const kod = String(r[0]).trim();
    const adet = String(r[2]).trim();
    if (!kod) throw new Error(`${satirNo}. satırda ürün kodu boş.`);
    if (gecerliKodlar && !gecerliKodlar.has(kod)) throw new Error(`${satirNo}. satırdaki "${kod}" kodu katalogda yok.`);
    if (!adet) throw new Error(`${satirNo}. satırda adet boş.`);
    const s = { kod: kod, adet: adet };
    ['tl', 'usd', 'eur'].forEach((pb, k) => {
      const v = r[3 + k];
      if (typeof v !== 'number' || !(v > 0)) {
        throw new Error(`${satirNo}. satırda (${kod}, ${adet}) ${pb.toUpperCase()} fiyatı sayı değil ya da boş: "${v}"`);
      }
      s[pb] = Math.round(v * 100) / 100;
    });
    satirlar.push(s);
  });
  if (!satirlar.length) throw new Error(`"${SAYFA_FIYAT}" sayfasında hiç fiyat yok.`);
  return { gecerlilik: gecerlilik, satirlar: satirlar };
}

/** Katalogdaki ürün kodları. Okunamazsa null döner; kod denetimini yine de katalog oluşturulurken yapılır. */
function katalogKodlari() {
  const katalog = depodanOku('kaynak/katalog.json');
  return katalog ? new Set(katalog.urunler.map((u) => u.kod)) : null;
}

function durumuGoster() {
  const ui = SpreadsheetApp.getUi();
  const yanit = github('get', `/repos/${DEPO}/actions/workflows/${AKIS}/runs?per_page=1`);
  if (yanit.getResponseCode() !== 200) {
    ui.alert('Durum alınamadı', `GitHub yanıtı: ${yanit.getResponseCode()}`, ui.ButtonSet.OK);
    return;
  }
  const calisma = JSON.parse(yanit.getContentText()).workflow_runs[0];
  if (!calisma) {
    ui.alert('Henüz hiç güncelleme yapılmamış.');
    return;
  }
  const zaman = Utilities.formatDate(new Date(calisma.created_at),
    SpreadsheetApp.getActive().getSpreadsheetTimeZone(), 'dd.MM.yyyy HH:mm');
  let durum;
  if (calisma.status !== 'completed') durum = 'Devam ediyor. Birkaç dakika sonra tekrar bakın.';
  else if (calisma.conclusion === 'success') durum = `Tamamlandı, katalog yayında:\n${SITE}`;
  else durum = 'Hata verdi. Yayındaki katalog değişmedi, eski fiyatlarla duruyor.\nLütfen katalog sorumlusuna haber verin.';
  ui.alert('Son güncelleme', `Başlama: ${zaman}\n\n${durum}` + anahtarUyarisi(yanit), ui.ButtonSet.OK);
}

// ---- Kurulum ----

function anahtariKaydet() {
  const ui = SpreadsheetApp.getUi();
  const yanit = ui.prompt('GitHub anahtarı', 'KURULUM.md\'de anlatılan anahtarı yapıştırın:', ui.ButtonSet.OK_CANCEL);
  if (yanit.getSelectedButton() !== ui.Button.OK) return;
  PropertiesService.getScriptProperties().setProperty('GITHUB_ANAHTAR', yanit.getResponseText().trim());
  const deneme = github('get', `/repos/${DEPO}`);
  ui.alert(deneme.getResponseCode() === 200
    ? 'Anahtar kaydedildi, depoya erişim var.' + anahtarUyarisi(deneme, true)
    : `Anahtar kaydedildi ama depoya erişilemedi (yanıt: ${deneme.getResponseCode()}). DEPO ayarını ve anahtarın yetkilerini kontrol edin.`);
}

/** Fiyatlar ve Ayarlar sayfalarını oluşturur, yayındaki fiyatlarla doldurur. */
function tabloyuHazirla() {
  const ui = SpreadsheetApp.getUi();
  const ss = SpreadsheetApp.getActive();
  if (ss.getSheetByName(SAYFA_FIYAT) &&
      ui.alert('Mevcut "Fiyatlar" sayfası silinip yeniden oluşturulacak. Devam edilsin mi?', ui.ButtonSet.YES_NO) !== ui.Button.YES) return;

  const fiyatlar = depodanOku('kaynak/fiyatlar.json');
  const katalog = depodanOku('kaynak/katalog.json');
  if (!fiyatlar || !katalog) {
    ui.alert('Depodaki fiyatlar okunamadı. DEPO ayarını kontrol edin.');
    return;
  }
  const adlar = {};
  katalog.urunler.forEach((u) => { adlar[u.kod] = u.ad.tr; });

  const fiyat = sayfaSifirla(ss, SAYFA_FIYAT);
  const satirlar = fiyatlar.satirlar.map((s) => [s.kod, adlar[s.kod] || '', s.adet, s.tl, s.usd, s.eur]);
  fiyat.getRange(1, 1, 1, BASLIKLAR.length).setValues([BASLIKLAR])
    .setFontWeight('bold').setBackground('#B0141C').setFontColor('#FFFFFF');
  fiyat.getRange(2, 1, satirlar.length, BASLIKLAR.length).setValues(satirlar);
  fiyat.getRange('B2:B').setFontColor('#888888');
  fiyat.getRange('C2:C').setNumberFormat('@');
  fiyat.getRange('D2:F').setNumberFormat('#,##0.00');
  fiyat.getRange('D2:F').setDataValidation(SpreadsheetApp.newDataValidation()
    .requireNumberGreaterThan(0).setAllowInvalid(false)
    .setHelpText('Sıfırdan büyük bir sayı girin.').build());
  fiyat.setFrozenRows(1);
  fiyat.setColumnWidth(1, 110); fiyat.setColumnWidth(2, 240); fiyat.setColumnWidth(3, 70);
  [4, 5, 6].forEach((c) => fiyat.setColumnWidth(c, 100));

  const ayar = sayfaSifirla(ss, SAYFA_AYAR);
  ayar.getRange('A1:B1').setValues([['Geçerlilik tarihi', fiyatlar.gecerlilik]]);
  ayar.getRange('A1').setFontWeight('bold');
  ayar.getRange('A3').setValue('Fiyat değiştiğinde bu tarihi de güncelleyin. Katalogdaki fiyat listelerinde görünür.')
    .setFontColor('#888888');
  ayar.setColumnWidth(1, 140); ayar.setColumnWidth(2, 120);

  ss.getSheets().forEach((s) => { if (s.getName() !== SAYFA_FIYAT && s.getName() !== SAYFA_AYAR && s.getLastRow() === 0) ss.deleteSheet(s); });
  ss.setActiveSheet(fiyat);
  ui.alert('Tablo hazır.');
}

// ---- Yardımcılar ----

function sayfaSifirla(ss, ad) {
  const eski = ss.getSheetByName(ad);
  const yeni = ss.insertSheet(ad + ' (yeni)');
  if (eski) ss.deleteSheet(eski);
  return yeni.setName(ad);
}

/**
 * GitHub, bitiş tarihi olan anahtarlarda her yanıta bu tarihi ekler. Bitime az kaldıysa
 * (ya da "hep" istenirse) mesajın sonuna eklenecek uyarıyı döner; süresiz anahtarda boş döner.
 */
function anahtarUyarisi(yanit, hep) {
  const basliklar = yanit.getAllHeaders();
  const anahtar = Object.keys(basliklar).find((b) => b.toLowerCase() === 'github-authentication-token-expiration');
  if (!anahtar) return hep ? '\nAnahtarın bitiş tarihi yok.' : '';
  const bitis = new Date(basliklar[anahtar].replace(' UTC', 'Z').replace(' ', 'T'));
  const kalan = Math.floor((bitis - new Date()) / 86400000);
  if (!hep && kalan > ANAHTAR_UYARI_GUN) return '';
  const tarih = Utilities.formatDate(bitis, SpreadsheetApp.getActive().getSpreadsheetTimeZone(), 'dd.MM.yyyy');
  return `\n\nGitHub anahtarının süresi ${tarih} tarihinde (${kalan} gün sonra) doluyor.` +
    (hep ? '' : ' Lütfen katalog sorumlusuna haber verin.');
}

function depodanOku(yol) {
  const yanit = github('get', `/repos/${DEPO}/contents/${yol}`, null, 'application/vnd.github.raw+json');
  return yanit.getResponseCode() === 200 ? JSON.parse(yanit.getContentText()) : null;
}

function github(yontem, yol, govde, kabul) {
  const anahtar = PropertiesService.getScriptProperties().getProperty('GITHUB_ANAHTAR');
  if (!anahtar) throw new Error('GitHub anahtarı kayıtlı değil. "Katalog > Kurulum > GitHub anahtarını kaydet" menüsünü kullanın.');
  const secenek = {
    method: yontem,
    headers: { Authorization: 'Bearer ' + anahtar, Accept: kabul || 'application/vnd.github+json' },
    muteHttpExceptions: true,
  };
  if (govde) {
    secenek.contentType = 'application/json';
    secenek.payload = JSON.stringify(govde);
  }
  return UrlFetchApp.fetch('https://api.github.com' + yol, secenek);
}
