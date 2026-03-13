# Pain Miner — AI Problem Hunter 🔍

İnsanların problemlerini Reddit, Hacker News ve Product Hunt'tan kazıyan, AI ile analiz eden ve uygulama fikirleri üreten bir araç.

## Özellikler

- **Multi-Platform Scraping**: Reddit, Hacker News, Product Hunt
- **AI Analiz**: Gemini 2.5 Flash Lite ile problem tespiti ve skorlama
- **Uygulama Fikri Üretimi**: Her problem için webapp/mobil uygulama önerisi
- **Fırsat Skorlama**: Relevance, pain, implementability, market size bazlı skorlama
- **Periyodik Çalışma**: Belirli aralıklarla otomatik tarama

## Kurulum

```bash
# Klonla
git clone <repo-url> pain-miner
cd pain-miner

# Virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Bağımlılıklar
pip install -r requirements.txt

# Ortam değişkenleri
cp .env.template .env
# .env dosyasını düzenle: GEMINI_API_KEY, opsiyonel Reddit credentials
```

## Kullanım

```bash
# Veritabanını oluştur
python main.py init

# Tüm platformları tara + AI analiz
python main.py scrape

# Sadece Hacker News (API key gerekmez)
python main.py scrape --platform hackernews

# Sadece tarama, AI analiz yok
python main.py scrape --no-analysis

# Limit
python main.py scrape --platform hackernews --limit 10

# İstatistikler
python main.py stats

# En iyi problemler
python main.py top

# Uygulama fikirleri
python main.py ideas
```

## Pipeline

```
Reddit / HN / PH
       ↓
   Scraping
       ↓
  Pre-filter (Gemini)
       ↓
 Deep Analysis (Gemini)
       ↓
App Idea Generation (Gemini)
       ↓
  SQLite DB → Dashboard
```

## Yapı

```
pain-miner/
├── config/          # Konfigürasyon
├── db/              # Veritabanı katmanı
├── scrapers/        # Platform scraper'ları
├── analysis/        # AI analiz pipeline
│   └── prompts/     # Prompt şablonları
├── scheduler/       # Pipeline yönetici
├── utils/           # Yardımcı fonksiyonlar
└── main.py          # CLI giriş noktası
```

## Lisans

MIT
