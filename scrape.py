#!/usr/bin/env python3
"""
Scrape Lao Lottery results from lotto.thaiorc.com
and output as JSON API data.
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://lotto.thaiorc.com"
LAO_LOTTERY_URL = f"{BASE_URL}/lao/lottery.php"
LAO_STATS_LAST3_URL = f"{BASE_URL}/lao/last3/stats-years10.php"
LAO_STATS_LAST2_URL = f"{BASE_URL}/lao/last2/stats-years10.php"

# Thai month names to month numbers
THAI_MONTHS = {
    "มกราคม": 1, "กุมภาพันธ์": 2, "มีนาคม": 3, "เมษายน": 4,
    "พฤษภาคม": 5, "มิถุนายน": 6, "กรกฎาคม": 7, "สิงหาคม": 8,
    "กันยายน": 9, "ตุลาคม": 10, "พฤศจิกายน": 11, "ธันวาคม": 12,
}


def fetch_page(url: str) -> BeautifulSoup:
    """Fetch a page and return a BeautifulSoup object."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "th,en;q=0.9",
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.encoding = "tis-620"  # Thai encoding (windows-874 compatible)
    return BeautifulSoup(response.text, "html.parser")


def parse_thai_date(date_str: str) -> str:
    """
    Convert Thai Buddhist date dd/mm/yyyy (BE) to ISO date yyyy-mm-dd (CE).
    Example: 06/02/2569 -> 2026-02-06
    """
    parts = date_str.strip().split("/")
    if len(parts) != 3:
        return date_str
    day, month, year_be = int(parts[0]), int(parts[1]), int(parts[2])
    year_ce = year_be - 543
    return f"{year_ce:04d}-{month:02d}-{day:02d}"


def scrape_lottery_results() -> List[Dict]:
    """Scrape the main lottery results page."""
    soup = fetch_page(LAO_LOTTERY_URL)
    results = []

    # Find all table rows that contain lottery data
    # The data is in <tr> elements with <td class="...stats-title...">
    rows = soup.find_all("tr")

    for row in rows:
        cells = row.find_all("td")
        if len(cells) != 4:
            continue

        # Check if this row has the stats-title class (data row)
        first_cell = cells[0]
        if "stats-title" not in first_cell.get("class", []):
            continue

        # Skip header rows (stats-title3)
        if "stats-title3" in first_cell.get("class", []):
            continue

        # Extract date from the link
        link = first_cell.find("a")
        if not link:
            continue

        date_thai = link.get_text(strip=True)
        date_iso = parse_thai_date(date_thai)

        # Extract numbers
        num4 = cells[1].get_text(strip=True)
        num3 = cells[2].get_text(strip=True)
        num2 = cells[3].get_text(strip=True)

        # Extract contentID for detail link
        href = link.get("href", "")
        content_id_match = re.search(r"contentID=(\d+)", href)
        content_id = content_id_match.group(1) if content_id_match else None

        results.append({
            "date": date_iso,
            "date_thai": date_thai,
            "numbers": {
                "last4": num4,
                "last3": num3,
                "last2": num2,
            },
            "detail_url": f"{BASE_URL}/lao/jackpot.php?contentID={content_id}" if content_id else None,
        })

    return results


def scrape_digit_position_stats(soup, num_digits: int) -> Dict:
    """
    Parse the 'แยกตามหลัก' (digit position) statistics table.
    For 3-digit: หลักร้อย, หลักสิบ, หลักหน่วย
    For 2-digit: หลักสิบ, หลักหน่วย
    """
    digit_stats = {}

    # Find rows with stats-number class (เลข 0 - เลข 9)
    stats_number_fonts = soup.find_all("font", class_="stats-number")

    for font_tag in stats_number_fonts:
        label = font_tag.get_text(strip=True)  # e.g. "เลข 0"
        digit_match = re.search(r"(\d)", label)
        if not digit_match:
            continue

        digit = digit_match.group(1)
        # Navigate to parent row and get all rate values
        row = font_tag.find_parent("tr")
        if not row:
            continue

        rate_fonts = row.find_all("font", class_=re.compile(r"stats-rate\d"))
        values = [int(f.get_text(strip=True)) for f in rate_fonts]

        if num_digits == 3 and len(values) == 4:
            digit_stats[digit] = {
                "hundreds": values[0],
                "tens": values[1],
                "units": values[2],
                "total": values[3],
            }
        elif num_digits == 2 and len(values) == 3:
            digit_stats[digit] = {
                "tens": values[0],
                "units": values[1],
                "total": values[2],
            }

    return digit_stats


def scrape_frequency_distribution(soup) -> Dict[str, List[str]]:
    """
    Parse the 'แบ่งตามจำนวนครั้งที่ออก' (frequency distribution) table.
    Returns dict of frequency -> list of numbers.
    """
    frequency = {}

    # Find the header td with exact text "จำนวนครั้ง"
    header_td = None
    for td in soup.find_all("td"):
        if td.get_text(strip=True) == "จำนวนครั้ง":
            header_td = td
            break

    if not header_td:
        return frequency

    freq_table = header_td.find_parent("table")
    if not freq_table:
        return frequency

    rows = freq_table.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) != 2:
            continue

        # First cell is frequency count, second cell has numbers
        freq_text = cells[0].get_text(strip=True)
        if not freq_text.isdigit():
            continue

        freq_count = freq_text
        # Extract numbers from font tags in the second cell
        number_fonts = cells[1].find_all("font")
        numbers = [f.get_text(strip=True) for f in number_fonts if f.get_text(strip=True)]

        if numbers:
            frequency[freq_count] = numbers

    return frequency


def scrape_never_drawn(soup, num_digits: int) -> List[str]:
    """
    Parse the 'เลขที่ยังไม่ออก' (numbers never drawn) section.
    """
    never_drawn = []

    # Find the div that contains never-drawn numbers
    div_id = f"statslast{num_digits}All"
    container = soup.find("div", id=div_id)
    if not container:
        return never_drawn

    # Extract numbers from font tags
    number_fonts = container.find_all("font")
    never_drawn = [f.get_text(strip=True) for f in number_fonts if f.get_text(strip=True)]

    return never_drawn


def scrape_stats_last3() -> Dict:
    """Scrape 3-digit statistics from stats-years10 page."""
    print("Scraping 3-digit stats (เลข 3 ตัว)...")
    soup = fetch_page(LAO_STATS_LAST3_URL)

    # Extract total draws count
    meta_desc = soup.find("meta", attrs={"name": "description"})
    description = meta_desc["content"] if meta_desc else ""

    digit_stats = scrape_digit_position_stats(soup, 3)
    frequency = scrape_frequency_distribution(soup)
    never_drawn = scrape_never_drawn(soup, 3)

    return {
        "description": description,
        "digit_position_stats": digit_stats,
        "frequency_distribution": frequency,
        "never_drawn": never_drawn,
        "never_drawn_count": len(never_drawn),
    }


def scrape_stats_last2() -> Dict:
    """Scrape 2-digit statistics from stats-years10 page."""
    print("Scraping 2-digit stats (เลข 2 ตัว)...")
    soup = fetch_page(LAO_STATS_LAST2_URL)

    # Extract total draws count
    meta_desc = soup.find("meta", attrs={"name": "description"})
    description = meta_desc["content"] if meta_desc else ""

    digit_stats = scrape_digit_position_stats(soup, 2)
    frequency = scrape_frequency_distribution(soup)
    never_drawn = scrape_never_drawn(soup, 2)

    return {
        "description": description,
        "digit_position_stats": digit_stats,
        "frequency_distribution": frequency,
        "never_drawn": never_drawn,
        "never_drawn_count": len(never_drawn),
    }


def scrape_stats_by_date(num_digits: int) -> Dict[str, Dict]:
    """
    Scrape statistics by date of month (1-31).
    num_digits: 3 for last3, 2 for last2
    URL pattern:
      3-digit: /lao/last3/stats-date{d}.php?ay=2559
      2-digit: /lao/last2/stats-date{d}.php?ay=2559
    """
    label = f"เลข {num_digits} ตัว"
    path_segment = f"last{num_digits}"
    print(f"Scraping stats by date ({label}) วันที่ 1-31...")

    all_dates = {}
    for day in range(1, 32):
        url = f"{BASE_URL}/lao/{path_segment}/stats-date{day}.php?ay=2559"
        try:
            soup = fetch_page(url)
            digit_stats = scrape_digit_position_stats(soup, num_digits)
            frequency = scrape_frequency_distribution(soup)

            all_dates[str(day)] = {
                "date": day,
                "digit_position_stats": digit_stats,
                "frequency_distribution": frequency,
                "source_url": url,
            }

            sys.stdout.write(f"\r  วันที่ {day}/31 ...")
            sys.stdout.flush()

            # Small delay to be polite to the server
            if day < 31:
                time.sleep(0.3)
        except Exception as e:
            print(f"\n  Error on date {day}: {e}", file=sys.stderr)
            continue

    print(f"\r  วันที่ 1-31 เสร็จ ({len(all_dates)} วัน)")
    return all_dates


def save_json(data, filepath: str) -> None:
    """Save data as JSON file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved: {filepath}")


def scrape_latest_only():
    """Scrape only the latest lottery results (latest, results, year files)."""
    print("Mode: latest - Scraping Lao Lottery results only...")
    results = scrape_lottery_results()

    if not results:
        print("No results found!", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(results)} results")

    now = datetime.utcnow().isoformat() + "Z"

    # 1. Latest result
    latest = {
        "status": "ok",
        "updated_at": now,
        "source": LAO_LOTTERY_URL,
        "data": results[0] if results else None,
    }
    save_json(latest, "api/latest.json")

    # 2. All recent results
    all_results = {
        "status": "ok",
        "updated_at": now,
        "source": LAO_LOTTERY_URL,
        "count": len(results),
        "data": results,
    }
    save_json(all_results, "api/results.json")

    # 3. Results grouped by year
    by_year: Dict[str, List] = {}
    for r in results:
        year = r["date"][:4]
        by_year.setdefault(year, []).append(r)

    for year, year_results in by_year.items():
        year_data = {
            "status": "ok",
            "updated_at": now,
            "source": LAO_LOTTERY_URL,
            "year": year,
            "count": len(year_results),
            "data": year_results,
        }
        save_json(year_data, f"api/year/{year}.json")

    # Update index
    _save_index(now, by_year)
    print("Done! (latest only)")


def scrape_full():
    """Scrape everything: results + all statistics."""
    print("Mode: full - Scraping all Lao Lottery data...")
    results = scrape_lottery_results()

    if not results:
        print("No results found!", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(results)} results")

    now = datetime.utcnow().isoformat() + "Z"

    # 1. Latest result
    latest = {
        "status": "ok",
        "updated_at": now,
        "source": LAO_LOTTERY_URL,
        "data": results[0] if results else None,
    }
    save_json(latest, "api/latest.json")

    # 2. All recent results
    all_results = {
        "status": "ok",
        "updated_at": now,
        "source": LAO_LOTTERY_URL,
        "count": len(results),
        "data": results,
    }
    save_json(all_results, "api/results.json")

    # 3. Results grouped by year
    by_year: Dict[str, List] = {}
    for r in results:
        year = r["date"][:4]
        by_year.setdefault(year, []).append(r)

    for year, year_results in by_year.items():
        year_data = {
            "status": "ok",
            "updated_at": now,
            "source": LAO_LOTTERY_URL,
            "year": year,
            "count": len(year_results),
            "data": year_results,
        }
        save_json(year_data, f"api/year/{year}.json")

    # 4. Stats: 3-digit (เลข 3 ตัว)
    stats_last3 = scrape_stats_last3()
    stats3_data = {
        "status": "ok",
        "updated_at": now,
        "source": LAO_STATS_LAST3_URL,
        "period": "10 ปีย้อนหลัง",
        "data": stats_last3,
    }
    save_json(stats3_data, "api/stats/last3.json")
    print(f"  - แยกตามหลัก: {len(stats_last3['digit_position_stats'])} หลัก")
    print(f"  - แบ่งตามจำนวนครั้ง: {len(stats_last3['frequency_distribution'])} กลุ่ม")
    print(f"  - เลขที่ยังไม่ออก: {stats_last3['never_drawn_count']} เลข")

    # 5. Stats: 2-digit (เลข 2 ตัว)
    stats_last2 = scrape_stats_last2()
    stats2_data = {
        "status": "ok",
        "updated_at": now,
        "source": LAO_STATS_LAST2_URL,
        "period": "10 ปีย้อนหลัง",
        "data": stats_last2,
    }
    save_json(stats2_data, "api/stats/last2.json")
    print(f"  - แยกตามหลัก: {len(stats_last2['digit_position_stats'])} หลัก")
    print(f"  - แบ่งตามจำนวนครั้ง: {len(stats_last2['frequency_distribution'])} กลุ่ม")
    print(f"  - เลขที่ยังไม่ออก: {stats_last2['never_drawn_count']} เลข")

    # 6. Stats by date: 3-digit (เลข 3 ตัว ตามวันที่ออก 1-31)
    stats_by_date_3 = scrape_stats_by_date(3)
    by_date3_data = {
        "status": "ok",
        "updated_at": now,
        "source": "https://lotto.thaiorc.com/lao/last3/stats-date{1-31}.php",
        "period": "10 ปีย้อนหลัง",
        "count": len(stats_by_date_3),
        "data": stats_by_date_3,
    }
    save_json(by_date3_data, "api/stats/last3-by-date.json")
    for day, day_data in stats_by_date_3.items():
        save_json({
            "status": "ok",
            "updated_at": now,
            "date": int(day),
            "period": "10 ปีย้อนหลัง",
            "data": day_data,
        }, f"api/stats/last3/date{day}.json")

    # 7. Stats by date: 2-digit (เลข 2 ตัว ตามวันที่ออก 1-31)
    stats_by_date_2 = scrape_stats_by_date(2)
    by_date2_data = {
        "status": "ok",
        "updated_at": now,
        "source": "https://lotto.thaiorc.com/lao/last2/stats-date{1-31}.php",
        "period": "10 ปีย้อนหลัง",
        "count": len(stats_by_date_2),
        "data": stats_by_date_2,
    }
    save_json(by_date2_data, "api/stats/last2-by-date.json")
    for day, day_data in stats_by_date_2.items():
        save_json({
            "status": "ok",
            "updated_at": now,
            "date": int(day),
            "period": "10 ปีย้อนหลัง",
            "data": day_data,
        }, f"api/stats/last2/date{day}.json")

    # 8. Index
    _save_index(now, by_year)
    print("Done! (full)")


def _save_index(now: str, by_year: Dict[str, List]) -> None:
    """Save the index.json file listing available endpoints."""
    index = {
        "status": "ok",
        "name": "Lao Lottery API",
        "description": "ข้อมูลผลหวยลาว scraped จาก thaiorc.com",
        "updated_at": now,
        "endpoints": {
            "latest": "api/latest.json",
            "all_results": "api/results.json",
            "by_year": [f"api/year/{y}.json" for y in sorted(by_year.keys(), reverse=True)],
            "stats_last3": "api/stats/last3.json",
            "stats_last2": "api/stats/last2.json",
            "stats_last3_by_date": "api/stats/last3-by-date.json",
            "stats_last3_date": [f"api/stats/last3/date{d}.json" for d in range(1, 32)],
            "stats_last2_by_date": "api/stats/last2-by-date.json",
            "stats_last2_date": [f"api/stats/last2/date{d}.json" for d in range(1, 32)],
        },
    }
    save_json(index, "api/index.json")


def main():
    parser = argparse.ArgumentParser(description="Scrape Lao Lottery data")
    parser.add_argument(
        "--mode",
        choices=["full", "latest"],
        default="full",
        help="Scraping mode: 'full' = all data + stats, 'latest' = results only (default: full)",
    )
    args = parser.parse_args()

    if args.mode == "latest":
        scrape_latest_only()
    else:
        scrape_full()


if __name__ == "__main__":
    main()
