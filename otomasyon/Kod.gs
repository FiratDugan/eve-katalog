/**
 * EVE Tekstil katalog güncelleme tablosu.
 *
 * Tabloya "Katalog" menüsü ekler:
 *   - Kataloğu güncelle: Ürünler ve Fiyatlar sayfalarını denetler, GitHub'a gönderir; katalog
 *     birkaç dakika içinde yeni bilgiler ve fiyatlarla yeniden oluşturulup yayınlanır.
 *   - Son güncellemenin durumu: son oluşturmanın sürdüğünü, yayına alındığını ya da hata verdiğini gösterir.
 *
 * Tablo mevcut ürünlerin adlarını, açıklamalarını, özelliklerini (TR/EN/DE) ve fiyatlarını değiştirir.
 * Yeni ürün, görsel, kategori değişiklikleri tablodan yapılamaz.
 *
 * Kurulum için bkz. KURULUM.md. GitHub anahtarı betik ayarlarına kaydedilir. Anahtar yalnızca
 * katalog oluşturma akışını başlatabilir ve depoyu okuyabilir; depoya yazamaz.
 */

// ---- Ayarlar (kurulumda doldurulur) ----
const DEPO = 'FiratDugan/eve-katalog';        // GitHub'daki depo: sahip/ad
const SITE = 'https://firatdugan.github.io/eve-katalog/';  // Kataloğun yayın adresi
// ---------------------------------------

const SAYFA_URUN = 'Ürünler';
const SAYFA_FIYAT = 'Fiyatlar';
const SAYFA_AYAR = 'Ayarlar';
const BASLIKLAR = ['Kod', 'Ürün (yalnızca bilgi)', 'Adet', 'TL', 'USD', 'EUR'];
const DILLER = ['tr', 'en', 'de'];
// Ürünler sayfasının sütunları: [alan, başlık]. Sayfa başlıklara göre okunur, sütun sırası önemli değil.
const URUN_SUTUNLARI = [
  ['kod', 'Kod'], ['kategori', 'Kategori (bilgi)'],
  ...ucDil('ad', 'Ürün Adı'), ...ucDil('varyant', 'Varyant'), ...ucDil('aciklama', 'Açıklama'),
  ['olcu', 'Ölçü'], ['agirlik', 'Ağırlık'],
  ...ucDil('dolgu', 'Dolgu'), ...ucDil('kumas', 'Kumaş'), ['sertlik', 'Sertlik'], ...ucDil('paket', 'Paketleme'),
];
const UC_DILLI = { ad: 'Ürün Adı', varyant: 'Varyant', aciklama: 'Açıklama', dolgu: 'Dolgu', kumas: 'Kumaş', paket: 'Paketleme' };
const AKIS = 'katalog.yml';
const AZAMI_VERI = 60000;      // GitHub'ın akış girdisi sınırı ~65.000 karakter
const ANAHTAR_UYARI_GUN = 30;  // anahtarın bitmesine bu kadar gün kala uyarılır

function ucDil(alan, baslik) {
  return DILLER.map((d) => [`${alan}.${d}`, `${baslik} (${d.toUpperCase()})`]);
}

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Katalog')
    .addItem('Kataloğu güncelle', 'kataloguGuncelle')
    .addItem('Son güncellemenin durumu', 'durumuGoster')
    .addSeparator()
    .addSubMenu(SpreadsheetApp.getUi().createMenu('Kurulum (yalnızca ilk kez)')
      .addItem('GitHub anahtarını kaydet', 'anahtariKaydet')
      .addItem('Tabloyu yayındaki katalogla hazırla', 'tabloyuHazirla'))
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

  const sikistirilmis = Utilities.base64Encode(
    Utilities.gzip(Utilities.newBlob(JSON.stringify(veri), 'application/json')).getBytes());
  if (sikistirilmis.length > AZAMI_VERI) {
    ui.alert('Tablo çok büyük', 'Veri GitHub\'ın tek seferde kabul ettiği sınırı aşıyor. Lütfen katalog sorumlusuna haber verin.', ui.ButtonSet.OK);
    return;
  }

  const fiyatliUrun = new Set(veri.fiyatlar.map((s) => s.kod)).size;
  const onay = ui.alert(
    'Katalog güncellensin mi?',
    `${veri.urunler.length} ürün bilgisi, ${fiyatliUrun} ürün için ${veri.fiyatlar.length} fiyat satırı\n` +
    `Geçerlilik tarihi: ${veri.gecerlilik}\n\n` +
    'Tarih doğru değilse önce "Ayarlar" sayfasından düzeltin.',
    ui.ButtonSet.YES_NO);
  if (onay !== ui.Button.YES) return;

  const yanit = github('post', `/repos/${DEPO}/actions/workflows/${AKIS}/dispatches`, {
    ref: 'main',
    inputs: { veri: sikistirilmis },
  });
  if (yanit.getResponseCode() !== 204) {
    ui.alert('Gönderilemedi', `GitHub yanıtı: ${yanit.getResponseCode()}\n${yanit.getContentText()}`, ui.ButtonSet.OK);
    return;
  }
  ui.alert('Güncelleme başladı',
    'Katalog yaklaşık 10–15 dakika içinde yeni bilgilerle yayında olur.\n\n' +
    'Sonucu "Katalog > Son güncellemenin durumu" menüsünden görebilirsiniz.' + anahtarUyarisi(yanit),
    ui.ButtonSet.OK);
}

/** Tabloyu okur ve denetler. Sorun varsa hangi sayfa ve satırda olduğunu söyleyen bir hata fırlatır. */
function tabloyuOku() {
  const ss = SpreadsheetApp.getActive();
  const urun = ss.getSheetByName(SAYFA_URUN);
  const fiyat = ss.getSheetByName(SAYFA_FIYAT);
  const ayar = ss.getSheetByName(SAYFA_AYAR);
  if (!urun || !fiyat || !ayar) throw new Error(`"${SAYFA_URUN}", "${SAYFA_FIYAT}" ve "${SAYFA_AYAR}" sayfaları bulunamadı.`);

  const tarih = ayar.getRange('B1').getValue();
  const gecerlilik = Object.prototype.toString.call(tarih) === '[object Date]'
    ? Utilities.formatDate(tarih, ss.getSpreadsheetTimeZone(), 'dd.MM.yyyy')
    : String(tarih).trim();
  if (!gecerlilik) throw new Error(`"${SAYFA_AYAR}" sayfasında geçerlilik tarihi (B1) boş.`);

  const katalog = depodanOku('kaynak/katalog.json');
  const gecerliKodlar = katalog ? new Set(katalog.urunler.map((u) => u.kod)) : null;
  const sertlikler = katalog ? katalog.metin.tr.sertlik_etiket : null;
  return {
    gecerlilik: gecerlilik,
    urunler: urunleriOku(urun, gecerliKodlar, sertlikler),
    fiyatlar: fiyatlariOku(fiyat, gecerliKodlar),
  };
}

function urunleriOku(sayfa, gecerliKodlar, sertlikler) {
  const tum = sayfa.getDataRange().getValues();
  const basliklar = tum[0].map((h) => String(h).trim());
  const sutun = {};
  URUN_SUTUNLARI.forEach(([alan, baslik]) => {
    const i = basliklar.indexOf(baslik);
    if (i < 0) throw new Error(`"${SAYFA_URUN}" sayfasında "${baslik}" sütunu bulunamadı.`);
    sutun[alan] = i;
  });

  const urunler = [];
  const gorulen = new Set();
  tum.slice(1).forEach((r, i) => {
    const satirNo = i + 2;
    const deger = (alan) => String(r[sutun[alan]]).trim();
    const kod = deger('kod');
    if (!kod) {
      if (URUN_SUTUNLARI.every(([alan]) => !deger(alan))) return;  // boş satır
      throw new Error(`${SAYFA_URUN}: ${satirNo}. satırda ürün kodu boş.`);
    }
    if (gecerliKodlar && !gecerliKodlar.has(kod)) {
      throw new Error(`${SAYFA_URUN}: ${satirNo}. satırdaki "${kod}" kodu katalogda yok. Yeni ürünler tablodan eklenemez.`);
    }
    if (gorulen.has(kod)) throw new Error(`${SAYFA_URUN}: "${kod}" kodu iki kez yazılmış (${satirNo}. satır).`);
    gorulen.add(kod);

    const u = { kod: kod, olcu: deger('olcu'), agirlik: deger('agirlik'), sertlik: deger('sertlik') };
    Object.keys(UC_DILLI).forEach((alan) => {
      const v = {};
      DILLER.forEach((d) => { v[d] = deger(`${alan}.${d}`); });
      const bos = DILLER.filter((d) => !v[d]);
      if (bos.length === DILLER.length) {
        if (alan === 'ad') throw new Error(`${SAYFA_URUN}: ${satirNo}. satırda (${kod}) ürün adı boş.`);
        return;
      }
      if (bos.length) {
        throw new Error(`${SAYFA_URUN}: ${satirNo}. satırda (${kod}) "${UC_DILLI[alan]}" için ` +
          `${bos.map((d) => d.toUpperCase()).join(' ve ')} çevirisi boş. TR, EN ve DE üçü birlikte doldurulmalı.`);
      }
      u[alan] = v;
    });
    if (u.sertlik && sertlikler && sertlikler.indexOf(u.sertlik) < 0) {
      throw new Error(`${SAYFA_URUN}: ${satirNo}. satırda (${kod}) sertlik "${u.sertlik}" tanınmadı. Listeden seçin: ${sertlikler.join(', ')}`);
    }
    urunler.push(u);
  });
  if (!urunler.length) throw new Error(`"${SAYFA_URUN}" sayfasında hiç ürün yok.`);
  return urunler;
}

function fiyatlariOku(sayfa, gecerliKodlar) {
  const satirlar = [];
  sayfa.getDataRange().getValues().slice(1).forEach((r, i) => {
    const satirNo = i + 2;
    if (r.slice(0, 6).every((h) => String(h).trim() === '')) return;  // boş satır
    const kod = String(r[0]).trim();
    const adet = String(r[2]).trim();
    if (!kod) throw new Error(`${SAYFA_FIYAT}: ${satirNo}. satırda ürün kodu boş.`);
    if (gecerliKodlar && !gecerliKodlar.has(kod)) throw new Error(`${SAYFA_FIYAT}: ${satirNo}. satırdaki "${kod}" kodu katalogda yok.`);
    const s = { kod: kod, adet: adet };  // adet boş olabilir
    ['tl', 'usd', 'eur'].forEach((pb, k) => {
      const v = r[3 + k];
      // USD/EUR henüz girilmemiş olabilir: katalogda "—" görünür. TL zorunlu.
      if (pb !== 'tl' && String(v).trim() === '') {
        s[pb] = null;
        return;
      }
      if (typeof v !== 'number' || !(v > 0)) {
        throw new Error(`${SAYFA_FIYAT}: ${satirNo}. satırda (${kod}${adet ? ', ' + adet : ''}) ${pb.toUpperCase()} fiyatı sayı değil ya da boş: "${v}"`);
      }
      s[pb] = Math.round(v * 100) / 100;
    });
    satirlar.push(s);
  });
  return satirlar;
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
  else durum = 'Hata verdi. Yayındaki katalog değişmedi, eski haliyle duruyor.\nLütfen katalog sorumlusuna haber verin.';
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

/** Ürünler, Fiyatlar ve Ayarlar sayfalarını oluşturur, yayındaki katalogla doldurur. */
function tabloyuHazirla() {
  const ui = SpreadsheetApp.getUi();
  const ss = SpreadsheetApp.getActive();
  if ((ss.getSheetByName(SAYFA_URUN) || ss.getSheetByName(SAYFA_FIYAT)) &&
      ui.alert(`Mevcut "${SAYFA_URUN}", "${SAYFA_FIYAT}" ve "${SAYFA_AYAR}" sayfaları silinip yayındaki katalogla yeniden oluşturulacak. Devam edilsin mi?`,
        ui.ButtonSet.YES_NO) !== ui.Button.YES) return;

  const fiyatlar = depodanOku('kaynak/fiyatlar.json');
  const katalog = depodanOku('kaynak/katalog.json');
  if (!fiyatlar || !katalog) {
    ui.alert('Depodaki katalog okunamadı. DEPO ayarını ve GitHub anahtarını kontrol edin.');
    return;
  }

  // Ürünler
  const kategoriler = {};
  katalog.kategoriler.forEach((k) => { kategoriler[k.id] = k.ad.tr; });
  const sertlikler = katalog.metin.tr.sertlik_etiket;
  const urun = sayfaSifirla(ss, SAYFA_URUN);
  const urunSatirlari = katalog.urunler.map((u) => URUN_SUTUNLARI.map(([alan]) => {
    const o = u.ozellik || {};
    if (alan === 'kod') return u.kod;
    if (alan === 'kategori') return kategoriler[u.kategori] || u.kategori;
    if (alan === 'olcu' || alan === 'agirlik') return o[alan] || '';
    if (alan === 'sertlik') return o.sertlik ? sertlikler[o.sertlik - 1] : '';
    const [ad, dil] = alan.split('.');
    const kaynak = (ad === 'ad' || ad === 'varyant' || ad === 'aciklama') ? u[ad] : o[ad];
    return (kaynak && kaynak[dil]) || '';
  }));
  urun.getRange(1, 1, 1, URUN_SUTUNLARI.length).setValues([URUN_SUTUNLARI.map(([, b]) => b)])
    .setFontWeight('bold').setBackground('#B0141C').setFontColor('#FFFFFF').setWrap(true);
  urun.getRange(2, 1, urun.getMaxRows() - 1, URUN_SUTUNLARI.length).setNumberFormat('@');  // "01" gibi değerler metin kalsın
  urun.getRange(2, 1, urunSatirlari.length, URUN_SUTUNLARI.length).setValues(urunSatirlari).setVerticalAlignment('top');
  urun.getRange(2, 1, urunSatirlari.length, 2).setFontColor('#888888');
  const sertlikSutun = URUN_SUTUNLARI.findIndex(([alan]) => alan === 'sertlik') + 1;
  urun.getRange(2, sertlikSutun, urunSatirlari.length, 1).setDataValidation(SpreadsheetApp.newDataValidation()
    .requireValueInList(sertlikler, true).setAllowInvalid(false).build());
  urun.setFrozenRows(1);
  urun.setFrozenColumns(1);
  URUN_SUTUNLARI.forEach(([alan], i) => urun.setColumnWidth(i + 1, alan.startsWith('aciklama') ? 260 : 150));
  // Kod ve kategori görsel ve sayfa düzenine bağlı: değiştirilmesin
  urun.getRange(1, 1, urun.getMaxRows(), 2).protect().setDescription('Kod ve kategori tablodan değiştirilemez').setWarningOnly(true);

  // Fiyatlar
  const adlar = {};
  katalog.urunler.forEach((u) => { adlar[u.kod] = u.ad.tr; });
  const fiyat = sayfaSifirla(ss, SAYFA_FIYAT);
  const satirlar = fiyatlar.satirlar.map((s) => [s.kod, adlar[s.kod] || '', s.adet, s.tl, s.usd ?? '', s.eur ?? '']);
  fiyat.getRange(1, 1, 1, BASLIKLAR.length).setValues([BASLIKLAR])
    .setFontWeight('bold').setBackground('#B0141C').setFontColor('#FFFFFF');
  // Kod, ad ve adet metin olarak kalsın: "01" gibi ürün adları sayıya dönüşmesin
  fiyat.getRange('A2:C').setNumberFormat('@');
  fiyat.getRange(2, 1, satirlar.length, BASLIKLAR.length).setValues(satirlar);
  fiyat.getRange('B2:B').setFontColor('#888888');
  fiyat.getRange('D2:F').setNumberFormat('#,##0.00');
  fiyat.getRange('D2:F').setDataValidation(SpreadsheetApp.newDataValidation()
    .requireNumberGreaterThan(0).setAllowInvalid(false)
    .setHelpText('Sıfırdan büyük bir sayı girin.').build());
  fiyat.setFrozenRows(1);
  fiyat.setColumnWidth(1, 150); fiyat.setColumnWidth(2, 240); fiyat.setColumnWidth(3, 70);
  [4, 5, 6].forEach((c) => fiyat.setColumnWidth(c, 100));

  // Ayarlar
  const ayar = sayfaSifirla(ss, SAYFA_AYAR);
  ayar.getRange('A1:B1').setValues([['Geçerlilik tarihi', fiyatlar.gecerlilik]]);
  ayar.getRange('A1').setFontWeight('bold');
  ayar.getRange('A3').setValue('Fiyat değiştiğinde bu tarihi de güncelleyin. Katalogdaki fiyat listelerinde görünür.')
    .setFontColor('#888888');
  ayar.setColumnWidth(1, 140); ayar.setColumnWidth(2, 120);

  ss.getSheets().forEach((s) => { if (![SAYFA_URUN, SAYFA_FIYAT, SAYFA_AYAR].includes(s.getName()) && s.getLastRow() === 0) ss.deleteSheet(s); });
  ss.setActiveSheet(urun);
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
