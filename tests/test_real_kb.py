import importlib.util
from pathlib import Path

from casavaiano.config import DATA_DIR, ROOT_DIR, Settings
from casavaiano.rag.chunking import chunk_kb, load_documents
from casavaiano.tools.live import load_lodgings

REAL_KB = DATA_DIR / "real" / "kb"


def load_script():
    path = ROOT_DIR / "scripts" / "import_site_kb.py"
    spec = importlib.util.spec_from_file_location("import_site_kb", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_real_kb_covers_every_apartment():
    sections = {
        h for d in load_documents(REAL_KB) if d.name == "appartamenti" for h, _ in d.sections
    }
    assert {lodging.name for lodging in load_lodgings()} <= sections


def test_real_kb_chunks_and_states_no_fixed_prices():
    chunks = chunk_kb("headings", REAL_KB)
    assert len(chunks) > 20
    text = " ".join(c.text for c in chunks)
    assert "da sabato a sabato" in text
    assert "50 €, una volta sola" in text
    assert "massimo di 6 notti" in text
    assert "16:00 alle 18:00" in text


def test_kb_dir_is_resolved_from_the_project_root():
    settings = Settings(_env_file=None, kb_dir="data/real/kb")
    assert settings.knowledge_base_dir == REAL_KB
    assert Settings(_env_file=None).knowledge_base_dir == DATA_DIR / "kb"


def test_import_script_renders_site_data():
    script = load_script()
    apartments = [
        {
            "name": "Castagno",
            "floor": "Piano terra",
            "size": 50,
            "tagline": "Accessibile a tutti",
            "text": "Accessibile anche agli ospiti con disabilità.",
            "rooms": ["Camera matrimoniale", "Bagno con doccia"],
            "tags": ["Accessibile"],
        }
    ]
    md = script.apartments_md(apartments)
    assert "## Castagno" in md and "Piano terra, 50 m²" in md
    assert "Note dei gestori: l'unico attrezzato" in md
    places = [
        {"name": "Volterra", "km": 17, "group": "citta", "tagline": "Etrusca", "intro": "Città."},
        {"name": "Chianti", "group": "citta", "intro": "Vino."},
        {
            "name": "Certaldo Alto",
            "group": "vicino",
            "intro": "Borgo.",
            "highlights": [{"name": "Casa Boccaccio", "desc": "Museo."}],
        },
    ]
    md = script.places_md(places)
    assert "## Volterra (circa 17 km)" in md
    assert "## Chianti\n" in md
    assert "## Certaldo Alto (a pochi minuti)" in md
    assert "- Casa Boccaccio: Museo." in md
    assert Path(script.KB_OUT) == REAL_KB


def test_owner_tone_only_in_live_mode():
    from casavaiano.agent.prompts import Persona, answer_system

    assert "the way the owners write" in answer_system(Persona("Rocco", "Tommaso", live=True))
    assert "the way the owners write" not in answer_system(Persona("Rocco", "Giulia"))


def test_kb_has_the_facts_approved_from_the_emails():
    text = " ".join(c.text for c in chunk_kb("headings", REAL_KB))
    for fact in (
        "acconto del 25%",
        "Fino a 30 giorni",
        "100 € per il soggiorno",
        "tre barbecue",
        "non ospita matrimoni",
        "google.com/maps",
        "taglia piccola o media",
    ):
        assert fact in text, fact
    assert "aspirapolvere" not in text
