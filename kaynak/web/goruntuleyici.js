(function () {
  'use strict';

  const K = window.KATALOG;
  const N = K.sayfaSayisi;

  const METIN = {
    tr: {
      baslik: 'Ürün Kataloğu',
      ara: 'Ürün kodu ara (örn. EVE-501)',
      pdf: 'PDF İndir',
      bulunamadi: 'Bu kodla ürün bulunamadı',
      sor: (kod) => `${kod} için WhatsApp'tan sor`,
      mesaj: (kod) => `Merhaba, katalogdaki ${kod} kodlu ürün hakkında bilgi almak istiyorum.`,
      onceki: 'Önceki sayfa', sonraki: 'Sonraki sayfa', sayfa: 'Sayfa'
    },
    en: {
      baslik: 'Product Catalogue',
      ara: 'Search product code (e.g. EVE-501)',
      pdf: 'Download PDF',
      bulunamadi: 'No product found with this code',
      sor: (kod) => `Ask about ${kod} on WhatsApp`,
      mesaj: (kod) => `Hello, I would like information about product ${kod} in your catalogue.`,
      onceki: 'Previous page', sonraki: 'Next page', sayfa: 'Page'
    }
  };

  const $ = (s) => document.querySelector(s);
  const alan = $('.kitap-alani');
  const girdi = $('.ara input');
  const hata = $('.ara-hata');
  const sayac = $('.sayac');
  const sorBtn = $('.sor');
  const oncekiBtn = $('.ok.onceki');
  const sonrakiBtn = $('.ok.sonraki');

  let dil = ilkDil();
  let pf = null;
  let mod = null;
  let simdiki = 0;

  function ilkDil() {
    const p = new URLSearchParams(location.search).get('dil');
    if (p === 'tr' || p === 'en') return p;
    try {
      const s = localStorage.getItem('eve-katalog-dil');
      if (s === 'tr' || s === 'en') return s;
    } catch (e) { /* depolama kapalı olabilir */ }
    return (navigator.language || '').toLowerCase().startsWith('tr') ? 'tr' : 'en';
  }

  const iki = (n) => String(n).padStart(2, '0');

  // Geniş ekranda çift sayfa, telefonda ve dikey ekranda tek sayfa
  function modSec() {
    const r = alan.getBoundingClientRect();
    const tekGenislik = Math.min(r.width, r.height * 794 / 1123);
    const ciftGenislik = Math.min(r.width / 2, r.height * 794 / 1123);
    return r.width >= 720 && ciftGenislik >= tekGenislik * 0.8 ? 'cift' : 'tek';
  }

  function kur(baslangic) {
    if (pf) { pf.destroy(); pf = null; }
    mod = modSec();

    const kitap = document.createElement('div');
    kitap.className = 'kitap';
    alan.appendChild(kitap);

    const sayfalar = [];
    for (let i = 1; i <= N; i++) {
      const d = document.createElement('div');
      d.className = 'kitap-sayfa';
      const img = document.createElement('img');
      img.alt = `${METIN[dil].sayfa} ${i}`;
      img.dataset.src = `sayfalar/${dil}/${iki(i)}.jpg?v=${K.surum}`;
      d.appendChild(img);
      kitap.appendChild(d);
      sayfalar.push(d);
    }
    yukle(baslangic, sayfalar);

    pf = new St.PageFlip(kitap, {
      width: 794, height: 1123, size: 'stretch',
      minWidth: mod === 'cift' ? 100 : 5000, maxWidth: 6000,
      minHeight: 100, maxHeight: 6000,
      autoSize: false, showCover: true,
      usePortrait: mod === 'tek',
      startPage: baslangic,
      flippingTime: mod === 'tek' ? 450 : 700,
      maxShadowOpacity: 0.35,
      mobileScrollSupport: false,
      showPageCorners: mod === 'cift'
    });
    pf.loadFromHTML(sayfalar);
    // showCover ilk ve son sayfayı "sert kapak" yapıyor: kapak (ve arkasındaki sayfa) 3B pano gibi
    // dönüp kitaptan taşıyor. Katalog bir broşür olduğu için tüm sayfaları kağıt gibi çeviriyoruz.
    pf.getPageCollection().getPages().forEach((p) => { p.setDensity('soft'); p.setDrawingDensity('soft'); });
    pf.on('flip', (e) => guncelle(e.data));
    pf.on('init', () => guncelle(baslangic));
  }

  // Sadece görünen sayfanın çevresindeki görselleri indir
  function yukle(i, liste) {
    const sayfalar = liste || alan.querySelectorAll('.kitap-sayfa');
    for (let j = Math.max(0, i - 2); j <= Math.min(N - 1, i + 3); j++) {
      const img = sayfalar[j] && sayfalar[j].querySelector('img');
      if (img && !img.getAttribute('src')) img.src = img.dataset.src;
    }
  }

  function gorunenler(i) {
    if (mod === 'tek' || i === 0) return [i];
    const bas = i % 2 === 1 ? i : i - 1;
    return bas + 1 < N ? [bas, bas + 1] : [bas];
  }

  function guncelle(i) {
    simdiki = i;
    yukle(i);
    const g = gorunenler(i);
    sayac.textContent = g.length === 2 ? `${g[0] + 1}–${g[1] + 1} / ${N}` : `${g[0] + 1} / ${N}`;
    oncekiBtn.disabled = g[0] === 0;
    sonrakiBtn.disabled = g[g.length - 1] === N - 1;

    const urun = K.urunler.find((u) => g.includes(u.sayfa - 1));
    if (urun) {
      sorBtn.hidden = false;
      sorBtn.querySelector('span').textContent = METIN[dil].sor(urun.kod);
      sorBtn.href = `https://wa.me/${K.whatsapp}?text=${encodeURIComponent(METIN[dil].mesaj(urun.kod))}`;
    } else {
      sorBtn.hidden = true;
    }
    const hash = urun ? `#${urun.kod}` : (g[0] > 0 ? `#s${g[0] + 1}` : '');
    history.replaceState(null, '', `?dil=${dil}${hash}`);
  }

  function git(sayfaNo) {
    const i = Math.max(0, Math.min(N - 1, sayfaNo - 1));
    if (!pf || gorunenler(simdiki).includes(i)) return;
    if (Math.abs(i - simdiki) <= 2) pf.flip(i);
    else { pf.turnToPage(i); guncelle(i); }
  }

  function bul(q) {
    const t = q.trim().toLocaleUpperCase('tr').replace(/\s+/g, '');
    if (!t) return null;
    return K.urunler.find((u) => u.kod.toUpperCase() === t)
      || K.urunler.find((u) => u.kod.toUpperCase().replace(/[^A-Z0-9]/g, '').includes(t.replace(/[^A-Z0-9]/g, '')))
      || K.urunler.find((u) => u.ad[dil].toLocaleLowerCase(dil).includes(q.trim().toLocaleLowerCase(dil)));
  }

  function ara(e) {
    if (e) e.preventDefault();
    const u = bul(girdi.value);
    if (!u) {
      hata.textContent = METIN[dil].bulunamadi;
      setTimeout(() => { hata.textContent = ''; }, 2500);
      return;
    }
    hata.textContent = '';
    girdi.value = u.kod;
    girdi.blur();
    document.body.classList.remove('ara-acik');
    git(u.sayfa);
  }

  function dilUygula() {
    const m = METIN[dil];
    document.documentElement.lang = dil;
    document.title = `EVE Tekstil — ${m.baslik}`;
    $('[data-t="baslik"]').textContent = m.baslik;
    $('[data-t="pdf"]').textContent = m.pdf;
    girdi.placeholder = m.ara;
    girdi.setAttribute('aria-label', m.ara);
    oncekiBtn.setAttribute('aria-label', m.onceki);
    sonrakiBtn.setAttribute('aria-label', m.sonraki);
    const pdf = $('.pdf');
    pdf.href = `${K.pdf[dil]}?v=${K.surum}`;
    pdf.setAttribute('download', K.pdf[dil].split('/').pop());
    pdf.setAttribute('aria-label', m.pdf);
    document.querySelectorAll('.dil button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.dil === dil)));
    $('#kodlar').innerHTML = K.urunler.map((u) => `<option value="${u.kod}">${u.ad[dil]}</option>`).join('');
  }

  function baslangicSayfasi() {
    const h = decodeURIComponent(location.hash.slice(1));
    if (!h) return 0;
    const s = /^s(\d+)$/i.exec(h);
    if (s) return Math.max(0, Math.min(N - 1, Number(s[1]) - 1));
    const u = K.urunler.find((x) => x.kod.toUpperCase() === h.toUpperCase());
    return u ? u.sayfa - 1 : 0;
  }

  // ---------- Olaylar ----------

  $('.ara').addEventListener('submit', ara);
  girdi.addEventListener('change', () => { if (K.urunler.some((u) => u.kod === girdi.value)) ara(); });
  $('.ara-ac').addEventListener('click', () => {
    document.body.classList.toggle('ara-acik');
    if (document.body.classList.contains('ara-acik')) girdi.focus();
  });

  document.querySelectorAll('.dil button').forEach((b) => b.addEventListener('click', () => {
    if (b.dataset.dil === dil) return;
    dil = b.dataset.dil;
    try { localStorage.setItem('eve-katalog-dil', dil); } catch (e) { /* yok say */ }
    dilUygula();
    kur(simdiki);
  }));

  oncekiBtn.addEventListener('click', () => pf && pf.flipPrev());
  sonrakiBtn.addEventListener('click', () => pf && pf.flipNext());

  document.addEventListener('keydown', (e) => {
    if (e.target === girdi || !pf) return;
    if (e.key === 'ArrowLeft') pf.flipPrev();
    if (e.key === 'ArrowRight') pf.flipNext();
  });

  let zamanlayici;
  window.addEventListener('resize', () => {
    clearTimeout(zamanlayici);
    zamanlayici = setTimeout(() => { if (modSec() !== mod) kur(simdiki); }, 150);
  });

  dilUygula();
  kur(baslangicSayfasi());
})();
