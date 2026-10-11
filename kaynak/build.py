#!/usr/bin/env python3
"""Eve Tekstil kataloğunu üretir.

  python3 kaynak/build.py

katalog.json + fiyatlar.json + gorseller/  ->  cikti/Eve-Tekstil-Katalog-TR.pdf, -EN.pdf
                               cikti/web/  (siteye yüklenecek klasör)

Ürün görselleri ürün koduyla adlandırılır: gorseller/EVE-501_1.jpg (ana görsel),
EVE-501_2.jpg, EVE-501_3.jpg (yan görseller). Gerçek fotoğraflar gelince aynı
adla değiştirip betiği tekrar çalıştırmak yeterli.

Fiyatlar fiyatlar.json'dadır. Bu dosyayı firmanın Google E-Tablosu doldurur
(bkz. otomasyon/), elle de düzenlenebilir.
"""
import html
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

KAYNAK = Path(__file__).resolve().parent
KOK = KAYNAK.parent
GORSELLER = KOK / "gorseller"
ONBELLEK = KAYNAK / "_onbellek"
CIKTI = KOK / "cikti"
WEB = CIKTI / "web"
DILLER = ["tr", "en"]
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
SAYFA_GENISLIK = 1240  # web sürümündeki sayfa görsellerinin genişliği (px)
FIYAT_SATIR_SAYFA = 16  # bir fiyat listesi sayfasına sığan fiyat satırı; fazlası devam sayfasına geçer

IKONLAR = {
    "visco": '<path d="M3 8c3-2 6 2 9 0s6-2 9 0M3 13c3-2 6 2 9 0s6-2 9 0M3 18c3-2 6 2 9 0s6-2 9 0"/>',
    "yikanabilir": '<path d="M3 6h18l-2 13a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2L3 6z"/><path d="M4 10c2.7 1.4 5.3-1.4 8 0s5.3 1.4 8 0"/>',
    "nefes": '<path d="M4 9h11a3 3 0 1 0-3-3M4 15h14a3 3 0 1 1-3 3M4 12h8"/>',
    "oeko": '<path d="M5 19c0-8 6-14 15-14 0 9-6 15-14 15"/><path d="M5 19l8-8"/>',
}

e = html.escape


def gorseller(kod):
    """Ürün koduna ait görseller, sıralı (EVE-501_1, EVE-501_2 ...)."""
    bulunan = [p for p in GORSELLER.glob(f"{kod}_*") if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
    return sorted(bulunan, key=lambda p: p.stem)


def img(yol, genislik):
    """Görseli sayfadaki kullanım boyutuna küçültüp (önbellekte) kullanır; PDF'i hafif tutar."""
    if yol is None or not yol.exists():
        return '<div style="width:100%;height:100%;background:#EDE6DE"></div>'
    kopya = ONBELLEK / f"{yol.stem}-{genislik}.jpg"
    if not kopya.exists() or kopya.stat().st_mtime < yol.stat().st_mtime:
        ONBELLEK.mkdir(exist_ok=True)
        subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "80", "-Z", str(genislik),
                        str(yol), "--out", str(kopya)], check=True, stdout=subprocess.DEVNULL)
    return f'<img src="_onbellek/{e(kopya.name)}" alt="">'


def kontrol(veri):
    kodlar = [u["kod"] for u in veri["urunler"]]
    tekrar = {k for k in kodlar if kodlar.count(k) > 1}
    if tekrar:
        sys.exit(f"HATA: aynı kod birden fazla üründe kullanılmış: {', '.join(sorted(tekrar))}")
    kategoriler = {k["id"] for k in veri["kategoriler"]}
    for u in veri["urunler"]:
        if u["kategori"] not in kategoriler:
            sys.exit(f"HATA: {u['kod']} ürününün kategorisi tanımlı değil: {u['kategori']}")
        if not gorseller(u["kod"]):
            print(f"  uyarı: {u['kod']} için görsel yok (gorseller/{u['kod']}_1.jpg bekleniyor)")
        if not u.get("fiyatlar"):
            print(f"  uyarı: {u['kod']} için fiyat yok, fiyat listesinde görünmeyecek")


def fiyatlari_yukle(veri):
    """fiyatlar.json'u okur, denetler ve her ürüne kendi fiyat satırlarını ekler.
    Tablodan hatalı veri gelirse derleme durur; yayındaki katalog olduğu gibi kalır."""
    fiyat = json.loads((KAYNAK / "fiyatlar.json").read_text(encoding="utf-8"))
    if not str(fiyat.get("gecerlilik", "")).strip():
        sys.exit("HATA: fiyat geçerlilik tarihi boş")
    urunler = {u["kod"]: u for u in veri["urunler"]}
    for u in urunler.values():
        u["fiyatlar"] = []
    for s in fiyat.get("satirlar", []):
        kod = str(s.get("kod", "")).strip()
        if kod not in urunler:
            sys.exit(f"HATA: fiyat listesindeki '{kod}' kodlu ürün katalogda yok")
        if not str(s.get("adet", "")).strip():
            sys.exit(f"HATA: {kod} fiyatında adet boş")
        for para_birimi in ("tl", "usd", "eur"):
            deger = s.get(para_birimi)
            if isinstance(deger, bool) or not isinstance(deger, (int, float)) or deger <= 0:
                sys.exit(f"HATA: {kod} ({s.get('adet')}) için {para_birimi.upper()} fiyatı geçersiz: {deger!r}")
        urunler[kod]["fiyatlar"].append(s)
    veri["fiyat"] = {"gecerlilik": str(fiyat["gecerlilik"]).strip()}


def fiyat_parcalari(urunler):
    """Fiyatı olan ürünleri, her sayfaya en fazla FIYAT_SATIR_SAYFA satır düşecek şekilde böler."""
    parcalar, parca, satir = [], [], 0
    for u in urunler:
        n = len(u.get("fiyatlar", []))
        if not n:
            continue
        if parca and satir + n > FIYAT_SATIR_SAYFA:
            parcalar.append(parca)
            parca, satir = [], 0
        parca.append(u)
        satir += n
    if parca:
        parcalar.append(parca)
    return parcalar


def para(x, dil):
    s = f"{x:,.2f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".") if dil == "tr" else s


def sayfa_plani(veri):
    """Sayfa sırasını ve her ürünün sayfa numarasını belirler."""
    plan = [("kapak", None), ("hakkimizda", None), ("dizin", None)]
    for kat in veri["kategoriler"]:
        urunler = [u for u in veri["urunler"] if u["kategori"] == kat["id"]]
        if not urunler:
            continue
        plan.append(("bolum", kat))
        plan += [("urun", u) for u in urunler]
        # Kategorinin fiyat listesi, son ürünün hemen arkasından gelir
        # ardından o listedeki ürünlerin görsel sayfası
        for j, parca in enumerate(fiyat_parcalari(urunler)):
            plan.append(("fiyat", (kat, parca, j > 0)))
            plan.append(("galeri", (kat, parca)))
    # Sayfa çevirmeli görünümde arka kapak tek başına kalsın diye toplam sayfa çift olmalı
    if (len(plan) + 1) % 2:
        plan.append(("notlar", None))
    plan.append(("arka", None))
    return plan


def alt(m, no):
    return f'<footer class="sayfa-alt"><span>EVE TEKSTİL · {e(m["katalog"])} {VERI["firma"]["yil"]}</span><span class="no">{no:02d}</span></footer>'


def s_kapak(dil, m, no):
    f = VERI["firma"]
    return f'''
<section class="sayfa kapak" id="p{no}">
  <div class="kapak-gorsel">{img(GORSELLER / "kapak.jpg", 1800)}</div>
  <div class="kapak-ust"><div class="logo"><b>EVE</b><i>TEKSTİL</i></div><div class="dil">{dil.upper()}</div></div>
  <div class="kapak-alt">
    <div class="etiket">EVE Tekstil · {f["yil"]}</div>
    <h1>{"<br>".join(e(w) for w in m["katalog"].split(" ", 1))}</h1>
    <p class="slogan">{e(f["slogan"][dil])}</p>
    <div class="cizgi"><span>{e(f["web"])}</span><span class="ornek-not">{e(m["ornek_not"])}</span></div>
  </div>
</section>'''


def s_hakkimizda(dil, m, no):
    f = VERI["firma"]
    paragraflar = "".join(f"<p>{e(p)}</p>" for p in m["hakkimizda"])
    rakamlar = "".join(f"<div><b>{e(a)}</b><span>{e(b)}</span></div>" for a, b in m["rakamlar"])
    rozetler = "".join(f"<span>{e(s)}</span>" for s in f["sertifikalar"])
    return f'''
<section class="sayfa hakkimizda" id="p{no}">
  <div class="icerik">
    <div class="etiket">{e(m["hakkimizda_etiket"])}</div>
    <h2>{e(m["hakkimizda_baslik"])}</h2>
    <div class="metin">{paragraflar}</div>
    <div class="rakamlar">{rakamlar}</div>
    <div class="sertifikalar"><div class="etiket">{e(m["sertifika_baslik"])}</div><div class="rozetler">{rozetler}</div></div>
  </div>
  <div class="alt-blok"><blockquote>{e(f["slogan"][dil])}</blockquote>{alt(m, no)}</div>
</section>'''


def s_dizin(dil, m, no, plan):
    satirlar = []
    for i, (tur, nesne) in enumerate(plan, 1):
        if tur == "bolum":
            satirlar.append(f'<tr class="grup"><td colspan="3">{e(nesne["ad"][dil])}</td></tr>')
        elif tur == "urun":
            satirlar.append(
                f'<tr><td class="kod"><a href="#p{i}">{e(nesne["kod"])}</a></td>'
                f'<td><a href="#p{i}">{e(nesne["ad"][dil])}</a></td><td>{i:02d}</td></tr>'
            )
        elif tur == "fiyat" and not nesne[2]:
            satirlar.append(
                f'<tr class="fiyat-satir"><td class="kod"><a href="#p{i}">₺ $ €</a></td>'
                f'<td><a href="#p{i}">{e(m["fiyat_baslik"])}</a></td><td>{i:02d}</td></tr>'
            )
    return f'''
<section class="sayfa dizin" id="p{no}">
  <div class="icerik">
    <div class="etiket">{e(m["kod"])} · {e(m["urun"])}</div>
    <h2>{e(m["dizin_baslik"])}</h2>
    <p class="aciklama">{e(m["dizin_aciklama"])}</p>
    <table><thead><tr><th>{e(m["kod"])}</th><th>{e(m["urun"])}</th><th>{e(m["sayfa"])}</th></tr></thead>
    <tbody>{"".join(satirlar)}</tbody></table>
  </div>
  {alt(m, no)}
</section>'''


def s_bolum(dil, m, no, kat, sira):
    urunler = [u["kod"] for u in VERI["urunler"] if u["kategori"] == kat["id"]]
    aralik = urunler[0] if len(urunler) == 1 else f"{urunler[0]} — {urunler[-1]}"
    return f'''
<section class="sayfa bolum" id="p{no}">
  <div class="bolum-gorsel">{img(GORSELLER / kat["gorsel"], 1600)}</div>
  <div class="bolum-metin">
    <div class="bolum-no">{sira:02d}</div>
    <h2>{e(kat["ad"][dil])}</h2>
    <p>{e(kat["aciklama"][dil])}</p>
    <div class="kod-araligi">{e(aralik)}</div>
  </div>
  {alt(m, no)}
</section>'''


def s_urun(dil, m, no, u):
    kat = next(k for k in VERI["kategoriler"] if k["id"] == u["kategori"])
    g = gorseller(u["kod"])
    ana, yan = (g[0] if g else None), g[1:3]
    yan_html = "".join(f"<div>{img(p, 700)}</div>" for p in yan)
    o = u["ozellik"]
    sertlik = "".join(f'<i class="{"dolu" if i < o["sertlik"] else ""}"></i>' for i in range(3))
    ozellikler = [
        (m["kod"], e(u["kod"]), "kod-satir"),
        (m["olcu"], e(o["olcu"]), ""),
        (m["dolgu"], e(o["dolgu"][dil]), ""),
        (m["kilif"], e(o["kilif"][dil]), ""),
        (m["yikama"], e(o["yikama"][dil]), ""),
        (m["yas"], e(o["yas"][dil]), ""),
        (m["sertlik"], f'<span class="sertlik"><span class="bar">{sertlik}</span>{e(m["sertlik_etiket"][o["sertlik"] - 1])}</span>', ""),
    ]
    dl = "".join(f'<div class="{c}"><dt>{e(a)}</dt><dd>{b}</dd></div>' for a, b, c in ozellikler)
    ikonlar = "".join(
        f'<li><svg viewBox="0 0 24 24">{IKONLAR[i]}</svg>{e(m["ikon"][i])}</li>' for i in u.get("ikonlar", [])
    )
    return f'''
<section class="sayfa urun" id="p{no}" data-kod="{e(u["kod"])}">
  <header class="sayfa-ust"><span>{e(kat["ad"][dil])}</span><span>EVE TEKSTİL</span></header>
  <div class="urun-gorseller{"" if yan else " tek"}">
    <div class="ana">{img(ana, 1300)}<div class="kod-rozet">{e(u["kod"])}</div></div>
    {f'<div class="yan">{yan_html}</div>' if yan else ""}
  </div>
  <div class="urun-bilgi">
    <div>
      <h3>{e(u["ad"][dil])}</h3>
      <p class="aciklama">{e(u["aciklama"][dil])}</p>
      <ul class="ikonlar">{ikonlar}</ul>
    </div>
    <dl class="ozellikler">{dl}</dl>
  </div>
  {alt(m, no)}
</section>'''


def s_fiyat(dil, m, no, kat, urunler, devam, plan):
    urun_sayfa = {u["kod"]: i for i, (tur, u) in enumerate(plan, 1) if tur == "urun"}
    f = VERI["fiyat"]
    govde = []
    for u in urunler:
        satirlar = u["fiyatlar"]
        for k, fy in enumerate(satirlar):
            tl, usd, eur = fy["tl"], fy["usd"], fy["eur"]
            bas = ""
            if k == 0:
                bas = (f'<td class="kod" rowspan="{len(satirlar)}"><a href="#p{urun_sayfa[u["kod"]]}">{e(u["kod"])}</a></td>'
                       f'<td class="ad" rowspan="{len(satirlar)}">{e(u["ad"][dil])}</td>')
            govde.append(
                f'<tr class="{"ilk" if k == 0 else ""}">{bas}<td class="adet">{e(str(fy["adet"]))}</td>'
                f'<td class="tutar">{para(tl, dil)}</td><td class="tutar">{para(usd, dil)}</td><td class="tutar">{para(eur, dil)}</td></tr>'
            )
    notlar = "".join(f"<li>{e(n)}</li>" for n in m["fiyat_notlar"])
    baslik = e(kat["ad"][dil]) + (f' <span>({e(m["fiyat_devam"])})</span>' if devam else "")
    return f'''
<section class="sayfa fiyat" id="p{no}">
  <header class="sayfa-ust"><span>{e(kat["ad"][dil])}</span><span>EVE TEKSTİL</span></header>
  <div class="icerik">
    <div class="etiket">{e(m["fiyat_baslik"])}</div>
    <h2>{baslik}</h2>
    <p class="gecerlilik">{e(m["fiyat_gecerlilik"].format(tarih=f["gecerlilik"]))}</p>
    <p class="aciklama">{e(m["fiyat_aciklama"])}</p>
    <table>
      <thead><tr><th>{e(m["kod"])}</th><th>{e(m["urun"])}</th><th class="adet">{e(m["adet"])}</th>
      <th class="tutar">TL <i>₺</i></th><th class="tutar">USD <i>$</i></th><th class="tutar">EUR <i>€</i></th></tr></thead>
      <tbody>{"".join(govde)}</tbody>
    </table>
  </div>
  <ul class="fiyat-notlar">{notlar}</ul>
  {alt(m, no)}
</section>'''


_OLCU = {}


def olcu(yol):
    """Görselin (genişlik, yükseklik) değeri."""
    if yol not in _OLCU:
        cikti = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(yol)],
                               capture_output=True, text=True, check=True).stdout.split()
        _OLCU[yol] = (int(cikti[cikti.index("pixelWidth:") + 1]), int(cikti[cikti.index("pixelHeight:") + 1]))
    return _OLCU[yol]


def uygun_gorsel(kod, oran):
    """Ürünün görselleri arasından kutu oranına en yakın olanı seçer (az kırpılsın diye)."""
    import math
    adaylar = gorseller(kod)
    if not adaylar:
        return None
    return min(adaylar, key=lambda p: abs(math.log((olcu(p)[0] / olcu(p)[1]) / oran)))


def galeri_duzeni(n, w=682, h=860, bosluk=14):
    """Sütun sayısını seçer; boş hücre kalırsa ilk ürün genişleyip boşluğu doldurur.
    Dönüş: sütun, satır, ilk kutunun genişliği (sütun), her kutunun en/boy oranı."""
    import math
    en_iyi = None
    for sutun in range(1, 5):
        satir = math.ceil(n / sutun)
        bos = sutun * satir - n
        if bos >= sutun:
            continue
        kw = (w - bosluk * (sutun - 1)) / sutun
        kh = (h - bosluk * (satir - 1)) / satir
        oranlar = [(kw * (1 + bos) + bosluk * bos) / kh] + [kw / kh] * (n - 1)
        puan = sum(abs(math.log(o / 1.3)) for o in oranlar) / n
        if en_iyi is None or puan < en_iyi[0]:
            en_iyi = (puan, sutun, satir, 1 + bos, oranlar)
    return en_iyi[1:]


def s_galeri(dil, m, no, kat, urunler, plan):
    urun_sayfa = {u["kod"]: i for i, (tur, u) in enumerate(plan, 1) if tur == "urun"}
    sutun, satir, ilk_genislik, oranlar = galeri_duzeni(len(urunler))
    kutular = []
    for k, u in enumerate(urunler):
        stil = f' style="grid-column:span {ilk_genislik}"' if k == 0 and ilk_genislik > 1 else ""
        kutular.append(
            f'<a class="kutu" href="#p{urun_sayfa[u["kod"]]}"{stil}>'
            f'<div class="gorsel">{img(uygun_gorsel(u["kod"], oranlar[k]), 1300)}</div>'
            f'<div class="yazi"><b>{e(u["kod"])}</b><span>{e(u["ad"][dil])}</span><i>{urun_sayfa[u["kod"]]:02d}</i></div></a>'
        )
    return f'''
<section class="sayfa galeri" id="p{no}">
  <header class="sayfa-ust"><span>{e(kat["ad"][dil])}</span><span>EVE TEKSTİL</span></header>
  <div class="etiket galeri-etiket">{e(m["galeri_etiket"])}</div>
  <div class="izgara" style="grid-template-columns:repeat({sutun},minmax(0,1fr));grid-template-rows:repeat({satir},minmax(0,1fr))">{"".join(kutular)}</div>
  {alt(m, no)}
</section>'''


def s_notlar(dil, m, no):
    return f'''
<section class="sayfa notlar" id="p{no}">
  <div class="icerik"><div class="etiket">{e(m["notlar"])}</div><div class="satirlar">{"<i></i>" * 16}</div></div>
  {alt(m, no)}
</section>'''


def s_arka(dil, m, no):
    f = VERI["firma"]
    bilgiler = [
        ("Tel", f'<a href="tel:{f["telefon"].replace(" ", "")}">{e(f["telefon"])}</a><br><a href="tel:{f["telefon2"].replace(" ", "")}">{e(f["telefon2"])}</a>'),
        ("WhatsApp", f'<a href="https://wa.me/{f["whatsapp"]}">{e(f["telefon"])}</a>'),
        ("E-mail" if dil == "en" else "E-posta", f'<a href="mailto:{f["eposta"]}">{e(f["eposta"])}</a>'),
        ("Web", f'<a href="https://{f["web"]}">{e(f["web"])}</a>'),
        ("Address" if dil == "en" else "Adres", e(f["adres"][dil])),
    ]
    dl = "".join(f"<div><dt>{a}</dt><dd>{b}</dd></div>" for a, b in bilgiler)
    rozetler = "".join(f"<span>{e(s)}</span>" for s in f["sertifikalar"])
    return f'''
<section class="sayfa arka" id="p{no}">
  <div class="icerik">
    <div class="etiket">EVE Tekstil</div>
    <h2>{e(m["iletisim_baslik"])}</h2>
    <p class="alt-baslik">{e(m["iletisim_alt"])}</p>
    <dl class="bilgiler">{dl}</dl>
    <div class="rozetler">{rozetler}</div>
  </div>
  <div class="dip"><div class="logo"><b>EVE</b><i>TEKSTİL</i></div><p>{e(m["katalog"])} {f["yil"]}<br>{e(m["ornek_not"])}</p></div>
</section>'''


def katalog_html(dil, plan):
    m = VERI["metin"][dil]
    parcalar, bolum_sira = [], 0
    for no, (tur, nesne) in enumerate(plan, 1):
        if tur == "kapak":
            parcalar.append(s_kapak(dil, m, no))
        elif tur == "hakkimizda":
            parcalar.append(s_hakkimizda(dil, m, no))
        elif tur == "dizin":
            parcalar.append(s_dizin(dil, m, no, plan))
        elif tur == "bolum":
            bolum_sira += 1
            parcalar.append(s_bolum(dil, m, no, nesne, bolum_sira))
        elif tur == "urun":
            parcalar.append(s_urun(dil, m, no, nesne))
        elif tur == "fiyat":
            kat, urunler, devam = nesne
            parcalar.append(s_fiyat(dil, m, no, kat, urunler, devam, plan))
        elif tur == "galeri":
            kat, urunler = nesne
            parcalar.append(s_galeri(dil, m, no, kat, urunler, plan))
        elif tur == "notlar":
            parcalar.append(s_notlar(dil, m, no))
        elif tur == "arka":
            parcalar.append(s_arka(dil, m, no))
    # ?sayfa=N ile tek sayfa gösterilir (web sürümü için sayfa görüntüsü alırken)
    betik = """<script>
const n = new URLSearchParams(location.search).get('sayfa');
if (n) { document.body.classList.add('tek'); document.getElementById('p' + n).classList.add('goster'); }
</script>"""
    return f'''<!doctype html>
<html lang="{dil}"><head><meta charset="utf-8">
<title>EVE Tekstil — {e(m["katalog"])} {VERI["firma"]["yil"]}</title>
<link rel="stylesheet" href="fontlar/fonts.css"><link rel="stylesheet" href="stil.css">
</head><body>{"".join(parcalar)}
{betik}</body></html>'''


def chrome(*args):
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    "--allow-file-access-from-files", "--virtual-time-budget=4000", *args],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    global VERI
    VERI = json.loads((KAYNAK / "katalog.json").read_text(encoding="utf-8"))
    fiyatlari_yukle(VERI)
    kontrol(VERI)
    plan = sayfa_plani(VERI)
    print(f"{len(VERI['urunler'])} ürün, {len(plan)} sayfa")

    if CIKTI.exists():
        shutil.rmtree(CIKTI)
    (WEB / "pdf").mkdir(parents=True)

    for dil in DILLER:
        onizleme = KAYNAK / f"onizleme-{dil}.html"
        onizleme.write_text(katalog_html(dil, plan), encoding="utf-8")
        url = onizleme.as_uri()

        pdf = CIKTI / f"Eve-Tekstil-Katalog-{dil.upper()}.pdf"
        chrome("--no-pdf-header-footer", f"--print-to-pdf={pdf}", url)
        shutil.copy(pdf, WEB / "pdf" / pdf.name)
        print(f"  {pdf.name}")

        hedef = WEB / "sayfalar" / dil
        hedef.mkdir(parents=True)
        for no in range(1, len(plan) + 1):
            png = hedef / f"{no:02d}.png"
            chrome(f"--force-device-scale-factor={SAYFA_GENISLIK / 794}", "--window-size=794,1123",
                   f"--screenshot={png}", f"{url}?sayfa={no}")
            subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "82",
                            str(png), "--out", str(png.with_suffix(".jpg"))], check=True, stdout=subprocess.DEVNULL)
            png.unlink()
        print(f"  web sayfaları ({dil}): {len(plan)}")

    # Web görüntüleyici
    veri_js = {
        "sayfaSayisi": len(plan),
        "urunler": [
            {"kod": u["kod"], "sayfa": i, "ad": {d: u["ad"][d] for d in DILLER}}
            for i, (tur, u) in enumerate(plan, 1) if tur == "urun"
        ],
        "pdf": {d: f"pdf/Eve-Tekstil-Katalog-{d.upper()}.pdf" for d in DILLER},
        "whatsapp": VERI["firma"]["whatsapp"],
        # Güncellemeden sonra tarayıcılar eski sayfa görsellerini/PDF'i önbellekten göstermesin
        "surum": str(int(time.time())),
    }
    sablon = (KAYNAK / "web" / "index.html").read_text(encoding="utf-8")
    (WEB / "index.html").write_text(sablon.replace("__VERI__", json.dumps(veri_js, ensure_ascii=False)), encoding="utf-8")
    for dosya in ["goruntuleyici.css", "goruntuleyici.js"]:
        shutil.copy(KAYNAK / "web" / dosya, WEB / dosya)
    shutil.copy(KAYNAK / "vendor" / "page-flip.browser.js", WEB / "page-flip.browser.js")
    print(f"Tamam → {CIKTI}")


if __name__ == "__main__":
    main()
