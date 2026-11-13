"""
Tests para SupabaseExporter: batching en lotes de 100 y protección de checkpoints ante error.
"""

from unittest.mock import MagicMock, patch
import pytest

from src.supabase_exporter import SupabaseExporter, BATCH_SIZE


@pytest.fixture
def mock_supabase():
    with patch.dict(
        "os.environ",
        {"SUPABASE_URL": "https://fake.supabase.co", "SUPABASE_KEY": "fake_key"},
    ), patch("src.supabase_exporter.create_client") as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        exporter = SupabaseExporter()
        yield exporter, mock_instance


def test_upsert_chunks_large_records(mock_supabase):
    exporter, mock_instance = mock_supabase
    mock_table = MagicMock()
    mock_instance.table.return_value = mock_table
    mock_upsert = MagicMock()
    mock_table.upsert.return_value = mock_upsert
    mock_upsert.execute.return_value = MagicMock(data=[{"id": 1}])

    # 250 registros deben generar 3 lotes (100, 100, 50)
    fake_records = [{"source_url": f"https://example.com/{i}"} for i in range(250)]
    exporter._upsert(fake_records)

    assert mock_table.upsert.call_count == 3
    # Verificar tamaño del primer y último lote
    first_call_batch = mock_table.upsert.call_args_list[0][0][0]
    last_call_batch = mock_table.upsert.call_args_list[2][0][0]
    assert len(first_call_batch) == BATCH_SIZE
    assert len(last_call_batch) == 50


def test_upsert_raises_on_failure_to_protect_checkpoints(mock_supabase):
    exporter, mock_instance = mock_supabase
    mock_table = MagicMock()
    mock_instance.table.return_value = mock_table
    mock_upsert = MagicMock()
    mock_table.upsert.return_value = mock_upsert
    mock_upsert.execute.side_effect = Exception("PostgREST 500 Internal Error")

    fake_records = [{"source_url": "https://example.com/fail"}]
    with pytest.raises(RuntimeError) as exc_info:
        exporter._upsert(fake_records)

    assert "Error al sincronizar con Supabase" in str(exc_info.value)


def test_map_to_db_format():
    with patch.dict(
        "os.environ",
        {"SUPABASE_URL": "https://fake.supabase.co", "SUPABASE_KEY": "fake_key"},
    ), patch("src.supabase_exporter.create_client"):
        exporter = SupabaseExporter()

    raw = {
        "job_title": "Backend Dev",
        "hard_skills": ["python", "docker"],
        "soft_skills": ["liderazgo"],
        "country": "CO",
    }
    mapped = exporter._map_to_db(raw)
    assert mapped["raw_hard_skills"] == ["python", "docker"]
    assert mapped["raw_soft_skills"] == ["liderazgo"]
    assert mapped["country"] == "co"
    assert "hard_skills" not in mapped
