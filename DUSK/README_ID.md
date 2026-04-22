# DUSK - Dust Unification and Sweeping Keeper

## Dokumentasi Lengkap Proyek

DUSK adalah robot vacuum cleaner pintar yang dikendalikan oleh Raspberry Pi Zero 2W. Robot ini beroperasi dalam dua mode: mode otomatis dengan pola pembersihan zig-zag menggunakan navigasi berbasis giroskop dan encoder dengan penghindaran halangan, serta mode manual yang dapat dikendalikan melalui antarmuka web dengan streaming kamera langsung. Robot ini dilengkapi dengan tampilan mata animasi pada dua layar OLED, dua sikat penyapu yang berputar berlawanan arah, dan sistem vakum motor brushless.

---

## Daftar Isi

1. [Gambaran Umum Sistem](#1-gambaran-umum-sistem)
2. [Daftar Komponen](#2-daftar-komponen)
3. [Diagram Pengkabelan](#3-diagram-pengkabelan)
4. [Distribusi Daya](#4-distribusi-daya)
5. [Arsitektur Perangkat Lunak](#5-arsitektur-perangkat-lunak)
6. [Struktur File](#6-struktur-file)
7. [Deskripsi Modul](#7-deskripsi-modul)
8. [Library dan Dependensi](#8-library-dan-dependensi)
9. [Persiapan dan Instalasi](#9-persiapan-dan-instalasi)
10. [Menjalankan Robot](#10-menjalankan-robot)
11. [Panel Kontrol Web](#11-panel-kontrol-web)
12. [Mode Operasi](#12-mode-operasi)
13. [Kalibrasi](#13-kalibrasi)
14. [Pemecahan Masalah](#14-pemecahan-masalah)
15. [Perbedaan Versi (RPi.GPIO vs libgpiod)](#15-perbedaan-versi)
16. [Catatan Keselamatan](#16-catatan-keselamatan)

---

## 1. Gambaran Umum Sistem

DUSK adalah robot vakum berpenggerak diferensial dengan kemampuan berikut:

- Pola pembersihan zig-zag otomatis dengan koreksi lurus menggunakan kontrol PID
- Deteksi halangan menggunakan dua sensor Time-of-Flight yang dipasang pada sudut 30 derajat ke kiri dan kanan
- Kontrol heading melalui giroskop MPU6050 dengan pelacakan yaw terintegrasi
- Pengukuran jarak menggunakan speed encoder optik pada kedua roda penggerak
- Panel kontrol berbasis web yang dapat diakses dari perangkat apapun di jaringan yang sama
- Streaming kamera MJPEG langsung dari Raspberry Pi Camera V2
- Mata animasi berkedip yang ditampilkan pada dua layar OLED 1.3 inci
- Motor vakum brushless yang dikendalikan melalui ESC 20A
- Dua motor penyapu N20 yang berputar berlawanan arah untuk mengarahkan debu
- Pemantauan baterai secara real-time melalui sensor arus/tegangan INA219
- Semua perangkat I2C dialihkan melalui multiplexer TCA9548A menggunakan bus I2C virtual

Raspberry Pi Zero 2W menggunakan bus I2C software-bitbanged pada GPIO5 (SDA) dan GPIO6 (SCL) karena pin I2C hardware bawaan rusak. Hal ini dikonfigurasi melalui device tree overlay i2c-gpio.

---

## 2. Daftar Komponen

### Pemrosesan dan Komunikasi

| Komponen | Jumlah | Fungsi |
|:--|:--|:--|
| Raspberry Pi Zero 2W | 1 | Pengendali utama, web server, host kamera |
| Raspberry Pi Camera V2 | 1 | Feed video langsung untuk mode manual |

### Sensor

| Komponen | Jumlah | Antarmuka | Fungsi |
|:--|:--|:--|:--|
| MPU6050 | 1 | I2C (TCA Ch.0) | Giroskop dan akselerometer untuk kontrol heading |
| TOF-200C VL53L0X | 2 | I2C (TCA Ch.3, Ch.4) | Sensor jarak time-of-flight untuk deteksi halangan |
| INA219 | 1 | I2C (TCA Ch.5) | Pemantauan tegangan, arus, dan daya baterai |
| Speed Encoder (4-pin, optik) | 2 | GPIO digital | Penghitungan pulsa rotasi roda untuk jarak dan kecepatan |

### Aktuator

| Komponen | Jumlah | Driver | Fungsi |
|:--|:--|:--|:--|
| Motor DC Geared (roda) | 2 | L298N | Roda penggerak kiri dan kanan |
| Motor N20 Geared (penyapu) | 2 | L298N | Sikat penyapu depan berputar berlawanan |
| Motor Brushless 980kV (vakum) | 1 | ESC 20A | Kipas hisap vakum |

### Display

| Komponen | Jumlah | Antarmuka | Fungsi |
|:--|:--|:--|:--|
| OLED 1.3" I2C (SSD1306) | 2 | I2C (TCA Ch.1, Ch.2) | Tampilan mata animasi kiri dan kanan |

### Driver Motor dan ESC

| Komponen | Jumlah | Fungsi |
|:--|:--|:--|
| L298N Motor Driver | 1 | Menggerakkan kedua motor roda geared |
| L298N Motor Driver | 1 | Menggerakkan kedua motor penyapu N20 (satu channel) |
| ESC 20A | 1 | Mengendalikan motor vakum brushless via PWM |

### Manajemen Daya

| Komponen | Jumlah | Fungsi |
|:--|:--|:--|
| Baterai Li-Po 3S 12V | 1 | Sumber daya utama (11.1V nominal, 12.6V penuh) |
| BMS 3S 12V | 1 | Proteksi pengisian/pengosongan baterai |
| LM2596 DC-DC (output 3.3V) | 1 | Menyuplai daya sensor dan multiplexer |
| LM2596 DC-DC (output 5.1V) | 1 | Menyuplai daya Raspberry Pi dan display OLED |

### Komponen Pasif dan Interkoneksi

| Komponen | Jumlah | Fungsi |
|:--|:--|:--|
| TCA9548A I2C Multiplexer | 1 | Mengalihkan bus I2C ke 6 channel perangkat |
| Resistor 4.7k Ohm | 1 | Pull-up pin RST TCA9548A ke 3.3V |
| Resistor 4.7k Ohm | 2 | Pull-up resistor I2C SDA dan SCL (disarankan) |

---

## 3. Diagram Pengkabelan

### Catatan Penting

- Rail 3.3V dan 5V berasal dari dua buck converter LM2596, BUKAN dari Raspberry Pi.
- Semua pin GND komponen terhubung bersama ke jalur ground bersama.
- "Channel" mengacu pada sub-bus I2C pada TCA9548A multiplexer (contoh: Channel 0 berarti SDA0/SCL0 pada TCA9548A).
- Raspberry Pi menggunakan I2C Virtual pada GPIO5 (SDA) dan GPIO6 (SCL) karena pin I2C hardware (GPIO2/GPIO3) tidak berfungsi.

### Raspberry Pi Zero 2W

| Pin Pi | Koneksi |
|:--|:--|
| 5V | Rail 5.1V (dari LM2596) |
| GND | Jalur ground bersama |

### TCA9548A I2C Multiplexer

| Pin TCA9548A | Koneksi |
|:--|:--|
| VCC | Rail 3.3V |
| GND | Jalur ground bersama |
| SDA | Raspberry Pi GPIO5 (I2C Virtual SDA) |
| SCL | Raspberry Pi GPIO6 (I2C Virtual SCL) |
| RST | Rail 3.3V melalui resistor 4.7k Ohm |

### MPU6050 (Giroskop dan Akselerometer)

| Pin MPU6050 | Koneksi |
|:--|:--|
| VCC | Rail 3.3V |
| GND | Jalur ground bersama |
| SDA | TCA9548A Channel 0 SDA |
| SCL | TCA9548A Channel 0 SCL |
| Pin lainnya | Tidak digunakan |

### OLED 1.3" Mata Kiri

| Pin OLED | Koneksi |
|:--|:--|
| VCC | Rail 5V |
| GND | Jalur ground bersama |
| SDA | TCA9548A Channel 1 SDA |
| SCL | TCA9548A Channel 1 SCL |

### OLED 1.3" Mata Kanan

| Pin OLED | Koneksi |
|:--|:--|
| VCC | Rail 5V |
| GND | Jalur ground bersama |
| SDA | TCA9548A Channel 2 SDA |
| SCL | TCA9548A Channel 2 SCL |

### VL53L0X Kiri (30 derajat ke kiri)

| Pin VL53L0X | Koneksi |
|:--|:--|
| VCC | Rail 3.3V |
| GND | Jalur ground bersama |
| SDA | TCA9548A Channel 3 SDA |
| SCL | TCA9548A Channel 3 SCL |

### VL53L0X Kanan (30 derajat ke kanan)

| Pin VL53L0X | Koneksi |
|:--|:--|
| VCC | Rail 3.3V |
| GND | Jalur ground bersama |
| SDA | TCA9548A Channel 4 SDA |
| SCL | TCA9548A Channel 4 SCL |

### INA219 (Monitor Daya)

| Pin INA219 | Koneksi |
|:--|:--|
| VCC | Rail 3.3V |
| GND | Jalur ground bersama |
| SDA | TCA9548A Channel 5 SDA |
| SCL | TCA9548A Channel 5 SCL |
| VIN+ | Terminal positif baterai |
| VIN- | Input positif (IN+) LM2596 |

### Speed Encoder Kiri

| Pin Encoder | Koneksi |
|:--|:--|
| VCC | Rail 3.3V |
| GND | Jalur ground bersama |
| DO | Raspberry Pi GPIO14 |
| AO | Tidak digunakan |

### Speed Encoder Kanan

| Pin Encoder | Koneksi |
|:--|:--|
| VCC | Rail 3.3V |
| GND | Jalur ground bersama |
| DO | Raspberry Pi GPIO7 |
| AO | Tidak digunakan |

### L298N Motor Driver - Motor Roda Geared

| Pin L298N | Koneksi |
|:--|:--|
| ENA | Raspberry Pi GPIO10 (PWM - kecepatan motor kiri) |
| IN1 | Raspberry Pi GPIO12 (arah motor kiri) |
| IN2 | Raspberry Pi GPIO13 (arah motor kiri) |
| IN3 | Raspberry Pi GPIO19 (arah motor kanan) |
| IN4 | Raspberry Pi GPIO16 (arah motor kanan) |
| ENB | Raspberry Pi GPIO9 (PWM - kecepatan motor kanan) |
| 12V | Positif baterai (melalui BMS) |
| GND | Jalur ground bersama |
| OUT1/OUT2 | Terminal motor geared kiri |
| OUT3/OUT4 | Terminal motor geared kanan |

### L298N Motor Driver - Motor Penyapu N20

| Pin L298N | Koneksi |
|:--|:--|
| ENA | Raspberry Pi GPIO26 (PWM - kecepatan penyapu) |
| IN1 | Raspberry Pi GPIO24 (arah penyapu) |
| IN2 | Raspberry Pi GPIO25 (arah penyapu) |
| IN3 | Tidak digunakan |
| IN4 | Tidak digunakan |
| ENB | Tidak digunakan |
| OUT1/OUT2 | Kedua motor N20 (dikabel dengan polaritas berlawanan) |

Kedua motor penyapu N20 terhubung ke channel output L298N yang sama (OUT1 dan OUT2). Satu motor memiliki terminal yang dibalik relatif terhadap yang lain, menyebabkan keduanya berputar berlawanan arah. Ini menciptakan gerakan menyapu ke dalam yang mengarahkan debu menuju area hisap vakum.

### ESC 20A (Motor Vakum Brushless)

| Pin ESC | Koneksi |
|:--|:--|
| VCC Baterai | Terminal positif baterai |
| GND Baterai | Jalur ground bersama |
| Sinyal (Data) | Raspberry Pi GPIO18 |
| UBEC 5V | Tidak digunakan |
| UBEC GND | Jalur ground bersama |
| Kabel motor (3) | Motor brushless 980kV (3 fase) |

### BMS 3S 12V

| Pin BMS | Koneksi |
|:--|:--|
| 4.2V | Positif sel baterai 1 |
| 8.4V | Positif sel baterai 2 |
| 12.6V | Positif sel baterai 3 |
| GND | Negatif baterai |
| I/O Positif | Input LM2596 3.3V + Input LM2596 5.1V + Positif port pengisian |
| I/O Negatif | GND LM2596 3.3V + GND LM2596 5.1V + Negatif port pengisian |

---

## 4. Distribusi Daya

```
Baterai Li-Po 3S (maks 12.6V)
    |
    +-- BMS 3S (proteksi)
         |
         +-- ESC 20A --> Motor Brushless 980kV
         |
         +-- L298N #1 (input 12V) --> Motor Roda Geared
         |
         +-- L298N #2 (input 12V) --> Motor Penyapu N20
         |
         +-- INA219 (VIN+ / VIN-) --> pemantauan
         |
         +-- LM2596 #1 --> Rail 3.3V
         |    +-- TCA9548A
         |    +-- MPU6050
         |    +-- VL53L0X (x2)
         |    +-- INA219
         |    +-- Speed Encoder (x2)
         |
         +-- LM2596 #2 --> Rail 5.1V
              +-- Raspberry Pi Zero 2W
              +-- OLED 1.3" (x2)
```

---

## 5. Arsitektur Perangkat Lunak

Perangkat lunak diorganisir menjadi enam paket subsistem yang dikoordinasikan oleh pengendali utama:

- **config** - Semua definisi pin hardware, alamat I2C, assignment channel, parameter motor, konstanta navigasi, dan pengaturan sistem dipusatkan dalam satu file.

- **i2c_mux** - Driver TCA9548A yang thread-safe dengan pola context manager. Semua akses sensor dan display I2C melewati modul ini untuk menghindari konflik bus.

- **sensors** - Giroskop/akselerometer MPU6050 dengan pelacakan heading terintegrasi, pengukuran jarak time-of-flight VL53L0X (akses register langsung), pemantauan baterai INA219 dengan estimasi persentase, dan penghitungan pulsa speed encoder.

- **actuators** - Penggerak diferensial berbasis L298N untuk motor roda, kontrol motor penyapu N20, dan kontrol motor vakum brushless berbasis ESC melalui PWM pigpio.

- **display** - Sistem animasi mata OLED ganda yang berjalan di daemon thread. Setiap mata digambar menggunakan PIL (Pillow) dengan garis luar elips, iris, pupil, dan pantulan highlight. Kedipan periodik terjadi pada interval acak.

- **navigation** - Mesin state pola pembersihan zig-zag dengan koreksi lurus menggunakan PID. Menggunakan feedback jarak encoder untuk panjang jalur, heading giroskop untuk akurasi belokan, dan sensor ToF untuk penghindaran halangan.

- **web** - Server REST API berbasis Flask dengan streaming kamera MJPEG. Menyediakan pergantian mode, kontrol manual, kontrol vakum/penyapu, dan pemantauan status real-time.

---

## 6. Struktur File

```
DUSK/
|-- config.py                  Konstanta konfigurasi dan assignment pin
|-- i2c_mux.py                 Driver multiplexer I2C TCA9548A
|-- main.py                    Titik masuk utama dan orkestrator sistem
|-- requirements.txt           Dependensi paket Python
|-- setup.sh                   Skrip setup sistem (sekali pakai)
|
|-- sensors/
|   |-- __init__.py
|   |-- mpu6050.py             Giroskop dan akselerometer MPU6050
|   |-- vl53l0x.py             Sensor jarak time-of-flight VL53L0X
|   |-- ina219.py              Monitor arus dan tegangan INA219
|   |-- encoders.py            Penghitung pulsa speed encoder
|
|-- actuators/
|   |-- __init__.py
|   |-- motors.py              Pengontrol motor roda geared (L298N)
|   |-- sweeper.py             Pengontrol motor penyapu N20 (L298N)
|   |-- vacuum.py              Pengontrol motor vakum brushless (ESC)
|
|-- display/
|   |-- __init__.py
|   |-- oled_eyes.py           Tampilan mata animasi OLED ganda
|
|-- navigation/
|   |-- __init__.py
|   |-- zigzag.py              Pola pembersihan zig-zag dengan penghindaran halangan
|
|-- web/
    |-- __init__.py
    |-- server.py              Web server Flask dan REST API
    |-- camera.py              Streaming MJPEG Picamera2
    |-- templates/
    |   |-- index.html         Halaman panel kontrol web
    |-- static/
        |-- style.css          Styling antarmuka web
        |-- script.js          Logika sisi klien antarmuka web
```

Direktori `DUSK_libgpiod/` memiliki struktur identik dengan file yang dimodifikasi untuk versi libgpiod (lihat Bagian 15).

---

## 7. Deskripsi Modul

### config.py

Memusatkan semua nilai yang dapat dikonfigurasi. Tidak ada nomor pin atau alamat yang di-hardcode di tempat lain dalam kode. Bagian utama:

- Nomor bus I2C (3, untuk bus virtual) dan alamat TCA9548A (0x70)
- Pemetaan channel-ke-perangkat TCA9548A (channel 0 sampai 5)
- Semua nomor pin GPIO dalam penomoran BCM
- Frekuensi PWM motor (1000 Hz), kecepatan default, dan kecepatan maksimum
- Rentang lebar pulsa ESC (1000-2000 mikrodetik)
- Parameter navigasi: jarak lurus, jarak geser, ambang batas halangan
- Konstanta PID (Kp, Ki, Kd) untuk koreksi lurus
- Dimensi OLED (128x64) dan timing kedipan
- Ambang batas tegangan baterai untuk Li-Po 3S
- Host web server, port, resolusi kamera

### i2c_mux.py

Multiplexer TCA9548A memungkinkan beberapa perangkat I2C dengan alamat yang sama untuk hidup berdampingan. Driver ini menyediakan:

- `select_channel(n)` - Menulis byte pemilihan channel ke mux
- `channel(n)` - Context manager yang mengambil thread lock, memilih channel, mengembalikan instance SMBus, dan melepas lock saat selesai
- `scan_all()` - Memindai semua 8 channel dan melaporkan perangkat yang terdeteksi
- Pola singleton melalui `get_mux()` untuk akses global

### sensors/mpu6050.py

Berkomunikasi dengan MPU6050 di alamat 0x68 pada TCA9548A Channel 0. Fitur utama:

- Membaca semua 14 byte data sensor dalam satu burst read dari register 0x3B
- Menyediakan pembacaan akselerometer (g) dan giroskop (derajat/detik)
- Mengintegrasikan giroskop sumbu-Z seiring waktu untuk menghasilkan sudut heading (yaw)
- Filter dead-zone mengabaikan noise giroskop di bawah 0.5 derajat/detik
- Rutinitas kalibrasi merata-ratakan 200 sampel saat diam untuk mengukur bias giroskop

### sensors/vl53l0x.py

Implementasi akses register I2C langsung untuk sensor time-of-flight VL53L0X. Tidak diperlukan kompilasi library C eksternal. Setiap instance sensor terikat pada channel TCA9548A tertentu:

- Sensor kiri pada Channel 3 (dipasang 30 derajat ke kiri)
- Sensor kanan pada Channel 4 (dipasang 30 derajat ke kanan)
- Mode pengukuran single-shot dengan timeout 500ms
- Mengembalikan jarak dalam milimeter (rentang 0 sampai 8190 mm)
- Kelas `DualVL53L0X` menyediakan deteksi halangan gabungan untuk kedua sensor

### sensors/ina219.py

Memantau tegangan baterai (tegangan bus), arus yang ditarik, dan konsumsi daya melalui resistor shunt. Terhubung pada TCA9548A Channel 5.

- Dikonfigurasi untuk rentang bus 32V dan rentang shunt 320mV
- Nilai kalibrasi dihitung dari resistansi shunt (0.1 ohm) dan arus maksimum yang diharapkan (10A)
- Persentase baterai dihitung dengan interpolasi linear antara tegangan kritis (9.9V) dan tegangan penuh (12.6V)
- Pengecekan ambang batas baterai rendah dan baterai kritis

### sensors/encoders.py

Menghitung pulsa digital dari speed encoder optik yang dipasang pada roda penggerak. Encoder kiri pada GPIO14, encoder kanan pada GPIO7.

- Versi RPi.GPIO menggunakan `add_event_detect` dengan callback edge FALLING
- Versi libgpiod menggunakan `wait_edge_events` di thread khusus
- Menghitung jarak dari jumlah pulsa, keliling roda, dan pulsa per putaran
- Kecepatan dihitung sebagai delta jarak terhadap delta waktu

### actuators/motors.py

Mengendalikan dua motor DC geared melalui driver H-bridge L298N. Menyediakan kemampuan penggerak diferensial:

- `forward(speed)`, `backward(speed)` - Kedua motor arah sama
- `turn_left(speed)`, `turn_right(speed)` - Satu motor aktif, satu berhenti
- `spin_left(speed)`, `spin_right(speed)` - Motor berlawanan arah (rotasi di tempat)
- `differential_drive(left, right)` - Kecepatan dan arah independen per motor
- PWM pada pin ENA/ENB pada 1000 Hz untuk kontrol kecepatan

### actuators/sweeper.py

Mengendalikan dua motor N20 geared yang terhubung ke satu channel output L298N dengan kabel polaritas terbalik. Ketika IN1 HIGH dan IN2 LOW, satu motor berputar searah jarum jam dan yang lain berlawanan jarum jam, menyapu debu ke dalam.

### actuators/vacuum.py

Mengendalikan motor brushless 980kV melalui ESC 20A menggunakan pigpio untuk timing PWM presisi pada GPIO18.

- Komunikasi ESC menggunakan lebar pulsa gaya servo: 1000 mikrodetik (mati) sampai 2000 mikrodetik (throttle penuh)
- Urutan arming mengirim throttle minimum selama 3 detik
- Kontrol kecepatan memetakan 0-100 persen ke rentang 1150-2000 mikrodetik
- Termasuk rutinitas kalibrasi ESC untuk mengatur endpoint throttle

### display/oled_eyes.py

Mengelola dua display OLED SSD1306 1.3 inci yang menampilkan mata animasi. Setiap display diakses melalui wrapper `MuxedSerial` kustom yang mengalihkan channel TCA9548A sebelum setiap transaksi I2C.

Anatomi mata (digambar dengan PIL/Pillow):
- Elips luar (mengisi sebagian besar layar 128x64)
- Lingkaran iris putih (radius 20 piksel)
- Lingkaran pupil hitam (radius 10 piksel)
- Lingkaran highlight putih kecil (offset untuk efek pantulan)

Animasi kedipan:
- Interval acak antara 3 dan 7 detik
- Animasi menutup 4 langkah diikuti animasi membuka 4 langkah
- 20% kemungkinan kedipan ganda
- Berjalan di daemon thread agar tidak memblokir operasi lain

### navigation/zigzag.py

Mengimplementasikan pola pembersihan otomatis sebagai mesin state:

1. DRIVE_STRAIGHT - Bergerak maju sejauh jarak yang dikonfigurasi (default 1000mm), menggunakan koreksi PID dari error heading giroskop yang diterapkan sebagai kecepatan motor diferensial
2. TURN_FIRST - Berputar 90 derajat menggunakan feedback giroskop, dengan pengurangan kecepatan saat mendekati sudut target
3. SHIFT_FORWARD - Maju sejauh lebar robot (default 250mm) untuk pindah ke jalur berikutnya
4. TURN_SECOND - Berputar 90 derajat lagi ke arah yang sama
5. Kembali ke langkah 1 dengan arah belokan bergantian

Penghindaran halangan: Ketika sensor ToF mendeteksi objek dalam jarak 150mm, robot berhenti, mundur sebentar, berbelok menjauhi halangan, dan melanjutkan pola.

### web/server.py

Aplikasi Flask yang menyediakan:

- `GET /` - Menyajikan halaman panel kontrol HTML
- `GET /video_feed` - Stream kamera MJPEG
- `POST /api/mode` - Beralih antara "auto" dan "manual"
- `POST /api/control` - Perintah manual (forward, backward, left, right, stop)
- `POST /api/vacuum` - Mulai, berhenti, atau atur kecepatan vakum
- `POST /api/sweeper` - Mulai, berhenti, atau toggle motor penyapu
- `GET /api/status` - Respons JSON dengan semua data sensor, status baterai, state navigasi

### web/camera.py

Menangkap frame dari Raspberry Pi Camera V2 menggunakan Picamera2, mengonversinya ke JPEG, dan menyediakan fungsi generator untuk streaming MJPEG. Penangkapan frame berjalan di thread khusus. Kamera dimulai saat memasuki mode manual dan dihentikan di mode otomatis untuk menghemat sumber daya CPU.

---

## 8. Library dan Dependensi

### Paket Python (versi RPi.GPIO)

| Paket | Versi | Tujuan |
|:--|:--|:--|
| flask | >= 3.0 | Framework web server |
| smbus2 | >= 0.4 | Komunikasi I2C |
| luma.oled | >= 3.12 | Driver display OLED (SSD1306) |
| luma.core | >= 2.4 | Abstraksi display inti |
| Pillow | >= 10.0 | Penggambaran gambar untuk OLED |
| pigpio | >= 1.78 | PWM presisi untuk kontrol ESC |
| RPi.GPIO | >= 0.7 | Input/output GPIO dan interrupt |
| picamera2 | >= 0.3 | Antarmuka kamera Raspberry Pi |
| numpy | >= 1.24 | Operasi numerik |

### Paket Python (versi libgpiod)

Sama seperti di atas, kecuali `RPi.GPIO` diganti dengan:

| Paket | Versi | Tujuan |
|:--|:--|:--|
| gpiod | >= 2.1 | Antarmuka character device GPIO level rendah |

### Paket Sistem

| Paket | Tujuan |
|:--|:--|
| i2c-tools | Pemindaian dan debugging bus I2C |
| pigpio | Library C pigpio dan daemon |
| python3-pigpio | Binding Python pigpio |
| python3-libcamera | Stack kamera (dibutuhkan oleh picamera2) |
| python3-picamera2 | Paket sistem Picamera2 |
| libgpiod-dev | Header pengembangan libgpiod (hanya versi libgpiod) |

---

## 9. Persiapan dan Instalasi

### Prasyarat

- Raspberry Pi Zero 2W dengan Raspberry Pi OS (Bookworm atau lebih baru)
- Semua komponen hardware telah dirakit dan dikabel sesuai Bagian 3
- Konektivitas jaringan (Wi-Fi telah dikonfigurasi)
- Akses SSH telah diaktifkan

### Langkah 1: Transfer File

Dari komputer pengembangan Anda:

```bash
scp -r DUSK/ pi@<IP_RASPBERRY_PI>:~/DUSK/
```

Untuk versi libgpiod:

```bash
scp -r DUSK_libgpiod/ pi@<IP_RASPBERRY_PI>:~/DUSK/
```

### Langkah 2: Jalankan Skrip Setup

```bash
ssh pi@<IP_RASPBERRY_PI>
cd ~/DUSK
chmod +x setup.sh
sudo ./setup.sh
```

Skrip setup melakukan hal-hal berikut:

1. Memperbarui paket sistem
2. Menginstal semua dependensi sistem
3. Mengaktifkan antarmuka I2C dan Kamera melalui raspi-config
4. Menambahkan overlay I2C virtual ke /boot/config.txt (GPIO5 SDA, GPIO6 SCL, bus 3)
5. Menambahkan overlay PWM hardware untuk GPIO18
6. Mengaktifkan dan memulai service pigpiod systemd
7. Membuat virtual environment Python dengan semua paket pip
8. Menambahkan pengguna saat ini ke grup i2c, gpio, dan video
9. Membuat file service systemd opsional untuk auto-start

### Langkah 3: Reboot

```bash
sudo reboot
```

Reboot wajib dilakukan agar device tree overlay (I2C virtual dan PWM) berlaku.

### Langkah 4: Verifikasi Hardware

Setelah reboot:

```bash
# Verifikasi bus I2C virtual ada
ls /dev/i2c*
# Output yang diharapkan mencakup: /dev/i2c-3

# Scan untuk multiplexer TCA9548A
sudo i2cdetect -y 3
# Harus menampilkan alamat 0x70

# Verifikasi pigpiod berjalan
systemctl status pigpiod
```

---

## 10. Menjalankan Robot

### Start Manual

```bash
cd ~/DUSK
source venv/bin/activate
sudo python3 main.py
```

Urutan inisialisasi akan mencetak status setiap subsistem. Setelah semua sistem melaporkan OK, panel web dapat diakses.

### Service Systemd (Background / Auto-start)

```bash
# Aktifkan auto-start saat boot
sudo systemctl enable dusk

# Kontrol service manual
sudo systemctl start dusk
sudo systemctl stop dusk
sudo systemctl restart dusk

# Lihat log secara langsung
sudo journalctl -u dusk -f
```

### Shutdown

Tekan Ctrl+C atau kirim SIGTERM. Urutan shutdown akan:

1. Menghentikan navigasi zig-zag
2. Menghentikan semua motor (roda, penyapu, vakum)
3. Menghentikan stream kamera
4. Memainkan animasi mata OLED menutup
5. Melepaskan semua sumber daya GPIO
6. Menutup bus I2C

---

## 11. Panel Kontrol Web

Akses panel kontrol di:

```
http://<IP_RASPBERRY_PI>:5000
```

### Elemen Antarmuka

- **Saklar Mode** - Beralih antara mode Manual dan Otomatis
- **Kamera Langsung** - Feed video MJPEG (aktif hanya di mode manual)
- **Kontrol D-Pad** - Tombol arah untuk maju, mundur, kiri, kanan, dan berhenti
- **Dukungan Keyboard** - Tombol panah atau W/A/S/D untuk mengemudi (mode manual)
- **Tampilan Baterai** - Tegangan, arus, dan persentase dengan indikator visual
- **Slider Vakum** - Atur kecepatan motor vakum dari 0% hingga 100%
- **Toggle Penyapu** - Aktifkan atau nonaktifkan motor penyapu
- **Panel Sensor** - Jarak ToF kiri/kanan, heading, state navigasi, kecepatan roda

Panel status diperbarui setiap 500 milidetik melalui polling.

---

## 12. Mode Operasi

### Mode Otomatis

Ketika dialihkan ke mode otomatis:

1. Motor penyapu mulai pada kecepatan default (70%)
2. Motor vakum mulai pada kecepatan default (50%)
3. Navigasi zig-zag dimulai
4. Stream kamera dimatikan untuk menghemat CPU

Robot bergerak dalam garis lurus, membuat belokan 90 derajat di setiap ujung, bergeser sejauh satu lebar robot, dan membalik arah. Pengontrol PID menggunakan error heading giroskop untuk menerapkan koreksi kecepatan motor diferensial, menjaga robot tetap pada jalur lurus.

Jika sensor ToF mendeteksi halangan dalam jarak 150mm, robot berhenti, mundur 500ms, berbelok menjauhi halangan, dan melanjutkan pola pembersihan.

### Mode Manual

Ketika dialihkan ke mode manual:

1. Navigasi berhenti dan motor mati
2. Stream kamera diaktifkan
3. Kontrol D-pad web dan keyboard menjadi aktif
4. Vakum dan penyapu dapat dikontrol secara independen melalui panel web

Perintah gerakan dikirim sebagai request POST. Menekan tombol arah mengirim perintah; melepasnya mengirim perintah berhenti. Ini memberikan kontrol yang responsif dan langsung.

---

## 13. Kalibrasi

### Kalibrasi Giroskop

Kalibrasi giroskop berjalan secara otomatis saat startup. Robot harus diam selama sekitar 1 detik sementara 100 sampel giroskop dirata-ratakan untuk menentukan offset bias. Jika robot digerakkan selama fase ini, pengukuran heading akan tidak akurat.

### Kalibrasi ESC

Jika ESC belum pernah dikalibrasi sebelumnya:

```python
from actuators.vacuum import VacuumMotor
motor = VacuumMotor()
motor.calibrate()
```

Ikuti petunjuk interaktif untuk mengatur endpoint throttle. Ini hanya perlu dilakukan sekali per ESC.

### Pulsa Per Putaran Encoder

Nilai default adalah 20 pulsa per putaran. Jika piringan encoder Anda memiliki jumlah slot yang berbeda, perbarui `ENCODER_PULSES_PER_REV` di config.py. Anda dapat memverifikasi dengan memutar roda satu putaran penuh secara manual dan memeriksa jumlah pulsa.

### Diameter Roda

Diameter roda default adalah 65mm (keliling 204.2mm). Ukur roda aktual Anda dan perbarui `WHEEL_DIAMETER_MM` dan `WHEEL_CIRCUMFERENCE_MM` di config.py untuk perhitungan jarak yang akurat.

---

## 14. Pemecahan Masalah

| Gejala | Kemungkinan Penyebab | Solusi |
|:--|:--|:--|
| `/dev/i2c-3` tidak ada | Overlay I2C virtual tidak dimuat | Periksa `/boot/config.txt` untuk `dtoverlay=i2c-gpio,i2c_gpio_sda=5,i2c_gpio_scl=6,bus=3`, reboot |
| `i2cdetect` tidak menampilkan perangkat di 0x70 | Masalah kabel TCA9548A | Verifikasi koneksi SDA/SCL ke GPIO5/6, periksa daya 3.3V, periksa pull-up resistor |
| Error WHO_AM_I MPU6050 | MPU6050 tidak mendapat daya atau channel salah | Verifikasi 3.3V ke MPU6050, verifikasi kabel TCA Channel 0 |
| VL53L0X mengembalikan 8190mm | Sensor tidak terinisialisasi atau di luar jangkauan | Periksa daya 3.3V, verifikasi kabel TCA Channel 3/4 |
| OLED tidak menampilkan apa-apa | Driver atau alamat salah | Verifikasi tipe kontroler SSD1306, coba alamat 0x3D jika 0x3C gagal |
| Motor tidak berputar | L298N tidak mendapat daya atau ENA/ENB tidak terhubung | Verifikasi 12V ke L298N, verifikasi koneksi GPIO ENA/ENB |
| ESC berbunyi terus-menerus | ESC tidak di-arm atau tidak dikalibrasi | Jalankan urutan arming, atau lakukan kalibrasi ESC penuh |
| Error kamera | libcamera tidak terinstal | Jalankan `libcamera-hello` untuk tes, instal python3-picamera2 |
| Panel web tidak dapat diakses | Firewall memblokir port 5000 | Jalankan `sudo ufw allow 5000` atau nonaktifkan firewall |
| Error koneksi pigpio | pigpiod tidak berjalan | Jalankan `sudo pigpiod` atau `sudo systemctl start pigpiod` |
| Robot menyimpang saat lurus | Giroskop tidak terkalibrasi | Pastikan robot diam saat kalibrasi startup |
| Robot berbelok lebih/kurang dari 90 derajat | Toleransi belokan terlalu tinggi/rendah | Sesuaikan `TURN_TOLERANCE` di config.py |

---

## 15. Perbedaan Versi

Dua versi kode disediakan:

### DUSK/ (RPi.GPIO + pigpio)

- Menggunakan RPi.GPIO untuk input/output digital dan penghitungan encoder berbasis interrupt
- Menggunakan PWM RPi.GPIO untuk pin enable motor (ENA, ENB)
- Menggunakan pigpio secara eksklusif untuk PWM ESC (GPIO18)
- Membutuhkan paket pip `RPi.GPIO`

### DUSK_libgpiod/ (libgpiod + pigpio)

- Menggunakan antarmuka character device GPIO kernel Linux melalui library Python gpiod
- Penghitungan pulsa encoder menggunakan `gpiod.request_lines()` dengan deteksi `Edge.FALLING` dan `wait_edge_events()` di thread khusus
- Pin arah motor dan penyapu menggunakan `gpiod.request_lines()` dengan `Direction.OUTPUT`
- PWM motor (ENA, ENB, ENA penyapu) menggunakan pigpio `set_PWM_dutycycle()` karena libgpiod tidak mendukung PWM
- PWM ESC tetap menggunakan pigpio `set_servo_pulsewidth()`
- Tidak ada panggilan `GPIO.setmode()` atau `GPIO.cleanup()`; gpiod menangani pembersihan sumber daya melalui `request.release()`
- Membutuhkan paket pip `gpiod>=2.1` dan paket sistem `libgpiod-dev`
- Path GPIO chip dikonfigurasi sebagai `/dev/gpiochip0` di config.py

Versi libgpiod adalah pendekatan yang disarankan untuk versi Raspberry Pi OS yang lebih baru, karena RPi.GPIO tidak lagi dikembangkan dan digantikan oleh antarmuka character device.

### File yang Dimodifikasi di Versi libgpiod

| File | Perubahan |
|:--|:--|
| config.py | Ditambahkan `GPIO_CHIP = "/dev/gpiochip0"` |
| sensors/encoders.py | Mengganti interrupt RPi.GPIO dengan event edge gpiod |
| actuators/motors.py | Pin arah via gpiod, PWM via pigpio |
| actuators/sweeper.py | Pin arah via gpiod, PWM via pigpio |
| main.py | Menghapus import RPi.GPIO dan GPIO.cleanup() |
| requirements.txt | Mengganti RPi.GPIO dengan gpiod |
| setup.sh | Menambahkan paket libgpiod-dev dan python3-libgpiod |

---

## 16. Catatan Keselamatan

- Selalu pastikan baling-baling atau kipas vakum motor brushless terpasang dengan aman sebelum menjalankan motor vakum. Bagian yang lepas pada RPM tinggi sangat berbahaya.
- Jangan pernah menghubungkan output UBEC 5V ESC ke Raspberry Pi bersamaan dengan suplai LM2596 5.1V. Hal ini dapat menyebabkan konflik tegangan dan merusak Pi.
- Baterai Li-Po harus diisi dan dikosongkan melalui BMS. Jangan pernah melewati BMS.
- Ketika sistem melaporkan level baterai kritis (di bawah 9.9V untuk 3S), robot akan memulai shutdown darurat. Jangan terus mengoperasikan di bawah tegangan ini.
- Putuskan koneksi baterai sebelum melakukan perubahan pengkabelan.
- Driver motor L298N dan motor brushless dapat menarik arus yang signifikan. Pastikan semua kabel daya menggunakan konduktor dengan rating yang memadai.
- Rail 3.3V dan 5V harus berasal dari regulator LM2596, bukan dari pin 3.3V/5V Raspberry Pi sendiri. Pi tidak dapat menyuplai arus yang cukup untuk semua perangkat yang terhubung.
