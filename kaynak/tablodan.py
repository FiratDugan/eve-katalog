#!/usr/bin/env python3
"""Google E-Tablodan gelen ürün bilgilerini ve fiyatları katalog.json / fiyatlar.json'a işler.

  VERI=<base64 gzip JSON> python3 kaynak/tablodan.py

GitHub akışı (katalog.yml) çalıştırır; tablo betiği (otomasyon/Kod.gs) veriyi sıkıştırıp gönderir.
Tablo yalnızca mevcut ürünlerin metinlerini, özelliklerini ve fiyatlarını değiştirebilir.
Yeni ürün, görsel, kategori ve grup değişiklikleri katalog.json'dan yapılır.
Sorun bulunursa hiçbir dosya yazılmaz, akış durur ve yayındaki katalog olduğu gibi kalır.
"""

import base64
import gzip
import json
import os
import sys
from pathlib import Path

KAYNAK = Path(__file__).resolve().parent
DILLER = ["tr", "en", "de"]
UC_DILLI = ["ad", "varyant", "aciklama", "dolgu", "kumas", "paket"]


def hata(mesaj):
    sys.exit(f"HATA (tablo): {mesaj}")


def uc_dil(deger, kod, alan):
    """{"tr", "en", "de"} ya da None. Bir dil doluysa üçü de dolu olmalı."""
    if deger is None:
        return None
    temiz = {d: str(deger.get(d, "")).strip() for d in DILLER}
    dolu = [d for d in DILLER if temiz[d]]
    if not dolu:
        return None
    if len(dolu) < len(DILLER):
        eksik = ", ".join(d.upper() for d in DILLER if not temiz[d])
        hata(f"{kod}: '{alan}' alanının {eksik} karşılığı boş")
    return temiz


def main():
    ham = os.environ.get("VERI", "").strip()
    if not ham:
        hata("VERI boş")
    tablo = json.loads(gzip.decompress(base64.b64decode(ham)).decode("utf-8"))

    katalog_yolu = KAYNAK / "katalog.json"
    katalog = json.loads(katalog_yolu.read_text(encoding="utf-8"))
    urunler = {u["kod"]: u for u in katalog["urunler"]}
    sertlikler = katalog["metin"]["tr"]["sertlik_etiket"]

    gorulen = set()
    for t in tablo["urunler"]:
        kod = str(t.get("kod", "")).strip()
        if kod not in urunler:
            hata(f"'{kod}' kodlu ürün katalogda yok (yeni ürünler tablodan eklenemez)")
        if kod in gorulen:
            hata(f"'{kod}' kodu tabloda iki kez var")
        gorulen.add(kod)
        u = urunler[kod]

        ad = uc_dil(t.get("ad"), kod, "ürün adı")
        if not ad:
            hata(f"{kod}: ürün adı boş")
        u["ad"] = ad
        u["aciklama"] = uc_dil(t.get("aciklama"), kod, "açıklama") or {d: "" for d in DILLER}
        if u.get("grup"):
            u["varyant"] = uc_dil(t.get("varyant"), kod, "varyant") or {d: "" for d in DILLER}

        o = {"olcu": str(t.get("olcu", "")).strip(), "agirlik": str(t.get("agirlik", "")).strip()}
        for alan in ("dolgu", "kumas"):
            v = uc_dil(t.get(alan), kod, alan)
            if v:
                o[alan] = v
        sertlik = str(t.get("sertlik", "")).strip()
        if sertlik:
            if sertlik not in sertlikler:
                hata(f"{kod}: sertlik '{sertlik}' tanınmadı ({', '.join(sertlikler)})")
            o["sertlik"] = sertlikler.index(sertlik) + 1
        paket = uc_dil(t.get("paket"), kod, "paketleme")
        if paket:
            o["paket"] = paket
        u["ozellik"] = o

    eksik = [k for k in urunler if k not in gorulen]
    if eksik:
        print(f"  uyarı: tabloda olmayan ürünler değiştirilmedi: {', '.join(eksik)}")

    for s in tablo["fiyatlar"]:
        if s.get("kod") not in urunler:
            hata(f"fiyat listesindeki '{s.get('kod')}' kodlu ürün katalogda yok")
    fiyatlar = {"gecerlilik": str(tablo.get("gecerlilik", "")).strip(), "satirlar": tablo["fiyatlar"]}

    katalog_yolu.write_text(json.dumps(katalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (KAYNAK / "fiyatlar.json").write_text(json.dumps(fiyatlar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Tablodan: {len(gorulen)} ürün, {len(fiyatlar['satirlar'])} fiyat satırı")


if __name__ == "__main__":
    main()
