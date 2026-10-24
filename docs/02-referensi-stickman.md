# Riset & Analisis Referensi Stickman YouTube

> Dokumen ini dibuat **sebelum** gambar final diproduksi. Semua keputusan desain
> KAL di bawah ini punya rujukan, bukan tebakan.

---

## 1. Data kanal stickman yang terbukti besar

| Kanal | Subscriber | Format | Pelajaran |
|---|---|---|---|
| **Alan Becker** (`@alanbecker`) | ±34 juta | stick figure tanpa dialog, aksi & cerita | Karakter tanpa wajah bisa membuat orang peduli **jika gerak tubuh, timing, dan konfliknya jelas** |
| **CGP Grey** | ±6 juta | explainer, manusia digambar stick figure | Stickman **sebagai penyederhana** topik rumit; penonton menerima stickman untuk konten edukasi |
| **MinutePhysics** | ±5 juta | whiteboard + stick figure | Stick figure + narasi = format sains yang tahan lama; bahkan membuat video "cara menggambar stick figure" |
| **Hyun's Dojo** | ±1 juta | komunitas animasi fight | Bahasa visual stickman (silhouette, line of action) sudah mapan puluhan tahun |
| **Aniblague** | ±756 ribu | *"I tell stories through my stickman animations"* | Format **narator bercerita + stickman memerankan** |
| **Gray Animation** | ±586 ribu | cerita dengan stickman | idem |
| **Crazy Stickman** | ±555 ribu | cerita & rekonstruksi | idem |
| **CrimeTimes** | ±204 ribu | dokumenter kriminal dengan stick figure | **Niche dokumenter + stickman terbukti jalan** |

**Temuan kunci #1 — format yang persis cocok dengan KALDERA.**
Sejak 2024–2026 muncul gelombang kanal "stickman storytelling": *narator
membacakan cerita, stickman memerankan kejadiannya* — dokumenter kriminal,
peristiwa sejarah, cerita bertahan hidup, rekonstruksi. Ini bukan tren tebakan:
kanal sejenis sudah punya ratusan ribu sampai jutaan subscriber, dan sebagian
besar kontennya justru bertema **sejarah dan bencana**, bukan lelucon.
Artinya: **KALDERA = narasi dokumenter + stickman sebagai pemeran** adalah
format yang sudah divalidasi pasar, dan belum ada pemain besar di Bahasa
Indonesia untuk niche "sejarah Bumi".

**Temuan kunci #2 — stickman tanpa wajah tetap bisa emosional.**
Alan Becker tidak memakai dialog maupun ekspresi wajah detail; emosi dibawa oleh
**pose, timing, dan gerak**. Konsekuensi desain: KAL **tidak perlu** mata besar
atau mulut detail. Yang wajib adalah *pose yang terbaca* dan *aksesori pengenal*.

**Temuan kunci #3 — aksesori adalah identitas.**
Alan Becker membedakan 5 karakter yang bentuknya hampir sama hanya dengan
**warna**. Prinsip desain karakter menyebut hal yang sama: beri **satu ciri
khas** (topi, kacamata, kebiasaan) agar karakter langsung dikenali. Karena itu
KAL memakai **topi amber + syal rust** — dua blok warna yang masih terbaca
bahkan saat gambar diperkecil menjadi thumbnail 168×94 px.

**Temuan kunci #4 — silhouette test adalah hukum.**
Sumber tutorial animasi stick figure sepakat: pose harus terbaca walau diisi
hitam pekat; tangan/kaki **tidak boleh menempel ke tubuh**; aksi penting
digambar dari **samping**; beri **ruang negatif**. Semua pose KAL dirender
menghadap samping (3/4 → samping) dan lengannya dijauhkan dari torso.

**Temuan kunci #5 — latar harus tenang di tempat aksi.**
Pedoman *staging*: "keep the background quiet where the action happens."
Karena itu setiap gambar final diberi **halo kertas + bayangan kontak** di
belakang KAL, supaya siluetnya tidak tenggelam di ilustrasi yang detail.

**Temuan kunci #6 — 12 prinsip animasi dipakai harfiah.**
Yang diterapkan langsung ke rig KAL:
- *Anticipation* — sebelum berlari/terkejut ada gerakan kecil ke arah berlawanan.
- *Squash & stretch* — stick figure tidak bisa menebal, jadi "squash" dilakukan
  dengan menekuk lutut & memendekkan badan (pose `crouch`).
- *Follow through* — syal selalu bergerak 2–4 frame **setelah** badan berhenti.
- *Arcs* — lengan & syal memakai interpolasi bezier, bukan garis lurus.
- *Ease in/out* — semua transisi pose memakai easing, bukan linear.
- *Secondary action* — syal, kelopak mata berkedip, dan napas dada.
- *Exaggeration* — pose `shock` melampaui anatomi (tangan di atas kepala).
- *Staging* — satu ide per gambar; KAL tidak pernah menutupi objek utama.

---

## 2. Keputusan desain KAL (hasil riset, final)

| Aspek | Keputusan | Alasan dari riset |
|---|---|---|
| Proporsi | kepala ±1/4 tinggi badan (lebih besar dari manusia nyata) | *appeal* & keterbacaan di layar kecil |
| Ketebalan garis | tebal, sedikit gemetar (hand-inked) | meniru tinta; menghindari kesan vektor AI |
| Warna | hanya 2 blok: amber (topi) + rust (syal, tas) | *colour coding* ala Alan Becker |
| Wajah | 2 mata titik + garis mulut; tanpa hidung | Becker: emosi lewat gerak, bukan detail wajah |
| Arah | selalu **profil menyamping** | pose samping paling terbaca untuk stickman |
| Skala dalam frame | 10–25% tinggi layar | KAL adalah pengamat di dalam dunia, bukan maskot raksasa |
| Pergerakan wajib | syal & napas | penanda "hidup" saat gambar diam |
| Jumlah pose | 12 pose siap pakai | cukup untuk 12 menit narasi tanpa terasa berulang |

**Yang secara sadar ditolak:**
- Stickman gaya "storytime" murah (kepala besar, mulut besar, ekspresi lebay) —
  merusak nada dokumenter.
- Stickman bertarung (Hyun's Dojo) — tidak relevan untuk sejarah.
- Stickman putih garis tipis di latar hitam — tenggelam di palet kertas kami.
- Karakter manusia realistis di dalam ilustrasi — **dihapus seluruhnya**;
  semua figur dalam video adalah stickman.

---

## 3. Konsekuensi untuk 10 gambar

Aturan baru yang mengikat seluruh episode:

1. **Tidak ada manusia, wajah manusia, atau siluet tubuh realistis** di dalam
   gambar hasil generate. Kalau muncul, gambar dibuat ulang.
2. Setiap adegan yang butuh "orang" diisi **KAL** yang ditempel dari rig —
   jadi karakternya identik di 10 gambar, thumbnail, dan episode berikutnya.
3. Komposisi menyisakan **ruang kosong** (langit, tanah, air) untuk KAL.
4. KAL selalu lebih gelap daripada latar, dengan halo kertas tipis + bayangan
   kontak, supaya siluetnya lolos *silhouette test*.
5. Di 3 gambar yang murni lanskap (ledakan, aliran piroklastik, keruntuhan
   kaldera) KAL tetap hadir kecil di foreground sebagai skala manusia.

**Referensi silang ke file:**
- Rig & pose: `engine/stickman.py`
- Komposisi akhir + penempatan KAL: `tools/compose_art.py`
- Prompt gambar: `art/prompts.json`
