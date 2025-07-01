import json
import os
import re
import requests
from datetime import datetime
from typing import List, Dict, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import openai
from dataclasses import dataclass
from bs4 import BeautifulSoup


@dataclass
class HallOfFameEntry:
    participant_number: int
    name: str
    date: str
    parsed_date: datetime


class CreoleCreameryLLMScraper:
    def __init__(self):
        self.openai_client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self.db_url = os.environ["NEON_DATABASE_URL"]
        self.base_url = "https://creolecreamery.com/hall-of-fame/"

    def fetch_page_content(self) -> str:
        """Fetch the raw HTML content from the hall of fame page."""
        try:
            response = requests.get(self.base_url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            raise Exception(f"Failed to fetch page content: {str(e)}")

    def extract_with_beautiful_soup(self, html_content: str) -> List[HallOfFameEntry]:
        """Extract data using Beautiful Soup to parse the HTML table."""
        try:
            soup = BeautifulSoup(html_content, "html.parser")

            # Find the table with the hall of fame data
            tbody = soup.find("tbody", class_="row-hover")
            if not tbody:
                print("Could not find tbody with class 'row-hover'")
                return self._fallback_regex_parse(html_content)

            entries = []
            rows = tbody.find_all("tr")

            for row in rows:
                cells = row.find_all("td")
                if len(cells) >= 3:
                    try:
                        # Extract data from table cells
                        number_text = cells[0].get_text(strip=True)
                        name_text = cells[1].get_text(
                            separator=" ", strip=True
                        )  # Handle <br> tags
                        date_text = cells[2].get_text(strip=True)

                        # Clean up the data
                        participant_number = int(number_text)
                        name = name_text.upper()  # Ensure consistency
                        date = date_text

                        parsed_date = self._parse_date(date)

                        entry = HallOfFameEntry(
                            participant_number=participant_number,
                            name=name,
                            date=date,
                            parsed_date=parsed_date,
                        )
                        entries.append(entry)

                    except (ValueError, IndexError) as e:
                        print(f"Skipping row due to parsing error: {str(e)}")
                        continue

            print(f"Successfully extracted {len(entries)} entries using Beautiful Soup")
            return sorted(entries, key=lambda x: x.participant_number, reverse=True)

        except Exception as e:
            print(f"Beautiful Soup parsing failed: {str(e)}, falling back to regex")
            return self._fallback_regex_parse(html_content)

    def extract_with_llm(self, html_content: str) -> List[HallOfFameEntry]:
        """Use LLM to extract structured data from the HTML content (fallback method)."""

        # For LLM, let's extract just the table portion to save tokens
        soup = BeautifulSoup(html_content, "html.parser")
        tbody = soup.find("tbody", class_="row-hover")

        if tbody:
            table_html = str(tbody)[:4000]  # Limit to 4000 chars to save tokens
        else:
            table_html = html_content[:4000]

        prompt = f"""
        Extract all hall of fame entries from this HTML table. Each row has 3 columns:
        1. Participant number (integer)
        2. Name (may contain line breaks)
        3. Date (M/D/YY format)

        Return ONLY a valid JSON array with this structure:
        [
            {{
                "participant_number": 748,
                "name": "PHILLIP FANGUE",
                "date": "5/11/25"
            }}
        ]

        Rules:
        1. Extract ALL entries from the table
        2. participant_number should be an integer
        3. name should be cleaned of HTML tags and line breaks
        4. date should be the exact date string as shown
        5. Return ONLY the JSON array, no other text

        HTML Table:
        {table_html}
        """

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a precise data extraction assistant. Return only valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                max_tokens=4000,
            )

            response_text = response.choices[0].message.content.strip()

            # Clean up the response
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]

            entries_data = json.loads(response_text)

            # Convert to HallOfFameEntry objects
            entries = []
            for entry_data in entries_data:
                parsed_date = self._parse_date(entry_data["date"])
                entry = HallOfFameEntry(
                    participant_number=int(entry_data["participant_number"]),
                    name=entry_data["name"].strip().upper(),
                    date=entry_data["date"],
                    parsed_date=parsed_date,
                )
                entries.append(entry)

            print(f"Successfully extracted {len(entries)} entries using LLM")
            return sorted(entries, key=lambda x: x.participant_number, reverse=True)

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"LLM parsing failed: {str(e)}, falling back to regex")
            return self._fallback_regex_parse(html_content)

    def _parse_date(self, date_str: str) -> datetime:
        """Parse date string to datetime object, handling 2-digit years."""
        try:
            # Handle MM/DD/YY or M/D/YY formats
            if len(date_str.split("/")[-1]) == 2:
                # 2-digit year - assume 2000s for years 00-30, 1900s for 31-99
                month, day, year = date_str.split("/")
                year_int = int(year)
                if year_int <= 30:
                    full_year = 2000 + year_int
                else:
                    full_year = 1900 + year_int
                return datetime(full_year, int(month), int(day))
            else:
                # 4-digit year
                return datetime.strptime(date_str, "%m/%d/%Y")
        except ValueError:
            # Default to epoch if parsing fails
            return datetime(1970, 1, 1)

    def _fallback_regex_parse(self, html_content: str) -> List[HallOfFameEntry]:
        """Fallback regex parsing for HTML table structure."""
        entries = []

        # Updated pattern for HTML table structure
        # Look for <td> tags with the data
        soup = BeautifulSoup(html_content, "html.parser")

        # Find all table rows
        rows = soup.find_all("tr")

        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 3:
                try:
                    number_text = cells[0].get_text(strip=True)
                    name_text = cells[1].get_text(separator=" ", strip=True)
                    date_text = cells[2].get_text(strip=True)

                    # Extract number, handling extra spaces
                    participant_number = int(number_text.strip())
                    name = name_text.upper().strip()
                    date = date_text.strip()

                    parsed_date = self._parse_date(date)

                    entry = HallOfFameEntry(
                        participant_number=participant_number,
                        name=name,
                        date=date,
                        parsed_date=parsed_date,
                    )
                    entries.append(entry)

                except (ValueError, IndexError):
                    continue

        print(f"Regex fallback extracted {len(entries)} entries")
        return sorted(entries, key=lambda x: x.participant_number, reverse=True)

    def get_last_entry_from_db(self) -> Optional[int]:
        """Get the highest participant number from the database."""
        try:
            with psycopg2.connect(self.db_url) as conn:
                with conn.cursor() as cur:
                    # Check if table exists first
                    cur.execute(
                        """
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables
                            WHERE table_name = 'hall_of_fame_entries'
                        );
                    """
                    )
                    table_exists = cur.fetchone()[0]

                    if not table_exists:
                        print("Table doesn't exist yet, treating as first run")
                        return 0

                    cur.execute(
                        "SELECT MAX(participant_number) FROM hall_of_fame_entries"
                    )
                    result = cur.fetchone()
                    return result[0] if result[0] is not None else 0
        except Exception as e:
            print(f"Database query failed: {str(e)}")
            return 0

    def save_new_entries(
        self, entries: List[HallOfFameEntry], last_saved_number: int
    ) -> int:
        """Save new entries to the database."""
        new_entries = [e for e in entries if e.participant_number > last_saved_number]

        if not new_entries:
            return 0

        try:
            with psycopg2.connect(self.db_url) as conn:
                with conn.cursor() as cur:
                    # Create table if it doesn't exist
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS hall_of_fame_entries (
                            id SERIAL PRIMARY KEY,
                            participant_number INTEGER UNIQUE NOT NULL,
                            name VARCHAR(255) NOT NULL,
                            date_str VARCHAR(50) NOT NULL,
                            parsed_date TIMESTAMP NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """
                    )

                    # Insert new entries
                    for entry in new_entries:
                        cur.execute(
                            """
                            INSERT INTO hall_of_fame_entries
                            (participant_number, name, date_str, parsed_date)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (participant_number)
                            DO UPDATE SET
                                name = EXCLUDED.name,
                                date_str = EXCLUDED.date_str,
                                parsed_date = EXCLUDED.parsed_date,
                                updated_at = CURRENT_TIMESTAMP
                        """,
                            (
                                entry.participant_number,
                                entry.name,
                                entry.date,
                                entry.parsed_date,
                            ),
                        )

                    conn.commit()
                    return len(new_entries)

        except Exception as e:
            raise Exception(f"Database save failed: {str(e)}")


def lambda_handler(event, context):
    """AWS Lambda handler function."""
    try:
        scraper = CreoleCreameryLLMScraper()

        # Fetch the page content
        html_content = scraper.fetch_page_content()

        # Extract entries using Beautiful Soup (primary method)
        entries = scraper.extract_with_beautiful_soup(html_content)

        # Get last saved entry number
        last_saved_number = scraper.get_last_entry_from_db()

        # Save new entries
        new_entries_count = scraper.save_new_entries(entries, last_saved_number)

        result = {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": f"Successfully processed {len(entries)} total entries",
                    "new_entries_saved": new_entries_count,
                    "last_saved_number": last_saved_number,
                    "highest_number_found": (
                        max(e.participant_number for e in entries) if entries else 0
                    ),
                    "timestamp": datetime.now().isoformat(),
                }
            ),
        }

        print(f"Scraping completed: {new_entries_count} new entries saved")
        return result

    except Exception as e:
        error_result = {
            "statusCode": 500,
            "body": json.dumps(
                {"error": str(e), "timestamp": datetime.now().isoformat()}
            ),
        }
        print(f"Scraping failed: {str(e)}")
        return error_result


if __name__ == "__main__":
    # For local testing
    test_event = {}
    test_context = {}
    result = lambda_handler(test_event, test_context)
    print(json.dumps(result, indent=2))
