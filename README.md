# Lao Lottery API (หวยลาว)

Scrape ข้อมูลผลหวยลาวจาก [lotto.thaiorc.com](https://lotto.thaiorc.com/lao/lottery.php) แล้วเสิร์ฟเป็น JSON API ผ่าน GitHub Pages

## API Endpoints

เมื่อ deploy แล้ว จะได้ endpoint ดังนี้:

| Endpoint | รายละเอียด |
|----------|-----------|
| `/index.json` | รายการ endpoint ทั้งหมด |
| `/latest.json` | ผลหวยลาวล่าสุด |
| `/results.json` | ผลหวยลาวย้อนหลังทั้งหมด |
| `/year/{yyyy}.json` | ผลหวยลาวตามปี (ค.ศ.) |
| `/stats/last3.json` | สถิติเลข 3 ตัว (10 ปีย้อนหลัง) |
| `/stats/last2.json` | สถิติเลข 2 ตัว (10 ปีย้อนหลัง) |

### สถิติเลข 3 ตัว & 2 ตัว ประกอบด้วย

- **digit_position_stats** - แยกตามหลัก (หลักร้อย/สิบ/หน่วย) ว่าเลข 0-9 ออกกี่ครั้ง
- **frequency_distribution** - แบ่งตามจำนวนครั้งที่ออก เช่น เลขไหนออก 5 ครั้ง, 4 ครั้ง, ...
- **never_drawn** - เลขที่ยังไม่เคยออกเลย

## ตัวอย่าง Response

### ผลหวยล่าสุด (`/latest.json`)

```json
{
  "status": "ok",
  "updated_at": "2026-02-07T12:00:00Z",
  "data": {
    "date": "2026-02-06",
    "date_thai": "06/02/2569",
    "numbers": {
      "last4": "7430",
      "last3": "430",
      "last2": "30"
    }
  }
}
```

### สถิติเลข 3 ตัว (`/stats/last3.json`)

```json
{
  "status": "ok",
  "period": "10 ปีย้อนหลัง",
  "data": {
    "digit_position_stats": {
      "0": { "hundreds": 87, "tens": 100, "units": 79, "total": 266 },
      "1": { "hundreds": 78, "tens": 74, "units": 91, "total": 243 }
    },
    "frequency_distribution": {
      "5": ["138", "480"],
      "4": ["339", "459", "541", "575", "605", "667", "811"]
    },
    "never_drawn": ["000", "004", "008", "..."],
    "never_drawn_count": 436
  }
}
```

## วิธีใช้งาน

### 1. รันบนเครื่อง (Local)

```bash
pip install -r requirements.txt
python scrape.py
```

ไฟล์ JSON จะถูกสร้างในโฟลเดอร์ `api/`

### 2. Deploy บน GitHub

1. สร้าง GitHub repository ใหม่
2. Push โค้ดนี้ขึ้นไป
3. ไปที่ Settings > Pages > เลือก Source เป็น "GitHub Actions"
4. GitHub Actions จะรัน scraper ทุก 6 ชั่วโมง และ deploy ผลลัพธ์เป็น API

```bash
git init
git add .
git commit -m "init: lao lottery scraper"
git remote add origin https://github.com/<username>/thaiorc.git
git branch -M main
git push -u origin main
```

### 3. เรียกใช้ API

```bash
curl https://<username>.github.io/thaiorc/latest.json
```

## GitHub Actions

- **Schedule**: รันทุก 6 ชั่วโมง (`0 */6 * * *`)
- **Manual**: สามารถกด "Run workflow" ได้จาก Actions tab
- **Auto deploy**: ผลลัพธ์ถูก deploy เป็น GitHub Pages โดยอัตโนมัติ

## แหล่งข้อมูล

ข้อมูลถูก scrape จาก [lotto.thaiorc.com](https://lotto.thaiorc.com/lao/lottery.php)
