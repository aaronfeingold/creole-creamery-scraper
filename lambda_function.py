import json
import os
import requests
from datetime import datetime
from typing import List, Optional, Tuple
import psycopg2
from dataclasses import dataclass
from bs4 import BeautifulSoup
import re


@dataclass
class HallOfFameEntry:
    participant_number: int
    name: str
    date: str
    parsed_date: datetime
    notes: Optional[str] = None
    age: Optional[int] = None  # Age in total days
    elapsed_time: Optional[int] = None  # Elapsed time in total seconds
    completion_count: Optional[int] = (
        None  # Completion number from notes (1st, 2nd, 3rd, etc.)
    )


class CreoleCreameryLLMScraper:

    def __init__(self):
        self.db_url = os.environ["NEON_DATABASE_URL"]
        self.base_url = "https://creolecreamery.com/hall-of-fame/"

    def _normalize_age_to_days(self, age_text: str) -> Optional[int]:
        """Convert age text like '11 YEARS 5 MONTHS 21 DAYS' or '10 YRS OLD' to total days."""
        try:
            total_days = 0

            # Extract years - handle YEARS, YRS, YR patterns
            years_match = re.search(r"(\d+)\s+(?:YEARS?|YRS?|YR)", age_text)
            if years_match:
                total_days += int(years_match.group(1)) * 365

            # Extract months - handle MONTHS, MNTH, M patterns
            months_match = re.search(r"(\d+)\s+(?:MONTHS?|MNTH|M)", age_text)
            if months_match:
                total_days += int(months_match.group(1)) * 30  # Approximate

            # Extract days - handle DAYS, D patterns
            days_match = re.search(r"(\d+)\s+(?:DAYS?|D)", age_text)
            if days_match:
                total_days += int(days_match.group(1))

            return total_days if total_days > 0 else None
        except (ValueError, AttributeError):
            return None

    def _normalize_time_to_seconds(self, time_text: str) -> Optional[int]:
        """Convert time text like '6 MINUTES 40 SECONDS' to total seconds."""
        try:
            total_seconds = 0

            # Extract minutes
            minutes_match = re.search(r"(\d+)\s+MINUTES?", time_text)
            if minutes_match:
                total_seconds += int(minutes_match.group(1)) * 60

            # Extract seconds
            seconds_match = re.search(r"(\d+)\s+SECONDS?", time_text)
            if seconds_match:
                total_seconds += int(seconds_match.group(1))

            return total_seconds if total_seconds > 0 else None
        except (ValueError, AttributeError):
            return None

    def _extract_completion_count(self, notes_text: str) -> Optional[int]:
        """Extract completion count from notes like '2ND TIME', '3RD TIME', etc."""
        if not notes_text:
            return None

        try:
            # Look for patterns like "2ND TIME", "3RD TIME", etc.
            match = re.search(r"(\d+)(ST|ND|RD|TH)\s+TIME", notes_text.upper())
            if match:
                return int(match.group(1))
            return None
        except (ValueError, AttributeError):
            return None

    def parse_name_and_notes(
        self, raw_name: str
    ) -> Tuple[str, Optional[str], Optional[int], Optional[int], Optional[int]]:
        """
        Parse a name and extract any notes (completion count, age, time, etc.).

        Returns:
            Tuple of (cleaned_name, notes, age_in_days, elapsed_time_in_seconds, completion_count)

        Examples:
            "Bob Jones, 2nd time" -> ("BOB JONES", "2nd time", None, None, 2)
            "JAMES JONES, 11 YEARS 5 MONTHS 21 DAYS" -> ("JAMES JONES", "11 YEARS 5 MONTHS 21 DAYS", 4196, None, None)
            "Jill Smith 11 YEARS 5 MONTHS 21 DAYS" -> ("JILL SMITH", "11 YEARS 5 MONTHS 21 DAYS", 4196, None, None)
            "STEVEN HAMMOND 7 MINUTES" -> ("STEVEN HAMMOND", "7 MINUTES", None, 420, None)
            "JOHN VALDESPINO 6 MINUTES 40 SECONDS" -> ("JOHN VALDESPINO", "6 MINUTES 40 SECONDS", None, 400, None)
            "Jane Smith" -> ("JANE SMITH", None, None, None, None)
            "John Doe 5 YR 3 M 15 D" -> ("JOHN DOE", "5 YR 3 M 15 D", 1890, None, None)
        """
        # Clean up the raw name first
        cleaned = raw_name.strip().upper()

        # First check for comma-separated patterns (completion count, age, etc.)
        if "," in cleaned:
            parts = cleaned.split(",", 1)  # Split on first comma only
            name_part = parts[0].strip()
            potential_note = parts[1].strip()

            # Completion count patterns: "2nd time", "3rd time", etc.
            if re.match(r"^\d+(ST|ND|RD|TH)\s+TIME$", potential_note):
                completion_count = self._extract_completion_count(potential_note)
                return name_part, potential_note, None, None, completion_count

            # Age patterns after comma: "11 YEARS 5 MONTHS 21 DAYS", "10 YRS", etc.
            age_days = self._normalize_age_to_days(potential_note)
            if age_days is not None:
                return name_part, potential_note, age_days, None, None

            # If no pattern matches, treat the whole thing as the name
            return cleaned, None, None, None, None

        # Now check for patterns at the end of the name (no comma)

        # Age pattern: "11 YEARS 5 MONTHS 21 DAYS" or "10 YRS OLD" or "5 YR 3 M 15 D"
        age_match = re.search(
            r"\s+(\d+\s+(?:YEARS?|YRS?|YR)(?:\s+\d+\s+(?:MONTHS?|MNTH|M))?(?:\s+\d+\s+(?:DAYS?|D))?(?:\s+OLD)?)$",
            cleaned,
        )
        if age_match:
            note = age_match.group(1)
            name = cleaned[: age_match.start()].strip()
            age_days = self._normalize_age_to_days(note)
            return name, note, age_days, None, None

        # Time patterns: "7 MINUTES" or "6 MINUTES 40 SECONDS"
        time_match = re.search(r"\s+(\d+\s+MINUTES?(?:\s+\d+\s+SECONDS?)?)$", cleaned)
        if time_match:
            note = time_match.group(1)
            name = cleaned[: time_match.start()].strip()
            elapsed_seconds = self._normalize_time_to_seconds(note)
            return name, note, None, elapsed_seconds, None

        # No patterns found, return the whole name
        return cleaned, None, None, None, None

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
                raise Exception(
                    "HTML structure has changed: Could not find tbody with class 'row-hover'. "
                    "The website may have been updated."
                )

            entries = []
            rows = tbody.find_all("tr")

            for row in rows:
                cells = row.find_all("td")
                if len(cells) >= 3:
                    try:
                        # Extract data from table cells
                        print(cells)
                        number_text = cells[0].get_text(strip=True)
                        name_text = cells[1].get_text(
                            separator=" ", strip=True
                        )  # Handle <br> tags
                        date_text = cells[2].get_text(strip=True)

                        # Extract number, handling extra spaces
                        participant_number = int(number_text.strip())
                        name, notes, age_days, elapsed_seconds, completion_count = (
                            self.parse_name_and_notes(name_text)
                        )
                        date = date_text.strip()

                        parsed_date = self._parse_date(date)

                        entry = HallOfFameEntry(
                            participant_number=participant_number,
                            name=name,
                            date=date,
                            parsed_date=parsed_date,
                            notes=notes,
                            age=age_days,
                            elapsed_time=elapsed_seconds,
                            completion_count=completion_count,
                        )
                        entries.append(entry)

                    except (ValueError, IndexError) as e:
                        print(f"Skipping row due to parsing error: {str(e)}")
                        continue

            print(f"Successfully extracted {len(entries)} entries using Beautiful Soup")
            return sorted(entries, key=lambda x: x.participant_number, reverse=True)

        except Exception as e:
            print(f"Beautiful Soup parsing failed: {str(e)}")
            raise Exception(f"HTML parsing failed: {str(e)}")

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

        # Sort new entries by participant_number in ascending order (oldest first)
        # This ensures that database ID ordering matches chronological ordering
        new_entries = sorted(new_entries, key=lambda x: x.participant_number)

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
                            notes VARCHAR(255),
                            age INTEGER,
                            elapsed_time INTEGER,
                            completion_count INTEGER,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """
                    )

                    # Insert new entries in chronological order (oldest first)
                    for entry in new_entries:
                        cur.execute(
                            """
                            INSERT INTO hall_of_fame_entries
                            (participant_number, name, date_str, parsed_date, notes, age, elapsed_time,
                             completion_count)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (participant_number)
                            DO UPDATE SET
                                name = EXCLUDED.name,
                                date_str = EXCLUDED.date_str,
                                parsed_date = EXCLUDED.parsed_date,
                                notes = EXCLUDED.notes,
                                age = EXCLUDED.age,
                                elapsed_time = EXCLUDED.elapsed_time,
                                completion_count = EXCLUDED.completion_count,
                                updated_at = CURRENT_TIMESTAMP
                        """,
                            (
                                entry.participant_number,
                                entry.name,
                                entry.date,
                                entry.parsed_date,
                                entry.notes,
                                entry.age,
                                entry.elapsed_time,
                                entry.completion_count,
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
                    "extraction_method": "Beautiful Soup",
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
    # Test the name parsing function first
    def test_name_parsing():
        print("=== Testing Name Parsing ===")
        scraper = CreoleCreameryLLMScraper()

        test_cases = [
            "Bob Jones, 2nd time",  # Completion count with comma
            "Mike Stevens, 3rd time",  # Completion count with comma
            "JAMES JONES, 11 YEARS 5 MONTHS 21 DAYS",  # Age pattern with comma (new scenario)
            "Jill Smith 11 YEARS 5 MONTHS 21 DAYS",  # Age pattern (real format)
            "STEVEN HAMMOND 7 MINUTES",  # Time pattern (real format)
            "JOHN VALDESPINO 6 MINUTES 40 SECONDS",  # Time with seconds (real format)
            "Jane Smith",  # Normal name, no notes
            "Robert Brown, Jr.",  # Should NOT extract Jr. as notes
            "Sarah Johnson, 1st time",  # First time completion
            "Tom Davis 15 YEARS",  # Age without months/days
            "Alice Wilson 3 MINUTES 15 SECONDS",  # Another time example
            "John Doe 5 YR 3 M 15 D",  # Age with abbreviated units
            "Mary Smith 10 YRS 2 MNTH",  # Age with MNTH abbreviation
            "Bob Wilson, 7 YR 1 D",  # Age with comma and abbreviated units
        ]

        for test_name in test_cases:
            name, notes, age_days, elapsed_seconds, completion_count = (
                scraper.parse_name_and_notes(test_name)
            )
            print(
                f"'{test_name}' -> name: '{name}', notes: {notes}, "
                f"age_days: {age_days}, elapsed_seconds: {elapsed_seconds}, completion_count: {completion_count}"
            )
        print()

    test_name_parsing()

    # For local testing

    # Test with Beautiful Soup (default)
    print("=== Testing with Beautiful Soup (default) ===")
    test_event = {}
    test_context = {}
    result = lambda_handler(test_event, test_context)
    print(json.dumps(result, indent=2))
