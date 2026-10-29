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

try:  # Web sayfa görselleri için WebP (JPEG'in yaklaşık üçte biri); Pillow yoksa JPEG üretilir
    from PIL import Image
except ImportError:
    Image = None

KAYNAK = Path(__file__).resolve().parent
KOK = KAYNAK.parent
GORSELLER = KOK / "gorseller"
ONBELLEK = KAYNAK / "_onbellek"
CIKTI = KOK / "cikti"
WEB = CIKTI / "web"
DILLER = ["tr", "en"]
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
SAYFA_GENISLIK = 1240  # web sürümündeki sayfa görsellerinin genişliği (px)
SAYFA_UZANTI = "webp" if Image else "jpg"
FIYAT_SATIR_SAYFA = 16  # bir fiyat listesi sayfasına sığan fiyat satırı; fazlası devam sayfasına geçer
DIZIN_YUKSEKLIK = 700  # bir dizin sayfasındaki tabloya ayrılan yükseklik (px); fazlası sonraki dizin sayfasına geçer

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


def logo_dosyasi():
    """Şeffaf logoyu (gorseller/logo.png) 400 px PNG olarak önbelleğe alır; şeffaflık korunur."""
    kaynak, kopya = GORSELLER / "logo.png", ONBELLEK / "logo-400.png"
    if not kopya.exists() or kopya.stat().st_mtime < kaynak.stat().st_mtime:
        ONBELLEK.mkdir(exist_ok=True)
        subprocess.run(["sips", "-s", "format", "png", "-Z", "400", str(kaynak), "--out", str(kopya)],
                       check=True, stdout=subprocess.DEVNULL)
    return kopya


def logo():
    return f'<div class="logo"><img src="_onbellek/{logo_dosyasi().name}" alt="EVE Tekstil"></div>'


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
            print(f"  uyarı: {u['kod']} için fiyat yok, fiyat listesinde boş görünecek")
    gruplar = {g["id"] for g in veri.get("gruplar", [])}
    for u in veri["urunler"]:
        if u.get("grup") and u["grup"] not in gruplar:
            sys.exit(f"HATA: {u['kod']} ürününün grubu tanımlı değil: {u['grup']}")


def fiyatlari_yukle(veri):
    """fiyatlar.json'u okur, denetler ve her ürüne kendi fiyat satırlarını ekler.
    Tablodan hatalı veri gelirse derleme durur; yayındaki katalog olduğu gibi kalır."""
    fiyat = json.loads((KAYNAK / "fiyatlar.json").read_text(encoding="utf-8"))
    urunler = {u["kod"]: u for u in veri["urunler"]}
    for u in urunler.values():
        u["fiyatlar"] = []
    for s in fiyat.get("satirlar", []):
        kod = str(s.get("kod", "")).strip()
        if kod not in urunler:
            sys.exit(f"HATA: fiyat listesindeki '{kod}' kodlu ürün katalogda yok")
        for para_birimi in ("tl", "usd", "eur"):
            deger = s.get(para_birimi)
            if deger is None and para_birimi != "tl":
                continue  # USD/EUR henüz girilmemiş: listede "—" görünür
            if isinstance(deger, bool) or not isinstance(deger, (int, float)) or deger <= 0:
                sys.exit(f"HATA: {kod} ({s.get('adet')}) için {para_birimi.upper()} fiyatı geçersiz: {deger!r}")
        urunler[kod]["fiyatlar"].append(s)
    veri["fiyat"] = {"gecerlilik": str(fiyat.get("gecerlilik", "")).strip()}


def fiyat_parcalari(urunler):
    """Ürünleri, her sayfaya en fazla FIYAT_SATIR_SAYFA satır düşecek şekilde böler.
    Fiyatı girilmemiş ürün de listede boş bir satırla yer alır."""
    parcalar, parca, satir = [], [], 0
    for u in urunler:
        n = max(1, len(u.get("fiyatlar", [])))
        if parca and satir + n > FIYAT_SATIR_SAYFA:
            parcalar.append(parca)
            parca, satir = [], 0
        parca.append(u)
        satir += n
    if parca:
        parcalar.append(parca)
    return parcalar


def para(x, dil):
    if x is None:
        return "—"
    s = f"{x:,.2f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".") if dil == "tr" else s


def sayfa_plani(veri):
    """Sayfa sırasını ve her ürünün sayfa numarasını belirler."""
    plan = []
    for kat in veri["kategoriler"]:
        urunler = [u for u in veri["urunler"] if u["kategori"] == kat["id"]]
        if not urunler:
            continue
        plan.append(("bolum", kat))
        # Aynı gruptaki ardışık ürünler (ör. aynı yorganın tek/çift kişilik ölçüsü) tek sayfada
        sayfalar = []
        for u in urunler:
            if u.get("grup") and sayfalar and sayfalar[-1][0].get("grup") == u["grup"]:
                sayfalar[-1].append(u)
            else:
                sayfalar.append([u])
        plan += [("urun", s) for s in sayfalar]
        # Kategorinin fiyat listesi, son ürünün hemen arkasından gelir
        # ardından (kategoride kapatılmadıysa) o listedeki ürünlerin görsel sayfası
        for j, parca in enumerate(fiyat_parcalari(urunler)):
            plan.append(("fiyat", (kat, parca, j > 0)))
            if kat.get("galeri", True):
                plan.append(("galeri", (kat, parca)))
    dizin = [("dizin", parca) for parca in dizin_parcalari(plan)]
    plan = [("kapak", None), ("hakkimizda", None)] + dizin + plan
    plan.append(("arka", None))
    return plan


def urun_sayfalari(plan):
    """Ürün kodu -> ürünün sayfa numarası."""
    return {u["kod"]: i for i, (tur, us) in enumerate(plan, 1) if tur == "urun" for u in us}


def dizin_parcalari(plan):
    """Dizin satırlarını (plan içindeki sıra numaralarıyla) sayfalara böler.
    Kategori başlığı sayfanın son satırı olarak kalmaz."""
    yukseklik = {"bolum": 52, "urun": 35, "fiyat": 35}
    satirlar = [i for i, (tur, n) in enumerate(plan) if tur in ("bolum", "urun") or (tur == "fiyat" and not n[2])]
    parcalar, parca, dolu = [], [], 0
    for i in satirlar:
        tur, n = plan[i]
        satir = yukseklik[tur] * (len(n) if tur == "urun" else 1)
        h = satir + (yukseklik["urun"] if tur == "bolum" else 0)
        if parca and dolu + h > DIZIN_YUKSEKLIK:
            parcalar.append(parca)
            parca, dolu = [], 0
        parca.append(i)
        dolu += satir
    if parca:
        parcalar.append(parca)
    return parcalar


def alt(m, no):
    return f'<footer class="sayfa-alt"><span>EVE TEKSTİL · {e(m["katalog"])} {VERI["firma"]["yil"]}</span><span class="no">{no:02d}</span></footer>'


def s_kapak(dil, m, no):
    f = VERI["firma"]
    return f'''
<section class="sayfa kapak" id="p{no}">
  <div class="kapak-gorsel">{img(GORSELLER / VERI.get("kapak", "kapak.jpg"), 1800)}</div>
  <div class="kapak-ust">{logo()}<div class="dil">{dil.upper()}</div></div>
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


def s_dizin(dil, m, no, plan, parca):
    ilk_dizin = next(i for i, (tur, _) in enumerate(plan, 1) if tur == "dizin")
    kaydirma = sum(1 for tur, _ in plan if tur == "dizin") + 2  # dizin satırları dizinsiz plana göre numaralı
    satirlar = []
    for j in parca:
        i = j + kaydirma + 1
        tur, nesne = plan[i - 1]
        if tur == "bolum":
            satirlar.append(f'<tr class="grup"><td colspan="3">{e(nesne["ad"][dil])}</td></tr>')
        elif tur == "urun":
            satirlar += [
                f'<tr><td class="kod"><a href="#p{i}">{e(u["kod"])}</a></td>'
                f'<td><a href="#p{i}">{e(u["ad"][dil])}</a></td><td>{i:02d}</td></tr>'
                for u in nesne
            ]
        elif tur == "fiyat" and not nesne[2]:
            satirlar.append(
                f'<tr class="fiyat-satir"><td class="kod"><a href="#p{i}">₺ $ €</a></td>'
                f'<td><a href="#p{i}">{e(m["fiyat_baslik"])}</a></td><td>{i:02d}</td></tr>'
            )
    return f'''
<section class="sayfa dizin" id="p{no}">
  <div class="icerik">
    <div class="etiket">{e(m["kod"])} · {e(m["urun"])}</div>
    <h2>{e(m["dizin_baslik"])}{f' <span>({e(m["fiyat_devam"])})</span>' if no != ilk_dizin else ""}</h2>
    <p class="aciklama">{e(m["dizin_aciklama"])}</p>
    <table><thead><tr><th>{e(m["kod"])}</th><th>{e(m["urun"])}</th><th>{e(m["sayfa"])}</th></tr></thead>
    <tbody>{"".join(satirlar)}</tbody></table>
  </div>
  {alt(m, no)}
</section>'''


def s_bolum(dil, m, no, kat, sira):
    n = sum(1 for u in VERI["urunler"] if u["kategori"] == kat["id"])
    aciklama = kat.get("aciklama", {}).get(dil, "")
    return f'''
<section class="sayfa bolum" id="p{no}">
  <div class="bolum-gorsel">{img(GORSELLER / kat["gorsel"], 1600)}</div>
  <div class="bolum-metin">
    <div class="bolum-no">{sira:02d}</div>
    <h2>{e(kat["ad"][dil])}</h2>
    {f"<p>{e(aciklama)}</p>" if aciklama else ""}
    <div class="kod-araligi">{e(m["urun_sayisi"].format(n=n))}</div>
  </div>
  {alt(m, no)}
</section>'''


OZELLIK_ALANLARI = ("olcu", "agirlik", "dolgu", "kumas", "paket", "sertlik")


def ozellik_degeri(m, o, alan, dil):
    """Özellik alanının sayfadaki HTML'i; değer yoksa boş metin."""
    if not o.get(alan):
        return ""
    if alan == "sertlik":
        bar = "".join(f'<i class="{"dolu" if i < o["sertlik"] else ""}"></i>' for i in range(5))
        return f'<span class="sertlik"><span class="bar">{bar}</span>{e(m["sertlik_etiket"][o["sertlik"] - 1])}</span>'
    return e(o[alan][dil] if isinstance(o[alan], dict) else o[alan])


def s_grup(dil, m, no, us):
    """Aynı gruptaki ürünler tek sayfada: ortak özellikler bir kez, farklı olanlar ürün ürün."""
    grup = next(g for g in VERI["gruplar"] if g["id"] == us[0]["grup"])
    kat = next(k for k in VERI["kategoriler"] if k["id"] == us[0]["kategori"])
    anahtar = lambda u, a: json.dumps(u["ozellik"].get(a), sort_keys=True, ensure_ascii=False)
    farkli = [a for a in OZELLIK_ALANLARI if len({anahtar(u, a) for u in us}) > 1]
    ortak = [a for a in OZELLIK_ALANLARI if a not in farkli and us[0]["ozellik"].get(a)]
    dl = '<dl class="ozellikler">' + "".join(
        f'<div><dt>{e(m[a])}</dt><dd>{ozellik_degeri(m, us[0]["ozellik"], a, dil)}</dd></div>' for a in ortak) + "</dl>"
    aciklamalar = {u["aciklama"][dil] for u in us}
    aciklama = aciklamalar.pop() if len(aciklamalar) == 1 else ""
    ikonlar = "".join(
        f'<li><svg viewBox="0 0 24 24">{IKONLAR[i]}</svg>{e(m["ikon"][i])}</li>' for i in us[0].get("ikonlar", [])
    )
    bilgi = (f'<h3>{e(grup["ad"][dil])}</h3>' + (f'<p class="aciklama">{e(aciklama)}</p>' if aciklama else "")
             + (f'<ul class="ikonlar">{ikonlar}</ul>' if ikonlar else ""))
    ust = f'<header class="sayfa-ust"><span>{e(kat["ad"][dil])}</span><span>EVE TEKSTİL</span></header>'

    if grup.get("ortak_gorsel"):
        # Ürünler aynı görselleri paylaşır: görseller bir kez, altında ürün tablosu
        g = gorseller(us[0]["kod"])
        dikey = [p for p in g if olcu(p)[1] > olcu(p)[0]]
        yatay = [p for p in g if p not in dikey]
        bas = "".join(f"<th>{e(m[a])}</th>" for a in farkli)
        govde = "".join(
            f'<tr><td class="kod">{e(u["kod"])}</td><td>{e(u["varyant"][dil])}</td>'
            + "".join(f"<td>{ozellik_degeri(m, u['ozellik'], a, dil) or '—'}</td>" for a in farkli) + "</tr>"
            for u in us
        )
        tablo = (f'<table class="varyantlar"><thead><tr><th>{e(m["kod"])}</th><th>{e(m["urun"])}</th>{bas}</tr></thead>'
                 f"<tbody>{govde}</tbody></table>")
        rozet = f'<div class="kod-rozet">{" · ".join(e(u["kod"]) for u in us)}</div>'
        return f'''
<section class="sayfa urun cift grup" id="p{no}" data-kod="{e(us[0]["kod"])}">
  {ust}
  <div class="hero">{img(yatay[0] if yatay else (g[0] if g else None), 1300)}{rozet}</div>
  <div class="dikey-gorsel">{img(dikey[0] if dikey else None, 700)}</div>
  <div class="metin-kolon">{bilgi}{tablo}{dl}</div>
  {alt(m, no)}
</section>'''

    # Her ürünün kendi görseli: yan yana, altında kodu ve farklı özellikleri
    kutular = "".join(
        f'<figure><div class="gorsel">{img(next(iter(gorseller(u["kod"])), None), 700)}</div>'
        f'<figcaption><b>{e(u["kod"])}</b><span>{e(u["varyant"][dil])}</span>'
        + "".join(f'<div class="fark"><i>{e(m[a])}</i>{ozellik_degeri(m, u["ozellik"], a, dil) or "—"}</div>' for a in farkli)
        + "</figcaption></figure>"
        for u in us
    )
    return f'''
<section class="sayfa urun grup ayri" id="p{no}" data-kod="{e(us[0]["kod"])}">
  {ust}
  <div class="grup-gorseller" style="grid-template-columns:repeat({len(us)},minmax(0,1fr))">{kutular}</div>
  <div class="urun-bilgi">
    <div>{bilgi}</div>
    {dl}
  </div>
  {alt(m, no)}
</section>'''


def s_urun(dil, m, no, us):
    """Görsel düzeni görsellerin sayısına ve yönüne göre seçilir:
    3+ görsel: büyük görsel + 2 yan görsel; 1 yatay + 1 dikey: üstte yatay, altta dikey + bilgiler;
    tek dikey: solda görsel, sağda bilgiler. Gruplu ürünler tek sayfada (s_grup)."""
    if len(us) > 1:
        return s_grup(dil, m, no, us)
    u = us[0]
    kat = next(k for k in VERI["kategoriler"] if k["id"] == u["kategori"])
    g = gorseller(u["kod"])
    dikey = [p for p in g if olcu(p)[1] > olcu(p)[0]]
    yatay = [p for p in g if p not in dikey]
    o = u["ozellik"]
    ozellikler = [(m["kod"], e(u["kod"]), "kod-satir")]
    ozellikler += [(m[a], ozellik_degeri(m, o, a, dil), "") for a in OZELLIK_ALANLARI if o.get(a)]
    dl = "<dl class=\"ozellikler\">" + "".join(f'<div class="{c}"><dt>{e(a)}</dt><dd>{b}</dd></div>' for a, b, c in ozellikler) + "</dl>"
    ikonlar = "".join(
        f'<li><svg viewBox="0 0 24 24">{IKONLAR[i]}</svg>{e(m["ikon"][i])}</li>' for i in u.get("ikonlar", [])
    )
    aciklama = u["aciklama"][dil]
    bilgi = (f'<h3>{e(u["ad"][dil])}</h3>' + (f'<p class="aciklama">{e(aciklama)}</p>' if aciklama else "")
             + (f'<ul class="ikonlar">{ikonlar}</ul>' if ikonlar else ""))
    rozet = f'<div class="kod-rozet">{e(u["kod"])}</div>'
    ust = f'<header class="sayfa-ust"><span>{e(kat["ad"][dil])}</span><span>EVE TEKSTİL</span></header>'

    if len(g) <= 2 and dikey:
        if yatay:
            return f'''
<section class="sayfa urun cift" id="p{no}" data-kod="{e(u["kod"])}">
  {ust}
  <div class="hero">{img(yatay[0], 1300)}{rozet}</div>
  <div class="dikey-gorsel">{img(dikey[0], 700)}</div>
  <div class="metin-kolon">{bilgi}{dl}</div>
  {alt(m, no)}
</section>'''
        return f'''
<section class="sayfa urun dikey" id="p{no}" data-kod="{e(u["kod"])}">
  {ust}
  <div class="dikey-gorsel">{img(dikey[0], 900)}{rozet}</div>
  <div class="metin-kolon">{bilgi}</div>
  {dl}
  {alt(m, no)}
</section>'''

    sirali = dikey + yatay
    ana, yan = (sirali[0] if sirali else None), sirali[1:3]
    yan_html = "".join(f"<div>{img(p, 700)}</div>" for p in yan)
    return f'''
<section class="sayfa urun" id="p{no}" data-kod="{e(u["kod"])}">
  {ust}
  <div class="urun-gorseller{"" if yan else " tek"}">
    <div class="ana">{img(ana, 1300)}{rozet}</div>
    {f'<div class="yan">{yan_html}</div>' if yan else ""}
  </div>
  <div class="urun-bilgi">
    <div>{bilgi}</div>
    {dl}
  </div>
  {alt(m, no)}
</section>'''


def s_fiyat(dil, m, no, kat, urunler, devam, plan):
    urun_sayfa = urun_sayfalari(plan)
    f = VERI["fiyat"]
    govde = []
    for u in urunler:
        satirlar = u["fiyatlar"] or [{"adet": "", "tl": None, "usd": None, "eur": None}]
        for k, fy in enumerate(satirlar):
            tl, usd, eur = fy["tl"], fy["usd"], fy["eur"]
            bas = ""
            if k == 0:
                bas = (f'<td class="kod" rowspan="{len(satirlar)}"><a href="#p{urun_sayfa[u["kod"]]}">{e(u["kod"])}</a></td>'
                       f'<td class="ad" rowspan="{len(satirlar)}">{e(u["ad"][dil])}</td>')
            govde.append(
                f'<tr class="{"ilk" if k == 0 else ""}">{bas}<td class="adet">{e(str(fy.get("adet") or "—"))}</td>'
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
    {f'<p class="gecerlilik">{e(m["fiyat_gecerlilik"].format(tarih=f["gecerlilik"]))}</p>' if f["gecerlilik"] else ""}
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
    urun_sayfa = urun_sayfalari(plan)
    if kat.get("galeri_sira"):
        sira = kat["galeri_sira"]
        urunler = sorted(urunler, key=lambda u: sira.index(u["kod"]) if u["kod"] in sira else len(sira))
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
  <div class="dip">{logo()}<p>{e(m["katalog"])} {f["yil"]}<br>{e(m["ornek_not"])}</p></div>
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
            parcalar.append(s_dizin(dil, m, no, plan, nesne))
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
            if Image:
                Image.open(png).convert("RGB").save(png.with_suffix(".webp"), "WEBP", quality=80, method=5)
            else:
                subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "82",
                                str(png), "--out", str(png.with_suffix(".jpg"))], check=True, stdout=subprocess.DEVNULL)
            png.unlink()
        print(f"  web sayfaları ({dil}): {len(plan)} {SAYFA_UZANTI}")

    # Web görüntüleyici
    veri_js = {
        "sayfaSayisi": len(plan),
        "uzanti": SAYFA_UZANTI,
        "urunler": [
            {"kod": u["kod"], "sayfa": i, "ad": {d: u["ad"][d] for d in DILLER}}
            for i, (tur, us) in enumerate(plan, 1) if tur == "urun" for u in us
        ],
        "pdf": {d: f"pdf/Eve-Tekstil-Katalog-{d.upper()}.pdf" for d in DILLER},
        # Güncellemeden sonra tarayıcılar eski sayfa görsellerini/PDF'i önbellekten göstermesin
        "surum": str(int(time.time())),
    }
    sablon = (KAYNAK / "web" / "index.html").read_text(encoding="utf-8")
    (WEB / "index.html").write_text(sablon.replace("__VERI__", json.dumps(veri_js, ensure_ascii=False)), encoding="utf-8")
    for dosya in ["goruntuleyici.css", "goruntuleyici.js"]:
        shutil.copy(KAYNAK / "web" / dosya, WEB / dosya)
    shutil.copy(KAYNAK / "vendor" / "page-flip.browser.js", WEB / "page-flip.browser.js")
    shutil.copy(logo_dosyasi(), WEB / "logo.png")
    print(f"Tamam → {CIKTI}")


if __name__ == "__main__":
    main()
