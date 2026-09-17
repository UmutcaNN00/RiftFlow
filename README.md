# ⚡ RiftFlow — League of Legends Intelligent Automation & Assistant

<p align="center">
  <img src="https://raw.githubusercontent.com/UmutcaNN00/RiftFlow/main/assets/banner.png" alt="RiftFlow Banner" width="700" onerror="this.style.display='none'"/>
</p>

<p align="center">
  <b>Akıllı, Hafif ve Güçlü League of Legends Yardımcısı & Otomasyon Aracı</b><br>
  <i>Built with PySide6, Python, and official LCU (League Client Update) REST Protocol</i>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Language-Python%203.11+-3776AB?logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/GUI-PySide6%20(Qt)-41CD52?logo=qt&logoColor=white" />
  <img src="https://img.shields.io/badge/Status-Stable%20v2.0-26B47C" />
  <img src="https://img.shields.io/badge/License-MIT-blue" />
</p>

---

## 🌟 Özellikler (Features)

- ⚡ **Otomatik Maç Kabul (Auto Accept):** Maç bulunduğunda anında veya belirlediğiniz gecikme (1-10 sn) süresinde maçı kabul eder.
- 🎯 **Akıllı Şampiyon Seçimi (Auto Pick):** Kendi sıranız gelmeden önce niyetinizi gösterir (hover). Sıranız geldiğinde şampiyonu anında kilitler. 1. tercihiniz alınmışsa otomatik olarak 2. veya 3. tercihinizi kilitler.
- 🚫 **Otomatik Yasaklama (Auto Ban):** Ban sırası aktif olduğu milisaniyede belirlediğiniz yasaklama tercihinizi kilitler.
- 🔄 **Otomatik Takas Kabul (Auto Swap):** Gelen rol/koridor, seçim sırası veya ARAM şampiyon takas isteklerini anında onaylar.
- 🎲 **ARAM Otomatik Zar (Auto Reroll):** ARAM modunda yedek hakkınız varsa otomatik zar atar.
- 🚀 **Düşük Donanım Modu (FPS Boost):** Oyuna girildiğinde istemciyi arka plana küçülterek oyun içi FPS artışı sağlar.
- 🔁 **Otomatik Yeniden Oyna & Onur Verme:** Oyun bittiğinde istatistikleri geçip lobiye döner ve takım arkadaşınıza otomatik onur verir.
- 💬 **Lobi Karşılama Mesajı:** Şampiyon seçimine girildiğinde belirlediğiniz rol veya selamlaşma mesajını otomatik gönderir.

---

## 🚀 Hızlı Başlangıç (Quick Start)

### 1. Hazır EXE Olarak Çalıştırma
1. [Releases](https://github.com/UmutcaNN00/RiftFlow/releases) sayfasından RiftFlow.zip dosyasını indirin.
2. ZIP dosyasını bir klasöre çıkartın.
3. RiftFlow.exe dosyasını çalıştırın.
4. League of Legends istemcisini açtığınızda RiftFlow otomatik olarak bağlanacaktır.

### 2. Kaynak Koddan Çalıştırma (Development)
`ash
# Depoyu klonlayın
git clone https://github.com/UmutcaNN00/RiftFlow.git
cd RiftFlow

# Sanal ortam oluşturun ve aktif edin
python -m venv .venv
.venv\Scripts\activate

# Gereksinimleri yükleyin
pip install PySide6 requests urllib3 psutil

# Uygulamayı başlatın
python main.py
`

---

## ⚙️ Yapılandırma (settings.json)

Ayarlar arayüz üzerinden değiştirildiğinde settings.json dosyasına otomatik olarak kaydedilir:

`json
{
    "auto_accept": true,
    "accept_delay": 1,
    "auto_pick": true,
    "auto_ban": true,
    "pick_preference_1": "Jhin",
    "ban_preference_1": "Seraphine",
    "pick_preference_2": "Kai'Sa",
    "ban_preference_2": "Caitlyn",
    "pick_preference_3": "Ashe",
    "ban_preference_3": "Viego",
    "auto_swap_accept": true,
    "auto_low_spec": true,
    "auto_play_again": true
}
`

---

## 🛡️ Güvenlik & LCU Protokolü

RiftFlow, Riot Games'in resmi istemci süreçleri tarafından sağlanan yerel HTTPS REST API (League Client Update) ile güvenli bir şekilde iletişim kurar. Bellek manipülasyonu (memory injection) veya oyun dosyalarına müdahale yapmaz.

---

## 📄 Lisans

Bu proje MIT Lisansı altında lisanslanmıştır.

