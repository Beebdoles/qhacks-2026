"""Test the arrange endpoint: Flute Tutorial MP3 → guitar arrangement."""
import requests

API_URL = "http://localhost:8000"
INPUT_FILE = "midi-inputs/Flute Tutorial Twinkle twinkle little star - Flutie Funny.mp3"
OUTPUT_FILE = "midi-outputs/arranged_flute_to_guitar.mid"


def test_arrange():
    with open(INPUT_FILE, "rb") as f:
        resp = requests.post(
            f"{API_URL}/api/arrange",
            files={"file": (INPUT_FILE, f, "audio/mpeg")},
            data={"target_instrument": "guitar"},
        )

    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        with open(OUTPUT_FILE, "wb") as out:
            out.write(resp.content)
        print(f"Saved to {OUTPUT_FILE} ({len(resp.content)} bytes)")
    else:
        print(f"Error: {resp.text}")


if __name__ == "__main__":
    test_arrange()
